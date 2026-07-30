"""
eMAG 爬虫 - 解析模块

负责：
1. 列表页 HTML → 商品基本数据列表
2. 详情页 HTML → 商品完整数据
"""

import json
import re
from urllib.parse import urljoin

from scrapling.engines.toolbelt.custom import Response as ScraplingResponse

import config
from logger import logger
from utils import parse_price, extract_pnk_from_url, safe_filename


# ============================================================
# 列表页解析
# ============================================================
def parse_list_page(response: ScraplingResponse) -> list[dict]:
    """
    从列表页提取所有商品基本数据

    返回: [ { product_id, title, url, pnk, ... }, ... ]
    """
    products = []

    cards = response.css(".card-v2")
    logger.debug(f"列表页找到 {len(cards)} 个 .card-v2 卡片")

    for card in cards:
        try:
            product = _parse_single_card(card)
            if product and product.get("url"):
                products.append(product)
        except Exception as e:
            logger.warning(f"解析卡片失败: {e}")

    return products


def _parse_single_card(card) -> dict | None:
    """解析单个 .card-v2 产品卡片"""

    # ---- 1. 从 data-product JSON 提取核心数据 ----
    fav_btn = card.css(".add-to-favorites[data-product]")
    dp_raw = fav_btn[0].attrib.get("data-product", "{}") if fav_btn else "{}"
    try:
        dp = json.loads(dp_raw)
    except json.JSONDecodeError:
        dp = {}

    # ---- 2. 从 compare 按钮提取补充数据 ----
    cmp_btn = card.css(".card-compare-btn")
    cmp_data = {}
    if cmp_btn:
        cmp_data = {
            "data_id": cmp_btn[0].attrib.get("data-id", ""),
            "data_prod_id": cmp_btn[0].attrib.get("data-prod-id", ""),
            "data_offer_id": cmp_btn[0].attrib.get("data-offer-id", ""),
            "data_family_id": cmp_btn[0].attrib.get("data-family-id", ""),
            "data_img": cmp_btn[0].attrib.get("data-img", ""),
        }

    # ---- 3. 基本字段 ----
    pnk = dp.get("pnk") or cmp_data.get("data_id") or ""
    title = dp.get("product_name", "")

    # 链接
    link_el = card.css("a[href*='/pd/']")
    url = link_el[0].attrib.get("href", "") if link_el else ""
    if url and not url.startswith("http"):
        url = urljoin(config.BASE_DOMAIN, url)

    # 图片
    img_el = card.css("img[src*='emagst']")
    img_url = img_el[0].attrib.get("src", "") if img_el else cmp_data.get("data_img", "")

    # ---- 4. 价格 ----
    # eMAG 价格格式: <p>45<sup>,99</sup><span>Lei</span></p>
    # ::text 返回 ['45', ',', '99', 'Lei']，需拼接
    sale_price_el = card.css(".product-new-price")
    sale_price_text = ""
    if sale_price_el:
        parts = sale_price_el[0].css("::text").getall()
        sale_price_text = "".join(parts)

    prp_price_el = card.css(".pricing.rrp-lp30d")
    prp_text = ""
    if prp_price_el:
        parts = prp_price_el[0].css("::text").getall()
        prp_text = "".join(parts)

    sale_price = parse_price(sale_price_text)
    prp_price = parse_price(prp_text)

    # 折扣
    discount_badge = card.css(".badge-discount::text").get() or ""
    discount_pct = None
    if discount_badge:
        m = re.search(r"[-]?(\d+)", discount_badge)
        discount_pct = int(m.group(1)) if m else None
    elif sale_price and prp_price and prp_price > 0:
        discount_pct = round((1 - sale_price / prp_price) * 100)

    is_promo = bool(prp_price and sale_price and sale_price < prp_price)

    # ---- 5. 评分 ----
    avg_rating_text = card.css(".average-rating::text").get() or ""
    avg_rating = float(avg_rating_text) if avg_rating_text else None

    review_text_raw = card.css(".star-rating-text .hidden-xs::text").get() or ""
    review_count = None
    # 格式: "165 de review-uri" 或 "1216 review-uri" 或 "(165)"
    m = re.search(r"(\d[\d.]*)\s*(?:de\s*)?review", review_text_raw)
    if m:
        review_count = int(m.group(1).replace(".", ""))
    if review_count is None:
        # 备选: 从括号提取 "(165)"
        m2 = re.search(r"\((\d+)\)", review_text_raw)
        if m2:
            review_count = int(m2.group(1))

    # 星级百分比
    star_width_el = card.css(".star-rating-inner")
    star_pct = None
    if star_width_el:
        style = star_width_el[0].attrib.get("style", "")
        m = re.search(r"width:\s*([\d.]+)%", style)
        if m:
            star_pct = float(m.group(1))

    # ---- 6. 库存 ----
    stock_text = card.css(".text-availability-in_stock::text").get() or ""
    stock_text = stock_text.strip() if stock_text else ""
    is_in_stock = "stock" in card.css(".text-availability-in_stock").getall()[0] if card.css(".text-availability-in_stock") else False

    # ---- 7. 交付预估 ----
    estimate_text = card.css(".card-estimate-placeholder::text").get() or ""

    # ---- 8. 角标/标签 ----
    badges = []
    badge_els = card.css(".card-v2-badge:not(.badge-genius)")
    for b in badge_els:
        txt = b.text.strip()
        if txt and txt not in badges and len(txt) < 50:
            badges.append(txt)

    is_genius = len(card.css(".badge-genius")) > 0
    is_top_favorite = "Top Favorite" in badges
    is_super_pret = "Super Pret" in badges

    # ---- 9. 分期 ----
    installment_text = card.css(".my-wallet-badge::text").get() or ""
    installment_text = installment_text.strip()

    # ---- 10. 其他 ----
    category_trail = dp.get("category_trail", "")

    # 构建产品字典
    product = {
        # 标识
        "pnk": pnk,
        "product_id": dp.get("productid") or cmp_data.get("data_prod_id") or "",
        "offer_id": dp.get("offerid") or cmp_data.get("data_offer_id") or "",
        "family_id": cmp_data.get("data_family_id") or "",

        # 基本信息
        "title": title,
        "url": url,
        "category_trail": category_trail,

        # 价格
        "sale_price_ron": sale_price,
        "prp_price_ron": prp_price,
        "currency": dp.get("currency", "RON"),
        "is_promo": is_promo,
        "discount_pct": discount_pct,

        # 分期
        "installment": installment_text,

        # 评分
        "avg_rating": avg_rating,
        "review_count": review_count,
        "star_pct": star_pct,

        # 库存
        "stock_text": stock_text,
        "is_in_stock": is_in_stock,
        "delivery_estimate": estimate_text.strip(),

        # 图片
        "image_url": img_url,

        # 标签
        "badges": "|".join(badges) if badges else "",
        "is_genius": is_genius,
        "is_top_favorite": is_top_favorite,
        "is_super_pret": is_super_pret,

        # 原始标记
        "_has_family": dp.get("has_family", False),
        "_scm_category": dp.get("scm_super_category", {}).get("name", ""),
    }

    return product


