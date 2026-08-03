"""
eMAG Multi-Category Scraper v1.0.4
===================================
基于 Scrapling 的 eMAG 电商爬虫，支持多类目批量采集。
"""

import argparse
import os
import sys
import time
import glob as gb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from logger import logger
from crawler import crawl_list_pages, crawl_detail_pages
from save import save_csv, save_excel, save_json, download_all_images
from utils import load_checkpoint
from category_loader import load_categories, CategoryInfo, _extract_category_path


def parse_args():
    p = argparse.ArgumentParser(description="eMAG Multi-Category Scraper v1.0.4")
    p.add_argument("--list-only", action="store_true",
                   help="仅抓列表页并导出（默认不下载图片）")
    p.add_argument("--reset", action="store_true",
                   help="清除断点重新开始")
    p.add_argument("--export-only", action="store_true",
                   help="仅导出已有断点数据，不发起网络请求")
    p.add_argument("--no-images", action="store_true",
                   help="不下载图片")
    p.add_argument("--download-list-images", action="store_true",
                   help="--list-only 模式下也下载列表页缩略图")
    p.add_argument("--pages", type=int, default=0,
                   help="每个类目抓取页数（0=全部）")
    p.add_argument("--category-pages", type=int, default=0,
                   help="每个类目抓取页数（优先级高于 --pages）")
    p.add_argument("--auto-discover", action="store_true",
                   help="自动从 eMAG 首页导航发现类目")
    p.add_argument("--refresh-categories", action="store_true",
                   help="忽略类目缓存，重新从 eMAG 首页发现")
    p.add_argument("--debug", action="store_true",
                   help="调试模式：打印配置后退出")
    return p.parse_args()


def reset_checkpoints():
    for f in gb.glob(os.path.join(config.CHECKPOINT_DIR, "*.json")):
        os.remove(f)
    logger.info("已清除所有断点数据")


def print_debug_banner(args, effective_pages):
    mode = []
    if args.list_only: mode.append("list-only")
    if args.export_only: mode.append("export-only")
    if args.auto_discover: mode.append("auto-discover")
    if not mode: mode.append("full")
    if args.no_images: mode.append("no-images")
    if args.reset: mode.append("reset")
    print()
    print("=" * 60)
    print("  DEBUG — v1.0.4")
    print("=" * 60)
    print(f"  Mode:           {', '.join(mode)}")
    print(f"  Pages:          {effective_pages if effective_pages > 0 else 'ALL'}")
    print(f"  Run Dir:        {config.OUTPUT_DIR}")
    print("=" * 60)
    print()


def _dedup_key(p: dict) -> str:
    """生成稳定去重键: PNK > URL > product_id+offer_id > 无键保留"""
    pnk = p.get("pnk", "").strip()
    if pnk: return f"pnk:{pnk}"
    url = p.get("url", "").strip()
    if url: return f"url:{url}"
    pid = p.get("product_id", "")
    oid = p.get("offer_id", "")
    if pid or oid: return f"id:{pid}:{oid}"
    return f"hash:{hash(str(sorted(p.items()))) & 0x7FFFFFFF}"


def dedup_products(products: list[dict]) -> tuple[list[dict], int]:
    """跨类目去重，返回 (去重后列表, 跳过数量)"""
    seen = set()
    result = []
    skipped = 0
    for p in products:
        key = _dedup_key(p)
        if key not in seen:
            seen.add(key)
            result.append(p)
        else:
            skipped += 1
    return result, skipped


def do_export_only():
    list_files = gb.glob(os.path.join(config.CHECKPOINT_DIR, "list_pages_*.json"))
    all_products = []
    seen_pnks = set()
    for lf in sorted(list_files):
        cp = load_checkpoint(lf)
        if cp:
            for p in cp.get("products", []):
                pnk = p.get("pnk", "")
                if pnk and pnk not in seen_pnks:
                    seen_pnks.add(pnk)
                    all_products.append(p)
    if not all_products:
        logger.error("未找到任何有效断点数据。请先运行一次采集（python main.py）生成断点。")
        return
    detail_cp = load_checkpoint(config.CHECKPOINT_DETAIL_PAGES)
    detail_map = detail_cp.get("detail_data", {}) if detail_cp else {}
    for p in all_products:
        pnk = p.get("pnk", "")
        if pnk in detail_map:
            p.update(detail_map[pnk])
    logger.info(f"从断点加载: {len(all_products)} 个商品（去重后）")
    save_csv(all_products)
    save_excel(all_products)
    save_json(all_products)
    print(f"\nExport complete: {len(all_products)} products\n  {config.CSV_FILE}\n  {config.EXCEL_FILE}\n  {config.JSON_FILE}")


def export_all(products):
    save_csv(products)
    save_excel(products)
    save_json(products)


