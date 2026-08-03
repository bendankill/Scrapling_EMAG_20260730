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
from category_loader import load_categories, CategoryInfo
from scrapling.fetchers import Fetcher


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
                   help="自动从 eMAG 首页发现类目")
    p.add_argument("--debug", action="store_true",
                   help="调试模式：打印配置后退出")
    return p.parse_args()


def reset_checkpoints():
    """清除所有断点数据"""
    for f in gb.glob(os.path.join(config.CHECKPOINT_DIR, "*.json")):
        os.remove(f)
    logger.info("已清除所有断点数据")


def print_debug_banner(args, effective_pages):
    mode = []
    if args.list_only: mode.append("list-only")
    if args.export_only: mode.append("export-only")
    if args.auto_discover: mode.append("auto-discover")
    if not mode: mode.append("full (list + detail + images)")
    if args.no_images: mode.append("no-images")
    if args.reset: mode.append("reset")

    print()
    print("=" * 60)
    print("  DEBUG - Configuration")
    print("=" * 60)
    print(f"  Mode:           {', '.join(mode)}")
    print(f"  Max Pages:      {effective_pages if effective_pages > 0 else 'ALL'}")
    print(f"  Concurrent:     list={config.CONCURRENT_LIST}, detail={config.CONCURRENT_DETAIL}")
    print(f"  Delay:          {config.MIN_DELAY}-{config.MAX_DELAY}s")
    print(f"  Detail Delay:   {config.MIN_DETAIL_DELAY}-{config.MAX_DETAIL_DELAY}s")
    print(f"  Max Retries:    {config.MAX_RETRIES}")
    print(f"  Download Imgs:  {config.DOWNLOAD_IMAGES and not args.no_images}")
    print(f"  Categories:     {config.CATEGORIES_FILE}")
    print(f"  Run Dir:        {config.OUTPUT_DIR}")
    print(f"  Output:")
    print(f"    CSV:          {config.CSV_FILE}")
    print(f"    Excel:        {config.EXCEL_FILE}")
    print(f"    JSON:         {config.JSON_FILE}")
    print(f"    Images:       {config.IMAGES_DIR}")
    print(f"    Logs:         {config.LOGS_DIR}")
    print("=" * 60)
    print()


def do_export_only():
    """从断点文件导出数据，不发起任何网络请求"""
    # 自动发现所有 list_pages_*.json
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
        logger.error(
            "未找到任何有效断点数据。请先运行一次采集（python main.py）生成断点。"
        )
        return

    # 合并详情数据
    detail_cp = load_checkpoint(config.CHECKPOINT_DETAIL_PAGES)
    detail_map = detail_cp.get("detail_data", {}) if detail_cp else {}

    for p in all_products:
        pnk = p.get("pnk", "")
        if pnk in detail_map:
            p.update(detail_map[pnk])

    logger.info(f"从断点加载: {len(all_products)} 个商品（去重后）")

    # 导出（export_only 不下载图片）
    csv_path = save_csv(all_products)
    excel_path = save_excel(all_products)
    json_path = save_json(all_products)

    print()
    print("=" * 60)
    print("  Export Complete")
    print("=" * 60)
    print(f"  Products: {len(all_products)}")
    print(f"  CSV:  {csv_path}")
    print(f"  Excel: {excel_path}")
    print(f"  JSON: {json_path}")
    print("=" * 60)


def export_all(products, download_images=True):
    """导出 CSV / Excel / JSON。图片应在调用前已完成下载。"""
    csv_path = save_csv(products)
    excel_path = save_excel(products)
    json_path = save_json(products)
    return csv_path, excel_path, json_path


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
    print(f"  详情成功: {stats.get('success_detail', 0)}")
    print(f"  详情失败: {stats.get('fail_detail', 0)} 个")
    print()
    print(f"  运行目录: {config.OUTPUT_DIR}")
    print(f"    CSV:  {config.CSV_FILE}")
    print(f"    Excel: {config.EXCEL_FILE}")
    print(f"    JSON: {config.JSON_FILE}")
    print(f"    图片: {config.IMAGES_DIR}")
    print(f"    日志: {config.LOGS_DIR}")
    print("=" * 60)
    print()


