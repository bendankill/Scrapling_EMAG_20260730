"""
eMAG Multi-Category Scraper v1.0.5
===================================
可扩展并发多类目采集。支持 basic-only 快速模式和完整详情模式。
"""

import argparse
import os
import sys
import time
import glob as gb
import concurrent.futures
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from logger import logger
from crawler import crawl_list_pages, crawl_detail_pages
from save import save_csv, save_excel, save_json, download_all_images
from utils import load_checkpoint, is_valid_emag_url
from category_loader import load_categories, CategoryInfo, _extract_category_path


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_BAD_ARGS = 2
EXIT_PARTIAL = 3


def parse_args():
    p = argparse.ArgumentParser(description="eMAG Multi-Category Scraper v1.0.5")
    # 采集模式
    p.add_argument("--basic-only", action="store_true",
                   help="仅抓列表页基础数据（推荐大规模采集模式）")
    p.add_argument("--list-only", action="store_true",
                   help="同 --basic-only（兼容旧参数）")
    p.add_argument("--reset", action="store_true", help="清除断点重新开始")
    p.add_argument("--export-only", action="store_true",
                   help="仅导出已有断点，不发起网络请求")
    p.add_argument("--auto-discover", action="store_true",
                   help="从 eMAG 首页导航自动发现类目")
    p.add_argument("--refresh-categories", action="store_true",
                   help="忽略类目缓存重新扫描")
    # 图片
    p.add_argument("--no-images", action="store_true", help="所有模式不下载图片")
    p.add_argument("--download-main-images", action="store_true",
                   help="下载列表页主图（basic-only 模式）")
    p.add_argument("--download-list-images", action="store_true",
                   help="同 --download-main-images（兼容）")
    # 页数
    p.add_argument("--pages", type=int, default=0, help="每类目页数（0=全部）")
    p.add_argument("--category-pages", type=int, default=0,
                   help="每类目页数（优先级高于 --pages）")
    # 并发 v1.0.5
    p.add_argument("--category-workers", type=int, default=0,
                   help="并发类目数（默认4）")
    p.add_argument("--page-workers", type=int, default=0,
                   help="每类目并发页数（默认4）")
    p.add_argument("--max-in-flight", type=int, default=0,
                   help="全局最大并发请求数（默认16）")
    # 调试
    p.add_argument("--debug", action="store_true", help="打印配置后退出")
    return p.parse_args()


def reset_checkpoints():
    for f in gb.glob(os.path.join(config.CHECKPOINT_DIR, "*.json")):
        os.remove(f)
    logger.info("已清除所有断点数据")


def print_debug_banner(args, effective_pages):
    mode = []
    if args.basic_only or args.list_only: mode.append("basic-only")
    if args.auto_discover: mode.append("auto-discover")
    if not mode: mode.append("full")
    print(); print("=" * 60); print("  DEBUG — v1.0.5")
    print("=" * 60)
    print(f"  Mode:      {', '.join(mode)}")
    print(f"  Pages:     {effective_pages if effective_pages > 0 else 'ALL'}")
    print(f"  Workers:   cat={config.CATEGORY_WORKERS} page={config.PAGE_WORKERS} flight={config.MAX_IN_FLIGHT}")
    print(f"  Run Dir:   {config.OUTPUT_DIR}")
    print("=" * 60); print()


def _build_category_infos(urls: list[str]) -> list[CategoryInfo]:
    result = []
    for url in urls:
        if not is_valid_emag_url(url):
            logger.warning(f"非法URL，跳过: {url[:100]}")
            continue
        path = _extract_category_path(url)
        if not path:
            logger.warning(f"无法解析类目路径，跳过: {url[:100]}")
            continue
        result.append(CategoryInfo(url=url, category_path=path, index=len(result) + 1))
    return result


def _dedup_key(p: dict) -> str | None:
    pnk = p.get("pnk", "").strip()
    if pnk: return f"pnk:{pnk}"
    url = p.get("url", "").strip()
    if url:
        from urllib.parse import urlparse
        pu = urlparse(url)
        return f"url:{pu.netloc}{pu.path.rstrip('/')}"
    pid = p.get("product_id", ""); oid = p.get("offer_id", "")
    if pid or oid: return f"id:{pid}:{oid}"
    return None


def dedup_products(products: list[dict]) -> tuple[list[dict], int]:
    seen = set(); result = []; skipped = 0
    for p in products:
        k = _dedup_key(p)
        if k is None: result.append(p)
        elif k not in seen: seen.add(k); result.append(p)
        else: skipped += 1
    return result, skipped


