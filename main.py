import argparse
import json
import logging
import math
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from core.data_provider import fetch_ohlcv
from core.indicators import compute_all_indicators
from core.signal_engine import Signal, generate_signals
from core.portfolio_state import load_state, detect_conflicts, filter_signals

CONFIG_PATH = Path(__file__).parent / "config" / "tickers.json"
STATE_PATH = Path(__file__).parent / "config" / "state.json"
LOGS_DIR = Path(__file__).parent / "logs"

_DAYS = 420
_MIN_ROWS = 100  # minimum rows needed for valid indicator calculation

_KR_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

_SIGNAL_COLOR = {
    Signal.BUY: "bold green",
    Signal.SELL: "bold red",
    Signal.STAY: "yellow",
    Signal.UPGRADE: "bold cyan",
}

_SUPPRESS_REASONS = {
    Signal.BUY: "이미 보유 중 → BUY 억제",
    Signal.SELL: "보유 없음 → SELL 억제",
    Signal.UPGRADE: "1x 미보유 또는 2x 이미 보유 → UPGRADE 억제",
}

# Maps group_key → (1x state_key, 2x state_key) — None if not applicable
_GROUP_HOLDINGS = {
    "kospi.bull": ("KODEX200", "KODEX_LEVERAGE"),
    "kospi.bear": ("KODEX_INVERSE", "KODEX_INVERSE_2X"),
    "nasdaq.bull": ("KODEX_NASDAQ100", "KODEX_NASDAQ100_LEVERAGE"),
    "nasdaq.inverse": (None, "KODEX_NASDAQ100_INVERSE"),
}

# Maps group_key → (1x tickers.json path, 2x tickers.json path) — None if not applicable
_GROUP_TICKER_PATHS = {
    "kospi.bull": (("kospi", "bull_1x"), ("kospi", "bull_2x")),
    "kospi.bear": (("kospi", "bear_1x"), ("kospi", "bear_2x")),
    "nasdaq.bull": (("nasdaq", "bull_1x"), ("nasdaq", "bull_2x")),
    "nasdaq.inverse": (None, ("nasdaq", "bear_2x")),
}

_DEFAULT_STATE = {
    "KODEX200": False, "KODEX_LEVERAGE": False, "KODEX_INVERSE": False,
    "KODEX_INVERSE_2X": False, "KODEX_NASDAQ100": False,
    "KODEX_NASDAQ100_LEVERAGE": False, "KODEX_NASDAQ100_INVERSE": False,
}

console = Console()


def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)
    log_path = LOGS_DIR / f"agent_{datetime.now().strftime('%Y%m%d')}.log"
    logger = logging.getLogger("ketf")
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    return logger


def load_tickers_safe(logger: logging.Logger) -> dict | None:
    """Returns tickers dict from tickers.json, or None on fatal error."""
    if not CONFIG_PATH.exists():
        logger.critical("tickers.json 파일이 없습니다")
        console.print("[bold red]오류: config/tickers.json 파일이 없습니다.[/bold red]")
        return None
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.critical(f"tickers.json 파싱 오류: {e}")
        console.print("[bold red]오류: config/tickers.json 파일을 읽을 수 없습니다.[/bold red]")
        return None


def load_state_safe(logger: logging.Logger) -> dict:
    """Returns state dict. On JSON parse error, logs error and returns default state."""
    try:
        return load_state(str(STATE_PATH))
    except json.JSONDecodeError as e:
        logger.error(f"state.json 파싱 오류: {e}. 기본값 사용")
        return dict(_DEFAULT_STATE)
    except Exception as e:
        logger.error(f"state.json 로드 실패: {e}. 기본값 사용")
        return dict(_DEFAULT_STATE)


def fmt(val, decimals: int = 0) -> str:
    """Format a float with comma separators; returns 'N/A' for NaN or non-numeric values."""
    try:
        f = float(val)
        return "N/A" if math.isnan(f) else f"{f:,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def cloud_symbol(close: float, span_a: float, span_b: float) -> str:
    """Returns rich-markup cloud position symbol: ▲ (above), ▼ (below), ─ (inside)."""
    try:
        if math.isnan(float(span_a)) or math.isnan(float(span_b)):
            return "N/A"
    except (TypeError, ValueError):
        return "N/A"
    if close > span_a and close > span_b:
        return "[green]▲[/green]"
    if close < span_a and close < span_b:
        return "[red]▼[/red]"
    return "[yellow]─[/yellow]"


