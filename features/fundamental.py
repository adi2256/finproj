"""
Fundamental feature extraction.

Two data sources:
  1. yfinance Ticker.info  — valuation ratios, margins, current-snapshot metrics
  2. yfinance quarterly_financials / quarterly_balance_sheet  — growth rates over time

Each call to `compute(ticker)` returns a list of dicts, one per fiscal quarter,
ready for upsert_fundamental_features().

Notes
-----
- yfinance .info returns trailing-twelve-month figures; we pair them with the
  latest available quarter date.
- For historical quarterly time-series (revenue_qoq, revenue_yoy) we iterate
  the quarterly financials DataFrame.
- EPS surprise requires an analyst-estimate feed (Polygon, Alpha Vantage, etc.).
  The `eps_estimate` column is populated as None until that source is wired up
  (see TODO in settings.py).
"""
import logging
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def compute(ticker: str) -> list[dict]:
    """
    Pull fundamental features for a single ticker.
    Returns a list of dicts (one per quarter) ready for DB upsert.
    """
    try:
        t = yf.Ticker(ticker)
        return _build_records(ticker, t)
    except Exception as exc:
        logger.error("Fundamental compute failed for %s: %s", ticker, exc)
        return []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def _build_records(ticker: str, t: yf.Ticker) -> list[dict]:
    info = t.info or {}

    # ----------------------------------------------------------------
    # Snapshot metrics (from .info — TTM/current)
    # ----------------------------------------------------------------
    snapshot = {
        "pe_ratio":         _safe(info.get("trailingPE")),
        "pb_ratio":         _safe(info.get("priceToBook")),
        "ps_ratio":         _safe(info.get("priceToSalesTrailing12Months")),
        "ev_ebitda":        _safe(info.get("enterpriseToEbitda")),
        "gross_margin":     _pct(info.get("grossMargins")),
        "operating_margin": _pct(info.get("operatingMargins")),
        "net_margin":       _pct(info.get("profitMargins")),
        "roe":              _pct(info.get("returnOnEquity")),
        "roa":              _pct(info.get("returnOnAssets")),
        "eps_actual":       _safe(info.get("trailingEps")),
        "eps_estimate":     _safe(info.get("forwardEps")),   # forward as proxy until real estimates wired
        "debt_to_equity":   _safe(info.get("debtToEquity")),
        "current_ratio":    _safe(info.get("currentRatio")),
        "quick_ratio":      _safe(info.get("quickRatio")),
        "earnings_growth":  _pct(info.get("earningsGrowth")),
    }

    # EPS surprise (if both actuals and estimates exist)
    if snapshot["eps_actual"] is not None and snapshot["eps_estimate"] is not None:
        est = snapshot["eps_estimate"]
        if est != 0:
            snapshot["eps_surprise"] = round(
                (snapshot["eps_actual"] - est) / abs(est) * 100, 4
            )
        else:
            snapshot["eps_surprise"] = None
    else:
        snapshot["eps_surprise"] = None

    # ----------------------------------------------------------------
    # Historical quarterly revenue for growth rates
    # ----------------------------------------------------------------
    records = _build_quarterly_records(ticker, t, snapshot)

    if not records:
        # Fall back to a single snapshot record using today as period
        today = date.today()
        # Align to nearest quarter end
        q_month = ((today.month - 1) // 3) * 3 + 3
        period = date(today.year if q_month <= 12 else today.year + 1,
                      q_month if q_month <= 12 else q_month - 12, 1)
        records = [{
            "ticker":    ticker,
            "period":    period,
            "filing_id": None,
            **snapshot,
            "revenue_qoq": None,
            "revenue_yoy": None,
        }]

    return records


def _build_quarterly_records(
    ticker: str,
    t: yf.Ticker,
    snapshot: dict,
) -> list[dict]:
    """
    Build per-quarter rows using quarterly_financials for revenue growth.
    Returns [] if data is unavailable.
    """
    try:
        qf = t.quarterly_financials   # columns = quarter-end dates (newest first)
    except Exception:
        return []

    if qf is None or qf.empty:
        return []

    # Normalise column labels to date objects (yfinance returns Timestamps)
    qf = qf.T.copy()   # rows = quarters, cols = line items
    qf.index = pd.to_datetime(qf.index).date

    # Find the revenue row (label varies by yfinance version)
    rev_labels = ["Total Revenue", "Revenue", "TotalRevenue"]
    revenue: pd.Series | None = None
    for label in rev_labels:
        if label in qf.columns:
            revenue = qf[label].astype(float)
            break

    records = []
    quarters = sorted(qf.index)   # chronological order

    for i, q_date in enumerate(quarters):
        row: dict = {
            "ticker":    ticker,
            "period":    q_date,
            "filing_id": None,
            **snapshot,
        }

        if revenue is not None:
            rev_now = revenue.get(q_date)
            # QoQ: vs previous quarter
            if i >= 1:
                rev_prev_q = revenue.get(quarters[i - 1])
                row["revenue_qoq"] = _growth(rev_now, rev_prev_q)
            else:
                row["revenue_qoq"] = None

            # YoY: vs same quarter 4 periods ago
            if i >= 4:
                rev_prev_y = revenue.get(quarters[i - 4])
                row["revenue_yoy"] = _growth(rev_now, rev_prev_y)
            else:
                row["revenue_yoy"] = None
        else:
            row["revenue_qoq"] = None
            row["revenue_yoy"] = None

        records.append(row)

    return records


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _safe(val) -> float | None:
    """Return float or None, coercing infinities to None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if (f != f or abs(f) == float("inf")) else round(f, 4)
    except (TypeError, ValueError):
        return None


def _pct(val) -> float | None:
    """Convert a decimal fraction (0.35) to percentage (35.00)."""
    v = _safe(val)
    return round(v * 100, 4) if v is not None else None


def _growth(now, prev) -> float | None:
    """Return percentage growth from prev to now."""
    if now is None or prev is None or prev == 0:
        return None
    try:
        return round((float(now) - float(prev)) / abs(float(prev)) * 100, 4)
    except (TypeError, ValueError):
        return None


def compute_batch(tickers: list[str]) -> list[dict]:
    """Compute fundamental features for all tickers. Returns flat list of records."""
    all_records = []
    for ticker in tickers:
        records = compute(ticker)
        all_records.extend(records)
        logger.info("%s: %d fundamental records", ticker, len(records))
    return all_records
