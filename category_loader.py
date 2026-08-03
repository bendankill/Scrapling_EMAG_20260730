"""
eMAG 爬虫 - 多类目配置加载模块

负责：
1. 读取 config/categories.txt
2. 校验 / 去重 / 清理 URL
3. 从 URL 提取类目路径（用于翻页）
"""

import os
import re
from urllib.parse import urlparse

from logger import logger

# 配置文件路径
CATEGORIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "categories.txt")


class CategoryInfo:
    """单个类目的信息"""
    def __init__(self, url: str, category_path: str, index: int):
        self.url = url                # 完整第一页 URL
        self.category_path = category_path  # 类目路径，如 /mouse
        self.index = index            # 序号（1-based）


def load_categories(filepath: str = None) -> list[CategoryInfo]:
    """
    从配置文件读取类目列表

    参数:
        filepath: 配置文件路径，默认 config/categories.txt

    返回:
        CategoryInfo 列表（已去重、已排序）

    异常:
        FileNotFoundError: 配置文件不存在
        ValueError: 文件为空或无有效 URL
    """
    filepath = filepath or CATEGORIES_FILE

    # ---- 检查文件存在 ----
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"categories.txt not found: {filepath}\n"
            f"请创建 config/categories.txt，每行一个类目 URL"
        )

    # ---- 读取 ----
    with open(filepath, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    # ---- 清理：去空格 / 去空行 / 去重 ----
    seen = set()
    urls = []
    for line in raw_lines:
        url = line.strip()
        if not url:
            continue
        if url.startswith("#"):
            continue  # 支持注释行
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)

    if not urls:
        raise ValueError(
            f"No category URL found in: {filepath}\n"
            f"请添加至少一个类目 URL"
        )

    # ---- 构建 CategoryInfo ----
    categories = []
    for idx, url in enumerate(urls, 1):
        # 验证域名
        if "emag.ro" not in url:
            logger.warning(f"非 eMAG 域名，跳过: {url[:80]}")
            continue
        # 验证路径格式（商品列表页必须以 /c 结尾）
        parsed_path = urlparse(url).path.rstrip("/")
        if not parsed_path.endswith("/c"):
            logger.warning(
                f"URL 路径不以 /c 结尾（非商品列表页），跳过: {url[:80]}\n"
                f"  当前路径: {parsed_path}\n"
                f"  提示: 部门页（/d）和品牌页不受支持，请使用 /c 结尾的商品列表页 URL"
            )
            continue
        cat_path = _extract_category_path(url)
        if not cat_path:
            logger.warning(f"无法从 URL 提取类目路径，跳过: {url}")
            continue
        categories.append(CategoryInfo(url=url, category_path=cat_path, index=idx))

    if not categories:
        raise ValueError("没有有效的类目 URL（需 emag.ro 域名 + /c 商品列表页路径）")

    logger.info(f"已加载 {len(categories)} 个类目")
    for cat in categories:
        logger.info(f"  [{cat.index}] {cat.category_path} → {cat.url[:80]}")

    return categories


def _extract_category_path(url: str) -> str:
    """
    从 eMAG 类目 URL 提取翻页路径

    示例:
        https://www.emag.ro/mouse/c?ref=...  →  /mouse
        https://www.emag.ro/laptop-tablete/c  →  /laptop-tablete
        https://www.emag.ro/ssd/c             →  /ssd
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")  # /mouse/c → /mouse/c

    # 去掉末尾的 /c（类目过滤页标识）
    if path.endswith("/c"):
        path = path[:-2]

    # 去掉可能存在的 /pN 页码
    path = re.sub(r"/p\d+$", "", path)

    if not path or path == "/":
        return ""

    return path
