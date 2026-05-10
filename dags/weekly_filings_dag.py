"""
DAG: weekly_filings
Schedule: Sunday night (so fresh filings are ready Monday morning)
Task: Check EDGAR for new 10-K and 10-Q filings for each ticker.
      Incremental — only stores filings not already in the DB (ON CONFLICT DO NOTHING).
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner":            "finance-pipeline",
    "depends_on_past":  False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=10),
    "email_on_failure": False,
    # SEC filings run can take a while — generous timeout
    "execution_timeout": timedelta(hours=3),
}

with DAG(
    dag_id="weekly_filings",
    default_args=default_args,
    description="Weekly SEC EDGAR 10-K/10-Q ingestion for all universe tickers",
    schedule_interval="0 2 * * 0",  # 02:00 UTC Sunday = 9 PM ET Saturday
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["sec", "filings", "weekly"],
) as dag:

    def ingest_filings(**context):
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from data.ingestion.sec_filings import run
        stored = run()
        print(f"Stored {stored} SEC filings")

    PythonOperator(
        task_id="fetch_sec_filings",
        python_callable=ingest_filings,
    )
