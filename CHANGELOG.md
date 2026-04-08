# Changelog

All notable changes to this project will be documented in this file.

---

## [v1.9] - 2026-04-08

### Added — 交互层面全面优化

**📦 模块化拆分 (优化 2.1)**
- 新增 `src/i18n.py` — 提取 I18N 翻译字典（~200 行）和 `t()` / `sig_label()` / `vix_label()` 函数
- 新增 `src/styles.py` — 提取全部 CSS 样式（~390 行）+ `inject_styles()` 注入函数
- 新增 `src/components/newspaper_view.py` — 提取报纸版面渲染逻辑
- 新增 `src/components/sentiment_dashboard.py` — 提取市场情绪仪表盘
- 新增 `src/components/charts_view.py` — 提取行情图表组件（含懒加载）
- 新增 `src/components/history_view.py` — 提取历史记录组件（含 ZIP 导出 & 报告对比）
- `app.py` 从 1349 行精简至 ~536 行

**📊 分析进度指示器 (优化 2.2)**
- 新增 `st.progress()` 进度条，展示 5 步分析流程完成百分比
- 新增步骤药丸条（Step Pills）：✅ 已完成 / ⏳ 进行中 / 待处理，CSS 动画过渡
- 每个步骤实时更新当前状态文字

**🎛️ 侧边栏分组 & 预设模式 (优化 2.3)**
- 侧边栏控件按「基础设置」和「高级设置」分组，高级设置默认折叠
- 新增 3 个一键预设模式：
  - ⚡ 快速简报 — 3 篇文章，短报告，无音频/PDF
  - 🔬 深度报告 — 10 篇文章，全功能开启，报纸版面
  - 🇨🇳 A 股聚焦 — 8 篇文章，中文财经源优先
- 🔧 自定义模式保留完整手动控制

**🔄 情绪/图表懒加载 (优化 2.4)**
- 情绪分析和行情图表不再自动加载数据
- 新增「刷新数据」按钮 + 上次更新时间显示
- 用户自主决定何时刷新，减少不必要的 API 调用

**📦 历史导出 & 报告对比 (优化 2.5)**
- 新增批量 ZIP 导出功能 — 将所有报告（含 report.md / metadata.json / PDF / MP3）打包下载
- 新增两期报告对比视图 — 基于 unified diff 的绿增红删高亮
- 历史记录列表增加搜索、日期过滤、单条删除

**📱 移动端适配 CSS (优化 2.7)**
- `@media (max-width: 768px)` — 报纸单栏、Metric 卡片紧凑、进度条竖排
- `@media (max-width: 480px)` — 报头缩小、副标题堆叠

### Changed
- 版本号从 v1.8 升级至 v1.9
- `app.py` 重构 — 从单文件 1349 行拆分为 7 个模块
- 所有 UI 文本通过 `src/i18n.py` 统一管理

### Dependencies
- 无新增依赖

---

## [v1.8] - 2026-04-08

### Added
- **🔧 公共工具模块 (`src/utils.py`)**
  - 提取 `get_api_key()` / `get_proxy()` 公共函数，消除 collector.py 与 analyzer.py 中的重复代码
  - 新增 `retry_api_call()` — 带指数退避的 API 调用重试机制，区分可重试错误（429、5xx、timeout）和不可重试错误（401、403）

- **⚡ Gemini 真正流式输出 (`src/analyzer.py`)**
  - 新增 `_call_gemini_stream()` 方法，使用 `streamGenerateContent?alt=sse` 端点实现真正的 SSE 流式输出
  - 新增 `_call_openai_compat_stream()` 方法，智谱 GLM 也支持流式输出
  - `analyze_news_stream()` 现在逐块 yield 文本，Web UI 实时渲染每一个 token

- **🇨🇳 中文财经 RSS 源 (`src/config.py`)**
  - 新增新浪财经、财联社 (Cls.cn)、东方财富 (Eastmoney) RSS 源
  - 新增中文 Google News RSS 模板 (`GOOGLE_NEWS_CN_RSS_TEMPLATE`)

