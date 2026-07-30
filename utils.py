"""
eMAG 爬虫 - 工具函数
"""

import json
import os
import random
import re
import time
import hashlib
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import config
from logger import logger


# ============================================================
# 随机等待
# ============================================================
def random_sleep(min_sec: float = None, max_sec: float = None, reason: str = "") -> None:
    """随机等待，模拟人类行为"""
    lo = min_sec if min_sec is not None else config.MIN_DELAY
    hi = max_sec if max_sec is not None else config.MAX_DELAY
    seconds = random.uniform(lo, hi)
    if reason:
        logger.debug(f"等待 {seconds:.1f}s - {reason}")
    time.sleep(seconds)


# ============================================================
# User-Agent 轮换
# ============================================================
_ua_lock = threading.Lock()
_ua_index = 0

def get_random_ua() -> str:
    """获取随机 UA，保证线程不重复"""
    global _ua_index
    with _ua_lock:
        ua = config.USER_AGENTS[_ua_index % len(config.USER_AGENTS)]
        _ua_index += 1
    return ua


# ============================================================
# 文件名安全化
# ============================================================
def safe_filename(name: str, max_len: int = 120) -> str:
    """移除文件名中的非法字符"""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > max_len:
        name = name[:max_len]
    return name


# ============================================================
# 图片下载
# ============================================================
def download_image(
    url: str, product_id: str, index: int = 0, fetcher_cls=None
) -> str:
    """下载单张图片，返回本地路径"""
    if not url:
        return ""

    # 去除 URL 参数获得扩展名
    parsed = urlparse(url)
    path = parsed.path
    ext = os.path.splitext(path)[1] or ".jpg"
    if "?" in ext:
        ext = ".jpg"

    local_name = f"{product_id}_{index:03d}{ext}"
    local_path = os.path.join(config.IMAGES_DIR, local_name)

    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return local_path  # 已下载

    try:
        resp = fetcher_cls.get(url, impersonate="chrome", stealthy_headers=True, timeout=20)
        with open(local_path, "wb") as f:
            f.write(resp.body)
        logger.debug(f"图片已下载: {local_name}")
        return local_path
    except Exception as e:
        logger.warning(f"图片下载失败 [{url[:80]}]: {e}")
        return ""


def get_high_res_url(img_url: str) -> str:
    """将缩略图 URL 转为高清 URL"""
    if not img_url:
        return ""
    # 去掉 width/height 参数以获取原图
    high_res = re.sub(r"\?width=\d+&height=\d+.*$", "", img_url)
    return high_res if high_res else img_url


# ============================================================
# 断点续爬
# ============================================================
def save_checkpoint(filepath: str, data: Any) -> None:
    """保存断点数据"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_checkpoint(filepath: str) -> Any:
    """加载断点数据"""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


# ============================================================
# 价格解析
# ============================================================
def parse_price(text: str) -> float | None:
    """解析罗马尼亚价格字符串 -> float
    示例: '45,99 Lei', 'PRP: 69,99 Lei', '45,99'
    """
    if not text:
        return None
    # 移除非数字和逗号/句点
    cleaned = re.sub(r"[^\d,.]", "", text)
    # 如果同时有逗号和句点（如 1,234.56）
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # 罗马尼亚格式: 45,99 -> 45.99
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


# ============================================================
# 从 URL 提取产品 ID
# ============================================================
_PNK_RE = re.compile(r"/pd/([A-Z0-9]+)/")

def extract_pnk_from_url(url: str) -> str:
    """从 /pd/XXXXXX/ 提取产品 PNK"""
    m = _PNK_RE.search(url)
    return m.group(1) if m else ""


# ============================================================
# URL 工具
# ============================================================
def build_list_url(page_num: int) -> str:
    """构建列表页 URL"""
    if page_num <= 1:
        return f"{config.BASE_DOMAIN}{config.CATEGORY_PATH}/c"
    return f"{config.BASE_DOMAIN}{config.CATEGORY_PATH}/p{page_num}/c"


def build_detail_url(pnk: str, slug: str = "product") -> str:
    """构建详情页 URL"""
    return f"{config.BASE_DOMAIN}/{slug}/pd/{pnk}/"


def is_valid_product_url(url: str) -> bool:
    """检查是否为有效产品 URL"""
    return "/pd/" in url and url.startswith("http")
