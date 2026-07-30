"""
eMAG 爬虫 - 保存模块

输出格式: CSV / Excel / JSON + 图片下载
"""

import csv
import json
import os
from pathlib import Path

import config
from logger import logger


# ============================================================
# 字段扁平化
# ============================================================
def _flatten_dict(d: dict, prefix: str = "") -> dict:
    """将嵌套字典扁平化为一层"""
    flat = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(_flatten_dict(v, f"{key}_"))
        elif isinstance(v, list):
            flat[key] = "|".join(str(x) for x in v)
        else:
            flat[key] = v
    return flat


def _normalize_value(v) -> str:
    """将任意值转为 CSV 安全字符串"""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    # 移除换行符
    return str(v).replace("\n", " ").replace("\r", " ")


# ============================================================
# 收集所有字段名（非常重要：因为规格参数字段不固定）
# ============================================================
FIELD_ORDER = [
    "pnk", "product_id", "offer_id", "family_id",
    "title", "url", "category_trail",
    "sale_price_ron", "prp_price_ron", "currency", "is_promo", "discount_pct",
    "installment",
    "avg_rating", "review_count", "star_pct",
    "stock_text", "is_in_stock", "delivery_estimate",
    "image_url", "image_path",
    "badges", "is_genius", "is_top_favorite", "is_super_pret",
    "_has_family", "_scm_category",
    # 详情页字段
    "ld_name", "ld_sku", "ld_mpn", "ld_product_id",
    "brand", "manufacturer", "ld_category",
    "ld_price", "ld_price_currency", "ld_availability",
    "ld_rating_value", "ld_review_count",
    "ld_seller_name", "seller_name", "seller_rating", "seller_type",
    "warranty", "shipping_info",
    "description",
    "variants", "faq_count",
    "all_images", "_detail_url",
]


def _collect_all_fields(products: list[dict]) -> list[str]:
    """收集所有产品中出现过的全部字段，保持合理的顺序"""
    # 基础顺序
    all_fields = list(FIELD_ORDER)

    # 自动发现规格字段（以 spec_ 开头或非标准字段）
    spec_fields = set()
    other_fields = set()
    for p in products:
        for k in p:
            if k in all_fields:
                continue
            if k.startswith("spec_") or k.startswith("ld_prop_"):
                spec_fields.add(k)
            else:
                other_fields.add(k)

    # 添加非规格字段
    for f in sorted(other_fields):
        if f not in all_fields:
            all_fields.append(f)

    # 最后添加规格字段
    for f in sorted(spec_fields):
        if f not in all_fields:
            all_fields.append(f)

    return all_fields


# ============================================================
# CSV 写入
# ============================================================
def save_csv(products: list[dict], filepath: str = None) -> str:
    """保存为 CSV，字段自动展开"""
    filepath = filepath or config.CSV_FILE
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if not products:
        logger.warning("没有产品数据可保存到 CSV")
        return filepath

    fields = _collect_all_fields(products)
    logger.info(f"CSV 字段总数: {len(fields)}")

    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()

        for p in products:
            row = {k: _normalize_value(p.get(k)) for k in fields}
            writer.writerow(row)

    logger.info(f"CSV 已保存: {filepath} ({len(products)} 行)")
    return filepath


# ============================================================
# Excel 写入
# ============================================================
def save_excel(products: list[dict], filepath: str = None) -> str:
    """保存为 Excel（需要 openpyxl）"""
    filepath = filepath or config.EXCEL_FILE
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if not products:
        logger.warning("没有产品数据可保存到 Excel")
        return filepath

    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
    except ImportError:
        logger.error("缺少 openpyxl，请执行: pip install openpyxl")
        return ""

    fields = _collect_all_fields(products)
    logger.info(f"Excel 字段总数: {len(fields)}")

    wb = Workbook()
    ws = wb.active
    ws.title = "Products"

    # 标题行
    for col_idx, field in enumerate(fields, 1):
        ws.cell(row=1, column=col_idx, value=field)

    # 数据行
    for row_idx, p in enumerate(products, 2):
        for col_idx, field in enumerate(fields, 1):
            ws.cell(row=row_idx, column=col_idx, value=_normalize_value(p.get(field)))

    # 冻结首行
    ws.freeze_panes = "A2"

    wb.save(filepath)
    logger.info(f"Excel 已保存: {filepath} ({len(products)} 行)")
    return filepath


# ============================================================
# JSON 写入
# ============================================================
def save_json(products: list[dict], filepath: str = None) -> str:
    """保存为 JSON"""
    filepath = filepath or config.JSON_FILE
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if not products:
        logger.warning("没有产品数据可保存到 JSON")
        return filepath

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"JSON 已保存: {filepath} ({len(products)} 条)")
    return filepath


# ============================================================
# 图片下载
# ============================================================
def download_all_images(products: list[dict], fetcher_cls) -> None:
    """
    下载所有商品的主图和详情图片

    线程安全：使用 Fetcher 类的单次请求
    """
    from utils import download_image, get_high_res_url
    import concurrent.futures

    if not config.DOWNLOAD_IMAGES:
        logger.info("图片下载已禁用")
        return

    # 收集所有需要下载的图片
    image_tasks = []
    for p in products:
        pnk = p.get("pnk", "")
        # 主图
        main_img = p.get("image_url", "")
        if main_img:
            image_tasks.append((get_high_res_url(main_img), pnk, 0))

        # 详情页所有图片
        all_imgs = p.get("all_images", "")
        if all_imgs:
            for idx, img in enumerate(all_imgs.split("|"), 1):
                if img and img != main_img:
                    image_tasks.append((get_high_res_url(img), pnk, idx))

    if not image_tasks:
        logger.info("没有图片需要下载")
        return

    logger.info(f"开始下载 {len(image_tasks)} 张图片（并发 {config.CONCURRENT_IMAGE}）...")

    success = 0
    fail = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=config.CONCURRENT_IMAGE) as executor:
        futures = {
            executor.submit(download_image, url, pid, idx, fetcher_cls): (pid, idx)
            for url, pid, idx in image_tasks
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

    logger.info(f"图片下载完成: 成功 {success}, 失败 {fail}")

    # 更新产品的 image_path
    for p in products:
        pnk = p.get("pnk", "")
        main_path = os.path.join(config.IMAGES_DIR, f"{pnk}_000.jpg")
        if os.path.exists(main_path):
            p["image_path"] = main_path
        else:
            # 找第一个存在的
            import glob
            existing = glob.glob(os.path.join(config.IMAGES_DIR, f"{pnk}_*"))
            p["image_path"] = existing[0] if existing else ""
