import math
from enum import Enum

import pandas as pd


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    STAY = "STAY"
    UPGRADE = "UPGRADE"
    NONE = "None"


def _valid(*vals) -> bool:
    """Validate that all values are numeric and not NaN."""
    for v in vals:
        try:
            if math.isnan(float(v)):
                return False
        except (TypeError, ValueError):
            return False
    return True


def is_above_cloud(close, span_a, span_b) -> bool:
    """Check if close price is above both Ichimoku cloud spans."""
    if not _valid(close, span_a, span_b):
        return False
    return float(close) > float(span_a) and float(close) > float(span_b)


def is_below_cloud(close, span_a, span_b) -> bool:
    """Check if close price is below both Ichimoku cloud spans."""
    if not _valid(close, span_a, span_b):
        return False
    return float(close) < float(span_a) and float(close) < float(span_b)


def _kospi_bull_signal(
    daily: pd.DataFrame, weekly: pd.DataFrame, state: dict
) -> "Signal | None":
    holding_1x = bool(state.get("KODEX200"))
    holding_2x = bool(state.get("KODEX_LEVERAGE"))
    holding_any = holding_1x or holding_2x

    d = daily.iloc[-1]
    close = float(d["종가"])
    span_a = float(d["ichimoku_span_a"])
    span_b = float(d["ichimoku_span_b"])
    span_a_raw = float(d["ichimoku_span_a_raw"])
    span_b_raw = float(d["ichimoku_span_b_raw"])
    ma60 = float(d["ma_60"])

    # SELL: any one condition triggers
    if holding_any:
        if is_below_cloud(close, span_a, span_b) or (_valid(close, ma60) and close < ma60):
            return Signal.SELL

    # UPGRADE: only if holding 1x, all weekly conditions must be true
    if holding_1x:
        w = weekly.iloc[-1]
        wc = float(w["종가"])
        wa = float(w["ichimoku_span_a"])
        wb = float(w["ichimoku_span_b"])
        wm = float(w["ma_60"])
        if is_above_cloud(wc, wa, wb) and _valid(wc, wm) and wc > wm:
            return Signal.UPGRADE

    # BUY: all daily conditions must be true, only if not holding
    if not holding_any:
        if (
            is_above_cloud(close, span_a, span_b)
            and _valid(close, ma60) and close > ma60
            and _valid(span_a_raw, span_b_raw) and span_a_raw > span_b_raw
        ):
            return Signal.BUY

    return None


def _kospi_bear_signal(
    daily: pd.DataFrame, weekly: pd.DataFrame, state: dict
) -> "Signal | None":
    holding_1x = bool(state.get("KODEX_INVERSE"))
    holding_2x = bool(state.get("KODEX_INVERSE_2X"))
    holding_any = holding_1x or holding_2x

    d = daily.iloc[-1]
    close = float(d["종가"])
    span_a = float(d["ichimoku_span_a"])
    span_b = float(d["ichimoku_span_b"])
    span_a_raw = float(d["ichimoku_span_a_raw"])
    span_b_raw = float(d["ichimoku_span_b_raw"])
    ma60 = float(d["ma_60"])

    if holding_any:
        if is_below_cloud(close, span_a, span_b) or (_valid(close, ma60) and close < ma60):
            return Signal.SELL

    if holding_1x:
        w = weekly.iloc[-1]
        wc = float(w["종가"])
        wa = float(w["ichimoku_span_a"])
        wb = float(w["ichimoku_span_b"])
        wm = float(w["ma_60"])
        if is_above_cloud(wc, wa, wb) and _valid(wc, wm) and wc > wm:
            return Signal.UPGRADE

    if not holding_any:
        if (
            is_above_cloud(close, span_a, span_b)
            and _valid(close, ma60) and close > ma60
            and _valid(span_a_raw, span_b_raw) and span_a_raw > span_b_raw
        ):
            return Signal.BUY

    return None


def _nasdaq_bull_signal(
    daily: pd.DataFrame, weekly: pd.DataFrame, state: dict
) -> "Signal | None":
    holding_1x = bool(state.get("KODEX_NASDAQ100"))
    holding_2x = bool(state.get("KODEX_NASDAQ100_LEVERAGE"))
    holding_any = holding_1x or holding_2x

    d = daily.iloc[-1]
    close = float(d["종가"])
    span_a = float(d["ichimoku_span_a"])
    span_b = float(d["ichimoku_span_b"])
    span_a_raw = float(d["ichimoku_span_a_raw"])
    span_b_raw = float(d["ichimoku_span_b_raw"])
    ma60 = float(d["ma_60"])

    if holding_any:
        if is_below_cloud(close, span_a, span_b) or (_valid(close, ma60) and close < ma60):
            return Signal.SELL

    if holding_1x:
        w = weekly.iloc[-1]
        wc = float(w["종가"])
        wa = float(w["ichimoku_span_a"])
        wb = float(w["ichimoku_span_b"])
        wm = float(w["ma_60"])
        if is_above_cloud(wc, wa, wb) and _valid(wc, wm) and wc > wm:
            return Signal.UPGRADE

    if not holding_any:
        if (
            is_above_cloud(close, span_a, span_b)
            and _valid(close, ma60) and close > ma60
            and _valid(span_a_raw, span_b_raw) and span_a_raw > span_b_raw
        ):
            return Signal.BUY

    return None


