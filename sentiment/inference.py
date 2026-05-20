"""
Sentiment inference pipeline.

Scores unscored news articles and filing MD&A sections using the fine-tuned
FinBERT model, then aggregates daily sentiment per ticker.
"""
import logging
import os
import tempfile
from collections import defaultdict

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from config.settings import (
    SENTIMENT_BATCH_SIZE,
    SENTIMENT_MAX_LENGTH,
    SENTIMENT_MODEL_VERSION,
)


def _get_device() -> torch.device:
    """
    Pick the best available device.
    MPS (Apple Silicon) is used only if explicitly enabled via env var
    SENTIMENT_USE_MPS=1 — otherwise we default to CPU to avoid Metal OOM
    errors on M-series chips when batch sizes are large.
    CUDA is always preferred if available.
    """
    if torch.cuda.is_available():
        return torch.device("cuda")
    use_mps = os.getenv("SENTIMENT_USE_MPS", "0") == "1"
    if use_mps and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")
from data.storage.db_client import (
    bulk_insert_sentiment_scores,
    load_unscored_articles,
    load_unscored_filings,
    upsert_daily_sentiment_agg,
    upsert_filing_sentiment,
)

logger = logging.getLogger(__name__)

LABEL_MAP = {0: "positive", 1: "neutral", 2: "negative"}
SCORE_MAP = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}

_model = None
_tokenizer = None


def _load_model(model_path: str | None = None):
    """Load the fine-tuned model. Tries local path, then S3, then falls back to base FinBERT."""
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer

    device = _get_device()
    logger.info("Using device: %s", device)

    def _has_model_files(path: str) -> bool:
        return os.path.isdir(path) and os.path.isfile(os.path.join(path, "config.json"))

    # 1. Explicit path passed by caller
    if model_path and _has_model_files(model_path):
        logger.info("Loading model from explicit path: %s", model_path)
        load_from = model_path

    # 2. Local project directory (from scripts/restore_model.py)
    elif _has_model_files(os.path.join(os.path.dirname(os.path.dirname(__file__)), "finbert-finetuned", "final")):
        load_from = os.path.join(os.path.dirname(os.path.dirname(__file__)), "finbert-finetuned", "final")
        logger.info("Loading model from project dir: %s", load_from)

    # 3. Try S3 / MinIO
    else:
        load_from = "ProsusAI/finbert"
        try:
            from data.storage.s3_client import download_model_dir
            local_dir = os.path.join(tempfile.gettempdir(), f"finbert-{SENTIMENT_MODEL_VERSION}")
            if not _has_model_files(local_dir):
                download_model_dir(SENTIMENT_MODEL_VERSION, local_dir)
            if _has_model_files(local_dir):
                load_from = local_dir
                logger.info("Loaded model from S3: %s", SENTIMENT_MODEL_VERSION)
            else:
                logger.warning("S3 download produced no model files, falling back to ProsusAI/finbert")
        except Exception as exc:
            logger.warning("Could not load from S3 (%s), falling back to ProsusAI/finbert", exc)

    _tokenizer = AutoTokenizer.from_pretrained(load_from)
    _model = AutoModelForSequenceClassification.from_pretrained(load_from)
    _model.to(device)
    _model.eval()
    return _model, _tokenizer


