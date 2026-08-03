"""JSON-LD 解析兼容性测试"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parser import _extract_jsonld


class FakeResponse:
    def __init__(self, html):
        self.html_content = html


def test_standard_ld_json():
    html = '''<script type="application/ld+json">
    {"@type":"Product","name":"Test Mouse","sku":"ABC123"}
    </script>'''
    r = _extract_jsonld(FakeResponse(html))
    assert r is not None
    assert r["name"] == "Test Mouse"


def test_extra_attributes():
    html = '''<script type="application/ld+json" id="product-data" data-qa="ld">
    {"@type":"Product","name":"Extra Attr"}
    </script>'''
    r = _extract_jsonld(FakeResponse(html))
    assert r["name"] == "Extra Attr"


def test_whitespace_in_type():
    html = '''<script type = "application/ld+json" >
    {"@type":"Product","name":"Whitespace"}
    </script>'''
    r = _extract_jsonld(FakeResponse(html))
    assert r["name"] == "Whitespace"


def test_single_quotes():
    html = """<script type='application/ld+json'>
    {"@type":"Product","name":"Single Quote"}
    </script>"""
    r = _extract_jsonld(FakeResponse(html))
    assert r["name"] == "Single Quote"


def test_array_format():
    html = '''<script type="application/ld+json">
    [{"@type":"BreadcrumbList"},{"@type":"Product","name":"Array"}]
    </script>'''
    r = _extract_jsonld(FakeResponse(html))
    assert r["name"] == "Array"


def test_graph_structure():
    html = '''<script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[
      {"@type":"WebSite"},
      {"@type":"Product","name":"FromGraph"}
    ]}
    </script>'''
    r = _extract_jsonld(FakeResponse(html))
    assert r["name"] == "FromGraph"


def test_invalid_json_skipped():
    html = '''<script type="application/ld+json">
    {invalid json
    </script>
    <script type="application/ld+json">
    {"@type":"Product","name":"After Invalid"}
    </script>'''
    r = _extract_jsonld(FakeResponse(html))
    assert r["name"] == "After Invalid"


def test_no_product_returns_none():
    html = '''<script type="application/ld+json">
    {"@type":"WebSite","name":"Not Product"}
    </script>'''
    r = _extract_jsonld(FakeResponse(html))
    assert r is None


def test_case_insensitive_type():
    html = '''<script TYPE="application/ld+json">
    {"@type":"Product","name":"Case"}
    </script>'''
    r = _extract_jsonld(FakeResponse(html))
    assert r is not None
