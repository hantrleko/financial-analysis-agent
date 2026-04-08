from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

logger = logging.getLogger(__name__)

# 资产分组：类别名 -> ticker 列表
ASSET_GROUPS = {
    "股指 (Indices)": [
        {"ticker": "SPY", "name": "S&P 500 (SPY)"},
        {"ticker": "QQQ", "name": "Nasdaq 100 (QQQ)"},
        {"ticker": "000300.SS", "name": "沪深300"},
    ],
    "大宗商品 (Commodities)": [
        {"ticker": "GC=F", "name": "Gold"},
        {"ticker": "CL=F", "name": "Crude Oil"},
        {"ticker": "SI=F", "name": "Silver"},
    ],
    "虚拟货币 (Crypto)": [
        {"ticker": "BTC-USD", "name": "Bitcoin"},
        {"ticker": "ETH-USD", "name": "Ethereum"},
    ],
    "外汇 (Forex)": [
        {"ticker": "EURUSD=X", "name": "EUR/USD"},
        {"ticker": "JPY=X", "name": "USD/JPY"},
        {"ticker": "CNY=X", "name": "USD/CNY"},
    ],
    "债券 (Bonds)": [
        {"ticker": "^TNX", "name": "US 10Y Treasury Yield"},
    ],
}


def fetch_price_data(
    tickers: list[str],
    period: str = "1mo",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """
    逐个使用 yf.Ticker().history() 下载收盘价。
    支持 period 或 start/end 自定义日期范围。
    """
    logger.info("Fetching price data for %d tickers, period=%s start=%s end=%s",
                len(tickers), period, start, end)
    frames: dict[str, pd.Series] = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            if start and end:
                hist = t.history(start=start, end=end)
            else:
                hist = t.history(period=period)
            if hist.empty:
                logger.warning("  ⚠ No data for %s", ticker)
                continue
            frames[ticker] = hist["Close"]
            logger.info("  ✓ %s: %d rows", ticker, len(hist))
        except Exception as e:
            logger.warning("  ✗ %s: %s", ticker, e)

    if not frames:
        logger.warning("No price data fetched.")
        return pd.DataFrame()

    df = pd.DataFrame(frames)
    logger.info("Combined DataFrame shape: %s", df.shape)
    return df


def fetch_ohlcv_data(
    ticker: str,
    period: str = "1mo",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Fetch OHLCV data for a single ticker (for candlestick charts)."""
    try:
        t = yf.Ticker(ticker)
        if start and end:
            hist = t.history(start=start, end=end)
        else:
            hist = t.history(period=period)
        return hist
    except Exception as e:
        logger.warning("Failed to fetch OHLCV for %s: %s", ticker, e)
        return pd.DataFrame()


def create_price_chart(df: pd.DataFrame, title: str = "Asset Price Trends") -> go.Figure:
    fig = go.Figure()

    if df.empty:
        fig.update_layout(title="暂无数据", template="plotly_dark")
        return fig

    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            continue
        pct = (series / series.iloc[0] - 1) * 100
        fig.add_trace(
            go.Scatter(
                x=pct.index,
                y=pct.values,
                mode="lines",
                name=col,
                hovertemplate="%{x|%Y-%m-%d}<br>" + col + ": %{y:.2f}%<extra></extra>",
            )
        )

    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=400,
        showlegend=True,
        yaxis_title="Change (%)",
        margin=dict(l=60, r=30, t=60, b=30),
    )
    return fig


def create_candlestick_chart(
    ohlcv: pd.DataFrame, title: str = "Candlestick Chart",
) -> go.Figure:
    """Create a candlestick (K-line) chart from OHLCV data."""
    fig = go.Figure()
    if ohlcv.empty:
        fig.update_layout(title="暂无数据", template="plotly_dark")
        return fig

    fig.add_trace(go.Candlestick(
        x=ohlcv.index,
        open=ohlcv["Open"],
        high=ohlcv["High"],
        low=ohlcv["Low"],
        close=ohlcv["Close"],
        increasing_line_color="#22c55e",
        decreasing_line_color="#ef4444",
        name="Price",
    ))

    # Add MA20 overlay
    if len(ohlcv) >= 20:
        ma20 = ohlcv["Close"].rolling(window=20).mean()
        fig.add_trace(go.Scatter(
            x=ohlcv.index, y=ma20, mode="lines",
            name="MA20", line=dict(color="#60a5fa", width=1.5),
        ))

    # Add volume as bar chart on secondary y-axis
    if "Volume" in ohlcv.columns:
        colors = [
            "#22c55e" if c >= o else "#ef4444"
            for c, o in zip(ohlcv["Close"], ohlcv["Open"])
        ]
        fig.add_trace(go.Bar(
            x=ohlcv.index, y=ohlcv["Volume"], name="Volume",
            marker_color=colors, opacity=0.4, yaxis="y2",
        ))

    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=500,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        yaxis=dict(title="Price", side="left"),
        yaxis2=dict(title="Volume", side="right", overlaying="y",
                    showgrid=False, range=[0, ohlcv.get("Volume", pd.Series([1])).max() * 4]),
        margin=dict(l=60, r=60, t=60, b=30),
    )
    return fig


def create_correlation_matrix(
    tickers: list[str],
    names: list[str],
    period: str = "3mo",
) -> go.Figure:
    """Create a correlation heatmap for the given assets."""
    df = fetch_price_data(tickers, period=period)
    if df.empty or len(df.columns) < 2:
        fig = go.Figure()
        fig.update_layout(title="数据不足", template="plotly_dark")
        return fig

    # Map ticker columns to display names
    name_map = dict(zip(tickers, names))
    df = df.rename(columns=name_map)

    returns = df.pct_change().dropna()
    corr = returns.corr()

    fig = go.Figure(data=go.Heatmap(
        z=np.round(corr.values, 2),
        x=corr.columns.tolist(),
        y=corr.index.tolist(),
        colorscale="RdBu_r",
        zmin=-1, zmax=1,
        text=np.round(corr.values, 2),
        texttemplate="%{text}",
        textfont={"size": 11},
        hovertemplate="%{x} vs %{y}: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="Asset Correlation Matrix",
        template="plotly_dark",
        height=500,
        margin=dict(l=100, r=30, t=60, b=100),
    )
    return fig


def create_asset_dashboard(
    selected_groups: list[str],
    period: str = "1mo",
    chart_type: str = "line",
    start: str | None = None,
    end: str | None = None,
) -> dict[str, go.Figure]:
    """
    为选定的资产类别分别生成图表。
    chart_type: 'line' 折线图 | 'candlestick' K线图
    """
    logger.info("Building dashboard for groups: %s, period=%s, type=%s",
                selected_groups, period, chart_type)
    figures: dict[str, go.Figure] = {}
    for group_name in selected_groups:
        assets = ASSET_GROUPS.get(group_name)
        if not assets:
            logger.warning("Unknown group '%s', skipping.", group_name)
            continue

        tickers = [a["ticker"] for a in assets]
        ticker_to_name = {a["ticker"]: a["name"] for a in assets}

        if chart_type == "candlestick":
            # Candlestick: one chart per ticker in group
            for asset in assets:
                ohlcv = fetch_ohlcv_data(asset["ticker"], period=period,
                                         start=start, end=end)
                fig = create_candlestick_chart(
                    ohlcv, title=f"{group_name} — {asset['name']}",
                )
                figures[f"{group_name} — {asset['name']}"] = fig
        else:
            df = fetch_price_data(tickers, period=period, start=start, end=end)
            df = df.rename(columns=ticker_to_name)
            fig = create_price_chart(df, title=group_name)
            figures[group_name] = fig

    logger.info("Dashboard complete: %d charts generated.", len(figures))
    return figures


if __name__ == "__main__":
    # 快速测试：拉取股指数据并输出统计
    df = fetch_price_data(["SPY", "QQQ"], period="5d")
    if not df.empty:
        logger.info("Head:\n%s", df.head())
        logger.info("Describe:\n%s", df.describe())
    fig = create_price_chart(df, title="Test Chart")
    fig.show()
