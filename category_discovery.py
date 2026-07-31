"""
eMAG 全站类目自动发现模块

功能:
1. 访问 eMAG 首页,提取导航菜单中的所有商品类目链接
2. 过滤非商品列表页(品牌页/帮助/博客/活动页等)
3. 去重
4. 缓存到 config/categories_auto.json
"""

import json
import os
import re
from urllib.parse import urljoin, urlparse

from scrapling.fetchers import Fetcher

import config
from logger import logger

# 缓存文件路径
AUTO_CACHE_FILE = os.path.join(config.BASE_DIR, "config", "categories_auto.json")

# 非商品类目的 URL 关键词（过滤用）
SKIP_PATTERNS = [
    "/brand/", "/brands/", "/help/", "/blog/", "/info/", "/contact/",
    "/login", "/register", "/cart", "/wishlist", "/account",
    "/campaign/", "/promotii/", "/promo/", "/oferta", "/campanii",
    "/search", "/favorites", "/compara", "/compare",
    "/resigilate", "/outlet", "/genius", "/easybox",
    "/tazz", "/fashiondays", "/pcgarage",
    "/vanzator", "/seller", "/vendor",
    "javascript:", "#", "tel:", "mailto:",
]

# 必须包含的特征（商品列表页标识）
PRODUCT_LIST_MARKER = "/c"  # eMAG 商品列表页 URL 以 /c 结尾


def discover_categories(start_url: str = None, force_refresh: bool = False) -> list[str]:
    """
    从 eMAG 首页自动发现所有商品类目 URL

    返回: 去重后的类目 URL 列表
    """
    start_url = start_url or config.BASE_DOMAIN

    # 检查缓存
    if not force_refresh and os.path.exists(AUTO_CACHE_FILE):
        logger.info("从缓存加载类目列表...")
        try:
            with open(AUTO_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            urls = cached.get("urls", [])
            if urls:
                logger.info(f"缓存命中: {len(urls)} 个类目")
                return urls
        except (json.JSONDecodeError, KeyError):
            logger.warning("缓存文件损坏，重新发现")

    # 抓取首页
    logger.info(f"正在访问 eMAG 首页: {start_url}")
    try:
        resp = Fetcher.get(start_url, impersonate="chrome", stealthy_headers=True, timeout=30)
    except Exception as e:
        logger.error(f"无法访问首页: {e}")
        return []

    if resp.status != 200:
        logger.error(f"首页返回 HTTP {resp.status}，无法发现类目")
        return []

    # 提取所有链接
    all_links = _extract_links(resp)
    logger.info(f"首页提取到 {len(all_links)} 个链接")

    # 过滤: 只保留商品列表页
    product_urls = []
    for link in all_links:
        if _is_valid_category(link):
            product_urls.append(link)

    # 去重
    unique_urls = _deduplicate(product_urls)
    logger.info(f"过滤后: {len(product_urls)} → 去重: {len(unique_urls)} 个商品类目")

    # 排序（按 URL 字母序，方便查看）
    unique_urls.sort()

    # 缓存
    _save_cache(unique_urls)

    return unique_urls


def _extract_links(resp) -> list[str]:
    """从首页 HTML 提取所有链接"""
    links = set()

    # 所有 <a href>
    hrefs = resp.css("a[href]::attr(href)").getall()
    for href in hrefs:
        if href and not href.startswith(("javascript:", "#", "tel:", "mailto:")):
            full = urljoin(config.BASE_DOMAIN, href)
            links.add(full)

    return list(links)


def _is_valid_category(url: str) -> bool:
    """判断 URL 是否为商品列表类目页"""
    # 必须是 eMAG 域名
    if config.BASE_DOMAIN not in url:
        return False

    # 必须有 /c 后缀（商品列表页标识）
    if not url.rstrip("/").endswith("/c"):
        return False

    # 排除非商品页
    for pattern in SKIP_PATTERNS:
        if pattern in url.lower():
            return False

    # 排除纯数字结尾的 /c （如 /p2/c 是分页，不是独立类目）
    m = re.search(r"/p(\d+)/c$", url.rstrip("/"))
    if m:
        return False

    return True


def _deduplicate(urls: list[str]) -> list[str]:
    """去重: 按 base URL（去除 query params）"""
    seen = set()
    result = []
    for url in urls:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if base not in seen:
            seen.add(base)
            result.append(url)
    return result


def _save_cache(urls: list[str]):
    """保存类目缓存"""
    os.makedirs(os.path.dirname(AUTO_CACHE_FILE), exist_ok=True)
    cache_data = {
        "source": config.BASE_DOMAIN,
        "discovered_at": __import__("datetime").datetime.now().isoformat(),
        "count": len(urls),
        "urls": urls,
    }
    with open(AUTO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    logger.info(f"类目缓存已保存: {AUTO_CACHE_FILE} ({len(urls)} 个)")
