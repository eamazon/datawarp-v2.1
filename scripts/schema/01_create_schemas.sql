-- DataWarp v2 Schema Creation
-- Purpose: Create PostgreSQL schemas
-- Run: psql -d datawarp -f 01_create_schemas.sql

-- Create schemas if they don't exist
CREATE SCHEMA IF NOT EXISTS datawarp;
CREATE SCHEMA IF NOT EXISTS staging;

-- Grant permissions (adjust as needed)
GRANT USAGE ON SCHEMA datawarp TO PUBLIC;
GRANT USAGE ON SCHEMA staging TO PUBLIC;
GRANT ALL ON SCHEMA datawarp TO CURRENT_USER;
GRANT ALL ON SCHEMA staging TO CURRENT_USER;

\echo 'Schemas created successfully'