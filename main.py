"""
eMAG Mouse Category Scraper
============================
基于 Scrapling 的完整 eMAG 爬虫

用法:
    # 仅爬列表页（快，~5分钟）
    python main.py --list-only

    # 列表 + 详情 + 图片（完整，~数小时）
    python main.py

    # 重置后重新开始
    python main.py --reset

    # 仅导出（不爬取）
    python main.py --export-only
"""

import argparse
import os
import sys
import time

# 确保项目目录在 Python Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from logger import logger
from crawler import crawl_list_pages, crawl_detail_pages
from save import save_csv, save_excel, save_json, download_all_images
from utils import load_checkpoint
from category_loader import load_categories, CategoryInfo
from scrapling.fetchers import Fetcher


def parse_args():
    p = argparse.ArgumentParser(description="eMAG Multi-Category Scraper")
    p.add_argument("--auto-discover", action="store_true",
                   help="自动发现 eMAG 全站商品类目")
    p.add_argument("--refresh-categories", action="store_true",
                   help="强制重新扫描类目（清除缓存）")
    p.add_argument("--list-only", action="store_true", help="仅爬列表页")
    p.add_argument("--reset", action="store_true", help="清除断点重新开始")
    p.add_argument("--export-only", action="store_true", help="仅导出已有数据")
    p.add_argument("--no-images", action="store_true", help="不下载图片")
    p.add_argument("--pages", type=int, default=0,
                   help="限制爬取页数（0=全部；单类目模式）")
    p.add_argument("--category-pages", type=int, default=0,
                   help="每个一级类目采集页数（默认 10；多类目模式）")
    p.add_argument("--debug", action="store_true", help="调试模式：打印配置后退出")
    return p.parse_args()


def reset_checkpoints():
    """清除所有断点数据"""
    import glob
    for f in glob.glob(os.path.join(config.CHECKPOINT_DIR, "*.json")):
        os.remove(f)
    logger.info("已清除所有断点数据")


def print_debug_banner(args):
    """调试模式：打印完整配置"""
    mode = []
    if args.list_only:
        mode.append("list-only")
    if args.export_only:
        mode.append("export-only")
    if not mode:
        mode.append("full (list + detail + images)")
    if args.no_images:
        mode.append("no-images")
    if args.reset:
        mode.append("reset")

    print()
    print("=" * 60)
    print("  DEBUG - Configuration")
    print("=" * 60)
    print(f"  Mode:           {', '.join(mode)}")
    print(f"  Category Pages: {args.category_pages if args.category_pages > 0 else args.pages if args.pages > 0 else config.MAX_PAGES_PER_CATEGORY}（默认）")
    print(f"  --pages (legacy): {args.pages if args.pages > 0 else 'unset'}")
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


