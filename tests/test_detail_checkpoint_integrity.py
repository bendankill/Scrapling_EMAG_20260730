"""P0-1: 无效详情断点重新验证和重新抓取"""
import sys, os, json, tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class FakeResponse:
    def __init__(self, html, status=200):
        self.html_content = html
        self.status = status


def _make_valid_detail():
    return {"ld_name": "Test Mouse", "brand": "Logitech", "ld_sku": "ABC123"}


def _setup_checkpoint(tmpdir, completed_pnks, detail_data):
    """创建临时断点目录和文件"""
    cp_dir = os.path.join(tmpdir, "checkpoint")
    os.makedirs(cp_dir, exist_ok=True)
    cp_file = os.path.join(cp_dir, "detail_pages.json")
    data = {"completed_pnks": completed_pnks, "detail_data": detail_data}
    with open(cp_file, "w") as f:
        json.dump(data, f)
    return cp_dir


def test_stale_completed_without_data(monkeypatch, tmpdir):
    """completed_pnks包含PNK但detail_data无对应数据 → 重新抓取"""
    import crawler
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=["ABC123"], detail_data={})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)

    # Mock网络请求
    called_urls = []
    def fake_fetch(url, **kw):
        called_urls.append(url)
        return FakeResponse("<html>" + "x" * 6000 + "</html>")

    monkeypatch.setattr(crawler, "fetch_with_retry", fake_fetch)
    # Mock parse_detail_page 返回有效详情
    monkeypatch.setattr(crawler, "parse_detail_page",
                        lambda resp, url: _make_valid_detail())

    products = [{"pnk": "ABC123", "url": "https://emag.ro/pd/ABC123/"}]
    result, stats = crawler.crawl_detail_pages(products)

    assert len(called_urls) == 1  # 必须重新请求
    assert stats["success"] == 1
    assert stats["failed"] == 0
    assert stats["complete"] is True


def test_stale_completed_empty_detail(monkeypatch, tmpdir):
    """completed_pnks包含PNK但详情为空字典 → 重新抓取"""
    import crawler
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=["ABC123"],
                                detail_data={"ABC123": {}})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)

    called = []
    monkeypatch.setattr(crawler, "fetch_with_retry", lambda url, **kw: FakeResponse("x" * 6000))
    monkeypatch.setattr(crawler, "parse_detail_page", lambda r, u: _make_valid_detail())

    products = [{"pnk": "ABC123", "url": "https://emag.ro/pd/ABC123/"}]
    _, stats = crawler.crawl_detail_pages(products)
    assert stats["success"] == 1
    assert stats["failed"] == 0
    assert stats["complete"] is True


def test_valid_checkpoint_no_fetch(monkeypatch, tmpdir):
    """有效断点恢复 → 不发起网络请求"""
    import crawler
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=["ABC123"],
                                detail_data={"ABC123": _make_valid_detail()})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)

    called = []
    monkeypatch.setattr(crawler, "fetch_with_retry", lambda url, **kw: called.append(url) or None)

    products = [{"pnk": "ABC123", "url": "https://emag.ro/pd/ABC123/"}]
    _, stats = crawler.crawl_detail_pages(products)
    assert len(called) == 0
    assert stats["success"] == 1
    assert stats["from_checkpoint"] == 1
    assert stats["failed"] == 0
    assert stats["complete"] is True


def test_other_class_pnk_not_inflate(monkeypatch, tmpdir):
    """其他类目PNK不得增加本次成功数"""
    import crawler
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=["OTHER", "ABC123"],
                                detail_data={"OTHER": _make_valid_detail(),
                                             "ABC123": _make_valid_detail()})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)
    monkeypatch.setattr(crawler, "fetch_with_retry", lambda url, **kw: None)

    # 本次只有ABC123
    products = [{"pnk": "ABC123", "url": "https://emag.ro/pd/ABC123/"}]
    _, stats = crawler.crawl_detail_pages(products)
    assert stats["success"] == 1  # ABC123从断点恢复
    assert stats["failed"] == 0
    # OTHER不在本次商品集合中，不影响统计


def test_mixed_valid_and_failed(monkeypatch, tmpdir):
    """一个有效断点 + 一个本次失败 → complete=False"""
    import crawler
    cp_dir = _setup_checkpoint(tmpdir, completed_pnks=["GOOD"],
                                detail_data={"GOOD": _make_valid_detail()})
    monkeypatch.setattr(config, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(config, "CHECKPOINT_DETAIL_PAGES", os.path.join(cp_dir, "detail_pages.json"))
    monkeypatch.setattr(config, "CHECKPOINT_INTERVAL", 999)

    # GOOD从断点恢复，BAD请求第一次成功但详情无效（模拟失败）
    def fake_fetch(url, **kw):
        return FakeResponse("x" * 6000)

    def fake_parse(resp, url):
        if "GOOD" in url:
            return _make_valid_detail()
        return {}  # BAD返回空→_is_detail_valid=False→failed

    monkeypatch.setattr(crawler, "fetch_with_retry", fake_fetch)
    monkeypatch.setattr(crawler, "parse_detail_page", fake_parse)

    products = [
        {"pnk": "GOOD", "url": "https://emag.ro/pd/GOOD/"},
        {"pnk": "BAD", "url": "https://emag.ro/pd/BAD/"},
    ]
    _, stats = crawler.crawl_detail_pages(products)
    assert stats["success"] == 1
    assert stats["failed"] == 1
    assert stats["complete"] is False
