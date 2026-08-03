"""字段映射和类目拆分测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from field_mapper import split_category_trail, normalize_product, FIELD_MAP


class TestCategorySplit:
    def test_single_level(self):
        r = split_category_trail("Single")
        assert r == {"一级类": "Single"}

    def test_two_levels_slash(self):
        r = split_category_trail("A/B")
        assert r == {"一级类": "A", "二级类": "B"}

    def test_three_levels(self):
        r = split_category_trail("A/B/C")
        assert r == {"一级类": "A", "二级类": "B", "三级类": "C"}

    def test_five_levels(self):
        r = split_category_trail("A/B/C/D/E")
        assert len(r) == 5
        assert r["五级类"] == "E"

    def test_over_five_truncates(self):
        r = split_category_trail("A/B/C/D/E/F/G")
        assert len(r) == 5
        assert r["五级类"] == "E"

    def test_empty(self):
        assert split_category_trail("") == {}
        assert split_category_trail(None) == {}

    def test_arrow_separator(self):
        r = split_category_trail("A→B→C")
        assert r == {"一级类": "A", "二级类": "B", "三级类": "C"}

    def test_pipe_separator(self):
        r = split_category_trail("A|B")
        assert r == {"一级类": "A", "二级类": "B"}

    def test_mixed_separators(self):
        r = split_category_trail("A/B>C")
        assert r == {"一级类": "A", "二级类": "B", "三级类": "C"}


class TestFieldMap:
    def test_key_mappings(self):
        assert FIELD_MAP["pnk"] == "PNK码"
        assert FIELD_MAP["title"] == "产品标题"
        assert FIELD_MAP["sale_price_ron"] == "前端价格"


class TestNormalizeProduct:
    def test_basic_normalization(self):
        p = {"pnk": "ABC123", "title": "Test Mouse", "sale_price_ron": 45.99,
             "category_trail": "PC/Mouse", "brand": "Logitech",
             "avg_rating": 4.5, "review_count": 100, "product_id": "123"}
        norm = normalize_product(p)
        assert norm["PNK码"] == "ABC123"
        assert norm["产品标题"] == "Test Mouse"
        assert norm["一级类"] == "PC"
        assert norm["二级类"] == "Mouse"
        assert "product_id" in norm  # 兜底保留

    def test_spec_detail_excludes_metadata(self):
        """规格详情不应包含 product_id、currency 等"""
        p = {
            "pnk": "X", "title": "T", "sale_price_ron": 10.0,
            "category_trail": "A/B",
            "product_id": "999", "offer_id": "888",
            "currency": "RON", "is_promo": True,
            "stock_text": "in stoc",
            "type": "Standard",   # ← 这是规格
            "dpi": "1000 dpi",    # ← 这是规格
            "spec_Tip": "Standard",
            "spec_Rezolutie (dpi)": "1000 dpi",
        }
        norm = normalize_product(p)
        spec = norm.get("规格详情", "")
        # 不应包含
        assert "product_id" not in spec
        assert "currency" not in spec
        assert "is_promo" not in spec
        assert "stock_text" not in spec
        # 应包含规格
        assert "Standard" in spec or "Tip" in spec
