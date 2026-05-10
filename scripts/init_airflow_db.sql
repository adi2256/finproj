-- Creates the Airflow metadata database alongside financedb.
-- Called by docker-entrypoint-initdb.d on first container start.
CREATE DATABASE airflow_db;
GRANT ALL PRIVILEGES ON DATABASE airflow_db TO finance_user;
