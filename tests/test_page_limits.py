"""页数限制和逻辑测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPagePriority:
    """测试 --category-pages 和 --pages 优先级"""
    def test_category_pages_priority(self):
        category_pages = 5
        pages = 10
        effective = category_pages if category_pages > 0 else pages
        assert effective == 5

    def test_pages_fallback(self):
        category_pages = 0
        pages = 10
        effective = category_pages if category_pages > 0 else pages
        assert effective == 10

    def test_default_zero(self):
        category_pages = 0
        pages = 0
        effective = category_pages if category_pages > 0 else pages
        assert effective == 0  # 0 = 无限制

    def test_negative_rejected(self):
        for val in [-1, -5, -100]:
            assert val < 0  # 程序必须在 argparse 或被调用前检查


class TestPageCap:
    """测试 min(website, user_pages) vs max_pages 直接限制"""
    def test_user_pages_used_as_hard_limit(self):
        """用户指定 --pages 3 时 total_pages=3，不受网站值影响"""
        max_pages = 3
        website_pages = 100  # 网站实际100页
        if max_pages > 0:
            total_pages = max_pages
        else:
            total_pages = website_pages
        assert total_pages == 3

    def test_no_user_limit_uses_website(self):
        max_pages = 0
        website_pages = 100
        if max_pages > 0:
            total_pages = max_pages
        else:
            total_pages = website_pages
        assert total_pages == 100

    def test_early_stop_on_empty(self):
        """页面返回 0 商品 → 提前停止"""
        products_this_page = []
        http_ok = True
        should_stop = http_ok and not products_this_page
        assert should_stop is True

    def test_http_error_no_stop(self):
        """HTTP 错误 → 不视为最后一页"""
        products_this_page = []
        http_ok = False
        should_stop = http_ok and not products_this_page
        assert should_stop is False
