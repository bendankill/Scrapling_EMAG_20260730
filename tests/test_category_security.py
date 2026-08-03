"""域名和URL安全验证测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import _is_valid_emag_url, _build_category_infos


def test_valid_www_emag():
    assert _is_valid_emag_url("https://www.emag.ro/mouse/c")


def test_valid_emag():
    assert _is_valid_emag_url("https://emag.ro/mouse/c")


def test_valid_subdomain():
    assert _is_valid_emag_url("https://s13.emag.ro/mouse/c")


def test_reject_evil_emag():
    assert not _is_valid_emag_url("https://evil-emag.ro/mouse/c")


def test_reject_emag_evil_com():
    assert not _is_valid_emag_url("https://www.emag.ro.evil.com/mouse/c")


def test_reject_query_spoof():
    assert not _is_valid_emag_url("https://evil.com/mouse/c?next=emag.ro")


def test_reject_javascript():
    assert not _is_valid_emag_url("javascript:void(0)")


def test_reject_file():
    assert not _is_valid_emag_url("file:///etc/passwd")


def test_reject_department_page():
    assert not _is_valid_emag_url("https://www.emag.ro/laptop/d")


def test_reject_no_c_suffix():
    assert not _is_valid_emag_url("https://www.emag.ro/mouse")


def test_reject_http_only():
    # http 仍然允许但生产建议 https
    assert _is_valid_emag_url("http://www.emag.ro/mouse/c")


class TestBuildCategoryInfos:
    def test_sequential_index(self):
        cats = _build_category_infos([
            "https://www.emag.ro/a/c",
            "https://www.emag.ro/b/c",
            "https://www.emag.ro/c/c"
        ])
        assert [c.index for c in cats] == [1, 2, 3]

    def test_invalid_filtered_index(self):
        cats = _build_category_infos([
            "https://evil-emag.ro/mouse/c",
            "https://www.emag.ro/a/c",
            "https://www.emag.ro/b/c"
        ])
        assert [c.index for c in cats] == [1, 2]

    def test_all_invalid(self):
        cats = _build_category_infos([
            "https://evil-emag.ro/mouse/c",
            "https://www.emag.ro.evil.com/mouse/c",
            "https://evil.com/mouse/c?next=emag.ro"
        ])
        assert len(cats) == 0