# ============================================================
# 列表页汇总信息
# ============================================================
def parse_list_page_meta(response: ScraplingResponse) -> dict:
    """提取列表页元信息：总商品数、总页数、当前页等"""
    meta = {
        "total_products": 0,
        "total_pages": 0,
        "current_page": 1,
        "per_page": 60,
    }

    # 总数
    total_el = response.css(".sidebar-total-products-info::text").get()
    if total_el:
        m = re.search(r"(\d[\d.]*)\s*produse", total_el)
        if m:
            meta["total_products"] = int(m.group(1).replace(".", ""))

    # 当前页码
    current_el = response.css("[class*=active][class*=pagination] a::text, .pagination .active a::text, .pagination .active::text").get()
    if current_el:
        try:
            meta["current_page"] = int(current_el.strip())
        except ValueError:
            pass

    # 推导总页数
    if meta["total_products"] > 0:
        meta["total_pages"] = (meta["total_products"] + meta["per_page"] - 1) // meta["per_page"]

    return meta


# ============================================================
# 详情页解析
# ============================================================
def parse_detail_page(response: ScraplingResponse, product_url: str) -> dict:
    """
    从详情页提取完整商品数据

    返回: 合并了 JSON-LD、规格表、描述等的完整字典
    """
    detail = {
        "_detail_url": product_url,
    }

    # ---- 1. JSON-LD 结构化数据 ----
    ld_json = _extract_jsonld(response)
    if ld_json:
        _parse_product_jsonld(detail, ld_json)

    # ---- 2. 规格参数表 ----
    specs = _parse_specs_table(response)
    detail.update(specs)

    # ---- 3. 描述 ----
    detail["description"] = _parse_description(response)

    # ---- 4. 图片列表 ----
    detail["all_images"] = _parse_all_images(response)

    # ---- 5. 卖家信息 ----
    seller_info = _parse_seller(response)
    detail.update(seller_info)

    # ---- 6. 变体 ----
    variants = _parse_variants(response)
    detail["variants"] = variants

    # ---- 7. FAQ / Q&A ----
    detail["faq_count"] = _parse_faq_count(response)

    # ---- 8. 配送信息 ----
    detail["shipping_info"] = _parse_shipping(response)

    # ---- 9. 保修 ----
    detail["warranty"] = _parse_warranty(response)

    return detail


