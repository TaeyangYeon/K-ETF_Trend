import json
import pytest
from pathlib import Path

from core.signal_engine import Signal


ALL_FALSE_STATE = {
    "KODEX200": False,
    "KODEX_LEVERAGE": False,
    "KODEX_INVERSE": False,
    "KODEX_INVERSE_2X": False,
    "KODEX_NASDAQ100": False,
    "KODEX_NASDAQ100_LEVERAGE": False,
    "KODEX_NASDAQ100_INVERSE": False,
}


def _state(**overrides) -> dict:
    s = dict(ALL_FALSE_STATE)
    s.update(overrides)
    return s


# ── load_state ────────────────────────────────────────────────────────────────

def test_load_state_reads_existing_file(tmp_path):
    from core.portfolio_state import load_state

    state_file = tmp_path / "state.json"
    data = dict(ALL_FALSE_STATE)
    data["KODEX200"] = True
    state_file.write_text(json.dumps(data))

    result = load_state(str(state_file))
    assert result["KODEX200"] is True
    assert result["KODEX_LEVERAGE"] is False


def test_load_state_missing_file_creates_all_false(tmp_path):
    from core.portfolio_state import load_state

    state_file = tmp_path / "state.json"
    assert not state_file.exists()

    result = load_state(str(state_file))

    assert state_file.exists()
    for key in ALL_FALSE_STATE:
        assert result[key] is False


# ── save_state ────────────────────────────────────────────────────────────────

def test_save_state_writes_json(tmp_path):
    from core.portfolio_state import save_state

    state_file = tmp_path / "state.json"
    state = _state(KODEX200=True)

    save_state(state, str(state_file))

    written = json.loads(state_file.read_text())
    assert written["KODEX200"] is True
    assert written["KODEX_LEVERAGE"] is False


# ── detect_conflicts ──────────────────────────────────────────────────────────

def test_detect_conflicts_no_conflicts():
    from core.portfolio_state import detect_conflicts

    assert detect_conflicts(ALL_FALSE_STATE) == []


def test_detect_conflicts_kospi_bull_and_bear():
    from core.portfolio_state import detect_conflicts

    state = _state(KODEX200=True, KODEX_INVERSE=True)
    warnings = detect_conflicts(state)
    assert len(warnings) >= 1
    assert any("KOSPI" in w or "코스피" in w for w in warnings)


def test_detect_conflicts_kospi_leverage_and_inverse2x():
    from core.portfolio_state import detect_conflicts

    state = _state(KODEX_LEVERAGE=True, KODEX_INVERSE_2X=True)
    warnings = detect_conflicts(state)
    assert len(warnings) >= 1


def test_detect_conflicts_nasdaq_bull_and_inverse():
    from core.portfolio_state import detect_conflicts

    state = _state(KODEX_NASDAQ100=True, KODEX_NASDAQ100_INVERSE=True)
    warnings = detect_conflicts(state)
    assert len(warnings) >= 1
    assert any("나스닥" in w or "NASDAQ" in w for w in warnings)


def test_detect_conflicts_nasdaq_leverage_and_inverse():
    from core.portfolio_state import detect_conflicts

    state = _state(KODEX_NASDAQ100_LEVERAGE=True, KODEX_NASDAQ100_INVERSE=True)
    warnings = detect_conflicts(state)
    assert len(warnings) >= 1


def test_detect_conflicts_1x_and_2x_same_direction_kospi_bull():
    from core.portfolio_state import detect_conflicts

    state = _state(KODEX200=True, KODEX_LEVERAGE=True)
    warnings = detect_conflicts(state)
    assert len(warnings) >= 1
    assert any("KODEX200" in w or "레버리지" in w for w in warnings)


def test_detect_conflicts_1x_and_2x_same_direction_kospi_bear():
    from core.portfolio_state import detect_conflicts

    state = _state(KODEX_INVERSE=True, KODEX_INVERSE_2X=True)
    warnings = detect_conflicts(state)
    assert len(warnings) >= 1


def test_detect_conflicts_1x_and_2x_same_direction_nasdaq_bull():
    from core.portfolio_state import detect_conflicts

    state = _state(KODEX_NASDAQ100=True, KODEX_NASDAQ100_LEVERAGE=True)
    warnings = detect_conflicts(state)
    assert len(warnings) >= 1


