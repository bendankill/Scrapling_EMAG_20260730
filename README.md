# eMAG Multi-Category Scraper

基于 [Scrapling](https://github.com/D4Vinci/Scrapling) 的 eMAG 电商爬虫，支持多类目批量采集。

## 快速开始

```bash
# 1. 激活虚拟环境
C:\Users\jac\scrapling-env\activate.bat

# 2. 进入项目目录
cd Scrapling_EMAG

# 3. 安装依赖
pip install -r requirements.txt

# 4. 编辑类目配置
notepad config/categories.txt

# 5. 运行
python main.py
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

## 运行模式

| 命令 | 说明 |
|------|------|
| `python main.py` | 完整模式：列表 + 详情 + 图片 |
| `python main.py --list-only` | 仅列表页（快速） |
| `python main.py --no-images` | 不下载图片 |
| `python main.py --reset` | 清除断点重新开始 |
| `python main.py --export-only` | 仅导出已有数据 |
| `python main.py --pages 10` | 每个类目仅抓前10页 |
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