def resolve_etf_name(group_key: str, signal: Signal, state: dict, tickers: dict) -> str:
    """Returns the specific ETF name for a signal, based on state and group."""
    paths = _GROUP_TICKER_PATHS.get(group_key)
    holdings = _GROUP_HOLDINGS.get(group_key)
    if paths is None or holdings is None:
        return group_key

    path_1x, path_2x = paths
    key_1x, key_2x = holdings

    def name_from_path(path):
        if path is None:
            return None
        market, role = path
        return tickers.get(market, {}).get(role, {}).get("name")

    if signal == Signal.BUY:
        return name_from_path(path_1x) or name_from_path(path_2x) or group_key

    if signal == Signal.UPGRADE:
        return name_from_path(path_2x) or group_key

    if signal in (Signal.SELL, Signal.STAY):
        # Show currently held ETF
        if key_2x and state.get(key_2x):
            name = name_from_path(path_2x)
            if name:
                return name
        if key_1x and state.get(key_1x):
            name = name_from_path(path_1x)
            if name:
                return name
        # Fallback: show 1x name (or 2x if no 1x)
        return name_from_path(path_1x) or name_from_path(path_2x) or group_key

    return group_key


def _print_indicator_tables(etf_list: list, market_data: dict) -> None:
    """Print daily and weekly indicator tables. ETFs missing from market_data show N/A."""
    daily_table = Table(title="일봉 지표 (최신 거래일)", show_lines=True)
    daily_table.add_column("ETF", style="bold cyan", no_wrap=True)
    daily_table.add_column("종가", justify="right")
    daily_table.add_column("MA60", justify="right")
    daily_table.add_column("Span A", justify="right")
    daily_table.add_column("Span B", justify="right")
    daily_table.add_column("ADX", justify="right")
    daily_table.add_column("Cloud", justify="center")

    weekly_table = Table(title="주봉 지표 (최신 주)", show_lines=True)
    weekly_table.add_column("ETF", style="bold cyan", no_wrap=True)
    weekly_table.add_column("주봉종가", justify="right")
    weekly_table.add_column("주봉MA60", justify="right")
    weekly_table.add_column("주봉 Span A", justify="right")
    weekly_table.add_column("주봉 Span B", justify="right")
    weekly_table.add_column("주봉Cloud", justify="center")

    for info in etf_list:
        name = info["name"]
        key = f"{info['market']}.{info['role']}"
        if key not in market_data:
            daily_table.add_row(name, *["N/A"] * 6)
            weekly_table.add_row(name, *["N/A"] * 5)
            continue

        daily, weekly = market_data[key]
        d = daily.iloc[-1]
        w = weekly.iloc[-1]

        daily_table.add_row(
            name,
            fmt(d["종가"]),
            fmt(d["ma_60"]),
            fmt(d["ichimoku_span_a"]),
            fmt(d["ichimoku_span_b"]),
            fmt(d["adx"], 1),
            cloud_symbol(d["종가"], d["ichimoku_span_a"], d["ichimoku_span_b"]),
        )
        weekly_table.add_row(
            name,
            fmt(w["종가"]),
            fmt(w["ma_60"]),
            fmt(w["ichimoku_span_a"]),
            fmt(w["ichimoku_span_b"]),
            cloud_symbol(w["종가"], w["ichimoku_span_a"], w["ichimoku_span_b"]),
        )

    console.print(daily_table)
    console.print()
    console.print(weekly_table)


