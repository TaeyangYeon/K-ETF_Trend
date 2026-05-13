import time
from datetime import datetime, timedelta

import pandas as pd
from pykrx import stock


def fetch_ohlcv(ticker: str, days: int = 300, logger=None) -> pd.DataFrame:
    """Fetch OHLCV data for a KRX ticker. Returns DataFrame with columns [시가, 고가, 저가, 종가, 거래량], DatetimeIndex; empty DataFrame on failure."""
    end_date = datetime.today().strftime("%Y%m%d")
    # ~300 trading days ≈ 1.5 years; use 2x calendar days as buffer
    start_dt = datetime.today() - timedelta(days=int(days * 2))
    start_date = start_dt.strftime("%Y%m%d")

    try:
        df = stock.get_market_ohlcv_by_date(start_date, end_date, ticker)
        time.sleep(1)
        if df is None or df.empty:
            if logger:
                logger.warning(f"{ticker}: 데이터 없음")
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        return df[["시가", "고가", "저가", "종가", "거래량"]].tail(days)
    except Exception as e:
        if logger:
            logger.error(f"{ticker} 조회 실패: {e}")
        return pd.DataFrame()
