import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from core.data_provider import fetch_ohlcv

CONFIG_PATH = Path(__file__).parent / "config" / "tickers.json"

console = Console()


def load_tickers() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    tickers = []
    for market, roles in data.items():
        for role, info in roles.items():
            tickers.append({"market": market, "role": role, **info})
    return tickers


def main():
    tickers = load_tickers()

    table = Table(title="K-ETF Trend Agent — 최근 5거래일 종가", show_lines=True)
    table.add_column("ETF", style="bold cyan", no_wrap=True)
    table.add_column("티커", style="dim")
    for i in range(5, 0, -1):
        table.add_column(f"D-{i}", justify="right")

    for info in tickers:
        name = info["name"]
        ticker = info["ticker"]
        console.print(f"  조회 중: {name} ({ticker})")
        df = fetch_ohlcv(ticker)
        if df.empty:
            table.add_row(name, ticker, *["N/A"] * 5)
            continue
        last5 = df["종가"].tail(5).tolist()
        while len(last5) < 5:
            last5.insert(0, None)
        cells = [f"{v:,.0f}" if v is not None else "N/A" for v in last5]
        table.add_row(name, ticker, *cells)

    console.print()
    console.print(table)


if __name__ == "__main__":
    main()