- **🤖 Gemini 模型自定义 (`app.py`, `src/analyzer.py`)**
  - 侧边栏新增 Gemini Model 下拉选择器，支持 gemini-2.5-flash / 2.0-flash / 1.5-pro 等多个模型
  - 支持通过 `GEMINI_MODEL` 环境变量覆盖默认模型

- **🔁 分析流水线 (`src/pipeline.py`)**
  - 新增统一分析流水线模块，消除 `main.py` 和 `app.py` 之间的核心逻辑重复
  - `PipelineConfig` 数据类集中管理所有分析参数
  - `run_pipeline()` 函数封装完整 5 步流程：采集 → 抓取 → 分析 → 媒体生成 → 保存历史

- **✅ 扩充单元测试 (`tests/`)**
  - 新增 `test_analyzer.py` — 分析器核心逻辑、LLM 回退机制测试
  - 新增 `test_sentiment.py` — 情绪评分模型、VIX 分类、反向评分测试
  - 新增 `test_media_gen.py` — TTS 文本清洗、分段、Emoji 剥离测试
  - 新增 `test_visualizer.py` — 图表生成、资产分组配置测试
  - 新增 `test_utils.py` — API Key 获取、代理配置、重试机制测试
  - 新增 `test_pipeline.py` — 流水线配置数据类测试

- **📖 README.md**
  - 新增完整项目文档：功能特性、架构说明、快速开始、环境变量、目录结构

### Changed
- **`main.py` 重构** — 全部 `print()` 替换为 `logger`，使用 `pipeline.run_pipeline()` 统一流程
- **API 调用增加重试** — collector.py 和 analyzer.py 中的所有外部 API 调用均通过 `retry_api_call()` 包装
- 版本号从 v1.7 升级至 v1.8

### Dependencies
- 无新增依赖

---

## [v1.7] - 2026-03-18

### Fixed
- **📰 新闻来源筛选真正生效 (`src/collector.py`)**
  - 修复侧边栏 `News Sources` 选择不影响采集结果的问题
  - RSS 聚合新增来源过滤逻辑，支持匹配扩展源名（如 `CNBC (Markets)` 归属 `CNBC`）

- **📜 历史记录 ID 冲突修复 (`src/history.py`)**
  - `run_id` 从秒级升级为微秒级时间戳
  - 新增目录冲突兜底后缀，避免同秒并发触发时覆盖历史结果

- **🔐 报纸版面渲染安全加固 (`app.py`)**
  - 报纸模式内联 Markdown 渲染前统一做 HTML 转义
  - 保留 Markdown 强调样式的同时，防止动态文本注入 HTML

### Added
- **✅ 核心回归测试 (`tests/`)**
  - 新增 `collector` 来源过滤测试
  - 新增 `history` 唯一 run_id 测试与保存加载回归测试
  - 新增报纸渲染内联格式安全转义测试

---

## [v1.6] - 2026-03-16

### Changed — 双引擎架构 & 全免费运行

**🤖 双 LLM 引擎 (`src/analyzer.py`, `src/config.py`)**
- 彻底移除 You.com Agent / Groq / DeepSeek 依赖，仅保留两个引擎：
  - **智谱 GLM-4-Flash** — 免费，日常分析默认引擎
  - **Gemini 2.0 Flash** — 免费，深度分析自动切换
- 开启「🔬 深度分析」时自动升级为 Gemini；普通模式用 GLM-4-Flash
- 侧边栏新增「🤖 LLM Engine」引擎选择器，支持手动切换
- API Key 支持 `.env` 和 Streamlit Secrets 双渠道读取

**📡 新闻采集简化 (`src/collector.py`)**
- 移除 You.com Search，新闻采集统一走 RSS（完全免费）
- 删除 `youdotcom` SDK 依赖，`requirements.txt` 瘦身

