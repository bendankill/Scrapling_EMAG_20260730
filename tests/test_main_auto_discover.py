"""auto-discover 流程测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import _build_category_infos


def test_strings_to_category_info():
    urls = ["https://www.emag.ro/mouse/c", "https://www.emag.ro/laptop-tablete/c"]
    cats = _build_category_infos(urls)
    assert len(cats) == 2
    assert cats[0].url == urls[0]
    assert cats[0].category_path == "/mouse"
    assert cats[0].index == 1
    assert cats[1].category_path == "/laptop-tablete"


def test_invalid_url_filtered():
    urls = ["https://www.emag.ro/invalid", "https://www.emag.ro/mouse/c"]
    cats = _build_category_infos(urls)
    # /invalid 不以 /c 结尾 → 被过滤；只保留 mouse/c
    assert len(cats) == 1
    assert cats[0].category_path == "/mouse"


def test_empty_urls():
    cats = _build_category_infos([])
    assert len(cats) == 0