def print_summary(stats: dict, start_time: float):
    elapsed = time.time() - start_time
    h, m, s = int(elapsed // 3600), int((elapsed % 3600) // 60), int(elapsed % 60)
    print()
    print("=" * 60)
    print("  抓取完成!")
    print("=" * 60)
    print(f"  耗时: {h}h {m}m {s}s")
    print(f"  类目: {stats.get('categories_done',0)}成功/{stats.get('categories_failed',0)}失败")
    print(f"  页数限制: {stats.get('page_limit', 'ALL')}")
    print(f"  实际抓取: {stats.get('pages_crawled', 0)} 页")
    print(f"  共商品: {stats.get('total_products', 0)} 个")
    if stats.get('dedup_skipped', 0) > 0:
        print(f"  去重跳过: {stats['dedup_skipped']} 个")
    print(f"  详情成功: {stats.get('success_detail', 0)}")
    print(f"  详情失败: {stats.get('fail_detail', 0)}")
    print()
    print(f"  运行目录: {config.OUTPUT_DIR}")
    print(f"    CSV:  {config.CSV_FILE}")
    print(f"    Excel: {config.EXCEL_FILE}")
    print(f"    JSON: {config.JSON_FILE}")
    print(f"    图片: {config.IMAGES_DIR}")
    print(f"    日志: {config.LOGS_DIR}")
    print("=" * 60)
    print()


def _build_category_infos(urls: list[str]) -> list[CategoryInfo]:
    """将 URL 字符串列表转为 CategoryInfo 列表，过滤非商品列表页"""
    from urllib.parse import urlparse
    result = []
    for idx, url in enumerate(urls, 1):
        parsed = urlparse(url)
        if not parsed.path.rstrip("/").endswith("/c"):
            logger.warning(f"路径不以 /c 结尾，跳过: {url[:100]}")
            continue
        if "emag.ro" not in parsed.netloc and "emag.ro" not in url:
            logger.warning(f"非 eMAG 域名，跳过: {url[:80]}")
            continue
        path = _extract_category_path(url)
        if not path:
            logger.warning(f"无法解析类目路径，跳过: {url[:100]}")
            continue
        result.append(CategoryInfo(url=url, category_path=path, index=idx + len(result)))
    return result


def main():
    args = parse_args()

    # 拒绝负数页数，非零退出码
    if args.pages < 0:
        sys.exit("错误: --pages 不能为负数")
    if args.category_pages < 0:
        sys.exit("错误: --category-pages 不能为负数")

    effective_pages = args.category_pages if args.category_pages > 0 else args.pages
    start_time = time.time()

    print()
    print("=" * 60)
    print("  eMAG Multi-Category Scraper v1.0.4")
    print("=" * 60)
    print()

    if args.debug:
        print_debug_banner(args, effective_pages)
        return

    if args.export_only:
        do_export_only()
        return

    if args.reset:
        reset_checkpoints()

    # ---- 类目加载 ----
    if args.auto_discover:
        try:
            from category_discovery import discover_categories
            raw_urls = discover_categories(force_refresh=args.refresh_categories)
            categories = _build_category_infos(raw_urls)
            if not categories:
                logger.error("自动发现未找到有效类目")
                return
        except Exception as e:
            logger.error(f"类目自动发现失败: {e}")
            return
        if effective_pages <= 0:
            effective_pages = getattr(config, 'MAX_PAGES_PER_CATEGORY', 10)
            logger.info(f"自动发现模式: 每类目默认 {effective_pages} 页")
    else:
        try:
            categories = load_categories()
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            return

    # ---- 图片开关 ----
    if args.no_images:
        config.DOWNLOAD_IMAGES = False

    # ---- list-only 默认不下载图片 ----
    list_img = args.download_list_images and config.DOWNLOAD_IMAGES
    if args.list_only and not args.download_list_images:
        config.DOWNLOAD_IMAGES = False

    # ---- 统计 ----
    stats = {
        "total_categories": len(categories),
        "categories_done": 0, "categories_failed": 0,
        "page_limit": effective_pages if effective_pages > 0 else "ALL",
        "pages_crawled": 0, "total_products": 0,
        "dedup_skipped": 0,
        "success_detail": 0, "fail_detail": 0,
    }

    all_products = []

    # ================================================================
    # Phase 1: 多类目列表页
    # ================================================================
    print()
    logger.info("=" * 60)
    logger.info("Phase 1: 多类目列表页采集")
    logger.info("=" * 60)

    for cat in categories:
        logger.info(f"  [{cat.index}/{len(categories)}] {cat.category_path}")
        try:
            cp, cs = crawl_list_pages(start_url=cat.url, category_path=cat.category_path,
                                       max_pages=effective_pages)
            if cp:
                all_products.extend(cp)
                stats["categories_done"] += 1
                stats["pages_crawled"] += cs.get("pages_crawled", 0)
                logger.info(f"  → {len(cp)} products, {cs.get('pages_crawled',0)} pages")
            else:
                stats["categories_failed"] += 1
        except Exception as e:
            logger.error(f"  类目异常: {e}")
            stats["categories_failed"] += 1

    # ---- 跨类目 PNK 去重 ----
    before_dedup = len(all_products)
    all_products, dedup_skipped = dedup_products(all_products)
    stats["dedup_skipped"] = dedup_skipped
    stats["total_products"] = len(all_products)
    if dedup_skipped:
        logger.info(f"跨类目去重: {before_dedup} → {len(all_products)} (跳过 {dedup_skipped})")

    if not all_products:
        logger.error("所有类目均无数据，退出")
        return

    # ---- list-only ----
    if args.list_only:
        if list_img:
            download_all_images(all_products, __import__('scrapling.fetchers', fromlist=['Fetcher']).Fetcher)
        export_all(all_products)
        print_summary(stats, start_time)
        return

    # ================================================================
    # Phase 2: 详情页
    # ================================================================
    all_products = crawl_detail_pages(all_products)
    cp_detail = load_checkpoint(config.CHECKPOINT_DETAIL_PAGES)
    if cp_detail:
        stats["success_detail"] = len(cp_detail.get("completed_pnks", []))
    stats["fail_detail"] = stats["total_products"] - stats["success_detail"]

    # ================================================================
    # Phase 3: 图片 → 导出
    # ================================================================
    if config.DOWNLOAD_IMAGES:
        download_all_images(all_products, __import__('scrapling.fetchers', fromlist=['Fetcher']).Fetcher)
    export_all(all_products)
    print_summary(stats, start_time)


if __name__ == "__main__":
    main()
