"""
eMAG 爬虫 - 爬取模块

负责：
1. HTTP 请求封装（带重试、UA轮换、Session保持）
2. 列表页翻页爬取
3. 详情页爬取
4. 并发控制
"""

import time
import os
import threading
import concurrent.futures
from typing import Callable

from scrapling.fetchers import Fetcher

import config
from logger import logger
from utils import (
    random_sleep, get_random_ua, save_checkpoint, load_checkpoint,
    build_list_url,
)
from parser import parse_list_page, parse_list_page_meta, parse_detail_page


def _is_detail_valid(detail: dict, resp=None) -> bool:
    """验证详情解析结果是否包含有效产品数据"""
    if not detail or not isinstance(detail, dict):
        return False
    # 检查响应是否可能是反爬页面
    if resp and hasattr(resp, 'html_content'):
        html = resp.html_content
        if len(html) < 5000 or 'captcha' in html.lower():
            return False
    # 必须有产品名称或品牌或规格等实质内容
    has_content = (
        detail.get("ld_name") or detail.get("brand")
        or detail.get("manufacturer") or detail.get("description")
        or detail.get("ld_sku")
    )
    return bool(has_content)


# ============================================================
# HTTP 请求封装（带重试）
# ============================================================
def fetch_with_retry(
    url: str,
    max_retries: int = None,
    **kwargs,
):
    """
    带重试和 UA 轮换的 HTTP GET

    返回: Scrapling Response 对象
    """
    max_retries = max_retries or config.MAX_RETRIES

    # 保存原始 headers（不修改调用者字典）
    original_headers = dict(kwargs.get("headers", {}))
    for attempt in range(max_retries):
        try:
            ua = get_random_ua()
            # 每次重试新建 headers 副本
            attempt_headers = dict(original_headers)
            # 大小写不敏感检查 User-Agent
            has_ua = any(k.lower() == "user-agent" for k in attempt_headers)
            if not has_ua:
                attempt_headers["User-Agent"] = ua
            # 从 kwargs 移除 headers 避免重复传递
            call_kwargs = {k: v for k, v in kwargs.items() if k != "headers"}
            resp = Fetcher.get(
                url,
                impersonate="chrome",
                stealthy_headers=True,
                timeout=30,
                headers=attempt_headers,
                **call_kwargs,
            )

            if resp.status == 200:
                return resp

            # 触发重试的状态码
            if resp.status in config.RETRY_STATUS_CODES:
                wait = config.RETRY_BACKOFF * (attempt + 1)
                logger.warning(
                    f"HTTP {resp.status} 重试 {attempt+1}/{max_retries}, "
                    f"等待 {wait}s: {url[:80]}"
                )
                time.sleep(wait)
                continue

            # 非200且不在重试列表的状态码 → 记入失败
            logger.warning(f"HTTP {resp.status} (non-retryable): {url[:80]}")
            return None

        except Exception as e:
            wait = config.RETRY_BACKOFF * (attempt + 1)
            logger.warning(
                f"请求异常 重试 {attempt+1}/{max_retries}, "
                f"等待 {wait}s: {e}"
            )
            time.sleep(wait)

    logger.error(f"达到最大重试次数: {url[:80]}")
    return None


