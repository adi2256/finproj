import os
from dotenv import load_dotenv

load_dotenv()

# --- Database ---
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DB_NAME = os.getenv("POSTGRES_DB", "financedb")
DB_USER = os.getenv("POSTGRES_USER", "finance_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "changeme")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# --- Storage backend ---
# "local"  → plain files on disk inside ./storage/  (default, zero setup)
# "minio"  → MinIO Docker container, S3-compatible, browser UI at :9001
# "b2"     → Backblaze B2 (S3-compatible, requires B2 app key)
# "s3"     → AWS S3 (requires real AWS credentials)
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")

# Local backend root (ignored when backend is minio/b2/s3)
STORAGE_ROOT = os.getenv("STORAGE_ROOT", "storage")

# MinIO settings (only used when STORAGE_BACKEND=minio)
MINIO_ENDPOINT         = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ROOT_USER        = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD    = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")

# Backblaze B2 settings (only used when STORAGE_BACKEND=b2)
B2_ENDPOINT            = os.getenv("B2_ENDPOINT", "")
B2_APPLICATION_KEY_ID  = os.getenv("B2_APPLICATION_KEY_ID", "")
B2_APPLICATION_KEY     = os.getenv("B2_APPLICATION_KEY", "")

# Used by boto3 for MinIO, B2, and AWS S3
AWS_REGION             = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID      = os.getenv("AWS_ACCESS_KEY_ID", MINIO_ROOT_USER)
AWS_SECRET_ACCESS_KEY  = os.getenv("AWS_SECRET_ACCESS_KEY", MINIO_ROOT_PASSWORD)
S3_BUCKET              = os.getenv("S3_BUCKET", "finance-data")

S3_PREFIXES = {
    "news":    "raw/news/",
    "filings": "raw/filings/",
    "models":  "models/",
}

# --- Sentiment model ---
SENTIMENT_MODEL_NAME = os.getenv("SENTIMENT_MODEL_NAME", "ProsusAI/finbert")
SENTIMENT_MODEL_VERSION = os.getenv("SENTIMENT_MODEL_VERSION", "finbert-finetuned-v1")
SENTIMENT_BATCH_SIZE = int(os.getenv("SENTIMENT_BATCH_SIZE", 32))
SENTIMENT_MAX_LENGTH = int(os.getenv("SENTIMENT_MAX_LENGTH", 512))

# --- API Keys ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")

# --- Ingestion settings ---
OHLCV_START_DATE = "2022-01-01"   # 2+ years of history
NEWS_LOOKBACK_HOURS = 2           # hourly DAG pulls last 2h to handle overlap

# --- Stock universe ---
SECTORS = {
    "Technology": [
        "AAPL", "MSFT", "NVDA", "META", "GOOGL",
        "AMD", "INTC", "CRM", "ADBE", "ORCL",
        "QCOM", "TXN", "AMAT", "MU", "KLAC",
        "NOW", "SNOW", "PANW", "CRWD", "ZS",
    ],
    "Healthcare": [
        "JNJ", "UNH", "LLY", "ABBV", "MRK",
        "TMO", "ABT", "DHR", "PFE", "AMGN",
        "GILD", "ISRG", "REGN", "VRTX", "BSX",
        "SYK", "ZTS", "DXCM", "IDXX", "IQV",
    ],
    "Financials": [
        "BRK-B", "JPM", "V", "MA", "BAC",
        "WFC", "GS", "MS", "AXP", "BLK",
        "SCHW", "CB", "PGR", "ICE", "CME",
        "MCO", "SPGI", "AON", "MMC", "TRV",
    ],
    "Consumer": [
        "AMZN", "TSLA", "HD", "MCD", "NKE",
        "SBUX", "TGT", "LOW", "COST", "TJX",
        "YUM", "CMG", "BKNG", "MAR", "HLT",
        "DPZ", "DKNG", "ABNB", "EBAY", "ETSY",
    ],
    "Energy": [
        "XOM", "CVX", "COP", "SLB", "EOG",
        "PXD", "MPC", "PSX", "VLO", "OXY",
        "HAL", "DVN", "BKR", "FANG", "HES",
        "KMI", "WMB", "LNG", "EQT", "AR",
    ],
}

ALL_TICKERS = [ticker for tickers in SECTORS.values() for ticker in tickers]