def main():
    args = parse_args()

    # ---- 页数优先级: --category-pages > --pages > 默认 ----
    if args.category_pages < 0 or args.pages < 0:
        logger.error("页数参数不能为负数")
        return
    effective_pages = args.category_pages if args.category_pages > 0 else args.pages

    start_time = time.time()

    print()
    print("=" * 60)
    print("  eMAG Multi-Category Scraper v1.0.4")
    print(f"  Config: {config.CATEGORIES_FILE}")
    print("=" * 60)
    print()

    # ---- 调试模式（不创建 run dir 之外的副作用） ----
    if args.debug:
        print_debug_banner(args, effective_pages)
        logger.info("调试模式：已打印配置，程序退出")
        return

    # ---- 仅导出模式（不发起任何网络请求，不清除断点） ----
    if args.export_only:
        do_export_only()
        return

    # ---- 重置断点（仅当 --reset 指定时） ----
    if args.reset:
        reset_checkpoints()

    # ---- 加载类目 ----
    if args.auto_discover:
        try:
            from category_discovery import discover_categories
            categories = discover_categories()
        except Exception as e:
            logger.error(f"类目自动发现失败: {e}")
            return
        # 自动发现模式下未指定页数时使用安全默认值
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
    list_download_images = config.DOWNLOAD_IMAGES and args.download_list_images

    # ---- list-only: 默认不下载图片 ----
    if args.list_only and not args.download_list_images:
        list_download_images = False
        config.DOWNLOAD_IMAGES = False

    # ---- 统计 ----
    stats = {
        "total_categories": len(categories),
        "categories_done": 0,
        "categories_failed": 0,
        "website_total_pages": 0,
        "page_limit": effective_pages if effective_pages > 0 else "ALL",
        "pages_crawled": 0,
        "total_products": 0,
        "success_detail": 0,
        "fail_detail": 0,
    }

    all_products = []

    # ================================================================
    # Phase 1: 多类目列表页采集
    # ================================================================
    print()
    logger.info("=" * 60)
    logger.info("Phase 1: 多类目列表页采集")
    logger.info("=" * 60)

    for cat in categories:
        print()
        logger.info("-" * 50)
        logger.info(f"Category [{cat.index}/{len(categories)}]: {cat.category_path}")
        logger.info("-" * 50)

        try:
            cat_products, cat_stats = crawl_list_pages(
                start_url=cat.url,
                category_path=cat.category_path,
                max_pages=effective_pages,
            )

            if cat_products:
                all_products.extend(cat_products)
                stats["categories_done"] += 1
                stats["pages_crawled"] += cat_stats.get("pages_crawled", 0)
                stats["website_total_pages"] += cat_stats.get("website_total_pages", 0)
                logger.info(
                    f"Category [{cat.index}] done: {cat.category_path} "
                    f"→ {len(cat_products)} products, "
                    f"{cat_stats.get('pages_crawled', 0)} pages"
                )
            else:
                logger.warning(f"Category [{cat.index}] no data: {cat.category_path}")
                stats["categories_failed"] += 1

        except Exception as e:
            logger.error(f"Category [{cat.index}] error: {cat.category_path} — {e}")
            stats["categories_failed"] += 1
            continue

    stats["total_products"] = len(all_products)

    if not all_products:
        logger.error("所有类目均无数据，退出")
        return

    # ================================================================
    # Phase 1.5: --list-only → 导出列表数据（不访问详情, 默认不下载图片）
    # ================================================================
    if args.list_only:
        logger.info("--list-only mode: exporting list-page data")
        if list_download_images:
            logger.info("Downloading list-page thumbnails (--download-list-images)")
            download_all_images(all_products, Fetcher)
        export_all(all_products, download_images=False)
        stats["success_detail"] = 0
        stats["fail_detail"] = 0
        print_summary(stats, start_time)
        return

    # ================================================================
    # Phase 2: 详情页
    # ================================================================
    print()
    logger.info("=" * 50)
    logger.info("Phase 2: 爬取详情页")
    logger.info("=" * 50)

    all_products = crawl_detail_pages(all_products)

    cp = load_checkpoint(config.CHECKPOINT_DETAIL_PAGES)
    if cp:
        stats["success_detail"] = len(cp.get("completed_pnks", []))
    stats["fail_detail"] = stats["total_products"] - stats["success_detail"]

    # ================================================================
    # Phase 3: 先下载图片（更新 image_path / image_count），再导出
    # ================================================================
    print()
    logger.info("=" * 50)
    logger.info("Phase 3: 下载图片 → 导出数据")
    logger.info("=" * 50)

    if config.DOWNLOAD_IMAGES:
        download_all_images(all_products, Fetcher)

    export_all(all_products, download_images=False)

    print_summary(stats, start_time)


if __name__ == "__main__":
    main()