def do_export_only(basic_only=False):
    list_files = gb.glob(os.path.join(config.CHECKPOINT_DIR, "list_pages_*.json"))
    all_products = []
    for lf in sorted(list_files):
        cp = load_checkpoint(lf)
        if cp and cp.get("products"):
            all_products.extend(cp["products"])
    if not all_products:
        logger.error("未找到有效断点数据")
        return 1
    all_products, skipped = dedup_products(all_products)
    logger.info(f"导出 {len(all_products)} 商品 (去重 {skipped})")

    if not basic_only:
        detail_cp = load_checkpoint(config.CHECKPOINT_DETAIL_PAGES)
        dm = detail_cp.get("detail_data", {}) if detail_cp else {}
        for p in all_products:
            pnk = p.get("pnk", "")
            if pnk in dm: p.update(dm[pnk])

    save_csv(all_products); save_excel(all_products); save_json(all_products)
    return 0


def export_all(products):
    save_csv(products); save_excel(products); save_json(products)


def print_summary(stats, start):
    e = time.time() - start
    h, m, s = int(e//3600), int((e%3600)//60), int(e%60)
    pps = stats.get("pages_crawled", 0) / max(e, 1)
    print(); print("=" * 60); print("  完成!"); print("=" * 60)
    print(f"  耗时: {h}h{m}m{s}s  ({pps:.1f} pages/s)")
    d, p, f = stats.get("categories_done",0), stats.get("categories_partial",0), stats.get("categories_failed",0)
    print(f"  类目: {d}成功/{p}部分/{f}失败")
    if stats.get("failed_pages"): print(f"  失败页: {stats['failed_pages']}")
    print(f"  页数限制: {stats.get('page_limit','ALL')}")
    print(f"  实际抓取: {stats.get('pages_crawled',0)} 页")
    print(f"  共商品: {stats.get('total_products',0)} 个")
    if stats.get("dedup_skipped"): print(f"  去重: {stats['dedup_skipped']}")
    print(f"  主图获取: {stats.get('main_images',0)} / 缺失: {stats.get('main_image_missing',0)}")
    print(f"  详情请求: {stats.get('detail_requests', stats.get('success_detail',0)+stats.get('fail_detail',0))}")
    print(f"  详情成功: {stats.get('success_detail',0)} / 失败: {stats.get('fail_detail',0)}")
    print(f"\n  运行目录: {config.OUTPUT_DIR}")
    print(f"    CSV:  {config.CSV_FILE}")
    print(f"    Excel: {config.EXCEL_FILE}")
    print(f"    JSON: {config.JSON_FILE}")
    print(f"    图片: {config.IMAGES_DIR}")
    print("=" * 60); print()


def crawl_category_sync(cat, effective_pages, basic_only, download_images):
    """同步爬取单个类目（由线程池调用）"""
    cp, cs = crawl_list_pages(
        start_url=cat.url, category_path=cat.category_path,
        max_pages=effective_pages,
        page_workers=config.PAGE_WORKERS,
        max_in_flight=config.MAX_IN_FLIGHT,
    )
    # 主图统计
    mi = sum(1 for p in cp if p.get("main_image_url"))
    m_miss = len(cp) - mi
    return {
        "category": cat, "products": cp, "stats": cs,
        "main_images": mi, "main_image_missing": m_miss,
    }


def crawl_all_categories(categories, effective_pages, basic_only, download_images):
    """并发爬取所有类目"""
    results = []
    cat_workers = min(config.CATEGORY_WORKERS, len(categories))
    logger.info(f"并发类目: {cat_workers}, 并发页: {config.PAGE_WORKERS}, 飞行上限: {config.MAX_IN_FLIGHT}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=cat_workers) as ex:
        futures = {ex.submit(crawl_category_sync, c, effective_pages, basic_only, download_images): c for c in categories}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            done += 1
            try:
                r = fut.result()
                results.append(r)
                cat = r["category"]
                logger.info(f"[{done}/{len(categories)}] {cat.category_path} → {len(r['products'])} products, {r['stats'].get('pages_crawled',0)} pages")
            except Exception as e:
                logger.error(f"类目[{done}]异常: {e}")
    results.sort(key=lambda r: r["category"].index)
    return results


def main() -> int:
    args = parse_args()
    if args.pages < 0 or args.category_pages < 0:
        print("错误: 页数不能为负数", file=sys.stderr)
        return EXIT_BAD_ARGS
    if args.category_workers < 0 or args.page_workers < 0 or args.max_in_flight < 0:
        print("错误: 并发参数不能为负数", file=sys.stderr)
        return EXIT_BAD_ARGS

    effective_pages = args.category_pages if args.category_pages > 0 else args.pages
    basic_only = args.basic_only or args.list_only
    download_main = args.download_main_images or args.download_list_images
    t0 = time.time()

    print(); print("=" * 60); print("  eMAG Multi-Category Scraper v1.0.5")
    print("=" * 60); print()

    if args.debug:
        print_debug_banner(args, effective_pages)
        return EXIT_SUCCESS

    if args.export_only:
        return do_export_only(basic_only=basic_only)

    if args.reset:
        reset_checkpoints()

    # ---- 并发参数 ----
    if args.category_workers > 0: config.CATEGORY_WORKERS = args.category_workers
    if args.page_workers > 0: config.PAGE_WORKERS = args.page_workers
    if args.max_in_flight > 0: config.MAX_IN_FLIGHT = args.max_in_flight
    # 合理性检查
    if config.CATEGORY_WORKERS > 32:
        logger.warning(f"类目并发 {config.CATEGORY_WORKERS} 偏高，建议 ≤32")

    # ---- 类目加载 ----
    if args.auto_discover:
        try:
            from category_discovery import discover_categories
            raw = discover_categories(force_refresh=args.refresh_categories)
            categories = _build_category_infos(raw)
        except Exception as e:
            logger.error(f"自动发现失败: {e}"); return EXIT_FAILURE
        if effective_pages <= 0: effective_pages = config.MAX_PAGES_PER_CATEGORY
    else:
        try:
            categories = load_categories()
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e)); return EXIT_FAILURE

    if not categories:
        logger.error("无有效类目"); return EXIT_FAILURE

    # ---- 图片开关 ----
    if args.no_images: config.DOWNLOAD_IMAGES = False
    if basic_only and not download_main: config.DOWNLOAD_IMAGES = False

    # ---- 并发采集 ----
    logger.info(f"开始采集 {len(categories)} 个类目 (mode={'basic-only' if basic_only else 'full'})")
    results = crawl_all_categories(categories, effective_pages, basic_only, download_main)

    # ---- 汇总 ----
    all_products = []; mi_total = 0; mi_miss_total = 0
    stats = {"total_categories": len(categories), "categories_done": 0,
             "categories_partial": 0, "categories_failed": 0,
             "page_limit": effective_pages if effective_pages > 0 else "ALL",
             "pages_crawled": 0, "failed_pages": 0, "total_products": 0,
             "dedup_skipped": 0, "main_images": 0, "main_image_missing": 0,
             "detail_requests": 0, "success_detail": 0, "fail_detail": 0}

    for r in results:
        cs = r["stats"]
        if r["products"]:
            all_products.extend(r["products"])
            stats["pages_crawled"] += cs.get("pages_crawled", 0)
            stats["failed_pages"] += cs.get("failed_pages", 0)
            if cs.get("complete", True): stats["categories_done"] += 1
            else: stats["categories_partial"] += 1
        else:
            stats["categories_failed"] += 1
        mi_total += r.get("main_images", 0)
        mi_miss_total += r.get("main_image_missing", 0)

    # 去重
    before = len(all_products)
    all_products, ds = dedup_products(all_products)
    stats["dedup_skipped"] = ds
    stats["total_products"] = len(all_products)
    stats["main_images"] = mi_total; stats["main_image_missing"] = mi_miss_total

    exit_code = EXIT_SUCCESS
    if not all_products: exit_code = EXIT_FAILURE
    elif stats["categories_failed"] > 0 or stats["categories_partial"] > 0: exit_code = EXIT_PARTIAL

    if not all_products:
        print_summary(stats, t0); return exit_code

    # ---- basic-only: 导出列表数据（不访问详情） ----
    if basic_only:
        logger.info("basic-only mode: 仅导出列表数据")
        if download_main and config.DOWNLOAD_IMAGES:
            download_all_images(all_products, __import__('scrapling.fetchers', fromlist=['Fetcher']).Fetcher)
        export_all(all_products)
        stats["detail_requests"] = 0
        print_summary(stats, t0)
        return exit_code

    # ================================================================
    # 完整模式: 详情页 + 图片 + 导出
    # ================================================================
    all_products, detail_stats = crawl_detail_pages(all_products)
    stats["detail_requests"] = detail_stats.get("total_products", 0)
    stats["success_detail"] = detail_stats.get("success", 0)
    stats["fail_detail"] = detail_stats.get("failed", 0)
    if not detail_stats.get("complete", True):
        if stats["fail_detail"] >= detail_stats.get("total_products", 999): exit_code = EXIT_FAILURE
        elif exit_code < EXIT_PARTIAL: exit_code = EXIT_PARTIAL

    if config.DOWNLOAD_IMAGES:
        download_all_images(all_products, __import__('scrapling.fetchers', fromlist=['Fetcher']).Fetcher)
    export_all(all_products)
    print_summary(stats, t0)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
