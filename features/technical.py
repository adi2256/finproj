"""
Technical indicator computation using pandas-ta.

Takes a raw OHLCV DataFrame (date index, columns: open/high/low/close/adj_close/volume)
and returns a DataFrame of computed features with the same index.

All indicators are computed from adj_close so splits/dividends don't introduce
artificial signals.
"""
import logging

import numpy as np
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)

# Minimum rows needed before indicators are meaningful
MIN_ROWS = 210   # enough for SMA-200 + a few days of signal


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all technical features for a single ticker.

    Parameters
    ----------
    df : DataFrame with DatetimeIndex and columns
         [open, high, low, close, adj_close, volume]

    Returns
    -------
    DataFrame with same index and technical feature columns.
    NaN values are expected for the warm-up period of long-window indicators.
    """
    if len(df) < MIN_ROWS:
        logger.warning("Only %d rows — some long-window indicators will be all-NaN", len(df))

    # Work on a copy; use adj_close as the close proxy
    d = df.copy()
    price = d["adj_close"].rename("close")
    high  = d["high"]
    low   = d["low"]
    vol   = d["volume"].astype(float)

    out = pd.DataFrame(index=d.index)

    # ------------------------------------------------------------------
    # Moving averages
    # ------------------------------------------------------------------
    out["sma_20"]  = ta.sma(price, length=20)
    out["sma_50"]  = ta.sma(price, length=50)
    out["sma_200"] = ta.sma(price, length=200)
    out["ema_20"]  = ta.ema(price, length=20)
    out["ema_50"]  = ta.ema(price, length=50)
    out["ema_200"] = ta.ema(price, length=200)

    # ------------------------------------------------------------------
    # Momentum — RSI
    # ------------------------------------------------------------------
    out["rsi_14"] = ta.rsi(price, length=14)

    # ------------------------------------------------------------------
    # MACD (12, 26, 9)
    # ------------------------------------------------------------------
    macd_df = ta.macd(price, fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        out["macd"]        = macd_df.iloc[:, 0]   # MACD line
        out["macd_signal"] = macd_df.iloc[:, 1]   # Signal line
        out["macd_hist"]   = macd_df.iloc[:, 2]   # Histogram

    # ------------------------------------------------------------------
    # Bollinger Bands (20, 2)
    # ------------------------------------------------------------------
    bb_df = ta.bbands(price, length=20, std=2)
    if bb_df is not None and not bb_df.empty:
        out["bb_lower"] = bb_df.iloc[:, 0]
        out["bb_mid"]   = bb_df.iloc[:, 1]
        out["bb_upper"] = bb_df.iloc[:, 2]
        # %B: where is close within the band
        band_width = out["bb_upper"] - out["bb_lower"]
        out["bb_pct"] = (price - out["bb_lower"]) / band_width.replace(0, np.nan)

    # ------------------------------------------------------------------
    # ATR (Average True Range, 14)
    # ------------------------------------------------------------------
    atr_series = ta.atr(high, low, price, length=14)
    if atr_series is not None:
        out["atr_14"] = atr_series

    # ------------------------------------------------------------------
    # OBV (On-Balance Volume)
    # ------------------------------------------------------------------
    obv_series = ta.obv(price, vol)
    if obv_series is not None:
        out["obv"] = obv_series.astype("Int64")   # nullable int

    # ------------------------------------------------------------------
    # Volume z-score (trailing 20-day)
    # ------------------------------------------------------------------
    vol_mean = vol.rolling(20).mean()
    vol_std  = vol.rolling(20).std(ddof=1)
    out["volume_zscore"] = (vol - vol_mean) / vol_std.replace(0, np.nan)

    # ------------------------------------------------------------------
    # Returns
    # ------------------------------------------------------------------
    out["daily_return"]   = price.pct_change()
    out["log_return"]     = np.log(price / price.shift(1))
    # 20-day realised vol, annualised (√252)
    out["rolling_vol_20"] = out["log_return"].rolling(20).std() * np.sqrt(252)

    return out


def compute_batch(tickers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute technical features for all tickers in a stacked DataFrame.

    Parameters
    ----------
    tickers_df : DataFrame with MultiIndex (ticker, date) and OHLCV columns.

    Returns
    -------
    Same MultiIndex DataFrame with feature columns appended.
    """
    results = []
    for ticker, group in tickers_df.groupby(level="ticker"):
        single = group.droplevel("ticker")
        try:
            feats = compute(single)
            feats["ticker"] = ticker
            feats = feats.reset_index()   # date becomes a column
            results.append(feats)
        except Exception as exc:
            logger.error("Technical compute failed for %s: %s", ticker, exc)

    if not results:
        return pd.DataFrame()

    combined = pd.concat(results, ignore_index=True)
    return combined
