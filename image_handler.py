"""
eMAG 爬虫 - 商品图库处理模块

负责：
1. 从详情页解析完整商品图库
2. 去重 + 高清优先
3. 图片下载（带重试/并发/命名）
"""

import os
import re
import concurrent.futures
from urllib.parse import urlparse

import config
from logger import logger


# ============================================================
# Image Gallery Parser — 解析商品图库
# ============================================================
class ImageGalleryParser:
    """从详情页 HTML 提取全部商品图片 URL"""

    def __init__(self, response, product_pnk: str = ""):
        self.response = response
        self.product_pnk = product_pnk
        self._urls: list[str] = []

    def extract(self) -> list[str]:
        """
        提取所有商品图片，去重，优先高清

        返回: 去重后的图片 URL 列表（已去除尺寸参数）
        """
        raw_urls = []

        # ---- 1. 从 <img> 标签提取 ----
        img_srcs = self.response.css(
            "img[src*='emagst'][src*='/products/']::attr(src)"
        ).getall()
        raw_urls.extend(img_srcs)

        # ---- 2. 从 <a> 标签的 href 提取（大图链接） ----
        a_hrefs = self.response.css(
            "a[href*='emagst'][href*='/products/']::attr(href)"
        ).getall()
        raw_urls.extend(a_hrefs)

        # ---- 3. 从 data-src / data-img 属性提取（懒加载） ----
        for attr in ["data-src", "data-img", "data-image", "data-original"]:
            lazy = self.response.css(f"[{attr}*='emagst'][{attr}*='/products/']::attr({attr})").getall()
            raw_urls.extend(lazy)

        if not raw_urls:
            logger.debug(f"[{self.product_pnk}] 详情页未找到产品图片")
            return []

        # ---- 去重 + 高清优先 ----
        self._urls = self._dedup_and_prefer_hires(raw_urls)
        logger.debug(
            f"[{self.product_pnk}] 图库: 原始 {len(raw_urls)} 个 → 去重 {len(self._urls)} 张"
        )
        return self._urls

    def _dedup_and_prefer_hires(self, urls: list[str]) -> list[str]:
        """
        去重策略：
        1. 按 base URL（去掉 ?width= 等参数）分组
        2. 每组保留最高分辨率版本（无参数 > 大尺寸 > 小尺寸）
        3. 按原始出现顺序排序
        """
        # {base_url: (best_url, size_rank, first_seen_index)}
        groups: dict[str, tuple[str, int, int]] = {}

        for idx, url in enumerate(urls):
            base = re.sub(r"\?.*$", "", url)
            size = self._extract_size(url)

            if base in groups:
                _, prev_rank, prev_idx = groups[base]
                if size > prev_rank or (size == prev_rank and idx < prev_idx):
                    groups[base] = (url, size, idx)
            else:
                groups[base] = (url, size, idx)

        # 按首次出现顺序排序
        sorted_items = sorted(groups.values(), key=lambda x: x[2])
        return [item[0] for item in sorted_items]

    @staticmethod
    def _extract_size(url: str) -> int:
        """
        从 URL 提取图片尺寸用于比较
        无 width 参数 = 原图，返回极大值
        """
        m = re.search(r"width=(\d+)", url)
        if m:
            return int(m.group(1))
        # 无参数 = 原图，最高优先级
        return 99999

    @property
    def count(self) -> int:
        return len(self._urls)


