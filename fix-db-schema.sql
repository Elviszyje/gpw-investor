-- Migration script to fix database schema issues
-- Run this if you encounter missing columns/tables errors

-- Fix health_check table if it exists without service_name column
DO $$
BEGIN
    -- Add service_name column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'health_check' 
        AND column_name = 'service_name'
    ) THEN
        ALTER TABLE health_check ADD COLUMN service_name VARCHAR(50) NOT NULL DEFAULT 'unknown';
        UPDATE health_check SET service_name = 'database' WHERE service_name = 'unknown';
    END IF;
    
    -- Ensure status column exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'health_check' 
        AND column_name = 'status'
    ) THEN
        ALTER TABLE health_check ADD COLUMN status VARCHAR(20) DEFAULT 'healthy';
    END IF;
    
    -- Ensure last_check column exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'health_check' 
        AND column_name = 'last_check'
    ) THEN
        ALTER TABLE health_check ADD COLUMN last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    END IF;
END$$;

-- Create ticker_mappings table if it doesn't exist
CREATE TABLE IF NOT EXISTS ticker_mappings (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    bankier_symbol VARCHAR(50),
    stooq_symbol VARCHAR(50),
    gpw_symbol VARCHAR(50),
    source VARCHAR(20) DEFAULT 'manual',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert some default ticker mappings if table is empty
INSERT INTO ticker_mappings (ticker, bankier_symbol, stooq_symbol, source) VALUES
    ('KGHM', 'kghm', 'kghm', 'auto'),
    ('PKN', 'pknorlen', 'pkn', 'auto'),
    ('CDR', 'cdr', 'cdr', 'auto'),
    ('JSW', 'jsw', 'jsw', 'auto'),
    ('LPP', 'lpp', 'lpp', 'auto'),
    ('PKNM', 'pknm', 'pknm', 'auto'),
    ('DIINO', 'diino', 'diino', 'auto'),
    ('MBANK', 'mbank', 'mbank', 'auto')
ON CONFLICT (ticker) DO NOTHING;

-- Ensure all tables have proper permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gpw_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gpw_user;

-- Update existing health check entry
INSERT INTO health_check (service_name, status) VALUES ('database', 'healthy')
ON CONFLICT DO NOTHING;
