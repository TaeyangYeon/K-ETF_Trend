import json
from pathlib import Path

from core.signal_engine import Signal

STATE_TICKER_MAP = {
    "KODEX200": ("kospi", "bull_1x"),
    "KODEX_LEVERAGE": ("kospi", "bull_2x"),
    "KODEX_INVERSE": ("kospi", "bear_1x"),
    "KODEX_INVERSE_2X": ("kospi", "bear_2x"),
    "KODEX_NASDAQ100": ("nasdaq", "bull_1x"),
    "KODEX_NASDAQ100_LEVERAGE": ("nasdaq", "bull_2x"),
    "KODEX_NASDAQ100_INVERSE": ("nasdaq", "bear_2x"),
}

_DEFAULT_STATE = {k: False for k in STATE_TICKER_MAP}

# Maps signal group key → (1x state key or None, 2x state key or None)
_GROUP_HOLDINGS: dict[str, tuple[str | None, str | None]] = {
    "kospi.bull": ("KODEX200", "KODEX_LEVERAGE"),
    "kospi.bear": ("KODEX_INVERSE", "KODEX_INVERSE_2X"),
    "nasdaq.bull": ("KODEX_NASDAQ100", "KODEX_NASDAQ100_LEVERAGE"),
    "nasdaq.inverse": (None, "KODEX_NASDAQ100_INVERSE"),
}


def load_state(path: str = "config/state.json") -> dict:
    p = Path(path)
    if not p.exists():
        state = dict(_DEFAULT_STATE)
        save_state(state, path)
        return state
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict, path: str = "config/state.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def detect_conflicts(state: dict) -> list[str]:
    warnings: list[str] = []

    bull_kospi = bool(state.get("KODEX200")) or bool(state.get("KODEX_LEVERAGE"))
    bear_kospi = bool(state.get("KODEX_INVERSE")) or bool(state.get("KODEX_INVERSE_2X"))
    if bull_kospi and bear_kospi:
        warnings.append("⚠️ 충돌: KOSPI 상승(KODEX200/레버리지)과 하락(인버스) 포지션을 동시에 보유 중입니다.")

    bull_nasdaq = bool(state.get("KODEX_NASDAQ100")) or bool(state.get("KODEX_NASDAQ100_LEVERAGE"))
    inv_nasdaq = bool(state.get("KODEX_NASDAQ100_INVERSE"))
    if bull_nasdaq and inv_nasdaq:
        warnings.append("⚠️ 충돌: 나스닥 상승(KODEX 나스닥100/레버리지)과 인버스 포지션을 동시에 보유 중입니다.")

    if bool(state.get("KODEX200")) and bool(state.get("KODEX_LEVERAGE")):
        warnings.append("⚠️ 충돌: KODEX200(1x)과 레버리지(2x)를 동시에 보유 중입니다.")

    if bool(state.get("KODEX_INVERSE")) and bool(state.get("KODEX_INVERSE_2X")):
        warnings.append("⚠️ 충돌: KODEX 인버스(1x)와 인버스2X(2x)를 동시에 보유 중입니다.")

    if bool(state.get("KODEX_NASDAQ100")) and bool(state.get("KODEX_NASDAQ100_LEVERAGE")):
        warnings.append("⚠️ 충돌: KODEX 나스닥100(1x)과 나스닥100 레버리지(2x)를 동시에 보유 중입니다.")

    return warnings


def filter_signals(raw_signals: dict, state: dict) -> dict:
    """Post-filter signals from signal_engine based on current portfolio state."""
    result: dict = {}
    for group_key, sig in raw_signals.items():
        holdings = _GROUP_HOLDINGS.get(group_key)
        if holdings is None:
            result[group_key] = sig
            continue

        key_1x, key_2x = holdings
        holding_1x = bool(state.get(key_1x)) if key_1x else False
        holding_2x = bool(state.get(key_2x)) if key_2x else False
        holding_any = holding_1x or holding_2x

        if sig == Signal.STAY:
            result[group_key] = sig
        elif sig == Signal.BUY:
            if not holding_any:
                result[group_key] = sig
        elif sig == Signal.SELL:
            if holding_any:
                result[group_key] = sig
        elif sig == Signal.UPGRADE:
            if holding_1x and not holding_2x:
                result[group_key] = sig

    return result
