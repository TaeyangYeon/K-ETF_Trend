import json
import math
from pathlib import Path

from rich.console import Console
from rich.table import Table

from core.data_provider import fetch_ohlcv
from core.indicators import compute_all_indicators
from core.signal_engine import Signal, generate_signals

CONFIG_PATH = Path(__file__).parent / "config" / "tickers.json"
STATE_PATH = Path(__file__).parent / "config" / "state.json"
console = Console()

# Weekly Span B needs 52+26 weekly rows to be non-NaN on the last bar.
# 420 trading days ≈ 84 weeks, giving span_b_raw at week 57 (> 52). ✓
_DAYS = 420

_SIGNAL_GROUP_LABELS = {
    "kospi.bull": "KODEX 200 / 레버리지",
    "kospi.bear": "KODEX 인버스 / 인버스2X",
    "nasdaq.bull": "KODEX 나스닥100 / 레버리지",
    "nasdaq.inverse": "KODEX 나스닥100인버스",
}

_SIGNAL_MARKUP = {
    Signal.BUY: "[bold green]BUY[/bold green]",
    Signal.SELL: "[bold red]SELL[/bold red]",
    Signal.STAY: "[yellow]STAY[/yellow]",
    Signal.UPGRADE: "[bold cyan]UPGRADE[/bold cyan]",
    Signal.NONE: "None",
}


def load_tickers() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    tickers = []
    for market, roles in data.items():
        for role, info in roles.items():
            tickers.append({"market": market, "role": role, **info})
    return tickers


def load_state() -> dict:
    with open(STATE_PATH, encoding="utf-8") as f:
        return json.load(f)


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
    state = load_state()

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

    market_data = {}

    for info in tickers:
        name = info["name"]
        ticker = info["ticker"]
        key = f"{info['market']}.{info['role']}"
        console.print(f"  조회 중: {name} ({ticker})")
        df = fetch_ohlcv(ticker, days=_DAYS)
        if df.empty:
            daily_table.add_row(name, *["N/A"] * 6)
            weekly_table.add_row(name, *["N/A"] * 5)
            continue

        daily, weekly = compute_all_indicators(df)
        market_data[key] = (daily, weekly)

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

    signals = generate_signals(market_data, state)

    signal_table = Table(title="매매 시그널", show_lines=True)
    signal_table.add_column("그룹", style="bold cyan", no_wrap=True)
    signal_table.add_column("시그널", justify="center")

    if signals:
        for group_key, sig in signals.items():
            label = _SIGNAL_GROUP_LABELS.get(group_key, group_key)
            markup = _SIGNAL_MARKUP.get(sig, sig.value)
            signal_table.add_row(label, markup)
    else:
        signal_table.add_row("전체", "None")

    console.print()
    console.print(signal_table)


if __name__ == "__main__":
    main()
