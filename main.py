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
from scrapling.fetchers import Fetcher


def parse_args():
    p = argparse.ArgumentParser(description="eMAG Mouse Category Scraper")
    p.add_argument("--list-only", action="store_true", help="仅爬列表页")
    p.add_argument("--reset", action="store_true", help="清除断点重新开始")
    p.add_argument("--export-only", action="store_true", help="仅导出已有数据")
    p.add_argument("--no-images", action="store_true", help="不下载图片")
    p.add_argument("--pages", type=int, default=0, help="限制爬取页数（0=全部）")
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
    print(f"  Max Pages:      {args.pages if args.pages > 0 else 'ALL'}")
    print(f"  Concurrent:     list={config.CONCURRENT_LIST}, detail={config.CONCURRENT_DETAIL}")
    print(f"  Delay:          {config.MIN_DELAY}-{config.MAX_DELAY}s")
    print(f"  Detail Delay:   {config.MIN_DETAIL_DELAY}-{config.MAX_DETAIL_DELAY}s")
    print(f"  Max Retries:    {config.MAX_RETRIES}")
    print(f"  Download Imgs:  {config.DOWNLOAD_IMAGES and not args.no_images}")
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
    print("  eMAG Mouse Category Scraper")
    print("  https://www.emag.ro/mouse/c")
    print("=" * 60)
    print()

    # ---- 调试模式 ----
    if args.debug:
        print_debug_banner(args)
        logger.info("调试模式：已打印配置，程序退出")
        return

    # ---- 重置 ----
    if args.reset:
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

    # ---- 图片开关 ----
    if args.no_images:
        config.DOWNLOAD_IMAGES = False

    # ---- 统计 ----
    stats = {
        "website_total_pages": 0,
        "page_limit": args.pages if args.pages > 0 else "ALL",
        "pages_crawled": 0,
        "total_products": 0,
        "success_detail": 0,
        "fail_detail": 0,
    }

    # ================================================================
    # Phase 1: 爬取列表页
    # ================================================================
    print()
    logger.info("=" * 50)
    logger.info("Phase 1: 爬取列表页")
    logger.info("=" * 50)

    # ---- 关键修复：将 --pages 传入 crawler，在爬取阶段就限制翻页 ----
    products, list_stats = crawl_list_pages(max_pages=args.pages)
    if not products:
        logger.error("列表页无数据，退出")
        return

    stats["website_total_pages"] = list_stats.get("website_total_pages", 0)
    stats["pages_crawled"] = list_stats.get("pages_crawled", 0)
    stats["total_products"] = len(products)

    # ---- 如果仅列表页 ----
    if args.list_only:
        logger.info("--list-only 模式: 仅保存列表页数据")
        save_csv(products)
        save_json(products)
        save_excel(products)
        if config.DOWNLOAD_IMAGES:
            download_all_images(products, Fetcher)
        print_summary(stats, start_time)
        return

    # ================================================================
    # Phase 2: 爬取详情页
    # ================================================================
    print()
    logger.info("=" * 50)
    logger.info("Phase 2: 爬取详情页")
    logger.info("=" * 50)

    products = crawl_detail_pages(products)

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

    export_all(products)

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

    # 图片
    if config.DOWNLOAD_IMAGES:
        download_all_images(products, Fetcher)
        # 更新 image_path
        for p in products:
            pnk = p.get("pnk", "")
            import glob as gb
            img_files = gb.glob(os.path.join(config.IMAGES_DIR, f"{pnk}_*"))
            if img_files:
                p["image_path"] = img_files[0]


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
    print(f"  网站总页数: {stats.get('website_total_pages', '?')}")
    print(f"  页数限制: {stats.get('page_limit', 'ALL')}")
    print(f"  实际抓取: {stats.get('pages_crawled', 0)} 页")
    print(f"  共商品: {stats.get('total_products', 0)} 个")
    print(f"  详情成功: {stats.get('success_detail', 0)} 个")
    print(f"  详情失败: {stats.get('fail_detail', 0)} 个")
    print()
    print(f"  CSV:  {config.CSV_FILE}")
    print(f"  Excel: {config.EXCEL_FILE}")
    print(f"  JSON: {config.JSON_FILE}")
    print(f"  图片: {config.IMAGES_DIR}")
    print(f"  日志: {config.LOGS_DIR}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