def _extract_jsonld(response: ScraplingResponse) -> dict | None:
    """提取 JSON-LD Product 数据"""
    scripts = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        response.html_content,
        re.DOTALL,
    )
    for s in scripts:
        try:
            data = json.loads(s)
            # 可能是单个对象或数组
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    return item
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _parse_product_jsonld(product: dict, ld: dict) -> None:
    """解析 Product JSON-LD 到 product 字典"""
    product["ld_name"] = ld.get("name", "")
    product["ld_description"] = ld.get("description", "")
    product["ld_sku"] = ld.get("sku", "")
    product["ld_mpn"] = ld.get("mpn", "")
    product["ld_product_id"] = ld.get("productID", "")
    product["ld_keywords"] = ld.get("keywords", "")
    product["ld_image"] = ld.get("image", "")
    product["ld_url"] = ld.get("url", "")

    # 品牌
    brand = ld.get("brand", {})
    product["brand"] = brand.get("name", "") if isinstance(brand, dict) else str(brand)

    # 制造商
    manufacturer = ld.get("manufacturer", {})
    product["manufacturer"] = manufacturer.get("name", "") if isinstance(manufacturer, dict) else str(manufacturer)

    # 分类
    product["ld_category"] = ld.get("category", "")

    # 评分
    agg = ld.get("aggregateRating", {})
    if agg:
        product["ld_rating_value"] = agg.get("ratingValue", "")
        product["ld_review_count"] = agg.get("reviewCount", "")
        product["ld_best_rating"] = agg.get("bestRating", "")
        product["ld_worst_rating"] = agg.get("worstRating", "")

    # 价格 & 库存
    offers = ld.get("offers", {})
    if isinstance(offers, dict):
        product["ld_price"] = offers.get("price", "")
        product["ld_price_currency"] = offers.get("priceCurrency", "")
        product["ld_availability"] = offers.get("availability", "")

        # 卖家
        seller = offers.get("seller", {})
        if isinstance(seller, dict):
            product["ld_seller_name"] = seller.get("name", "")
            product["ld_seller_url"] = seller.get("url", "")

    # 评论列表
    reviews = ld.get("review", [])
    if isinstance(reviews, list):
        product["ld_reviews_count_from_jsonld"] = len(reviews)
        # 提取评论摘要
        review_texts = []
        for r in reviews[:20]:
            body = r.get("reviewBody", "")
            if body:
                review_texts.append(body)
        product["ld_review_bodies"] = " | ".join(review_texts)

    # 附加属性
    addl = ld.get("additionalProperty", [])
    if addl:
        for prop in addl:
            name = prop.get("name", "")
            value = prop.get("value", "")
            if name:
                key = f"ld_prop_{name.lower().replace(' ', '_')}"
                product[key] = value


def _parse_specs_table(response: ScraplingResponse) -> dict:
    """解析规格参数表 -> 展开为独立字段"""
    specs = {}
    rows = response.css("table.specifications-table tr, .table-striped tr")
    for row in rows:
        label_el = row.css("td.col-xs-4::text, th::text")
        value_el = row.css("td.col-xs-8::text, td:not(.col-xs-4)::text")

        label = label_el.get()
        value = value_el.get()

        if label and value:
            label = label.strip()
            value = value.strip()
            if label and value and len(label) < 200:
                # 规范化为英文字段名
                key = _normalize_spec_key(label)
                specs[key] = value
                # 同时保存原始罗马尼亚语键
                specs[f"spec_{label}"] = value

    return specs


