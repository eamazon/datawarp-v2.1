-- DataWarp v2 Schema Teardown
-- Purpose: Drop all DataWarp tables and data
-- WARNING: This is destructive! Use only for testing/development
-- Run: psql -d datawarp -f 99_drop_all.sql
-- DataWarp v2 Schema Teardown
-- WARNING: This is destructive! Use only for testing/development
-- Run: psql -d datawarp -f 99_drop_all.sql

-- Drop registry tables (in reverse dependency order)
DROP TABLE IF EXISTS datawarp.tbl_column_metadata CASCADE;
DROP TABLE IF EXISTS datawarp.tbl_enrichment_api_calls CASCADE;
DROP TABLE IF EXISTS datawarp.tbl_enrichment_runs CASCADE;
DROP TABLE IF EXISTS datawarp.tbl_manifest_files CASCADE;
DROP TABLE IF EXISTS datawarp.tbl_pipeline_log CASCADE;
DROP TABLE IF EXISTS datawarp.tbl_load_history CASCADE;
DROP TABLE IF EXISTS datawarp.tbl_load_events CASCADE;
DROP TABLE IF EXISTS datawarp.tbl_data_sources CASCADE;

-- Drop all tables in staging schema (with visibility)
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'staging'
    LOOP
        EXECUTE 'DROP TABLE IF EXISTS staging.' || quote_ident(r.tablename) || ' CASCADE';
        RAISE NOTICE 'Dropped table: staging.%', r.tablename;
    END LOOP;
END $$;

-- Drop the staging schema itself
DROP SCHEMA IF EXISTS staging CASCADE;

\echo 'All DataWarp tables and staging schema dropped'