"""
DAG: daily_ohlcv
Schedule: 6:30 AM ET every weekday (market opens 9:30 AM; data for prior day is ready ~6 AM)
Task: Fetch previous day's OHLCV for all tickers and upsert into PostgreSQL.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

default_args = {
    "owner":            "finance-pipeline",
    "depends_on_past":  False,
    "retries":          3,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="daily_ohlcv",
    default_args=default_args,
    description="Ingest previous day OHLCV for all universe tickers",
    schedule_interval="30 11 * * 1-5",  # 11:30 UTC = 6:30 AM ET (weekdays only)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["price", "daily"],
) as dag:

    def ingest_ohlcv(**context):
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from data.ingestion.price_data import run_incremental
        inserted = run_incremental()
        print(f"Inserted {inserted} OHLCV rows")

    fetch = PythonOperator(
        task_id="fetch_ohlcv",
        python_callable=ingest_ohlcv,
    )

    trigger_features = TriggerDagRunOperator(
        task_id="trigger_feature_pipeline",
        trigger_dag_id="feature_pipeline",
        wait_for_completion=False,   # fire-and-forget; feature_pipeline has its own schedule too
    )

    fetch >> trigger_features
