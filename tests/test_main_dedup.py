"""跨类目 PNK 去重测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import dedup_products, _dedup_key


def test_dedup_same_pnk():
    p1 = {"pnk": "DUP", "title": "A"}
    p2 = {"pnk": "DUP", "title": "B"}
    result, skipped = dedup_products([p1, p2])
    assert len(result) == 1
    assert skipped == 1
    assert result[0]["title"] == "A"  # 保留首次


def test_no_duplicate():
    p1 = {"pnk": "A", "title": "X"}
    p2 = {"pnk": "B", "title": "Y"}
    result, skipped = dedup_products([p1, p2])
    assert len(result) == 2
    assert skipped == 0


def test_dedup_by_url():
    p1 = {"url": "https://x.com/pd/A/", "title": "X"}
    p2 = {"url": "https://x.com/pd/A/", "title": "Y"}
    result, skipped = dedup_products([p1, p2])
    assert len(result) == 1
    assert skipped == 1


def test_dedup_by_product_offer_id():
    p1 = {"product_id": "123", "offer_id": "456"}
    p2 = {"product_id": "123", "offer_id": "456"}
    result, skipped = dedup_products([p1, p2])
    assert len(result) == 1


def test_no_pnk_no_url_different():
    p1 = {"title": "Mouse A"}
    p2 = {"title": "Mouse B"}
    result, skipped = dedup_products([p1, p2])
    # 无稳定键时各自保留
    assert len(result) == 2


def test_dedup_key_stability():
    p = {"pnk": "TEST"}
    k1 = _dedup_key(p)
    k2 = _dedup_key(p)
    assert k1 == k2  # 幂等
