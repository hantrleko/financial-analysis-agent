# 🏦 Automated Financial Analysis System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)](https://streamlit.io)
[![Version](https://img.shields.io/badge/version-v1.8-green.svg)](CHANGELOG.md)

AI 驱动的自动化金融分析系统，集成多源新闻采集、双引擎 LLM 分析、市场情绪评估、语音播报和 PDF 导出。

An AI-powered automated financial analysis system with multi-source news aggregation, dual LLM engine analysis, market sentiment assessment, TTS audio briefings, and PDF export.

---

## ✨ Features

### 📰 Multi-Source News Aggregation
- **RSS Feeds**: Yahoo Finance, CNBC, Bloomberg, MarketWatch, BBC Business, NYT Business, 新浪财经, 财联社, 东方财富
- **Google News**: Dynamic search with customizable queries and time ranges (EN + CN)
- **Gemini Search Grounding**: AI-powered web search for the latest financial news

### 🤖 Dual LLM Engine
- **Gemini 2.5 Flash** (default) — Fast, high quality, free tier available
- **ZhiPu GLM-4-Flash** — Free, auto-fallback when Gemini is unavailable
- True streaming output via SSE (`streamGenerateContent`)
- Customizable Gemini model via sidebar or `GEMINI_MODEL` env var
- Automatic retry with exponential backoff for API calls

### 🧭 Market Sentiment Analysis
- Multi-factor scoring model across **13 sectors, 48 assets**
- Five factors: Daily change (30%) + 5D momentum (25%) + 20D trend (20%) + MA20 position (15%) + Volume ratio (10%)
- VIX fear/greed indicator with inverse scoring
- Opportunity & risk detection

### 📊 Interactive Charts
- Asset price trends with normalized % change comparison
- Support for indices, commodities, crypto, forex, bonds
- Configurable time range (1W to 1Y)

### 🔊 Audio & PDF Export
- **ElevenLabs TTS**: Premium voices for English and Chinese
- **Edge TTS** (Free): High-quality Chinese voices (晓晓, 云希, 晓悦)
- **PDF Export**: Full report with CJK font support, tables, lists, headings

### 📰 Newspaper Layout
- Classic newspaper-style presentation with masthead, headlines, dual-column layout
- Markdown → HTML parser with pullquotes, section titles, ordered/unordered lists

### 🌐 Bilingual (i18n)
- Full English and Chinese support (~100 translation keys)
- Language switcher in sidebar, instant switch

### 📜 History Management
- Auto-save analysis runs with full metadata
- Search by keyword and date range
- Auto-cleanup (max 50 runs / 90 days)

---

## 🏗️ Architecture

```
app.py              → Streamlit Web UI (main entry)
main.py             → CLI entry point
src/
├── config.py       → Centralized configuration constants
├── utils.py        → Shared utilities (API key, proxy, retry)
├── pipeline.py     → Unified analysis pipeline
├── collector.py    → News collection (RSS, Google News, Gemini Search)
├── analyzer.py     → LLM analysis engine (Gemini + ZhiPu)
├── sentiment.py    → Market sentiment multi-factor scoring
├── visualizer.py   → Price chart generation (Plotly)
├── media_gen.py    → TTS audio + PDF export
├── history.py      → Run history management
└── newspaper.py    → Newspaper layout renderer
tests/              → Unit tests (pytest)
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- API keys (at least one):
  - `GEMINI_API_KEY` — Google Gemini API
  - `ZHIPU_API_KEY` — ZhiPu GLM API
  - `ELEVENLABS_API_KEY` — ElevenLabs TTS (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/hantrleko/financial-analysis-agent.git
cd financial-analysis-agent

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env  # Edit with your API keys
```

### Run Web UI (Streamlit)

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

### Run CLI

```bash
python main.py
```

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes* | Google Gemini API key |
| `ZHIPU_API_KEY` | Yes* | ZhiPu GLM-4 API key |
| `ELEVENLABS_API_KEY` | No | ElevenLabs TTS API key |
| `GEMINI_PROXY` | No | HTTP proxy for Gemini API calls |
| `GEMINI_MODEL` | No | Override default Gemini model (e.g. `gemini-2.0-flash`) |
| `ACCESS_PASSWORD` | No | Password protection for Web UI |

\* At least one LLM API key is required.

API keys can also be configured via Streamlit secrets (`.streamlit/secrets.toml`).

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_analyzer.py -v
```

---

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

## 📄 License

This project is for educational and research purposes.
