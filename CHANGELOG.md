# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

### Fixed (Round 4)

- **详情统计**: crawl_detail_pages 返回 (products, detail_stats)，成功/失败与本次PNK交集
- **详情验证**: _is_detail_valid 检查空HTML/反爬/无产品数据
- **首页失败统计**: 返回完整failed_pages/complete结构
- **退出码**: --pages -1 → 2(BAD_ARGS), 全部详情失败→1, 部分失败→3
- **图片验证**: 已有文件通过签名验证，无效自动删除重建
- **_find_local_images**: 恢复为ImageDownloader实例方法，过滤无效图片
- **URL验证统一**: is_valid_emag_url 放 utils.py, main/category_loader 共用
- **类目编号**: len(result)+1 连续编号，过滤后不跳跃

### Fixed (Round 3)

- **图片下载崩溃**: _find_local_images 从嵌套函数恢复为模块级函数
- **域名安全**: _is_valid_emag_url 严格验证，拒绝伪造域名和 /d 页
- **类目连续编号**: _build_category_infos 使用 len(result)+1
- **去重无hash**: _dedup_key 无稳定标识返回None直接保留
- **export-only共用去重**: do_export_only 调用 dedup_products
- **部分失败统计**: categories_partial + failed_pages + 退出码(0/1/2/3)
- **README完整重写**: 全部参数、退出码、安全规则、验收命令

### Fixed (Round 2)

- auto-discover str→CategoryInfo, --refresh-categories, 跨类目去重
- /d部门页拒绝, pages_crawled统计, HTTP失败vs空页区分
- JPEG/PNG/GIF/WebP签名验证, retry headers, spec_*保留

---

## v1.0.4 (2026-08-03)

### Fixed

- **价格解析**: 正确支持罗马尼亚千位分隔符（`1.234,56`→1234.56）和美式格式（`1,234.56`→1234.56）
- **断点续爬**: 仅 `--reset` 时清除断点，正常运行保留断点支持中断后继续
- **export-only**: 自动发现并合并所有 `list_pages_*.json`，跨类目PNK去重
- **页数参数**: `--category-pages` 优先级高于 `--pages`；用户指定页数不受网站错误总页数影响
- **list-only**: 默认不下载图片，不访问详情页；新增 `--download-list-images` 显式启用
- **导出顺序**: 图片下载 → 生成 image_path/image_count → 再导出 CSV/Excel/JSON
- **Excel类型**: 价格/评分/数量保留数字类型，布尔值保留布尔类型，首行筛选
- **UA轮换**: `get_random_ua()` 生成的UA真正传入请求头
- **HTTP处理**: 非200非重试状态码返回None，不传给解析器
- **规格详情**: 仅包含真实规格字段，排除ID/价格/货币/库存等非规格字段
- **JSON-LD**: 兼容额外属性、空格、单引号、@graph 结构
- **.gitignore**: 正确忽略 `output/`、`checkpoint/` 等嵌套目录

### Added

- 自动化测试 (tests/): 价格解析、字段映射、JSON-LD、断点、页数限制、Excel类型、导出顺序
- CI pipeline (.github/workflows/ci.yml): Python 3.11/3.12, pytest + compileall
- `requirements-dev.txt`

### Changed

- 文档更新至 v1.0.4，命令示例与实际行为一致

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