def main():
    args = parse_args()

    start_time = time.time()

    print()
    print("=" * 60)
    print("  eMAG Multi-Category Scraper")
    print(f"  Config: {config.CATEGORIES_FILE}")
    print("=" * 60)
    print()

    # ---- 调试模式 ----
    if args.debug:
        print_debug_banner(args)
        logger.info("调试模式：已打印配置，程序退出")
        return

    # ---- 每次运行清除上一轮断点，确保分页计数从 0 开始 ----
    reset_checkpoints()

    # ---- 仅导出 ----
    if args.export_only:
        cp = load_checkpoint(config.CHECKPOINT_DETAIL_PAGES)
        products = []
        if cp and cp.get("detail_data"):
            logger.info("从断点加载详情数据...")
            list_cp = load_checkpoint(config.CHECKPOINT_LIST_PAGES)
            products = list_cp.get("products", []) if list_cp else []
            detail_map = cp.get("detail_data", {})
            for p in products:
                pnk = p.get("pnk", "")
                if pnk in detail_map:
                    p.update(detail_map[pnk])
        export_all(products)
        return

    # ---- 加载类目 ----
    categories = []

    if args.auto_discover:
        # 全站类目自动发现模式
        from category_discovery import discover_categories
        config.AUTO_DISCOVER = True
        logger.info("=" * 60)
        logger.info("Auto-Discover Mode: 扫描 eMAG 全站商品类目")
        logger.info("=" * 60)

        discovered = discover_categories(force_refresh=args.refresh_categories)
        if not discovered:
            logger.error("未发现任何商品类目，退出")
            return
        logger.info(f"发现 {len(discovered)} 个商品类目")

        # 转换为 CategoryInfo 列表
        from category_loader import CategoryInfo, _extract_category_path
        for idx, url in enumerate(discovered, 1):
            path = _extract_category_path(url)
            if path:
                categories.append(CategoryInfo(url=url, category_path=path, index=idx))

        # 每类目默认页数
        per_cat = args.category_pages or args.pages or config.MAX_PAGES_PER_CATEGORY
        logger.info(f"每类目限制: {per_cat} 页（--category-pages={args.category_pages}, --pages={args.pages}）")

    else:
        # 传统模式: 从 categories.txt 加载
        try:
            categories = load_categories()
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            return

    if not categories:
        logger.error("无可用类目，退出")
        return

    # ---- 图片开关 ----
    if args.no_images:
        config.DOWNLOAD_IMAGES = False

    # ---- 每类目页数：--category-pages > --pages > 默认 10 ----
    per_cat_pages = args.category_pages or args.pages or config.MAX_PAGES_PER_CATEGORY

    # ---- 统计 ----
    stats = {
        "total_categories": len(categories),
        "categories_done": 0,
        "categories_failed": 0,
        "pages_crawled": 0,
        "total_products": 0,
        "dedup_skipped": 0,
        "success_detail": 0,
        "fail_detail": 0,
    }

    # 去重：跨类目 PNK 唯一
    seen_pnks: set[str] = set()
    all_products = []

    # ================================================================
    # Phase 1: 遍历所有类目，每类目独立计数
    # ================================================================
    print()
    logger.info("=" * 60)
    logger.info(f"Phase 1: {len(categories)} 个类目, 每类目 ≤{per_cat_pages} 页")
    logger.info("=" * 60)

    for cat in categories:
        print()
        logger.info("=" * 50)
        logger.info(f"Category [{cat.index}/{len(categories)}]: {cat.category_path}")
        logger.info(f"  URL:  {cat.url[:100]}")
        logger.info(f"  Target Pages: {per_cat_pages}")
        logger.info("=" * 50)

        try:
            cat_products, cat_stats = crawl_list_pages(
                start_url=cat.url,
                category_path=cat.category_path,
                max_pages=per_cat_pages,
            )

            if not cat_products:
                logger.warning(f"类目无数据 [{cat.index}]: {cat.category_path}，跳过")
                stats["categories_failed"] += 1
                continue

            # ---- PNK 去重 ----
            new_count = 0
            dup_count = 0
            for p in cat_products:
                pnk = p.get("pnk", "")
                if pnk and pnk in seen_pnks:
                    dup_count += 1
                    continue
                if pnk:
                    seen_pnks.add(pnk)
                all_products.append(p)
                new_count += 1

            cat_pages = cat_stats.get("pages_crawled", 0)
            stats["categories_done"] += 1
            stats["pages_crawled"] += cat_pages
            stats["dedup_skipped"] += dup_count

            logger.info(
                f"Finished [{cat.category_path}]: "
                f"{cat_pages} 页, {new_count} 商品"
                + (f"（去重 {dup_count}）" if dup_count > 0 else "")
            )

        except Exception as e:
            logger.error(f"类目采集异常 [{cat.index}]: {cat.category_path} — {e}")
            stats["categories_failed"] += 1
            continue

    stats["total_products"] = len(all_products)

    if not all_products:
        logger.error("所有类目均无数据，退出")
        return

    # ---- 如果仅列表页 ----
    if args.list_only:
        logger.info("--list-only 模式: 仅保存列表页数据")
        save_csv(all_products)
        save_json(all_products)
        save_excel(all_products)
        if config.DOWNLOAD_IMAGES:
            download_all_images(all_products, Fetcher)
        print_summary(stats, start_time)
        return

    # ================================================================
    # Phase 2: 爬取详情页
    # ================================================================
    print()
    logger.info("=" * 50)
    logger.info("Phase 2: 爬取详情页")
    logger.info("=" * 50)

    all_products = crawl_detail_pages(all_products)

    # 统计详情结果
    cp = load_checkpoint(config.CHECKPOINT_DETAIL_PAGES)
    if cp:
        stats["success_detail"] = len(cp.get("completed_pnks", []))
    stats["fail_detail"] = stats["total_products"] - stats["success_detail"]

    # ================================================================
    # Phase 3: 导出
    # ================================================================
    print()
    logger.info("=" * 50)
    logger.info("Phase 3: 导出数据")
    logger.info("=" * 50)

    export_all(all_products)

    # ================================================================
    # 完成
    # ================================================================
    print_summary(stats, start_time)


def export_all(products: list[dict]):
    """导出 CSV / Excel / JSON / 图片"""
    from scrapling.fetchers import Fetcher

    if not products:
        logger.warning("没有产品数据可导出")
        return

    # CSV
    csv_path = save_csv(products)

    # Excel
    excel_path = save_excel(products)

    # JSON
    json_path = save_json(products)

    # 图片（ImageDownloader 内部已更新 image_path 和 image_count）
    if config.DOWNLOAD_IMAGES:
        download_all_images(products, Fetcher)


def print_summary(stats: dict, start_time: float):
    """打印最终统计"""
    elapsed = time.time() - start_time
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)

    print()
    print("=" * 60)
    print("  抓取完成!")
    print("=" * 60)
    print(f"  耗时: {hours}h {minutes}m {seconds}s")
    print(f"  类目总数: {stats.get('total_categories', '?')}")
    print(f"  类目成功: {stats.get('categories_done', 0)}")
    print(f"  类目失败: {stats.get('categories_failed', 0)}")
    print(f"  实际抓取: {stats.get('pages_crawled', 0)} 页")
    print(f"  共商品: {stats.get('total_products', 0)} 个")
    print(f"  去重跳过: {stats.get('dedup_skipped', 0)} 个")
    print(f"  详情成功: {stats.get('success_detail', 0)} 个")
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


if __name__ == "__main__":
    main()