def _nasdaq_inverse_signal(
    daily: pd.DataFrame, weekly: pd.DataFrame, state: dict
) -> "Signal | None":
    """Uses KODEX NASDAQ100 (bull_1x) indicators interpreted in reverse."""
    holding = bool(state.get("KODEX_NASDAQ100_INVERSE"))

    d = daily.iloc[-1]
    close = float(d["종가"])
    span_a = float(d["ichimoku_span_a"])
    span_b = float(d["ichimoku_span_b"])
    span_a_raw = float(d["ichimoku_span_a_raw"])
    span_b_raw = float(d["ichimoku_span_b_raw"])
    ma60 = float(d["ma_60"])

    # SELL: any one condition (reverse: above cloud OR close > ma60)
    if holding:
        if is_above_cloud(close, span_a, span_b) or (_valid(close, ma60) and close > ma60):
            return Signal.SELL

    # BUY: requires BOTH daily bearish confirmation AND weekly bearish conditions
    if not holding:
        daily_bearish = (
            is_below_cloud(close, span_a, span_b)
            and _valid(close, ma60) and close < ma60
            and _valid(span_a_raw, span_b_raw) and span_a_raw < span_b_raw
        )
        if daily_bearish:
            w = weekly.iloc[-1]
            wc = float(w["종가"])
            wa = float(w["ichimoku_span_a"])
            wb = float(w["ichimoku_span_b"])
            wm = float(w["ma_60"])
            if is_below_cloud(wc, wa, wb) and _valid(wc, wm) and wc < wm:
                return Signal.BUY

    return None


def generate_signals(market_data: dict, state: dict) -> dict:
    """Generate trading signals for all markets based on Ichimoku indicators and portfolio state; resolve KOSPI conflicts via ADX."""
    kospi_bull_d, kospi_bull_w = market_data.get("kospi.bull_1x", (None, None))
    kospi_bear_d, kospi_bear_w = market_data.get("kospi.bear_1x", (None, None))
    nasdaq_bull_d, nasdaq_bull_w = market_data.get("nasdaq.bull_1x", (None, None))

    kospi_bull_sig = (
        _kospi_bull_signal(kospi_bull_d, kospi_bull_w, state)
        if kospi_bull_d is not None else None
    )
    kospi_bear_sig = (
        _kospi_bear_signal(kospi_bear_d, kospi_bear_w, state)
        if kospi_bear_d is not None else None
    )
    nasdaq_bull_sig = (
        _nasdaq_bull_signal(nasdaq_bull_d, nasdaq_bull_w, state)
        if nasdaq_bull_d is not None else None
    )
    nasdaq_inv_sig = (
        _nasdaq_inverse_signal(nasdaq_bull_d, nasdaq_bull_w, state)
        if nasdaq_bull_d is not None else None
    )

    # KOSPI conflict resolution: both bull and bear entry signals fire simultaneously
    kospi_bull_entry = kospi_bull_sig in (Signal.BUY, Signal.UPGRADE)
    kospi_bear_entry = kospi_bear_sig in (Signal.BUY, Signal.UPGRADE)
    if kospi_bull_entry and kospi_bear_entry:
        adx = None
        if kospi_bull_d is not None:
            raw_adx = kospi_bull_d.iloc[-1]["adx"]
            if _valid(raw_adx):
                adx = float(raw_adx)

        holding_bull = bool(state.get("KODEX200")) or bool(state.get("KODEX_LEVERAGE"))
        holding_bear = bool(state.get("KODEX_INVERSE")) or bool(state.get("KODEX_INVERSE_2X"))

        if adx is not None and adx >= 25:
            # Adopt the new signal — the one conflicting with the current position
            if holding_bull:
                kospi_bull_sig = None      # discard old bull, keep new bear
            elif holding_bear:
                kospi_bear_sig = None      # discard old bear, keep new bull
            else:
                kospi_bull_sig = Signal.STAY   # holding neither: can't determine direction
                kospi_bear_sig = None
        else:
            # Weak trend or indeterminate: keep current position
            kospi_bull_sig = Signal.STAY
            kospi_bear_sig = None

    result = {}
    if kospi_bull_sig is not None:
        result["kospi.bull"] = kospi_bull_sig
    if kospi_bear_sig is not None:
        result["kospi.bear"] = kospi_bear_sig
    if nasdaq_bull_sig is not None:
        result["nasdaq.bull"] = nasdaq_bull_sig
    if nasdaq_inv_sig is not None:
        result["nasdaq.inverse"] = nasdaq_inv_sig

    return result