# ============================================================
# 列表页爬取
# ============================================================
def crawl_list_pages(
    start_url: str = "",
    category_path: str = "",
    max_pages: int = 0,
    progress_callback: Callable = None,
) -> tuple[list[dict], dict]:
    """
    爬取单个类目的所有列表页，返回所有产品基本数据

    参数:
        start_url: 类目第一页完整 URL（可含 query params）
        category_path: 类目翻页路径，如 /mouse、/laptop-tablete
        max_pages: 最大爬取页数，0 表示全部
        progress_callback: 进度回调

    返回:
        products: 产品字典列表（只含列表页数据）
        stats: 统计信息
    """
    # 检查断点（按类目隔离）
    safe_name = category_path.strip("/").replace("/", "_") or "default"
    checkpoint_file = os.path.join(config.CHECKPOINT_DIR, f"list_pages_{safe_name}.json")
    checkpoint = load_checkpoint(checkpoint_file)
    completed_pages = set(checkpoint.get("completed_pages", []) if checkpoint else [])
    all_products = checkpoint.get("products", []) if checkpoint else []

    # 先获取第一页以确定总页数
    logger.info(f"正在获取首页以确定总页数...")
    first_page = fetch_with_retry(start_url or build_list_url(1, category_path))
    if not first_page:
        logger.error("无法获取首页，退出")
        return [], {
            "category_path": category_path,
            "website_total_pages": 0, "total_pages": 0,
            "total_found": 0, "pages_crawled": 0,
            "failed_pages": 1, "complete": False,
            "error": "首页获取失败：无响应",
        }

    # ---- 保存首页 HTML 用于调试 ----
    try:
        debug_html = os.path.join(config.LOGS_DIR, "page1.html")
        with open(debug_html, "w", encoding="utf-8") as f:
            f.write(first_page.html_content)
        logger.debug(f"首页 HTML 已保存: {debug_html} ({len(first_page.html_content)} bytes)")
    except Exception:
        pass

    meta = parse_list_page_meta(first_page)
    website_total_pages = meta["total_pages"]
    total_products_count = meta["total_products"]
    logger.info(
        f"网站总计: {total_products_count} 个商品, "
        f"{website_total_pages} 页, 每页 {meta['per_page']} 个"
    )

    # 验证页数合理性（仅当无用户限制时才依赖网站值）
    if website_total_pages <= 0:
        logger.warning(f"无法解析网站总页数，将根据用户限制和空页检测控制翻页")
        website_total_pages = 0  # 标记为未知
    elif website_total_pages > 1000:
        logger.warning(f"网站总页数过大 ({website_total_pages})，限制为 1000")
        website_total_pages = 1000

    # ---- 翻页上限：用户 --pages N 优先，网站总页数兜底 ----
    if max_pages > 0:
        total_pages = max_pages  # 用户指定 → 以此为准
        logger.info(
            f"翻页上限: 用户指定 {max_pages} 页"
            + (f"（网站显示 {website_total_pages} 页）" if website_total_pages > 0
               else "（网站总页数未知）")
        )
    else:
        total_pages = website_total_pages if website_total_pages > 0 else 500
        logger.info(f"翻页上限: 自动检测 {total_pages} 页（网站总页数={website_total_pages}）")

    # 处理第一页
    if 1 not in completed_pages:
        products_p1 = parse_list_page(first_page)
        all_products.extend(products_p1)
        completed_pages.add(1)
        logger.info(f"Page 1 | Parsed: {len(products_p1)} | Running Total: {len(all_products)}")
        save_checkpoint(checkpoint_file, {
            "completed_pages": list(completed_pages),
            "products": all_products,
            "total_pages": total_pages,
            "total_products_count": total_products_count,
        })
        random_sleep(reason="首页后等待")

    if progress_callback:
        progress_callback(1, total_pages, len(all_products))

    # 翻页
    pages_to_fetch = [p for p in range(2, total_pages + 1) if p not in completed_pages]

    if not pages_to_fetch:
        logger.info("所有列表页已完成")
        return all_products, {
            "category_path": category_path,
            "website_total_pages": website_total_pages,
            "total_pages": total_pages,
            "total_found": len(all_products),
            "pages_crawled": len(completed_pages),
            "failed_pages": 0,
            "complete": True,
        }

    logger.info(f"还需爬取 {len(pages_to_fetch)} 页...")

    # 使用线程池并发爬取列表页
    page_lock = threading.Lock()
    pages_done = 0

    failed_pages = 0

    def fetch_single_page(page_num: int) -> tuple[int, list[dict], bool, int]:
        """
        返回: (page_num, products, http_ok, status_code)
          http_ok=True  → HTTP 200 正常页面
          http_ok=False → 请求失败（WAF/超时/403等），不能视为空页
        """
        nonlocal pages_done, failed_pages
        random_sleep(config.MIN_DELAY, config.MAX_DELAY, reason=f"翻页到 {page_num}")

        url = build_list_url(page_num, category_path)
        resp = fetch_with_retry(url)
        if not resp:
            logger.error(f"Page {page_num} HTTP 请求失败（无响应）")
            failed_pages += 1
            return page_num, [], False, 0

        status = resp.status
        if status != 200:
            logger.warning(f"Page {page_num} HTTP {status} — 请求失败，非最后一页")
            failed_pages += 1
            return page_num, [], False, status

        products = parse_list_page(resp)
        all_products.extend(products)
        logger.info(f"Page {page_num} | Parsed: {len(products)} | Running Total: {len(all_products)}")

        # 定期保存断点
        with page_lock:
            completed_pages.add(page_num)
            pages_done += 1
            if pages_done % config.CHECKPOINT_INTERVAL == 0:
                save_checkpoint(checkpoint_file, {
                    "completed_pages": list(completed_pages),
                    "products": all_products,
                    "total_pages": total_pages,
                    "total_products_count": total_products_count,
                })

        if progress_callback:
            progress_callback(page_num, total_pages, len(all_products))

        return page_num, products, True, 200

    # 顺序执行
    for page_num in pages_to_fetch:
        _, products, http_ok, status_code = fetch_single_page(page_num)

        if not http_ok:
            continue  # HTTP 失败，跳过，不视为最后一页

        # 仅 HTTP 200 + 正常解析 + 0 商品 → 真正空页
        if not products:
            logger.info(f"Page {page_num} 正常空页（HTTP 200），已到最后一页，停止翻页")
            break

        # 每5页保存一次完整断点
        if page_num % config.CHECKPOINT_INTERVAL == 0:
            save_checkpoint(checkpoint_file, {
                "completed_pages": list(completed_pages),
                "products": all_products,
                "total_pages": total_pages,
                "total_products_count": total_products_count,
            })

    # 最终保存
    save_checkpoint(checkpoint_file, {
        "completed_pages": list(completed_pages),
        "products": all_products,
        "total_pages": total_pages,
        "total_products_count": total_products_count,
    })

    stats = {
        "category_path": category_path,
        "website_total_pages": website_total_pages,
        "total_pages": total_pages,
        "total_found": len(all_products),
        "pages_crawled": len(completed_pages),
        "failed_pages": failed_pages,
        "complete": failed_pages == 0,
    }

    logger.info(
        f"列表页爬取完成: {stats['pages_crawled']}/{stats['total_pages']} 页, "
        f"{stats['total_found']} 个商品"
    )

    return all_products, stats