# ── filter_signals ────────────────────────────────────────────────────────────

def test_filter_signals_buy_suppressed_when_holding_1x():
    from core.portfolio_state import filter_signals

    raw = {"kospi.bull": Signal.BUY}
    state = _state(KODEX200=True)
    result = filter_signals(raw, state)
    assert "kospi.bull" not in result


def test_filter_signals_buy_suppressed_when_holding_2x():
    from core.portfolio_state import filter_signals

    raw = {"kospi.bull": Signal.BUY}
    state = _state(KODEX_LEVERAGE=True)
    result = filter_signals(raw, state)
    assert "kospi.bull" not in result


def test_filter_signals_buy_passes_when_not_holding():
    from core.portfolio_state import filter_signals

    raw = {"kospi.bull": Signal.BUY}
    result = filter_signals(raw, ALL_FALSE_STATE)
    assert result.get("kospi.bull") == Signal.BUY


def test_filter_signals_sell_suppressed_when_not_holding():
    from core.portfolio_state import filter_signals

    raw = {"kospi.bull": Signal.SELL}
    result = filter_signals(raw, ALL_FALSE_STATE)
    assert "kospi.bull" not in result


def test_filter_signals_sell_passes_when_holding_1x():
    from core.portfolio_state import filter_signals

    raw = {"kospi.bull": Signal.SELL}
    state = _state(KODEX200=True)
    result = filter_signals(raw, state)
    assert result.get("kospi.bull") == Signal.SELL


def test_filter_signals_sell_passes_when_holding_2x():
    from core.portfolio_state import filter_signals

    raw = {"kospi.bull": Signal.SELL}
    state = _state(KODEX_LEVERAGE=True)
    result = filter_signals(raw, state)
    assert result.get("kospi.bull") == Signal.SELL


def test_filter_signals_upgrade_suppressed_when_not_holding_1x():
    from core.portfolio_state import filter_signals

    raw = {"kospi.bull": Signal.UPGRADE}
    result = filter_signals(raw, ALL_FALSE_STATE)
    assert "kospi.bull" not in result


def test_filter_signals_upgrade_suppressed_when_holding_2x_only():
    from core.portfolio_state import filter_signals

    raw = {"kospi.bull": Signal.UPGRADE}
    state = _state(KODEX_LEVERAGE=True)
    result = filter_signals(raw, state)
    assert "kospi.bull" not in result


def test_filter_signals_upgrade_passes_when_holding_1x_only():
    from core.portfolio_state import filter_signals

    raw = {"kospi.bull": Signal.UPGRADE}
    state = _state(KODEX200=True)
    result = filter_signals(raw, state)
    assert result.get("kospi.bull") == Signal.UPGRADE


def test_filter_signals_stay_always_passes():
    from core.portfolio_state import filter_signals

    raw = {"kospi.bull": Signal.STAY}
    result = filter_signals(raw, ALL_FALSE_STATE)
    assert result.get("kospi.bull") == Signal.STAY


def test_filter_signals_nasdaq_inverse_buy_suppressed_when_holding():
    from core.portfolio_state import filter_signals

    raw = {"nasdaq.inverse": Signal.BUY}
    state = _state(KODEX_NASDAQ100_INVERSE=True)
    result = filter_signals(raw, state)
    assert "nasdaq.inverse" not in result


def test_filter_signals_nasdaq_inverse_sell_passes_when_holding():
    from core.portfolio_state import filter_signals

    raw = {"nasdaq.inverse": Signal.SELL}
    state = _state(KODEX_NASDAQ100_INVERSE=True)
    result = filter_signals(raw, state)
    assert result.get("nasdaq.inverse") == Signal.SELL


def test_filter_signals_multiple_signals():
    from core.portfolio_state import filter_signals

    raw = {
        "kospi.bull": Signal.BUY,     # holding → should be suppressed
        "kospi.bear": Signal.SELL,    # not holding → should be suppressed
        "nasdaq.bull": Signal.BUY,    # not holding → should pass
    }
    state = _state(KODEX200=True)
    result = filter_signals(raw, state)
    assert "kospi.bull" not in result
    assert "kospi.bear" not in result
    assert result.get("nasdaq.bull") == Signal.BUY
