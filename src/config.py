"""
集中管理项目配置常量。
所有可调参数统一在此维护，各模块通过 from src.config import ... 引用。
"""

VERSION = "v1.5"

# ──────────────────── 抓取参数 ────────────────────
MAX_SCRAPE_CHARS = 4000       # 每篇文章最大抓取字符数
MAX_SCRAPE_ARTICLES = 10      # 单次最多抓取文章数
SCRAPE_TIMEOUT = 10           # 抓取超时（秒）
SCRAPE_WORKERS = 5            # 并行抓取线程数

# ──────────────────── 新闻源 ────────────────────
AVAILABLE_SOURCES = [
    "Bloomberg", "Reuters", "AP News", "Yahoo Finance",
    "CNBC", "Financial Times", "Wall Street Journal",
]

SOURCE_DOMAINS = {
    "Bloomberg": "bloomberg.com",
    "Reuters": "reuters.com",
    "AP News": "apnews.com",
    "Yahoo Finance": "finance.yahoo.com",
    "CNBC": "cnbc.com",
    "Financial Times": "ft.com",
    "Wall Street Journal": "wsj.com",
}

RSS_FEEDS = [
    {"url": "https://finance.yahoo.com/news/rssindex", "source": "Yahoo Finance"},
    {"url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en", "source": "Google News (Business)"},
    {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "source": "CNBC"},
    {"url": "https://feeds.reuters.com/reuters/businessNews", "source": "Reuters"},
    {"url": "https://feeds.bloomberg.com/markets/news.rss", "source": "Bloomberg"},
]

# ──────────────────── 报告板块 ────────────────────
REPORT_SECTORS = {
    "宏观经济 Macro": "macro",
    "股票个股 Stocks": "stocks",
    "大宗商品 Commodities": "commodities",
    "虚拟货币 Crypto": "crypto",
    "外汇 Forex": "forex",
    "债券固收 Bonds": "bonds",
}

# ──────────────────── 市场快照 ────────────────────
SNAPSHOT_TICKERS = {
    "S&P 500 (SPY)": "SPY",
    "Nasdaq 100 (QQQ)": "QQQ",
    "Dow Jones (DIA)": "DIA",
    "Gold": "GC=F",
    "Crude Oil (WTI)": "CL=F",
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "US 10Y Yield": "^TNX",
    "VIX": "^VIX",
}

# ──────────────────── 上期报告注入 ────────────────────
PREVIOUS_REPORT_MAX_CHARS = 2000   # 注入上期报告的最大字符数
PREVIOUS_REPORT_MAX_AGE_HOURS = 72  # 上期报告最大有效时间（小时），超过则不对比

# ──────────────────── 新闻去重 ────────────────────
DEDUP_SIMILARITY_THRESHOLD = 0.65  # 标题相似度阈值，超过则视为重复

# ──────────────────── 市场快照 time_range 映射 ────────────────────
TIME_RANGE_PERIOD_MAP = {
    "24h": "1d",
    "week": "5d",
    "month": "1mo",
}

# ──────────────────── TTS ────────────────────
TTS_MAX_CHARS_PER_CHUNK = 4800     # ElevenLabs 单次调用最大字符数
EDGE_TTS_MAX_CHARS_PER_CHUNK = 50000  # Edge TTS 单次最大字符数

# ──────────────────── 历史记录容量管理 ────────────────────
HISTORY_MAX_RUNS = 50              # 最多保留的历史记录数
HISTORY_MAX_AGE_DAYS = 90          # 超过此天数的记录自动清理

