# Changelog

All notable changes to this project will be documented in this file.

---

## [v1.3] - 2026-03-06

### Added — Deep Analysis Mode
- **🔍 全文抓取**: 使用 `trafilatura` + `BeautifulSoup` 自动爬取新闻原文正文（最多 4000 字/篇），为 AI 提供真正的素材而非仅标题
- **📊 实时市场数据注入**: 分析时自动拉取 SPY/QQQ/DIA/Gold/Oil/BTC/ETH/EUR-USD/USD-JPY/10Y Yield/VIX 的 5 日行情，注入 Gemini prompt
- **🔄 多轮深度分析 (Chain-of-Analysis)**: Round 1 提取结构化事实和数据点 → Round 2 交叉关联 + 注入市场数据生成最终报告
- **📈 历史报告对比**: 自动加载上一期报告摘要注入 prompt，让 AI 识别趋势延续、反转和新风险
- **🔬 Deep Analysis 开关**: 侧边栏新增深度分析模式开关，可独立控制全文抓取和深度分析

### Changed
- `analyzer.py` 完全重构：消除 prompt 三重复制，提取 `_build_news_context`/`_briefing_structure`/`_extract_facts`/`_build_final_prompt` 等共享方法
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
- **⚡ Gemini 流式输出**: 分析报告改用 `generate_content_stream` 流式渲染，用户可实时看到生成过程
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
- Gemini 2.5 Flash AI 分析生成简报（支持中英文、三种长度）
- ElevenLabs TTS 语音播报
- PDF 导出（支持中文字体）
- 历史记录管理（保存/查看/删除）
- Streamlit Web UI + CLI 双入口
