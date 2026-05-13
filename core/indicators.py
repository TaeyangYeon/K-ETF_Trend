import pandas as pd
import ta


def resample_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    agg = {
        "시가": "first",
        "고가": "max",
        "저가": "min",
        "종가": "last",
        "거래량": "sum",
    }
    return daily_df.resample("W-FRI").agg(agg).dropna()


def calc_ichimoku(
    df: pd.DataFrame,
    conversion: int = 9,
    base: int = 26,
    span: int = 52,
) -> pd.DataFrame:
    df = df.copy()
    high = df["고가"]
    low = df["저가"]

    tenkan = (high.rolling(conversion).max() + low.rolling(conversion).min()) / 2
    kijun = (high.rolling(base).max() + low.rolling(base).min()) / 2
    span_a_raw = (tenkan + kijun) / 2
    span_b_raw = (high.rolling(span).max() + low.rolling(span).min()) / 2

    df["tenkan"] = tenkan
    df["kijun"] = kijun
    # Shift forward by `base` periods: df.iloc[-1] reflects the cloud visible on the last bar
    df["ichimoku_span_a"] = span_a_raw.shift(base)
    df["ichimoku_span_b"] = span_b_raw.shift(base)
    # Chikou: close plotted `base` periods in the past
    df["chikou"] = df["종가"].shift(-base)
    return df


def calc_ma(df: pd.DataFrame, period: int = 60) -> pd.DataFrame:
    df = df.copy()
    df[f"ma_{period}"] = df["종가"].rolling(period).mean()
    return df


def calc_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df = df.copy()
    indicator = ta.trend.ADXIndicator(
        high=df["고가"], low=df["저가"], close=df["종가"], window=period
    )
    df["adx"] = indicator.adx()
    return df


def compute_all_indicators(
    daily_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = calc_ichimoku(daily_df)
    daily = calc_ma(daily)
    daily = calc_adx(daily)

    weekly_raw = resample_weekly(daily_df)
    weekly = calc_ichimoku(weekly_raw)
    weekly = calc_ma(weekly)

    return daily, weekly