# ──────────────────── 市场情绪分析 ────────────────────
SENTIMENT_ASSETS = {
    # ── 股指：按地区 ──
    "🇺🇸 美股 US Equities": {
        "S&P 500":      {"ticker": "SPY",       "sector": "stocks"},
        "Nasdaq 100":   {"ticker": "QQQ",       "sector": "stocks"},
        "Dow Jones":    {"ticker": "DIA",       "sector": "stocks"},
        "Russell 2000": {"ticker": "IWM",       "sector": "stocks"},
    },
    "🇨🇳 A股 China A-Shares": {
        "沪深300 CSI 300":  {"ticker": "000300.SS", "sector": "stocks"},
        "上证指数 SSE":      {"ticker": "000001.SS", "sector": "stocks"},
        "创业板 ChiNext":    {"ticker": "399006.SZ", "sector": "stocks"},
    },
    "🇭🇰 港股 Hong Kong": {
        "恒生指数 HSI":      {"ticker": "^HSI",      "sector": "stocks"},
        "恒生科技 HSTECH":   {"ticker": "^HSTECH",   "sector": "stocks"},
    },
    "🇪🇺 欧洲 Europe": {
        "EURO STOXX 50": {"ticker": "^STOXX50E", "sector": "stocks"},
        "DAX (Germany)": {"ticker": "^GDAXI",    "sector": "stocks"},
        "FTSE 100 (UK)": {"ticker": "^FTSE",     "sector": "stocks"},
        "CAC 40 (France)": {"ticker": "^FCHI",   "sector": "stocks"},
    },
    "🇯🇵🇰🇷 日韩 Japan & Korea": {
        "日经225 Nikkei":    {"ticker": "^N225",  "sector": "stocks"},
        "KOSPI (Korea)":     {"ticker": "^KS11",  "sector": "stocks"},
    },
    "🌏 其他 Emerging & APAC": {
        "SENSEX (India)":    {"ticker": "^BSESN",  "sector": "stocks"},
        "NIFTY 50 (India)":  {"ticker": "^NSEI",   "sector": "stocks"},
        "ASX 200 (Australia)": {"ticker": "^AXJO", "sector": "stocks"},
        "Bovespa (Brazil)":  {"ticker": "^BVSP",   "sector": "stocks"},
        "台湾加权 TWSE":      {"ticker": "^TWII",   "sector": "stocks"},
    },
    # ── 大宗商品 ──
    "⛽ 能源 Energy": {
        "Crude Oil WTI":  {"ticker": "CL=F",   "sector": "commodities"},
        "Brent Crude":    {"ticker": "BZ=F",   "sector": "commodities"},
        "Natural Gas":    {"ticker": "NG=F",   "sector": "commodities"},
    },
    "🥇 贵金属 & 工业金属 Metals": {
        "Gold":      {"ticker": "GC=F",  "sector": "commodities"},
        "Silver":    {"ticker": "SI=F",  "sector": "commodities"},
        "Copper":    {"ticker": "HG=F",  "sector": "commodities"},
        "Platinum":  {"ticker": "PL=F",  "sector": "commodities"},
    },
    "🌾 农产品 Agriculture": {
        "Wheat":    {"ticker": "ZW=F",  "sector": "commodities"},
        "Corn":     {"ticker": "ZC=F",  "sector": "commodities"},
        "Soybean":  {"ticker": "ZS=F",  "sector": "commodities"},
    },
    # ── 加密货币 ──
    "₿ 加密货币 Crypto": {
        "Bitcoin":   {"ticker": "BTC-USD",  "sector": "crypto"},
        "Ethereum":  {"ticker": "ETH-USD",  "sector": "crypto"},
        "Solana":    {"ticker": "SOL-USD",  "sector": "crypto"},
        "BNB":       {"ticker": "BNB-USD",  "sector": "crypto"},
        "XRP":       {"ticker": "XRP-USD",  "sector": "crypto"},
    },
    # ── 外汇 ──
    "💱 外汇 Forex": {
        "DXY (USD Index)": {"ticker": "DX-Y.NYB",  "sector": "forex"},
        "EUR/USD":    {"ticker": "EURUSD=X",  "sector": "forex"},
        "GBP/USD":    {"ticker": "GBPUSD=X",  "sector": "forex"},
        "USD/JPY":    {"ticker": "JPY=X",     "sector": "forex"},
        "USD/CNY":    {"ticker": "CNY=X",     "sector": "forex"},
        "AUD/USD":    {"ticker": "AUDUSD=X",  "sector": "forex"},
        "USD/CHF":    {"ticker": "CHFUSD=X",  "sector": "forex"},
        "NZD/USD":    {"ticker": "NZDUSD=X",  "sector": "forex"},
    },
    # ── 债券 ──
    "🏛️ 债券 Bonds": {
        "US 10Y Yield":  {"ticker": "^TNX",  "sector": "bonds"},
        "US 2Y Yield":   {"ticker": "^IRX",  "sector": "bonds"},
        "US 30Y Yield":  {"ticker": "^TYX",  "sector": "bonds"},
        "TLT (20Y+ Bond ETF)": {"ticker": "TLT", "sector": "bonds"},
    },
    # ── 波动率 ──
    "📉 波动率 Volatility": {
        "VIX (S&P 500)": {"ticker": "^VIX",   "sector": "volatility"},
    },
}

# 情绪分级阈值
SENTIMENT_THRESHOLDS = {
    "strong_bull": 0.6,    # ≥ 0.6 → 强看多
    "bull": 0.2,           # ≥ 0.2 → 看多
    "neutral_upper": 0.2,  # (-0.2, 0.2) → 中性
    "bear": -0.2,          # ≤ -0.2 → 看空
    "strong_bear": -0.6,   # ≤ -0.6 → 强看空
}

# VIX 情绪等级
VIX_LEVELS = {
    "low": 15,       # < 15: 贪婪/低波动
    "normal": 20,    # 15-20: 正常
    "elevated": 25,  # 20-25: 警惕
    "high": 30,      # 25-30: 恐惧
    # > 30: 极度恐惧
}
