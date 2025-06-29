-- GPW Investor - Database Initialization Script
-- This script will be executed when PostgreSQL container starts for the first time

-- Set proper encoding and timezone
SET client_encoding = 'UTF8';
SET timezone = 'Europe/Warsaw';

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create a simple health check table for monitoring
CREATE TABLE IF NOT EXISTS health_check (
    id SERIAL PRIMARY KEY,
    status VARCHAR(50) DEFAULT 'healthy',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial health check record
INSERT INTO health_check (status) VALUES ('database_initialized') ON CONFLICT DO NOTHING;

-- Note: Detailed table creation (quotes, companies, recommendations, etc.) 
-- will be handled by the application using SQLAlchemy models

-- Grant permissions to the application user
GRANT ALL PRIVILEGES ON DATABASE gpw_investor TO gpw_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gpw_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gpw_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO gpw_user;

-- Grant future permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO gpw_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO gpw_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON FUNCTIONS TO gpw_user;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE '✅ GPW Investor database initialized successfully at %', CURRENT_TIMESTAMP;
    RAISE NOTICE '📊 Database: gpw_investor';
    RAISE NOTICE '👤 User: gpw_user';
    RAISE NOTICE '🌍 Timezone: Europe/Warsaw';
END $$;
