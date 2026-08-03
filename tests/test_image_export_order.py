"""图片先于导出的顺序测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestImageExportOrder:
    """验证图片下载在导出之前完成"""
    def test_image_path_in_export(self):
        """模拟: 先设置 image_path 再 normalize → 字段应存在"""
        from field_mapper import normalize_product
        p = {
            "pnk": "X", "title": "T", "sale_price_ron": 10.0,
            "category_trail": "A/B",
            "image_path": "/path/to/img.jpg",
            "image_count": 5,
        }
        norm = normalize_product(p)
        assert "image_path" in norm
        assert "image_count" in norm
        assert norm["image_count"] == 5

    def test_image_count_not_lost(self):
        """下载后 image_count 应在导出中"""
        from field_mapper import normalize_product
        p = {
            "pnk": "X", "title": "T", "sale_price_ron": 10.0,
            "category_trail": "A",
            "image_path": "",
            "image_count": 0,
        }
        norm = normalize_product(p)
        assert norm["image_count"] == 0  # 0 也应保留
