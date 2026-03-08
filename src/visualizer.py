import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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


def fetch_price_data(tickers: list[str], period: str = "1mo") -> pd.DataFrame:
    """
    逐个使用 yf.Ticker().history() 下载收盘价（比 yf.download 更稳定）。
    返回 DataFrame，列名为 ticker，索引为日期。
    """
    print(f"Fetching price data for {len(tickers)} tickers, period={period}...")
    frames = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            if hist.empty:
                print(f"  ⚠ No data for {ticker}")
                continue
            frames[ticker] = hist["Close"]
            print(f"  ✓ {ticker}: {len(hist)} rows")
        except Exception as e:
            print(f"  ✗ {ticker}: {e}")

    if not frames:
        print("Warning: No price data fetched.")
        return pd.DataFrame()

    df = pd.DataFrame(frames)
    print(f"Combined DataFrame shape: {df.shape}")
    return df


def create_price_chart(df: pd.DataFrame, title: str = "Asset Price Trends") -> go.Figure:
    """
    为每个资产创建一个子图，显示归一化百分比变化（相对于起始日）。
    返回 plotly Figure。
    """
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="暂无数据",
            template="plotly_dark",
        )
        return fig

    cols = list(df.columns)
    n = len(cols)
    fig = make_subplots(
        rows=n,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=cols,
    )

    for i, col in enumerate(cols, start=1):
        series = df[col].dropna()
        if series.empty:
            continue
        # 归一化为百分比变化
        pct = (series / series.iloc[0] - 1) * 100
        fig.add_trace(
            go.Scatter(
                x=pct.index,
                y=pct.values,
                mode="lines",
                name=col,
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}%<extra></extra>",
            ),
            row=i,
            col=1,
        )
        fig.update_yaxes(title_text="变化 (%)", row=i, col=1)

    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=max(300 * n, 400),
        showlegend=False,
        margin=dict(l=60, r=30, t=60, b=30),
    )

    return fig


def create_asset_dashboard(
    selected_groups: list[str], period: str = "1mo"
) -> dict[str, go.Figure]:
    """
    为选定的资产类别分别生成图表。
    返回 {类别名: plotly Figure} 字典。
    """
    print(f"Building dashboard for groups: {selected_groups}, period={period}")
    figures = {}
    for group_name in selected_groups:
        assets = ASSET_GROUPS.get(group_name)
        if not assets:
            print(f"Warning: Unknown group '{group_name}', skipping.")
            continue

        tickers = [a["ticker"] for a in assets]
        ticker_to_name = {a["ticker"]: a["name"] for a in assets}

        df = fetch_price_data(tickers, period=period)
        # 将列名从 ticker 替换为可读名称
        df = df.rename(columns=ticker_to_name)

        fig = create_price_chart(df, title=group_name)
        figures[group_name] = fig

    print(f"Dashboard complete: {len(figures)} charts generated.")
    return figures


if __name__ == "__main__":
    # 快速测试：拉取股指数据并输出统计
    df = fetch_price_data(["SPY", "QQQ"], period="5d")
    if not df.empty:
        print(df.head())
        print(df.describe())
    fig = create_price_chart(df, title="Test Chart")
    fig.show()