**🔒 安全**
- `.streamlit/secrets.toml` 加入 `.gitignore`，API Key 不会泄露到 GitHub

---

## [v1.5] - 2026-03-16

### Added — 市场情绪分析 & 报纸版面 & 全站双语

**🧭 市场情绪分析模块 (`src/sentiment.py`)**
- 新增多因子情绪评分引擎，覆盖全球 **13 个板块、48 个资产**
- 五因子评分模型：日涨跌 (30%) + 5 日动量 (25%) + 20 日趋势 (20%) + MA20 位置 (15%) + 量比 (10%)
- VIX 反向指标特殊处理，高 VIX 额外压低整体情绪
- 自动识别 💰 机会资产（score ≥ 0.2）和 ⚠️ 风险资产（score ≤ -0.2）
- 覆盖市场：美股、A 股、港股、欧洲、日韩、新兴市场、能源、贵金属、农产品、加密货币、外汇、债券、波动率
- Web UI 新增 🧭 Market Sentiment 标签页：总览指标卡、多空比例条、机会/风险双栏卡片、板块 Expander 数据表

**📰 报纸版面模式**
- 深度分析下可选「📰 Newspaper Layout / 报纸版面」复选框
- 经典报纸排版：羊皮纸底色、衬线字体、报头 (masthead)、头条大标题、副标题自动提取、双栏 CSS 排版、引用框、双线分隔、页脚声明
- Markdown → 报纸 HTML 解析器：支持标题层级、有序/无序列表、引用块、行内格式

**🌐 全站中英双语 (i18n)**
- 新建 I18N 翻译系统（~100 个 key），`t(key)` 函数自动切换语言
- 语言选择器提升到侧边栏最顶部，切换即时生效
- 所有 UI 文本双语化：侧边栏、4 个标签页、所有 spinner/提示/表头/按钮
- `sentiment.py` 的 SIGNAL_LABEL / VIX_EMOJI 按语言分组

**🎨 UI 美化**
- 自定义 CSS：Metric 卡片深色渐变 + 圆角阴影、侧边栏暗色渐变背景、Tab 加粗字号、Expander 圆角边框
- 情绪条绿/灰/红渐变 + 圆角阴影
- 资产卡片暗色组件，悬停高亮，涨跌色标
- Run Analysis 按钮 `primary` 类型突出 + `use_container_width` 全宽

### Changed — 功能逻辑优化 (12 项)

**📰 新闻采集 (`collector.py`)**
- 标题去重改为 `SequenceMatcher` 模糊匹配 (阈值 0.65) + URL 联合去重
- RSS 回退路径增加 `time_range` 时间过滤（`parsedate_to_datetime` 解析 RSS 日期）
- 移除类内重复的 `AVAILABLE_SOURCES`，统一使用 config 定义

**🧠 分析引擎 (`analyzer.py`)**
- 市场快照根据 `time_range` 动态调整 yfinance period（24h→1d, week→5d, month→1mo）
- 上期报告增加时间有效性校验（超过 72 小时不对比）
- `_summarize_previous_report` 新增中文标题关键词匹配（市场哨兵、展望、关键驱动等）
- 轻量模式也注入市场数据和历史报告（解耦深度分析）

**📊 可视化 (`visualizer.py`)**
- 同类资产归一化曲线合并到单张图上对比显示
- 全部 `print()` 替换为 `logging`

**🔊 音频 (`media_gen.py`)**
- TTS 长文本自动按段落分段拼接（ElevenLabs 4800 字/块，Edge TTS 50000 字/块）
- Edge TTS asyncio 改用 `loop.run_until_complete()` 避免多余循环

**📜 历史 (`history.py`)**
- 修复 `date_to` 当天记录被排除的边界 bug（时分秒自动补 23:59:59）
- 新增 `cleanup()` 自动容量管理（最多 50 条 / 90 天），每次 save_run 后自动触发

### Dependencies
- 无新增依赖

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
