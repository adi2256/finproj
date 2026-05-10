"""
DAG: nightly_sentiment
Schedule: Every night at 11 PM ET (03:00 UTC) after market close and news ingestion
Task graph:
    score_articles ──┐
                      ├──► aggregate_daily_sentiment
    score_filings  ──┘
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner":             "finance-pipeline",
    "depends_on_past":   False,
    "retries":           2,
    "retry_delay":       timedelta(minutes=5),
    "email_on_failure":  False,
    "execution_timeout": timedelta(hours=3),
}


def _sys_path_setup():
    import sys, os
    root = os.path.dirname(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)


def task_score_articles(**context):
    _sys_path_setup()
    from sentiment.inference import score_articles
    n = score_articles()
    print(f"Scored {n} articles")


def task_score_filings(**context):
    _sys_path_setup()
    from sentiment.inference import score_filings
    n = score_filings()
    print(f"Scored {n} filings")


def task_aggregate(**context):
    _sys_path_setup()
    from sentiment.inference import aggregate_daily_sentiment
    n = aggregate_daily_sentiment()
    print(f"Aggregated {n} daily sentiment rows")


with DAG(
    dag_id="nightly_sentiment",
    default_args=default_args,
    description="Score news articles and filings with FinBERT, aggregate daily sentiment",
    schedule_interval="0 3 * * 1-5",  # 03:00 UTC = 11 PM ET (weekdays)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["sentiment", "nightly"],
) as dag:

    articles_task = PythonOperator(
        task_id="score_articles",
        python_callable=task_score_articles,
    )

    filings_task = PythonOperator(
        task_id="score_filings",
        python_callable=task_score_filings,
    )

    aggregate_task = PythonOperator(
        task_id="aggregate_daily_sentiment",
        python_callable=task_aggregate,
    )

    [articles_task, filings_task] >> aggregate_task
