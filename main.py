import json
import math
from pathlib import Path

from rich.console import Console
from rich.table import Table

from core.data_provider import fetch_ohlcv
from core.indicators import compute_all_indicators

CONFIG_PATH = Path(__file__).parent / "config" / "tickers.json"
console = Console()

# Weekly Span B needs 52+26 weekly rows to be non-NaN on the last bar.
# 420 trading days ≈ 84 weeks, giving span_b_raw at week 57 (> 52). ✓
_DAYS = 420


def load_tickers() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    tickers = []
    for market, roles in data.items():
        for role, info in roles.items():
            tickers.append({"market": market, "role": role, **info})
    return tickers


def fmt(val, decimals: int = 0) -> str:
    try:
        f = float(val)
        return "N/A" if math.isnan(f) else f"{f:,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def cloud_pos(close: float, span_a: float, span_b: float) -> str:
    try:
        if math.isnan(float(span_a)) or math.isnan(float(span_b)):
            return "N/A"
    except (TypeError, ValueError):
        return "N/A"
    if close > span_a and close > span_b:
        return "[green]위[/green]"
    if close < span_a and close < span_b:
        return "[red]아래[/red]"
    return "[yellow]안[/yellow]"


def main():
    tickers = load_tickers()

    daily_table = Table(title="일봉 지표 (최신 거래일)", show_lines=True)
    daily_table.add_column("ETF", style="bold cyan", no_wrap=True)
    daily_table.add_column("종가", justify="right")
    daily_table.add_column("MA60", justify="right")
    daily_table.add_column("스팬A", justify="right")
    daily_table.add_column("스팬B", justify="right")
    daily_table.add_column("ADX", justify="right")
    daily_table.add_column("구름", justify="center")

    weekly_table = Table(title="주봉 지표 (최신 주)", show_lines=True)
    weekly_table.add_column("ETF", style="bold cyan", no_wrap=True)
    weekly_table.add_column("주봉 종가", justify="right")
    weekly_table.add_column("주봉 MA60", justify="right")
    weekly_table.add_column("주봉 스팬A", justify="right")
    weekly_table.add_column("주봉 스팬B", justify="right")
    weekly_table.add_column("구름", justify="center")

    for info in tickers:
        name = info["name"]
        ticker = info["ticker"]
        console.print(f"  조회 중: {name} ({ticker})")
        df = fetch_ohlcv(ticker, days=_DAYS)
        if df.empty:
            daily_table.add_row(name, *["N/A"] * 6)
            weekly_table.add_row(name, *["N/A"] * 5)
            continue

        daily, weekly = compute_all_indicators(df)
        d = daily.iloc[-1]
        w = weekly.iloc[-1]

        daily_table.add_row(
            name,
            fmt(d["종가"]),
            fmt(d["ma_60"]),
            fmt(d["ichimoku_span_a"]),
            fmt(d["ichimoku_span_b"]),
            fmt(d["adx"], 1),
            cloud_pos(d["종가"], d["ichimoku_span_a"], d["ichimoku_span_b"]),
        )
        weekly_table.add_row(
            name,
            fmt(w["종가"]),
            fmt(w["ma_60"]),
            fmt(w["ichimoku_span_a"]),
            fmt(w["ichimoku_span_b"]),
            cloud_pos(w["종가"], w["ichimoku_span_a"], w["ichimoku_span_b"]),
        )

    console.print()
    console.print(daily_table)
    console.print()
    console.print(weekly_table)


if __name__ == "__main__":
    main()
