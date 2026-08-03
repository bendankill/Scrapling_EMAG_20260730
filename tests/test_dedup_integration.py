"""去重集成测试 — 调用生产函数"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import dedup_products, _dedup_key


class TestDedupIntegration:
    def test_pnk_merged(self):
        p1 = {"pnk": "A", "title": "First"}
        p2 = {"pnk": "A", "title": "Second"}
        r, s = dedup_products([p1, p2])
        assert len(r) == 1
        assert r[0]["title"] == "First"
        assert s == 1

    def test_url_merged(self):
        p1 = {"url": "https://emag.ro/pd/A/", "title": "X"}
        p2 = {"url": "https://emag.ro/pd/A/?ref=1", "title": "Y"}
        r, s = dedup_products([p1, p2])
        assert len(r) == 1

    def test_id_merged(self):
        p1 = {"product_id": "123", "offer_id": "456"}
        p2 = {"product_id": "123", "offer_id": "456"}
        r, s = dedup_products([p1, p2])
        assert len(r) == 1

    def test_no_keys_preserved(self):
        """无稳定标识商品各自保留"""
        p1 = {"title": "same"}
        p2 = {"title": "same"}
        r, s = dedup_products([p1, p2])
        assert len(r) == 2
        assert s == 0

    def test_no_keys_different(self):
        p1 = {"title": "A", "price": 10}
        p2 = {"title": "B", "price": 20}
        r, s = dedup_products([p1, p2])
        assert len(r) == 2
        assert s == 0

    def test_order_preserved(self):
        products = [
            {"pnk": "Z"}, {"pnk": "A"}, {"pnk": "Z"}, {"pnk": "B"},
        ]
        r, s = dedup_products(products)
        assert len(r) == 3
        assert r[0]["pnk"] == "Z"
        assert r[1]["pnk"] == "A"
        assert r[2]["pnk"] == "B"
        assert s == 1


class TestDedupKey:
    def test_key_is_none_for_unidentified(self):
        assert _dedup_key({"title": "no id"}) is None

    def test_key_is_stable(self):
        p = {"pnk": "TEST"}
        assert _dedup_key(p) == _dedup_key(p)
        p2 = {"url": "https://x.com/a"}
        assert _dedup_key(p2) == _dedup_key(p2)
