-- ============================================================
-- Migration 003 — Update s3_path references for Backblaze B2
--
-- Run AFTER migrating objects with: python scripts/migrate_minio_to_b2.py
--
-- If your B2 bucket has the SAME name as MinIO (e.g. both "finance-data"),
-- the s3:// paths are already valid — run this as a no-op safety check.
--
-- If your B2 bucket has a DIFFERENT name, set the variables below:
--   OLD_BUCKET = your MinIO bucket name   (default: finance-data)
--   NEW_BUCKET = your B2 bucket name      (change this)
--
-- Usage:
--   psql -U finance_user -d financedb \
--     -v old_bucket="'finance-data'" \
--     -v new_bucket="'my-b2-bucket'" \
--     -f db/migrations/003_update_s3_paths_for_b2.sql
--
-- Or with same bucket name (no-op verification):
--   psql -U finance_user -d financedb \
--     -f db/migrations/003_update_s3_paths_for_b2.sql
-- ============================================================

BEGIN;

-- Default: same bucket name, paths stay unchanged
-- Override with -v old_bucket="'X'" -v new_bucket="'Y'" on the psql command line
\set fallback_old 'finance-data'
\set fallback_new 'finance-data'

DO $$
DECLARE
    v_old_bucket TEXT := :'fallback_old';
    v_new_bucket TEXT := :'fallback_new';
    affected_news    INT;
    affected_filings INT;
BEGIN
    IF v_old_bucket = v_new_bucket THEN
        RAISE NOTICE 'Bucket names are identical (%). No path updates needed.', v_old_bucket;
        RETURN;
    END IF;

    RAISE NOTICE 'Updating s3_path references: s3://% → s3://%', v_old_bucket, v_new_bucket;

    -- Update news_articles.s3_path
    UPDATE news_articles
    SET s3_path = REPLACE(s3_path, 's3://' || v_old_bucket || '/', 's3://' || v_new_bucket || '/')
    WHERE s3_path LIKE 's3://' || v_old_bucket || '/%';

    GET DIAGNOSTICS affected_news = ROW_COUNT;
    RAISE NOTICE 'Updated % rows in news_articles', affected_news;

    -- Update filings.s3_path
    UPDATE filings
    SET s3_path = REPLACE(s3_path, 's3://' || v_old_bucket || '/', 's3://' || v_new_bucket || '/')
    WHERE s3_path LIKE 's3://' || v_old_bucket || '/%';

    GET DIAGNOSTICS affected_filings = ROW_COUNT;
    RAISE NOTICE 'Updated % rows in filings', affected_filings;

    RAISE NOTICE 'Total paths updated: %', affected_news + affected_filings;
END $$;

COMMIT;