# ============================================================
# 详情页爬取
# ============================================================
def crawl_detail_pages(
    products: list[dict],
    progress_callback: Callable = None,
) -> tuple[list[dict], dict]:
    """
    为每个商品爬取详情页，扩充数据

    返回: (products, detail_stats)
    """
    empty_stats = {
        "total_products": len(products), "to_fetch": 0,
        "from_checkpoint": 0, "success": 0, "failed": 0,
        "complete": True,
    }
    if not config.FETCH_DETAILS:
        logger.info("详情页爬取已禁用")
        return products, empty_stats

    if not products:
        return products, empty_stats

    # 检查断点
    checkpoint = load_checkpoint(config.CHECKPOINT_DETAIL_PAGES)
    completed_pnks = set(checkpoint.get("completed_pnks", []) if checkpoint else [])
    detail_data_map = checkpoint.get("detail_data", {}) if checkpoint else {}

    # 先合并已有详情数据，并统计从断点恢复的商品数
    this_run_pnks = {p.get("pnk", "") for p in products if p.get("pnk")}
    restored_from_checkpoint = 0
    for p in products:
        pnk = p.get("pnk", "")
        if pnk in detail_data_map and pnk in this_run_pnks:
            p.update(detail_data_map[pnk])
            restored_from_checkpoint += 1

    # 过滤需要抓取详情的（且 PNK 在本次商品集合中）
    to_fetch = [p for p in products if p.get("pnk") and p.get("pnk") not in completed_pnks]

    if not to_fetch:
        logger.info("所有详情页已完成")
        return products, {
            "total_products": len(products), "to_fetch": 0,
            "from_checkpoint": restored_from_checkpoint,
            "success": restored_from_checkpoint, "failed": 0,
            "complete": True,
        }

    total = len(to_fetch)
    logger.info(f"开始爬取 {total} 个商品详情页（并发 {config.CONCURRENT_DETAIL}）...")

    lock = threading.Lock()
    done_count = 0
    success_count = 0
    fail_count = 0

    def fetch_one_detail(product: dict) -> dict:
        nonlocal done_count, success_count, fail_count

        url = product.get("url", "")
        pnk = product.get("pnk", "")

        if not url:
            with lock:
                done_count += 1
                fail_count += 1
            return product

        random_sleep(
            config.MIN_DETAIL_DELAY, config.MAX_DETAIL_DELAY,
            reason=f"详情页 {pnk}"
        )

        resp = fetch_with_retry(url)
        if not resp:
            with lock:
                done_count += 1
                fail_count += 1
            logger.warning(f"详情页失败 [{pnk}]: 无响应")
            return product

        try:
            detail = parse_detail_page(resp, url)

            # 验证详情有效性：非空 + 有实质性产品数据
            if not _is_detail_valid(detail, resp):
                with lock:
                    done_count += 1
                    fail_count += 1
                logger.warning(f"详情无效 [{pnk}]: 空HTML/反爬/无产品数据")
                return product

            product.update(detail)

            with lock:
                completed_pnks.add(pnk)
                detail_data_map[pnk] = detail
                done_count += 1
                success_count += 1

                if done_count % config.CHECKPOINT_INTERVAL == 0:
                    save_checkpoint(config.CHECKPOINT_DETAIL_PAGES, {
                        "completed_pnks": list(completed_pnks),
                        "detail_data": detail_data_map,
                    })
                    logger.info(
                        f"详情页进度: {done_count}/{total} "
                        f"({success_count} 成功, {fail_count} 失败)"
                    )

                if progress_callback:
                    progress_callback(done_count, total)

        except Exception as e:
            with lock:
                done_count += 1
                fail_count += 1
            logger.error(f"详情页解析异常 [{pnk}]: {e}")

        return product

    # 使用线程池并发爬取详情
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=config.CONCURRENT_DETAIL
    ) as executor:
        futures = {
            executor.submit(fetch_one_detail, p): p
            for p in to_fetch
        }
        for future in concurrent.futures.as_completed(futures):
            updated = future.result()
            # 在原列表中更新
            pnk = updated.get("pnk", "")
            for i, p in enumerate(products):
                if p.get("pnk") == pnk:
                    products[i] = updated
                    break

    # 最终保存
    save_checkpoint(config.CHECKPOINT_DETAIL_PAGES, {
        "completed_pnks": list(completed_pnks),
        "detail_data": detail_data_map,
    })

    # 统计：与本次商品PNK集合取交集
    this_run_completed = completed_pnks & this_run_pnks
    this_run_success = len(this_run_completed)
    this_run_failed = len(this_run_pnks) - this_run_success

    detail_stats = {
        "total_products": len(products),
        "to_fetch": len(to_fetch),
        "from_checkpoint": restored_from_checkpoint,
        "success": this_run_success,
        "failed": max(0, this_run_failed),
        "complete": this_run_failed == 0 and len(products) > 0,
    }

    logger.info(
        f"详情页爬取完成: {this_run_success} 成功, "
        f"{this_run_failed} 失败, 断点恢复 {restored_from_checkpoint}"
    )

    return products, detail_stats