# ============================================================
# Image Downloader — 下载图片
# ============================================================
class ImageDownloader:
    """批量下载商品图片，支持并发、重试、命名"""

    def __init__(self, fetcher_cls, max_workers: int = None):
        self.fetcher = fetcher_cls
        self.max_workers = max_workers or config.CONCURRENT_IMAGE
        self._stats = {"success": 0, "failed": 0, "skipped": 0}

    def download_product_images(
        self, product: dict, start_index: int = 1
    ) -> list[str]:
        """
        下载单个商品的全部图片

        参数:
            product: 商品字典（需含 pnk 和 image_urls 字段）
            start_index: 起始编号

        返回: 本地路径列表
        """
        pnk = product.get("pnk", "unknown")
        urls = product.get("_gallery_urls", [])

        if not urls:
            return []

        logger.info(
            f"[{pnk}] 图库: {len(urls)} 张图片, 开始下载..."
        )

        paths = []
        for i, url in enumerate(urls):
            path = self._download_single(url, pnk, start_index + i)
            paths.append(path)

        logger.info(
            f"[{pnk}] 下载完成: 成功 {self._stats['success']}, "
            f"失败 {self._stats['failed']}, 跳过 {self._stats['skipped']}"
        )
        return [p for p in paths if p]

    def download_all_products(
        self, products: list[dict]
    ) -> list[dict]:
        """
        并发下载所有商品的所有图片

        返回: 更新后的 products（含 image_path 和 image_count）
        """
        if not config.DOWNLOAD_IMAGES:
            logger.info("图片下载已禁用")
            return products

        # 收集有图库的商品
        tasks = []
        for p in products:
            pnk = p.get("pnk", "")
            urls = p.get("_gallery_urls", [])
            if urls:
                tasks.append((p, urls))

        if not tasks:
            logger.info("没有图片需要下载")
            return products

        total_images = sum(len(urls) for _, urls in tasks)
        logger.info(
            f"开始下载 {total_images} 张图片 "
            f"({len(tasks)} 个商品, 并发 {self.max_workers})"
        )

        # 构建扁平任务列表
        flat_tasks = []
        for product, urls in tasks:
            pnk = product.get("pnk", "")
            for idx, url in enumerate(urls, 1):
                flat_tasks.append((url, pnk, idx))

        success = 0
        fail = 0
        skip = 0

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            futures = {
                executor.submit(
                    self._download_single, url, pnk, idx
                ): (pnk, idx)
                for url, pnk, idx in flat_tasks
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    path = future.result()
                    if path:
                        success += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1

        self._stats = {"success": success, "failed": fail, "skipped": skip}
        logger.info(
            f"图片下载完成: 成功 {success}, 失败 {fail}, 跳过 {skip}"
        )

        # 更新产品的 image_path 和 image_count
        for product in products:
            pnk = product.get("pnk", "")
            paths = self._find_local_images(pnk)
            product["image_path"] = paths[0] if paths else ""
            product["image_count"] = len(paths)

        return products

    def _download_single(
        self, url: str, pnk: str, index: int
    ) -> str:
        """下载单张图片，返回本地路径（空字符串 = 失败/跳过）"""
        if not url:
            return ""

        # 解析扩展名
        parsed = urlparse(url)
        path_part = parsed.path
        ext = os.path.splitext(path_part)[1]
        if not ext or "?" in ext or len(ext) > 5:
            ext = ".jpg"

        local_name = f"{pnk}_{index:03d}{ext}"
        local_path = os.path.join(config.IMAGES_DIR, local_name)

        # 已存在且非空 → 跳过
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            self._stats["skipped"] += 1
            return local_path

        # 下载 + 验证
        try:
            resp = self.fetcher.get(
                url,
                impersonate="chrome",
                stealthy_headers=True,
                timeout=20,
            )
            # 验证: HTTP 200 + 非空 + 图片内容
            if resp.status != 200:
                logger.warning(f"  [{pnk}] #{index:03d} HTTP {resp.status}, 跳过")
                return ""
            body = resp.body if hasattr(resp, 'body') else b""
            if not body or len(body) < 64:
                logger.warning(f"  [{pnk}] #{index:03d} 响应体为空/过小({len(body)}B), 跳过")
                return ""
            if not _is_valid_image(body):
                content_type = resp.headers.get("Content-Type", "") if hasattr(resp, 'headers') else ""
                logger.warning(f"  [{pnk}] #{index:03d} 非图片内容(Content-Type={content_type}), 跳过")
                return ""

            with open(local_path, "wb") as f:
                f.write(body)
            logger.debug(f"  [{pnk}] #{index:03d} 已下载 ({len(body)} bytes)")
            return local_path
        except Exception as e:
            logger.warning(f"  [{pnk}] #{index:03d} 下载失败: {e} — {url[:80]}")
            return ""


def _is_valid_image(data: bytes) -> bool:
    """通过文件签名验证是否为有效图片（JPEG/PNG/GIF/WebP）"""
    if len(data) < 4:
        return False
    # JPEG: FF D8 FF
    if data[:3] == b'\xFF\xD8\xFF':
        return True
    # PNG: 89 50 4E 47
    if data[:4] == b'\x89PNG':
        return True
    # GIF: GIF87a or GIF89a
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return True
    # WebP: RIFF ... WEBP
    if data[:4] == b'RIFF' and len(data) >= 12 and data[8:12] == b'WEBP':
        return True
    # 拒绝 HTML/JSON/Captcha
    if data[:1] == b'<' or data[:1] == b'{':
        return False
    return False

    def _find_local_images(self, pnk: str) -> list[str]:
        """查找本地已下载的该商品图片"""
        import glob as gb
        pattern = os.path.join(config.IMAGES_DIR, f"{pnk}_*")
        return sorted(gb.glob(pattern))


# ============================================================
# 工具函数
# ============================================================
def get_high_res_url(img_url: str) -> str:
    """去除 URL 中的尺寸限制参数以获取原图"""
    if not img_url:
        return ""
    return re.sub(r"\?.*$", "", img_url)


def collect_gallery_from_detail(response, pnk: str = "") -> list[str]:
    """
    便捷函数：从详情页提取图库 URL

    返回: 去重高清图片 URL 列表
    """
    parser = ImageGalleryParser(response, pnk)
    return parser.extract()
