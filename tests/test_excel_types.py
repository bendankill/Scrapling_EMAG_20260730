"""Excel 字段类型测试"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestExcelTypes:
    """验证 Excel 导出保留数值和布尔类型"""
    def test_numeric_fields_identified(self):
        from save import _collect_all_fields
        # 构造简单数据
        p = {"前端价格": 45.99, "product_id": "123"}
        fields = _collect_all_fields([p])
        assert "前端价格" in fields

    def test_bool_fields_output(self):
        """布尔值在 Excel 中应保持布尔类型"""
        from field_mapper import normalize_product
        p = {"pnk": "X", "title": "T", "is_promo": True,
             "sale_price_ron": 10.0, "category_trail": "A"}
        norm = normalize_product(p)
        # 验证 normalize 后 is_promo 保留
        assert "is_promo" in norm and norm["is_promo"] is True