def main():
    parser = argparse.ArgumentParser(description="K-ETF Trend Rotation Agent")
    parser.add_argument("--detail", action="store_true", help="지표 상세 테이블 출력")
    parser.add_argument("--verbose", action="store_true", help="데이터 조회 및 시그널 필터링 상세 출력")
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("=== K-ETF Trend Rotation Agent 시작 ===")

    # Load config
    tickers_data = load_tickers_safe(logger)
    if tickers_data is None:
        sys.exit(1)

    state = load_state_safe(logger)

    # Build flat list of ETFs: [{market, role, name, ticker}, ...]
    etf_list = []
    for market, roles in tickers_data.items():
        for role, info in roles.items():
            etf_list.append({"market": market, "role": role, **info})

    # Print header
    now = datetime.now()
    weekday_str = _KR_WEEKDAYS[now.weekday()]
    date_str = now.strftime(f"%Y-%m-%d ({weekday_str})")
    separator = "═" * 34
    console.print(separator)
    console.print("K-ETF Trend Rotation Agent")
    console.print(date_str)
    console.print(separator)
    console.print()

    # Fetch data for all ETFs
    market_data = {}
    fetch_status = {}  # for --verbose: {name: (success, row_count)}

    for info in etf_list:
        name = info["name"]
        ticker = info["ticker"]
        key = f"{info['market']}.{info['role']}"
        logger.info(f"데이터 조회: {name} ({ticker})")
        df = fetch_ohlcv(ticker, days=_DAYS, logger=logger)

        if df.empty:
            logger.warning(f"{name} ({ticker}): 데이터 없음, 건너뜀")
            fetch_status[name] = (False, 0)
            continue

        if len(df) < _MIN_ROWS:
            logger.warning(f"{name} ({ticker}): 데이터 부족 ({len(df)}행), 건너뜀")
            fetch_status[name] = (False, len(df))
            continue

        logger.info(f"{name} ({ticker}): {len(df)}행 조회 성공")
        fetch_status[name] = (True, len(df))

        try:
            daily, weekly = compute_all_indicators(df)
            market_data[key] = (daily, weekly)
        except Exception as e:
            logger.error(f"{name} ({ticker}) 지표 계산 실패: {e}")
            fetch_status[name] = (False, len(df))

    if not market_data:
        console.print("[bold red]데이터를 조회할 수 없습니다.[/bold red]")
        logger.error("모든 ETF 데이터 조회 실패")
        sys.exit(1)

    # --verbose: show fetch status
    if args.verbose:
        console.print("[dim]── 데이터 조회 현황 ──[/dim]")
        for info in etf_list:
            name = info["name"]
            ticker = info["ticker"]
            if name in fetch_status:
                success, rows = fetch_status[name]
                if success:
                    console.print(f"[dim]  {name} ({ticker}): 조회 성공 ({rows}행)[/dim]")
                else:
                    console.print(f"[dim]  {name} ({ticker}): [yellow]조회 실패[/yellow][/dim]")
        console.print()

    # Generate signals
    try:
        raw_signals = generate_signals(market_data, state)
        filtered_signals = filter_signals(raw_signals, state)
    except Exception as e:
        logger.error(f"시그널 생성 실패: {e}")
        console.print("[bold red]시그널 생성 중 오류가 발생했습니다.[/bold red]")
        sys.exit(1)

    # Conflict warnings (above signal section)
    conflict_warnings = detect_conflicts(state)
    if conflict_warnings:
        for w in conflict_warnings:
            console.print(f"[bold yellow]{w}[/bold yellow]")
        console.print()

    # --verbose: show suppressed signals
    if args.verbose:
        suppressed = {k: v for k, v in raw_signals.items() if k not in filtered_signals}
        if suppressed:
            console.print("[dim]── 억제된 시그널 ──[/dim]")
            for group_key, sig in suppressed.items():
                etf_name = resolve_etf_name(group_key, sig, state, tickers_data)
                reason = _SUPPRESS_REASONS.get(sig, "억제")
                console.print(f"[dim]  {etf_name}: {sig.value} → {reason}[/dim]")
            console.print()

    # Signal output
    console.print("[bold]\\[시그널][/bold]")
    if filtered_signals:
        for group_key, sig in filtered_signals.items():
            etf_name = resolve_etf_name(group_key, sig, state, tickers_data)
            color = _SIGNAL_COLOR.get(sig, "")
            markup = f"[{color}]{sig.value}[/{color}]" if color else sig.value
            console.print(f"  {etf_name:<30}: {markup}")
            logger.info(f"시그널: {etf_name} → {sig.value}")
    else:
        console.print("  None")
        logger.info("시그널 없음")

    # --detail: show indicator tables
    if args.detail:
        console.print()
        _print_indicator_tables(etf_list, market_data)

    logger.info("=== 완료 ===")


if __name__ == "__main__":
    main()
