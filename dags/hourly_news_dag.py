"""
DAG: hourly_news
Schedule: Every hour during market hours (8 AM – 6 PM ET, weekdays)
Task: Pull articles published in the last 2h from NewsAPI and store to S3 + PostgreSQL.
      2h lookback (vs 1h interval) provides overlap so no articles fall through gaps.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner":            "finance-pipeline",
    "depends_on_past":  False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=3),
    "email_on_failure": False,
}

with DAG(
    dag_id="hourly_news",
    default_args=default_args,
    description="Hourly news ingestion from NewsAPI for all universe tickers",
    schedule_interval="0 13-23 * * 1-5",  # 13:00–23:00 UTC = 8 AM–6 PM ET
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["news", "hourly"],
) as dag:

    def ingest_news(**context):
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from data.ingestion.news_data import run
        stored = run(lookback_hours=2)
        print(f"Stored {stored} news articles")

    PythonOperator(
        task_id="fetch_news",
        python_callable=ingest_news,
    )
