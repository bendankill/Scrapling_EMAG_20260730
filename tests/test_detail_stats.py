"""详情统计测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler import _is_detail_valid


class TestDetailValidation:
    def test_valid_detail(self):
        d = {"ld_name": "Mouse", "brand": "Logitech", "ld_sku": "ABC"}
        assert _is_detail_valid(d) is True

    def test_empty_dict_invalid(self):
        assert _is_detail_valid({}) is False

    def test_none_invalid(self):
        assert _is_detail_valid(None) is False

    def test_captcha_html_invalid(self):
        class FakeResp:
            html_content = "<html>captcha</html>" * 10
        assert _is_detail_valid({"_detail_url": "x"}, FakeResp()) is False

    def test_no_content_invalid(self):
        assert _is_detail_valid({"_detail_url": "x", "warranty": ""}) is False


class FakeResp:
    def __init__(self, html):
        self.html_content = html

def test_valid_detail_with_resp():
    d = {"ld_name": "Mouse", "brand": "Logitech"}
    resp = FakeResp("<html>" + "x" * 6000 + "</html>")
    assert _is_detail_valid(d, resp) is True