def _normalize_spec_key(ro_key: str) -> str:
    """将罗马尼亚语规格名转为英文/通用键名"""
    ro_lower = ro_key.lower().strip()

    # 常见规格映射
    mapping = {
        "tip": "type",
        "tip mouse": "mouse_type",
        "interfata": "interface",
        "tip senzor": "sensor_type",
        "rezolutie (dpi)": "dpi",
        "rezolutie": "resolution",
        "numar butoane": "button_count",
        "butoane": "buttons",
        "greutate": "weight_g",
        "greutate (g)": "weight_g",
        "dimensiuni": "dimensions",
        "dimensiuni (mm)": "dimensions_mm",
        "lungime cablu": "cable_length",
        "lungime cablu (m)": "cable_length_m",
        "culoare": "color",
        "iluminare": "lighting",
        "iluminare rgb": "rgb_lighting",
        "tip baterie": "battery_type",
        "autonomie": "battery_life",
        "autonomie baterie": "battery_life",
        "senzor": "sensor",
        "senzor optic": "optical_sensor",
        "frecventa": "frequency",
        "rata de refresh": "refresh_rate",
        "acceleratie maxima": "max_acceleration",
        "viteza maxima": "max_speed",
        "durata de viata butoane": "button_lifespan",
        "conectivitate": "connectivity",
        "compatibilitate": "compatibility",
        "sistem de operare": "os_compatibility",
        "brand": "brand",
        "model": "model",
        "garantie": "warranty",
        "greutate fara cablu": "weight_without_cable",
        "alimentare": "power_source",
        "tip switch": "switch_type",
        "material": "material",
        "eroare": "error_rate",
        "distanta de ridicare": "lift_off_distance",
        "procesor": "processor",
        "memorie interna": "internal_memory",
        "profiluri": "profiles",
        "scroll": "scroll_type",
        "tip scroll": "scroll_type",
        "latime": "width_mm",
        "inaltime": "height_mm",
        "adancime": "depth_mm",
        "continut pachet": "package_content",
        "cod": "code",
        "alte caracteristici": "other_features",
        "tipuri de senzori": "sensor_types",
        "rezolutie optica": "optical_resolution",
        "viteza de raspuns": "response_time",
        "format": "format",
        "categorie": "category",
    }

    if ro_lower in mapping:
        return mapping[ro_lower]

    # 通用清理
    key = ro_key.lower()
    key = re.sub(r"[()]", "", key)
    key = re.sub(r"\s+", "_", key)
    key = re.sub(r"[^a-z0-9_]", "", key)
    return key if key else f"spec_{hash(ro_key) % 10000}"


def _parse_description(response: ScraplingResponse) -> str:
    """提取商品描述"""
    # 尝试多个选择器
    for sel in [
        ".product-description",
        "#product-description",
        "[class*=description-body]",
        "[class*=product-desc]",
        "[id*=description]",
    ]:
        desc_els = response.css(sel)
        if desc_els:
            text = desc_els[0].text.strip()
            if len(text) > 20:
                return text[:5000]  # 限制长度
    return ""


def _parse_all_images(response: ScraplingResponse) -> str:
    """提取所有商品图片 URL（管道符分隔）"""
    img_urls = response.css("img[src*='emagst'][src*='/products/']::attr(src)").getall()
    # 去重并过滤缩略图
    unique = []
    seen = set()
    for u in img_urls:
        # 优先保留大图
        clean = re.sub(r"\?width=\d+&height=\d+.*$", "", u)
        if clean not in seen:
            seen.add(clean)
            unique.append(clean)
    return "|".join(unique)


def _parse_seller(response: ScraplingResponse) -> dict:
    """提取卖家信息"""
    info = {
        "seller_name": "",
        "seller_rating": "",
        "seller_positive_pct": "",
        "seller_type": "",  # official / marketplace / third-party
    }

    # 卖家名称
    seller_name_el = response.css(".seller-name::text, [class*=seller-name]::text").get()
    if seller_name_el:
        info["seller_name"] = seller_name_el.strip()

    # 卖家评分
    seller_rating_el = response.css(".seller-rating .fw-bold::text, .seller-rating .text-primary::text").get()
    if seller_rating_el:
        info["seller_rating"] = seller_rating_el.strip()

    # 正面评价比例
    positive_text = response.css("[class*=seller-rating]::text").getall()
    for t in positive_text:
        m = re.search(r"(\d+)%\s*rating", t)
        if m:
            info["seller_positive_pct"] = m.group(1)
            break

    # 卖家类型判断
    if info["seller_name"] == "eMAG":
        info["seller_type"] = "official"
    elif info["seller_name"]:
        info["seller_type"] = "marketplace"

    return info


def _parse_variants(response: ScraplingResponse) -> str:
    """提取商品变体（颜色、尺寸等）"""
    # 检查是否有变体选择器
    variant_els = response.css("[class*=family-option], .js-product-family-variants a")
    variants = []
    for v in variant_els:
        txt = v.text.strip()
        href = v.attrib.get("href", "") if hasattr(v, "attrib") else ""
        if txt:
            variants.append(txt)
            if href:
                variants[-1] += f" ({href})"

    return "|".join(variants) if variants else ""


def _parse_faq_count(response: ScraplingResponse) -> int:
    """统计 FAQ 数量"""
    faq_els = response.css("[class*=qa-item], [class*=question-item], [class*=faq-item]")
    return len(faq_els)


def _parse_shipping(response: ScraplingResponse) -> str:
    """提取配送信息"""
    shipping_els = response.css("[class*=shipping], [class*=delivery], [class*=livrare]::text").getall()
    texts = [s.strip() for s in shipping_els if s.strip() and len(s.strip()) > 3]
    return " | ".join(texts[:5]) if texts else ""


def _parse_warranty(response: ScraplingResponse) -> str:
    """提取保修信息"""
    text = response.css("[class*=warranty]::text, [class*=garantie]::text").get() or ""
    return text.strip()
