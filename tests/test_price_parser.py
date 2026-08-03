"""罗马尼亚价格解析测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import parse_price


class TestParsePrice:
    def test_ro_simple(self):
        assert parse_price("45,99 Lei") == 45.99
        assert parse_price("529,97") == 529.97

    def test_ro_thousands_dot(self):
        assert parse_price("1.234,56 Lei") == 1234.56
        assert parse_price("2.499,90 Lei") == 2499.90

    def test_ro_thousands_space(self):
        assert parse_price("1 234,56 Lei") == 1234.56

    def test_ro_no_thousands(self):
        assert parse_price("1234,56 Lei") == 1234.56

    def test_ro_integer_thousands(self):
        # 1.234 Lei → 罗马尼亚千位分隔符 → 1234
        assert parse_price("1.234 Lei") == 1234.0

    def test_us_format(self):
        assert parse_price("1,234.56") == 1234.56

    def test_empty(self):
        assert parse_price("") is None
        assert parse_price(None) is None

    def test_no_number(self):
        assert parse_price("abc") is None

    def test_prp_prefix(self):
        assert parse_price("PRP: 69,99 Lei") == 69.99

    def test_only_integer(self):
        assert parse_price("529") == 529.0

    def test_ro_small_decimal(self):
        assert parse_price("0,99 Lei") == 0.99
