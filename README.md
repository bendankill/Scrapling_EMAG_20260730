# eMAG Multi-Category Scraper v1.0.4

基于 [Scrapling](https://github.com/D4Vinci/Scrapling) 的 eMAG 电商爬虫，支持多类目批量采集。

**Current Version: v1.0.4**

## 快速开始

```bash
call C:\Users\jac\scrapling-env\activate.bat
cd /d C:\Users\jac\scrapling-env\Scrapling_EMAG
pip install -r requirements.txt
```

## 全部参数

| 参数 | 说明 |
|------|------|
| `--list-only` | 仅抓列表页并导出。默认不访问详情页、不下载图片 |
| `--reset` | 清除所有断点重新开始 |
| `--export-only` | 仅从已有断点导出数据，不发起任何网络请求 |
| `--no-images` | 所有模式下不下载图片 |
| `--download-list-images` | `--list-only` 模式下也下载列表页缩略图 |
| `--pages N` | 每个类目抓取 N 页 |
| `--category-pages N` | 每个类目抓取 N 页（优先级高于 `--pages`） |
| `--auto-discover` | 从 eMAG 首页导航自动发现类目 |
| `--refresh-categories` | 忽略类目缓存，重新扫描首页导航 |
| `--debug` | 打印配置后退出，不发起采集 |

## 行为说明

### 页数控制
- 普通模式未指定 `--pages` 时，根据网站总页数自动抓取所有页
- 自动发现模式未指定页数时，默认每类目 10 页（安全上限）
- `--category-pages` > `--pages` > 默认值

### 断点续爬
- 不带 `--reset` 运行：尝试恢复上次断点继续采集
- `--reset`：删除所有断点，完全重新开始
- `--export-only`：不清除断点，不访问网络

### list-only
- 默认不访问商品详情页
- 默认不下载图片（使用 `--download-list-images` 显式启用）
- 仅导出列表页数据

### 域名安全
- 只接受 `emag.ro` 及 `*.emag.ro` 合法子域名
- 拒绝 `evil-emag.ro`、`emag.ro.evil.com` 等伪造域名
- 拒绝 `/d` 部门页（仅支持 `/c` 商品列表页）

### 退出码
| 码 | 含义 |
|----|------|
| 0 | 完全成功 |
| 1 | 一般失败（无数据/全部失败） |
| 2 | 参数错误 |
| 3 | 部分完成（存在失败页或部分类目失败） |

### 反爬处理
- HTTP 403、429、500-504 自动重试 3 次（指数退避）
- HTTP 511/WAF/Captcha 视为请求失败，不误判为正常空页
- 失败页计入 `failed_pages`，最终报告显示部分完成

## 输出目录

每次运行自动创建时间戳目录：

```
output/<YYYYMMDD_HHMMSS>/
├── products.csv
├── products.xlsx
├── products.json
├── images/
│   └── {PNK}_{001}.jpg ...
└── logs/
    ├── crawl.log
    ├── error.log
    └── network_debug.log
```

## 用户验收命令

```bat
REM 最快一页列表测试
python main.py --reset --list-only --pages 1

REM 两页列表验收
python main.py --reset --list-only --pages 2

REM 两页完整模式（含详情，不含图片）
python main.py --reset --pages 2 --no-images

REM 断点续爬（先 Ctrl+C 中断，再不带 reset 重运行）
python main.py --reset --pages 5 --no-images
REM ↑ 按 Ctrl+C
python main.py --pages 5 --no-images

REM 仅导出断点
python main.py --export-only --no-images

REM 自动发现
python main.py --reset --auto-discover --refresh-categories --category-pages 1 --list-only
```

## Version History

| Version | Date | Notes |
|---------|------|-------|
| v1.0.4 | 2026-08-03 | 数据完整性修复 + 退出码 + 域名安全 + 自动化测试 |
| v1.0.3 | 2026-07-31 | 数据结构规范化 + P0 分页修复 |
| v1.0.2 | 2026-07-31 | 翻页空页提前退出 |
| v1.0.1 | 2026-07-30 | 详情页全图库下载 |
| v1.0   | 2026-07-30 | 首个正式稳定版本 |

详细变更见 [CHANGELOG.md](CHANGELOG.md)。
