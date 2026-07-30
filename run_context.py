"""
eMAG 爬虫 - 运行上下文管理

每次程序启动时自动创建带时间戳的独立输出目录。
所有模块通过本模块获取统一路径，避免重复拼接。
"""

import os
from datetime import datetime

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class RunContext:
    """每次运行创建一个独立的时间戳目录，集中管理输出路径"""

    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # ---- 运行目录 ----
        self.run_dir = os.path.join(BASE_DIR, "output", self.timestamp)

        # ---- 子目录 ----
        self.images_dir = os.path.join(self.run_dir, "images")
        self.logs_dir = os.path.join(self.run_dir, "logs")

        # ---- 输出文件 ----
        self.csv_file = os.path.join(self.run_dir, "products.csv")
        self.excel_file = os.path.join(self.run_dir, "products.xlsx")
        self.json_file = os.path.join(self.run_dir, "products.json")

        # ---- 创建目录 ----
        for d in [self.run_dir, self.images_dir, self.logs_dir]:
            os.makedirs(d, exist_ok=True)


# 模块级单例：首次 import 时即创建本次运行目录
run = RunContext()
