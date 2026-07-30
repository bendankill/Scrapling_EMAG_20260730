"""
eMAG 爬虫 - 配置文件
"""

import os

# ============================================================
# 项目路径
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
CHECKPOINT_DIR = os.path.join(BASE_DIR, "checkpoint")
SPEED_DIR = os.path.join(BASE_DIR, "speed_mode")

# 确保目录存在
for d in [OUTPUT_DIR, IMAGES_DIR, LOGS_DIR, CHECKPOINT_DIR, SPEED_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# 目标 URL
# ============================================================
START_URL = "https://www.emag.ro/mouse/c?ref=hp_menu_quick-nav_23_22&type=category"
BASE_DOMAIN = "https://www.emag.ro"

# 分页格式: /mouse/p{N}/c  (N >= 2, 第一页无 p1)
CATEGORY_PATH = "/mouse"

# ============================================================
# 抓取策略
# ============================================================

# 抓取模式: "http" | "browser" | "auto"
# "http"  - 纯 HTTP，最快，适合服务端渲染页面
# "browser" - 浏览器模式，适合 JS 渲染页面
# "auto" - 自动判断（当前 emag 详情页用 http 即可）
FETCH_MODE = "http"

# 是否抓取详情页（数据量大，约 13918 个商品）
FETCH_DETAILS = True

# 是否下载图片
DOWNLOAD_IMAGES = True

# 并发数（同时抓取的页面数）
CONCURRENT_LIST = 2     # 列表页并发
CONCURRENT_DETAIL = 4   # 详情页并发
CONCURRENT_IMAGE = 8    # 图片下载并发

# 请求间隔（秒）- 随机在此范围内
MIN_DELAY = 2.0
MAX_DELAY = 5.0

# 详情页请求间隔（秒）- 比列表页更保守
MIN_DETAIL_DELAY = 1.5
MAX_DETAIL_DELAY = 4.0

# ============================================================
# 重试与容错
# ============================================================
MAX_RETRIES = 3             # 最大重试次数
RETRY_BACKOFF = 5           # 重试退避基础秒数
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]  # 触发重试的状态码

# ============================================================
# 断点续爬
# ============================================================
CHECKPOINT_LIST_PAGES = os.path.join(CHECKPOINT_DIR, "list_pages.json")
CHECKPOINT_DETAIL_PAGES = os.path.join(CHECKPOINT_DIR, "detail_pages.json")
CHECKPOINT_INTERVAL = 5  # 每抓取 N 个商品保存一次断点

# ============================================================
# User-Agent 轮换池
# ============================================================
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
]

# ============================================================
# 输出文件
# ============================================================
CSV_FILE = os.path.join(OUTPUT_DIR, "products.csv")
EXCEL_FILE = os.path.join(OUTPUT_DIR, "products.xlsx")
JSON_FILE = os.path.join(OUTPUT_DIR, "products.json")

# ============================================================
# Scrapling Fetcher 参数
# ============================================================
FETCHER_KWARGS = {
    "impersonate": "chrome",
    "stealthy_headers": True,
    "timeout": 30,
}
