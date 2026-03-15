# Changelog

All notable changes to this project will be documented in this file.

---

## [v1.4] - 2026-03-14

### Changed — You.com API 统一 & 全面优化

**🔄 API 统一：完全迁移到 You.com**
- 移除 Gemini API 依赖，分析引擎完全由 You.com Agent API 驱动
- 轻量模式使用 Express Agent（快速响应）
- 深度模式使用 Advanced Agent + ResearchTool（多步推理 + 网络验证）
- 新闻采集改用 You.com News 结果（`results.news`），优先获取结构化新闻数据
- 使用 `Freshness` 枚举替代查询字符串中的时间关键词，提升搜索精度

**⚡ 性能优化**
- 新闻全文抓取改为 `ThreadPoolExecutor` 并行抓取，速度提升 3-5x
- 市场快照改用 `yf.download()` 批量拉取 11 个指标，从 11 次 HTTP 请求减少到 1 次
- TTS 生成前自动清除 Markdown 格式和 Emoji，朗读效果显著改善

**🐛 Bug 修复**
- 修复英文模式 PDF 导出 Emoji 字符崩溃问题（`_strip_emoji()` + `_strip_md()` 增强）
- 修复中文 PDF 字体仅限 Windows 的问题，新增跨平台字体检测（Windows/macOS/Linux）
- 上期报告注入从固定截断 1500 字改为智能提取关键章节（Market Sentinel、Outlook 等）

**🏗️ 架构优化**
- 新增 `src/config.py` 集中管理所有可调常量（VERSION、抓取参数、ticker 列表、新闻源等）
- VERSION 统一到 config.py，消除 app.py 和 main.py 的重复定义
- 移除未使用的 `SECTOR_KEYWORDS` 常量
- 全局 `print()` 替换为 `logging` 模块，支持日志级别控制

**📜 History 增强**
- 新增 `search_runs()` 方法，支持按关键词和日期范围搜索历史记录
- Web UI History 标签页新增搜索/过滤控件

### Dependencies
- 移除 `google-genai`
- `requirements.txt` 全部添加最低版本号锁定

---

## [v1.3] - 2026-03-06

### Added — Deep Analysis Mode
- **🔍 全文抓取**: 使用 `trafilatura` + `BeautifulSoup` 自动爬取新闻原文正文（最多 4000 字/篇），为 AI 提供真正的素材而非仅标题
- **📊 实时市场数据注入**: 分析时自动拉取 SPY/QQQ/DIA/Gold/Oil/BTC/ETH/EUR-USD/USD-JPY/10Y Yield/VIX 的 5 日行情
- **🔄 多轮深度分析 (Chain-of-Analysis)**: Round 1 提取结构化事实和数据点 → Round 2 交叉关联 + 注入市场数据生成最终报告
- **📈 历史报告对比**: 自动加载上一期报告摘要注入 prompt，让 AI 识别趋势延续、反转和新风险
- **🔬 Deep Analysis 开关**: 侧边栏新增深度分析模式开关，可独立控制全文抓取和深度分析

### Changed
- `analyzer.py` 完全重构：消除 prompt 三重复制，提取共享方法
- `main.py` CLI 模式同步支持深度分析流程
- 分析流程从 4 步扩展为 5 步（采集 → 抓取全文 → 加载历史 → 分析 → 导出）

### Dependencies
- 新增 `trafilatura`、`beautifulsoup4`

---

## [v1.2] - 2026-03-05

### Fixed
- **🔧 ElevenLabs 懒加载**: `MediaGenerator` 不再在初始化时创建 ElevenLabs 客户端，仅在实际使用 ElevenLabs 引擎时才加载，避免无 API Key 时报错
- **🔧 asyncio 事件循环兼容**: Edge TTS 使用 `nest_asyncio` 兼容 Streamlit 已有事件循环，修复 `asyncio.run()` 冲突问题
- **🔧 app.py 代码去重**: 提取 `display_result()` 公共函数，消除运行/缓存展示的重复逻辑

### Improved
- **⚡ yfinance 数据缓存**: Market Charts 使用 `st.cache_data(ttl=300)` 缓存 5 分钟，避免频繁切换标签时重复拉取
- **📄 PDF 增强渲染**: 支持编号列表、Markdown 表格、引用块、链接剥离、四级标题
- **📰 多源 RSS 聚合**: RSS 兜底从单一 Yahoo Finance 扩展为 Yahoo + Google News + CNBC + Reuters + Bloomberg，自动去重

### Dependencies
- 新增 `nest-asyncio`

---

## [v1.1] - 2026-02-22

### Added
- **📂 报告板块分类**: 支持按宏观经济、股票个股、大宗商品、虚拟货币、外汇、债券固收等板块组织分析报告
- **🗣️ Edge TTS 中文语音**: 新增 Edge TTS 引擎（免费），提供晓晓、云希、晓悦等高质量中文语音，大幅提升中文播报自然度
- **📈 资产价格可视化**: 新增 Market Charts 标签页，支持查看股指、大宗商品、虚拟货币、外汇、债券等典型资产的价格走势（归一化百分比变化），可选 1 周至 1 年时间范围
- **📋 更新日志**: 新增 CHANGELOG.md，记录版本更新内容

### Changed
- 版本号从 v1.0 升级至 v1.1
- 侧边栏新增 Report Sectors 板块选择器和 TTS Engine 引擎选择器
- 主界面新增 📈 Market Charts 标签页

### Dependencies
- 新增 `edge-tts`、`yfinance`、`plotly`

---

## [v1.0] - 2026-02-17

### Initial Release
- 基于 You.com API + RSS 的新闻采集
- AI 分析生成简报（支持中英文、三种长度）
- ElevenLabs TTS 语音播报
- PDF 导出（支持中文字体）
- 历史记录管理（保存/查看/删除）
- Streamlit Web UI + CLI 双入口
