# eMAG Multi-Category Scraper

基于 [Scrapling](https://github.com/D4Vinci/Scrapling) 的 eMAG 电商爬虫，支持多类目批量采集。

**Current Version: v1.0.2**

## 快速开始

双击激活虚拟环境：

```bash
C:\Users\jac\scrapling-env\activate.bat
```

进入项目，安装依赖：

```bash
cd C:\Users\jac\scrapling-env\Scrapling_EMAG
pip install -r requirements.txt
```

## 常用命令

```bash
# 完整抓取（全部类目，含详情 + 图片）
python main.py

# 先试试抓前 2 页（120 个商品，约 2 分钟）
python main.py --list-only --pages 2

# 抓前 5 页含详情（约 10 分钟）
python main.py --pages 5

# 中断后继续（自动从断点恢复）
python main.py

# 清除断点重新开始
python main.py --reset
```

## 多类目采集

编辑 `config/categories.txt`，每行一个类目 URL：

```
https://www.emag.ro/mouse/c
https://www.emag.ro/laptop-tablete/c
https://www.emag.ro/monitoare/c
https://www.emag.ro/placi-video/c
https://www.emag.ro/ssd/c
```

程序启动后自动依次采集所有类目，无需修改代码。支持注释行（`#` 开头）、空行自动忽略、URL 自动去重。

## 全部参数

| 命令 | 说明 |
|------|------|
| `python main.py` | 完整模式：列表 + 详情 + 图片 |
| `python main.py --list-only` | 仅列表页（快速） |
| `python main.py --pages N` | 每个类目仅抓前 N 页 |
| `python main.py --no-images` | 不下载图片 |
| `python main.py --reset` | 清除断点重新开始 |
| `python main.py --export-only` | 仅导出已有数据 |
| `python main.py --debug` | 调试模式：打印配置后退出 |

## 项目结构

```
Scrapling_EMAG/
├── main.py            # 主程序入口
├── config.py          # 配置文件
├── category_loader.py # 多类目配置加载
├── crawler.py         # 爬取模块（请求+重试+并发）
├── parser.py          # 解析模块（HTML → 结构化数据）
├── save.py            # 保存模块（CSV/Excel/JSON/图片）
├── image_handler.py   # 图库解析 + 下载模块
├── logger.py          # 日志模块
├── utils.py           # 工具函数
├── run_context.py     # 运行目录管理
├── requirements.txt   # 依赖
├── README.md          # 本文档
├── config/
│   └── categories.txt # 类目 URL 配置
├── output/            # 输出（按运行时间分目录）
├── checkpoint/        # 断点数据
└── images/            # （已废弃，图片在 output/<时间>/images/）
```

## 特性

- **多类目采集**：通过配置文件管理，增加类目只需添加一行 URL
- 断点续爬：中断后自动从上次位置继续（按类目隔离）
- 失败重试：自动重试 3 次，指数退避
- 类目容错：某个类目失败不影响其他类目
- 随机延迟：2-5 秒随机等待防封
- UA 轮换：8 个 User-Agent 轮流使用
- 并发控制：列表页顺序，详情页 4 并发
- 自动字段展开：规格参数自动展开为独立列

## 商品图片下载

当前版本支持：

- 自动解析商品详情页图库（`<img>` + `data-src` + JSON-LD 等多源提取）
- 下载全部主页图片（非仅主图）
- 图片编号命名：`{PNK}_{001}.jpg`、`{PNK}_{002}.jpg` ...
- 自动去重（相同图片仅下载一次）
- 高清优先（优先下载无尺寸限制的原图）
- 图片下载失败不影响商品采集

## 抓取策略

1. **列表页**：纯 HTTP 抓取（服务端渲染），CSS 选择器 + data-product JSON
2. **详情页**：纯 HTTP 抓取，JSON-LD 结构化数据 + HTML 规格表
3. eMAG 页面全部为服务端渲染，无需浏览器

## 配置

修改 `config.py`：

- `CONCURRENT_DETAIL`：详情页并发数（默认 4）
- `MIN_DELAY / MAX_DELAY`：请求间隔（默认 2-5 秒）
- `MAX_RETRIES`：最大重试次数（默认 3）
- `CHECKPOINT_INTERVAL`：断点保存间隔

## Version History

| Version | Date | Notes |
|---------|------|-------|
| v1.0.2 | 2026-07-31 | 翻页空页提前退出保护 |
| v1.0.1 | 2026-07-30 | 详情页全图库下载 |
| v1.0   | 2026-07-30 | 首个正式稳定版本 |

详细变更见 [CHANGELOG.md](CHANGELOG.md)。
