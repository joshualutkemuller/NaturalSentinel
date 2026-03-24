-- Runs once on first database creation via postgres entrypoint.
-- The naturalsentinel database and sentinel user are created automatically
-- by POSTGRES_USER / POSTGRES_DB environment variables.

CREATE EXTENSION IF NOT EXISTS vector;
