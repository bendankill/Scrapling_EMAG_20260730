"""
eMAG 爬虫 - 输出数据结构规范化模块

负责：
1. 英文字段名 → 中文字段名映射
2. category_trail → 一级类~五级类拆分
3. 统一输出字段顺序
4. normalize_product() — 单入口
"""

import re

# ============================================================
# 字段名映射
# ============================================================
FIELD_MAP: dict[str, str] = {
    "pnk":             "PNK码",
    "prp_price_ron":   "PRP原价",
    "sale_price_ron":  "前端价格",
    "discount_pct":    "前端折扣",
    "title":           "产品标题",
    "url":             "产品链接",
    "image_url":       "产品图片",
    "avg_rating":      "评论分数",
    "review_count":     "评价数量",
    "badges":          "链接打标",
    "brand":           "品牌",
    "description":     "详情描述",
    "star_pct":        "星级值",
}


# ============================================================
# 输出字段顺序
# ============================================================
PRIORITY_ORDER: list[str] = [
    # --- 核心中文字段 ---
    "PNK码",
    "PRP原价",
    "一级类",
    "二级类",
    "三级类",
    "四级类",
    "五级类",
    "产品图片",
    "产品标题",
    "产品链接",
    "前端价格",
    "前端折扣",
    "品牌",
    "好评率",
    "星级值",
    "规格详情",
    "评价数量",
    "评论分数",
    "详情描述",
    "链接打标",

    # --- 英文兜底字段（保持原始顺序） ---
    "product_id",
    "offer_id",
    "family_id",
    "currency",
    "is_promo",
    "is_in_stock",
    "stock_text",
    "delivery_estimate",
    "installment",
    "is_genius",
    "is_top_favorite",
    "is_super_pret",
    "image_path",
    "image_count",

    # 类目原始值
    "category_trail",

    # JSON-LD
    "ld_name",
    "ld_sku",
    "ld_mpn",
    "ld_product_id",
    "ld_price",
    "ld_price_currency",
    "ld_availability",
    "ld_rating_value",
    "ld_review_count",
    "ld_best_rating",
    "ld_worst_rating",
    "ld_seller_name",
    "seller_name",
    "seller_rating",
    "seller_positive_pct",
    "seller_type",
    "manufacturer",
    "ld_category",
    "ld_keywords",
    "ld_description",
    "ld_image",
    "ld_url",
    "ld_reviews_count_from_jsonld",
    "ld_review_bodies",

    # 内部字段
    "_has_family",
    "_scm_category",
    "_detail_url",
]


def split_category_trail(trail: str) -> dict[str, str]:
    """
    拆分 category_trail 为一级类 ~ 五级类

    支持分隔符: / > >> | \\ →

    示例:
        "PC & Software/Periferice PC/Mouse"
        → {"一级类": "PC & Software",
           "二级类": "Periferice PC",
           "三级类": "Mouse"}
    """
    if not trail:
        return {}

    parts = re.split(r"\s*(?:/{1,2}|>{1,2}|\|+|\\+|→)\s*", trail.strip())
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return {}

    labels = ["一级类", "二级类", "三级类", "四级类", "五级类"]
    result = {}
    for i, part in enumerate(parts[:5]):
        result[labels[i]] = part
    return result


def _build_spec_detail(product: dict) -> str:
    """拼接英文规范化规格键值对为 规格详情"""
    parts = []
    for k, v in product.items():
        # 只取英文规范化 key，跳过罗马尼亚语原始键（spec_*）和内部字段
        if k.startswith("spec_") or k.startswith("_"):
            continue
        if k in FIELD_MAP or k in ("all_images", "category_trail"):
            continue
        if v and isinstance(v, str) and len(v) < 200:
            parts.append(f"{k}:{v}")
    return " | ".join(parts) if parts else ""


def normalize_product(product: dict) -> dict:
    """
    归一化：映射 → 拆分 → 排序 → 输出
    """
    out = {}

    # ---- 1. 类目拆分 ----
    cat_levels = split_category_trail(product.get("category_trail", ""))
    out.update(cat_levels)

    # ---- 2. 字段映射（英文→中文） ----
    for old_key, new_key in FIELD_MAP.items():
        if old_key in product:
            out[new_key] = product[old_key]

    # ---- 3. 好评率（如果有 seller_positive_pct 或从 rating 推算） ----
    if "seller_positive_pct" in product and product["seller_positive_pct"]:
        pct = product["seller_positive_pct"]
        out["好评率"] = f"{pct}%" if not str(pct).endswith("%") else str(pct)
    else:
        out["好评率"] = ""

    # ---- 4. 规格详情 ----
    spec = _build_spec_detail(product)
    if spec:
        out["规格详情"] = spec
    else:
        out["规格详情"] = ""

    # ---- 5. 英文兜底字段 ----
    for k, v in product.items():
        if k in FIELD_MAP:
            continue  # 已映射
        if k.startswith("_gallery"):
            continue  # 内部列表
        if k.startswith("spec_"):
            continue  # 罗马尼亚语规格
        if k.startswith("ld_prop_"):
            continue
        if k in ("category_trail", "all_images"):
            continue
        out[k] = v

    # ---- 6. 按 PRIORITY_ORDER 排序 + 追加未知字段 ----
    ordered = {}
    used = set()

    for field in PRIORITY_ORDER:
        if field in out:
            ordered[field] = out[field]
            used.add(field)

    # 追加 PRIORITY_ORDER 之外的字段
    for k, v in out.items():
        if k not in used:
            ordered[k] = v

    return ordered
