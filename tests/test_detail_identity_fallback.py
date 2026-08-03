"""P0-2: 无PNK商品使用URL备用标识参与详情抓取和统计"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from crawler import _detail_identity, _normalize_detail_url


class FakeResponse:
    def __init__(self, html, status=200):
        self.html_content = html
        self.status = status


def _make_valid_detail():
    return {"ld_name": "Test Mouse", "brand": "Logitech", "ld_sku": "ABC123"}


def _setup_checkpoint(tmpdir, completed_pnks, detail_data):
    cp_dir = os.path.join(tmpdir, "checkpoint")
    os.makedirs(cp_dir, exist_ok=True)
    cp_file = os.path.join(cp_dir, "detail_pages.json")
    data = {"completed_pnks": completed_pnks, "detail_data": detail_data}
    with open(cp_file, "w") as f:
        json.dump(data, f)
    return cp_dir


def test_identity_pnk_priority():
    assert _detail_identity({"pnk": "ABC", "url": "https://x.com/a"}) == "ABC"


def test_identity_url_fallback():
    ident = _detail_identity({"url": "https://emag.ro/pd/ABC/"})
    assert "emag.ro/pd/ABC" in ident


def test_identity_empty():
    assert _detail_identity({}) == ""


def test_url_normalization():
    a = _normalize_detail_url("https://EMAG.ro/pd/ABC/?ref=1")
    b = _normalize_detail_url("https://emag.ro/pd/ABC/")
    assert a == b


def test_no_pnk_with_url_success(monkeypatch, tmpdir):
    """无PNK有URL，详情成功 → success=1, complete=True"""
    import crawler
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=[], detail_data={})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)
    monkeypatch.setattr(crawler, "fetch_with_retry", lambda url, **kw: FakeResponse("x" * 6000))
    monkeypatch.setattr(crawler, "parse_detail_page", lambda r, u: _make_valid_detail())

    products = [{"url": "https://emag.ro/pd/ABC/"}]
    _, stats = crawler.crawl_detail_pages(products)
    assert stats["success"] == 1
    assert stats["failed"] == 0
    assert stats["complete"] is True


def test_no_pnk_with_url_fetch_fail(monkeypatch, tmpdir):
    """无PNK有URL，请求失败 → failed=1, complete=False"""
    import crawler
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=[], detail_data={})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)
    monkeypatch.setattr(crawler, "fetch_with_retry", lambda url, **kw: None)

    products = [{"url": "https://emag.ro/pd/ABC/"}]
    _, stats = crawler.crawl_detail_pages(products)
    assert stats["success"] == 0
    assert stats["failed"] == 1
    assert stats["complete"] is False


def test_no_pnk_no_url(monkeypatch, tmpdir):
    """无PNK无URL → failed=1, complete=False, 不发起请求"""
    import crawler
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=[], detail_data={})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)

    called = []
    monkeypatch.setattr(crawler, "fetch_with_retry", lambda url, **kw: called.append(url) or None)

    products = [{"title": "no url no pnk"}]
    _, stats = crawler.crawl_detail_pages(products)
    assert len(called) == 0
    assert stats["success"] == 0
    assert stats["failed"] == 1
    assert stats["complete"] is False


def test_mixed_pnk_and_no_pnk(monkeypatch, tmpdir):
    """PNK商品+无PNKURL商品混合 → stats正确"""
    import crawler
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=[], detail_data={})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)
    monkeypatch.setattr(crawler, "fetch_with_retry", lambda url, **kw: FakeResponse("x" * 6000))
    monkeypatch.setattr(crawler, "parse_detail_page", lambda r, u: _make_valid_detail())

    products = [
        {"pnk": "AAA", "url": "https://emag.ro/pd/AAA/"},
        {"url": "https://emag.ro/pd/BBB/"},
    ]
    _, stats = crawler.crawl_detail_pages(products)
    assert stats["total_products"] == 2
    assert stats["success"] == 2
    assert stats["failed"] == 0
    assert stats["complete"] is True


def test_url_checkpoint_restore(monkeypatch, tmpdir):
    """无PNK商品URL断点恢复 → 第二次不发起网络请求"""
    import crawler
    ident = _normalize_detail_url("https://emag.ro/pd/ABC/")
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=[ident],
                                detail_data={ident: _make_valid_detail()})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)

    called = []
    monkeypatch.setattr(crawler, "fetch_with_retry", lambda url, **kw: called.append(url) or None)

    products = [{"url": "https://emag.ro/pd/ABC/"}]
    _, stats = crawler.crawl_detail_pages(products)
    assert len(called) == 0
    assert stats["success"] == 1
    assert stats["from_checkpoint"] == 1
    assert stats["complete"] is True


def test_no_pnk_invalid_detail(monkeypatch, tmpdir):
    """无PNK有URL，解析无效 → failed=1, complete=False"""
    import crawler
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=[], detail_data={})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)
    monkeypatch.setattr(crawler, "fetch_with_retry", lambda url, **kw: FakeResponse("x" * 6000))
    monkeypatch.setattr(crawler, "parse_detail_page", lambda r, u: {})  # 空dict → 无效

    products = [{"url": "https://emag.ro/pd/ABC/"}]
    _, stats = crawler.crawl_detail_pages(products)
    assert stats["success"] == 0
    assert stats["failed"] == 1
    assert stats["complete"] is False