def predict_batch(texts: list[str], model_path: str | None = None) -> list[dict]:
    """
    Run sentiment on a list of texts. Returns list of {label, score}.

    On Apple Silicon (MPS) the Metal command buffer can exhaust GPU memory
    with large batches. We cap at 8 per batch when on MPS and flush the
    cache after every batch to keep pressure low.
    """
    model, tokenizer = _load_model(model_path)
    device = next(model.parameters()).device
    results = []

    # Reduce batch size on MPS to avoid Metal OOM; CPU/CUDA use the configured value
    effective_batch = 8 if device.type == "mps" else SENTIMENT_BATCH_SIZE

    for i in range(0, len(texts), effective_batch):
        batch_texts = texts[i : i + effective_batch]
        inputs = tokenizer(
            batch_texts,
            padding=True,
            truncation=True,
            max_length=SENTIMENT_MAX_LENGTH,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()

        # Free MPS command buffer memory immediately after each batch
        if device.type == "mps":
            torch.mps.empty_cache()

        for prob in probs:
            pred_idx = int(np.argmax(prob))
            label = LABEL_MAP[pred_idx]
            score = (
                float(prob[0]) * SCORE_MAP["positive"]
                + float(prob[1]) * SCORE_MAP["neutral"]
                + float(prob[2]) * SCORE_MAP["negative"]
            )
            results.append({"label": label, "score": round(score, 4)})

    return results


def score_articles(model_path: str | None = None, limit: int = 5000) -> int:
    """Score unscored news articles and insert into sentiment_scores."""
    df = load_unscored_articles(limit=limit)
    if df.empty:
        logger.info("No unscored articles found")
        return 0

    logger.info("Scoring %d articles", len(df))
    texts = df["headline"].tolist()
    predictions = predict_batch(texts, model_path=model_path)

    records = []
    for idx, row in df.iterrows():
        pred = predictions[idx]
        records.append({
            "article_id": int(row["article_id"]),
            "filing_id": None,
            "ticker": row["ticker"],
            "score": pred["score"],
            "label": pred["label"],
            "model_version": SENTIMENT_MODEL_VERSION,
        })

    inserted = bulk_insert_sentiment_scores(records)
    logger.info("Inserted %d sentiment scores for articles", inserted)
    return inserted


def score_filings(model_path: str | None = None) -> int:
    """Score MD&A sections from unscored filings."""
    df = load_unscored_filings()
    if df.empty:
        logger.info("No unscored filings found")
        return 0

    logger.info("Scoring %d filings", len(df))
    scored = 0

    for _, row in df.iterrows():
        mda_text = row["parsed_mda"]
        if not mda_text or len(mda_text.strip()) < 100:
            continue

        chunks = _chunk_text(mda_text, max_length=SENTIMENT_MAX_LENGTH * 4)
        chunk_preds = predict_batch(chunks, model_path=model_path)

        scores = [p["score"] for p in chunk_preds]
        avg_score = round(float(np.mean(scores)), 4)
        label = _score_to_label(avg_score)

        bulk_insert_sentiment_scores([{
            "article_id": None,
            "filing_id": int(row["filing_id"]),
            "ticker": row["ticker"],
            "score": avg_score,
            "label": label,
            "model_version": SENTIMENT_MODEL_VERSION,
        }])

        prev_score = _get_prev_filing_score(row["ticker"], row["period"])
        delta = round(avg_score - prev_score, 4) if prev_score is not None else None

        upsert_filing_sentiment({
            "filing_id": int(row["filing_id"]),
            "ticker": row["ticker"],
            "period": row["period"],
            "avg_score": avg_score,
            "label": label,
            "prev_period_score": prev_score,
            "score_delta": delta,
            "model_version": SENTIMENT_MODEL_VERSION,
        })
        scored += 1

    logger.info("Scored %d filings", scored)
    return scored


def aggregate_daily_sentiment() -> int:
    """Compute daily avg/min/max sentiment per ticker from sentiment_scores and upsert."""
    from sqlalchemy import text as sql_text
    from data.storage.db_client import get_conn

    sql = sql_text("""
        SELECT
            ss.ticker,
            DATE(na.published_at)  AS date,
            AVG(ss.score)          AS avg_score,
            MIN(ss.score)          AS min_score,
            MAX(ss.score)          AS max_score,
            COUNT(*)               AS article_count,
            ROUND(100.0 * SUM(CASE WHEN ss.label = 'positive' THEN 1 ELSE 0 END) / COUNT(*), 2) AS positive_pct,
            ROUND(100.0 * SUM(CASE WHEN ss.label = 'negative' THEN 1 ELSE 0 END) / COUNT(*), 2) AS negative_pct,
            ROUND(100.0 * SUM(CASE WHEN ss.label = 'neutral'  THEN 1 ELSE 0 END) / COUNT(*), 2) AS neutral_pct
        FROM sentiment_scores ss
        JOIN news_articles na ON na.id = ss.article_id
        WHERE ss.article_id IS NOT NULL
        GROUP BY ss.ticker, DATE(na.published_at)
    """)

    with get_conn() as conn:
        result = conn.execute(sql)
        cols = list(result.keys())
        rows = result.fetchall()

    import pandas as pd
    df = pd.DataFrame(rows, columns=cols)

    if df.empty:
        logger.info("No sentiment data to aggregate")
        return 0

    records = df.to_dict("records")
    n = upsert_daily_sentiment_agg(records)
    logger.info("Upserted %d daily sentiment aggregation rows", n)
    return n


def run_full_pipeline(model_path: str | None = None) -> dict:
    """Run the complete sentiment pipeline: articles → filings → aggregation."""
    articles = score_articles(model_path=model_path)
    filings = score_filings(model_path=model_path)
    agg = aggregate_daily_sentiment()
    return {"articles_scored": articles, "filings_scored": filings, "daily_agg_rows": agg}


def _chunk_text(text: str, max_length: int = 2000) -> list[str]:
    """Split long text into overlapping chunks for inference."""
    words = text.split()
    chunk_size = max_length // 5
    overlap = chunk_size // 4
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start = end - overlap
    return chunks or [text[:max_length]]


def _score_to_label(score: float) -> str:
    if score > 0.15:
        return "positive"
    elif score < -0.15:
        return "negative"
    return "neutral"


def _get_prev_filing_score(ticker: str, current_period) -> float | None:
    """Look up the sentiment score of the previous filing for YoY comparison."""
    from sqlalchemy import text as sql_text
    from data.storage.db_client import get_conn

    sql = sql_text("""
        SELECT avg_score FROM filing_sentiment
        WHERE ticker = :ticker AND period < :period
        ORDER BY period DESC LIMIT 1
    """)
    with get_conn() as conn:
        result = conn.execute(sql, {"ticker": ticker, "period": current_period})
        row = result.fetchone()
        return float(row[0]) if row else None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    results = run_full_pipeline()
    print(f"Pipeline complete: {results}")
