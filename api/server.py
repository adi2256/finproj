"""Flask API server — serves data from PostgreSQL to the React dashboard."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import text
from data.storage.db_client import get_conn

app = Flask(__name__)
CORS(app)


@app.route("/api/overview")
def overview():
    with get_conn() as conn:
        stocks = conn.execute(text("SELECT count(*) FROM stocks")).scalar()
        ohlcv = conn.execute(text("SELECT count(*) FROM ohlcv")).scalar()
        filings = conn.execute(text("SELECT count(*) FROM filings")).scalar()
        news = conn.execute(text("SELECT count(*) FROM news_articles")).scalar()
        sentiment = conn.execute(text("SELECT count(*) FROM sentiment_scores")).scalar()
        ohlcv_range = conn.execute(text("SELECT min(date), max(date) FROM ohlcv")).fetchone()
        sectors = conn.execute(text(
            "SELECT sector, count(*) as cnt FROM stocks WHERE sector IS NOT NULL GROUP BY sector ORDER BY cnt DESC"
        )).fetchall()
    return jsonify({
        "stocks": stocks,
        "ohlcv_rows": ohlcv,
        "filings": filings,
        "news_articles": news,
        "sentiment_scores": sentiment,
        "date_range": {
            "start": str(ohlcv_range[0]) if ohlcv_range[0] else None,
            "end": str(ohlcv_range[1]) if ohlcv_range[1] else None,
        },
        "sectors": [{"sector": r[0], "count": r[1]} for r in sectors],
    })


@app.route("/api/stocks")
def stocks():
    with get_conn() as conn:
        rows = conn.execute(text(
            "SELECT s.ticker, s.name, s.sector, s.market_cap, s.exchange, "
            "  (SELECT count(*) FROM ohlcv o WHERE o.ticker = s.ticker) as ohlcv_days, "
            "  (SELECT count(*) FROM filings f WHERE f.ticker = s.ticker) as filing_count "
            "FROM stocks s WHERE s.active ORDER BY s.sector, s.ticker"
        )).fetchall()
    return jsonify([{
        "ticker": r[0], "name": r[1], "sector": r[2],
        "market_cap": r[3], "exchange": r[4],
        "ohlcv_days": r[5], "filing_count": r[6],
    } for r in rows])


@app.route("/api/ohlcv/<ticker>")
def ohlcv(ticker):
    days = request.args.get("days", 365, type=int)
    start = date.today() - timedelta(days=days)
    with get_conn() as conn:
        rows = conn.execute(text(
            "SELECT date, open, high, low, close, adj_close, volume "
            "FROM ohlcv WHERE ticker = :ticker AND date >= :start ORDER BY date ASC"
        ), {"ticker": ticker.upper(), "start": str(start)}).fetchall()
    return jsonify([{
        "date": str(r[0]), "open": float(r[1] or 0), "high": float(r[2] or 0),
        "low": float(r[3] or 0), "close": float(r[4] or 0),
        "adj_close": float(r[5] or 0), "volume": int(r[6] or 0),
    } for r in rows])


@app.route("/api/filings/<ticker>")
def filings(ticker):
    with get_conn() as conn:
        rows = conn.execute(text(
            "SELECT type, period, filed_at, accession_number, "
            "  LEFT(parsed_mda, 500) as mda_preview "
            "FROM filings WHERE ticker = :ticker ORDER BY period DESC"
        ), {"ticker": ticker.upper()}).fetchall()
    return jsonify([{
        "type": r[0], "period": str(r[1]) if r[1] else None,
        "filed_at": str(r[2]) if r[2] else None,
        "accession_number": r[3], "mda_preview": r[4],
    } for r in rows])


@app.route("/api/sector-performance")
def sector_performance():
    with get_conn() as conn:
        rows = conn.execute(text("""
            SELECT s.sector,
                   count(DISTINCT o.ticker) as tickers,
                   round(avg(o.close)::numeric, 2) as avg_close,
                   round(avg(o.volume)::numeric, 0) as avg_volume,
                   min(o.date) as earliest,
                   max(o.date) as latest
            FROM ohlcv o
            JOIN stocks s ON s.ticker = o.ticker
            WHERE s.sector IS NOT NULL
            GROUP BY s.sector
            ORDER BY s.sector
        """)).fetchall()
    return jsonify([{
        "sector": r[0], "tickers": r[1], "avg_close": float(r[2] or 0),
        "avg_volume": float(r[3] or 0),
        "earliest": str(r[4]) if r[4] else None,
        "latest": str(r[5]) if r[5] else None,
    } for r in rows])


@app.route("/api/top-movers")
def top_movers():
    with get_conn() as conn:
        rows = conn.execute(text("""
            WITH latest AS (
                SELECT DISTINCT ON (ticker) ticker, date, close, volume
                FROM ohlcv ORDER BY ticker, date DESC
            ), prev AS (
                SELECT DISTINCT ON (ticker) ticker, close as prev_close
                FROM ohlcv WHERE date < (SELECT max(date) FROM ohlcv)
                ORDER BY ticker, date DESC
            )
            SELECT l.ticker, s.name, s.sector, l.close, p.prev_close,
                   round(((l.close - p.prev_close) / NULLIF(p.prev_close, 0) * 100)::numeric, 2) as pct_change,
                   l.volume
            FROM latest l
            JOIN prev p ON p.ticker = l.ticker
            JOIN stocks s ON s.ticker = l.ticker
            ORDER BY abs((l.close - p.prev_close) / NULLIF(p.prev_close, 0)) DESC
            LIMIT 20
        """)).fetchall()
    return jsonify([{
        "ticker": r[0], "name": r[1], "sector": r[2],
        "close": float(r[3] or 0), "prev_close": float(r[4] or 0),
        "pct_change": float(r[5] or 0), "volume": int(r[6] or 0),
    } for r in rows])


@app.route("/api/price-history")
def price_history():
    """Multi-ticker price history for comparison charts."""
    tickers = request.args.get("tickers", "AAPL,MSFT,NVDA")
    days = request.args.get("days", 365, type=int)
    start = date.today() - timedelta(days=days)
    ticker_list = [t.strip().upper() for t in tickers.split(",")]

    with get_conn() as conn:
        rows = conn.execute(text(
            "SELECT ticker, date, adj_close FROM ohlcv "
            "WHERE ticker = ANY(:tickers) AND date >= :start "
            "ORDER BY date ASC"
        ), {"tickers": ticker_list, "start": str(start)}).fetchall()

    result = {}
    for r in rows:
        t = r[0]
        if t not in result:
            result[t] = []
        result[t].append({"date": str(r[1]), "price": float(r[2] or 0)})
    return jsonify(result)


@app.route("/api/volume-leaders")
def volume_leaders():
    with get_conn() as conn:
        rows = conn.execute(text("""
            SELECT o.ticker, s.name, s.sector,
                   round(avg(o.volume)::numeric, 0) as avg_volume,
                   round(avg(o.close)::numeric, 2) as avg_close
            FROM ohlcv o
            JOIN stocks s ON s.ticker = o.ticker
            WHERE o.date >= (current_date - interval '30 days')
            GROUP BY o.ticker, s.name, s.sector
            ORDER BY avg(o.volume) DESC
            LIMIT 15
        """)).fetchall()
    return jsonify([{
        "ticker": r[0], "name": r[1], "sector": r[2],
        "avg_volume": float(r[3] or 0), "avg_close": float(r[4] or 0),
    } for r in rows])


if __name__ == "__main__":
    app.run(debug=True, port=5001)
