# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## v1.0.3 (2026-07-31)

### Added

- 输出数据结构规范化：中文字段名（PNK码/产品标题/前端价格等）
- 类目自动拆分：`category_trail` → 一级类~五级类
- 多分隔符兼容：`/ > >> | \ →`
- `field_mapper.py`：字段映射/类目拆分/排序 统一模块
- `category_discovery.py`：eMAG 全站类目自动发现
- `--auto-discover` 模式
- 每类目独立页数限制 + PNK 跨类目去重
- 首页 HTML 调试保存 (`logs/page1.html`)

### Fixed

- P0：`all_products.extend()` 重复执行导致商品数翻倍
- P0：断点泄露导致跨运行继承分页状态
- P0：网站总页数解析错误导致 `--pages N` 被截断
- P0：`min(website, max_pages)` 在网站显示 2 页时截断用户指定的 3 页
- meta 解析多选择器兜底 + 统计信息与实际采集一致

### Changed

- JSON/CSV/Excel 三种导出字段顺序完全一致
- 翻页上限：`--pages N` 优先，网站总页数仅作兜底
- 每页日志格式：`Page N | Parsed: X | Running Total: Y`

---

## v1.0.2 (2026-07-31)

### Fixed

- 翻页循环增加空页提前退出：`parse_list_page_meta` 解析失败（总页数=0）导致降级为 500 页上限时，若当前页无商品则自动 `break`，避免数千次无效请求

---

## v1.0.1 (2026-07-30)

### Changed

- 详情页图片下载从仅主图改为全部图库图片
- 新增 `image_handler.py`：`ImageGalleryParser` + `ImageDownloader`
- 图库多源提取：`<img>` 标签 + `data-src` 懒加载 + `<a>` 大图链接
- 高清优先策略：原图（无 `width=` 参数）> 大尺寸 > 缩略图
- CSV 新增 `image_count` 字段
- 图片下载逻辑收敛到 `ImageDownloader`，代码量净减 37 行

---

## v1.0 (2026-07-30)

### Added

- 多类目采集：通过 `config/categories.txt` 配置多个 eMAG 类目 URL
- 类目配置自动去重、注释行支持、空行忽略
- 单个类目异常不影响后续类目的容错机制
- 输出目录按运行时间自动归档 (`output/<YYYYMMDD_HHMMSS>/`)
- 所有输出（CSV / Excel / JSON / 图片 / 日志）统一归档到运行目录
- `RunContext` 统一输出路径管理模块
- `CategoryLoader` 多类目配置加载模块
- `--debug` 调试模式（打印配置后退出）
- `--pages N` 页面数量限制（在爬取阶段即实现，非事后截断）
- CHANGELOG.md

### Changed

- 类目 URL 从硬编码改为 `config/categories.txt` 配置文件驱动
- `build_list_url()` 接受动态 `category_path` 参数
- 断点按类目隔离存储 (`checkpoint/list_pages_{category}.json`)
- `crawl_list_pages()` 签名变更：接受 `start_url` + `category_path`
- 输出目录结构从扁平改为按运行时间分目录
- 日志优化：增加类目级别追踪日志

### Fixed

- `--pages` 参数未在爬取阶段生效的 Bug（现在在 `crawl_list_pages` 内部钳制翻页上限）
- 价格解析：`45,99 Lei` 格式（含 `<sup>` 标签的整数+小数分离）正确拼接
- PRP 价格提取选择器修正
- 评论文本正则跨语言兼容
