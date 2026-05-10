"""
DAG: feature_pipeline
Schedule: Runs after daily_ohlcv (triggered via TriggerDagRunOperator in that DAG,
          but also has its own 7:30 AM ET schedule as a safety net).

Task graph:
    compute_technical  ──┐
                          ├──► compute_analytics
    refresh_fundamental ─┘

Technical and fundamental are parallelised; analytics waits for both
because it reads from technical_features.
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
    "execution_timeout": timedelta(hours=2),
}


def _sys_path_setup():
    import sys, os
    root = os.path.dirname(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)


def task_technical(**context):
    _sys_path_setup()
    from features.pipeline import run_technical
    from datetime import date, timedelta
    start = (date.today() - timedelta(days=300)).isoformat()
    n = run_technical(start=start)
    print(f"Technical: {n} rows upserted")


def task_fundamental(**context):
    _sys_path_setup()
    from features.pipeline import run_fundamental
    n = run_fundamental()
    print(f"Fundamental: {n} rows upserted")


def task_analytics(**context):
    _sys_path_setup()
    from features.pipeline import run_analytics
    n = run_analytics(lookback_days=252)
    print(f"Sector analytics: {n} rows upserted")


with DAG(
    dag_id="feature_pipeline",
    default_args=default_args,
    description="Compute technical indicators, fundamental features, and sector analytics",
    schedule_interval="30 12 * * 1-5",   # 12:30 UTC = 7:30 AM ET (after daily_ohlcv at 11:30)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["features", "daily"],
) as dag:

    technical_task = PythonOperator(
        task_id="compute_technical",
        python_callable=task_technical,
    )

    fundamental_task = PythonOperator(
        task_id="refresh_fundamental",
        python_callable=task_fundamental,
    )

    analytics_task = PythonOperator(
        task_id="compute_analytics",
        python_callable=task_analytics,
    )

    # Analytics depends on both upstream stages completing
    [technical_task, fundamental_task] >> analytics_task
