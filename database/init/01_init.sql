-- FTIAS Database Initialization Script
-- PostgreSQL 15+

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search optimization

-- Create custom types
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('viewer', 'analyst', 'administrator');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Set timezone
SET timezone = 'UTC';

-- Create schema for application
CREATE SCHEMA IF NOT EXISTS ftias;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA ftias TO ftias_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ftias TO ftias_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA ftias TO ftias_user;

-- Create audit trigger function
CREATE OR REPLACE FUNCTION ftias.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'FTIAS database initialized successfully';
END $$;
