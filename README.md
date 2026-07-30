# eMAG Mouse Category Scraper

基于 [Scrapling](https://github.com/D4Vinci/Scrapling) 的 eMAG 电商爬虫，抓取鼠标分类全部商品。

## 快速开始

```bash
# 1. 激活虚拟环境
C:\Users\jac\scrapling-env\activate.bat

# 2. 进入项目目录
cd Scrapling_EMAG

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
python main.py
```

## 运行模式

| 命令 | 说明 |
|------|------|
| `python main.py` | 完整模式：列表 + 详情 + 图片 |
| `python main.py --list-only` | 仅列表页（快速，约5分钟） |
| `python main.py --no-images` | 不下载图片 |
| `python main.py --reset` | 清除断点重新开始 |
| `python main.py --export-only` | 仅导出已有数据 |
| `python main.py --pages 10` | 仅抓前10页 |

## 项目结构

```
Scrapling_EMAG/
├── main.py          # 主程序入口
├── config.py        # 配置文件
├── crawler.py       # 爬取模块（请求+重试+并发）
├── parser.py        # 解析模块（HTML → 结构化数据）
├── save.py          # 保存模块（CSV/Excel/JSON/图片）
├── logger.py        # 日志模块
├── utils.py         # 工具函数
├── requirements.txt # 依赖
├── README.md        # 本文档
├── output/          # 输出文件
│   ├── products.csv
│   ├── products.xlsx
│   └── products.json
├── images/          # 商品图片
├── logs/            # 日志
│   ├── crawl.log
│   └── error.log
└── checkpoint/      # 断点数据
```

## 特性

- 断点续爬：中断后自动从上次位置继续
- 失败重试：自动重试 3 次，指数退避
- 随机延迟：2-5 秒随机等待防封
- UA 轮换：8 个 User-Agent 轮流使用
- 并发控制：列表页顺序，详情页 4 并发
- 自动字段展开：规格参数自动展开为独立列

## 抓取策略

1. **列表页**：纯 HTTP 抓取（服务端渲染），CSS 选择器 + data-product JSON
2. **详情页**：纯 HTTP 抓取，JSON-LD 结构化数据 + HTML 规格表
3. eMAG 的鼠标页面全部为服务端渲染，无需浏览器

## 配置

修改 `config.py`：

- `CONCURRENT_DETAIL`：详情页并发数（默认 4）
- `MIN_DELAY / MAX_DELAY`：请求间隔（默认 2-5 秒）
- `MAX_RETRIES`：最大重试次数（默认 3）
- `CHECKPOINT_INTERVAL`：断点保存间隔
