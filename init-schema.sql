-- GPW Investor Database Schema
-- This script creates all necessary tables for the application

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Companies table
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255),
    sector VARCHAR(100),
    industry VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ticker mappings for data import
CREATE TABLE IF NOT EXISTS ticker_mappings (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    source_ticker VARCHAR(20),
    source VARCHAR(50) DEFAULT 'bankier',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily quotes
CREATE TABLE IF NOT EXISTS quotes_daily (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    open_price DECIMAL(10,4),
    high_price DECIMAL(10,4),
    low_price DECIMAL(10,4),
    close_price DECIMAL(10,4),
    volume BIGINT,
    turnover DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, date)
);

-- Intraday quotes
CREATE TABLE IF NOT EXISTS quotes_intraday (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    datetime TIMESTAMP NOT NULL,
    price DECIMAL(10,4),
    volume BIGINT,
    turnover DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Price alerts/rules
CREATE TABLE IF NOT EXISTS price_rules (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    threshold_value DECIMAL(10,4),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    triggered_at TIMESTAMP NULL
);

-- Recommendations
CREATE TABLE IF NOT EXISTS recommendations (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    recommendation_type VARCHAR(50),  -- legacy column
    recommendation VARCHAR(20),       -- new expected column
    signal VARCHAR(20),
    price DECIMAL(10,4),             -- legacy column  
    entry_price DECIMAL(10,4),       -- new expected column
    target_price DECIMAL(10,4),
    stop_loss DECIMAL(10,4),
    confidence DECIMAL(3,2),         -- legacy column
    buy_confidence DECIMAL(5,2),     -- new expected column
    sell_confidence DECIMAL(5,2),    -- new expected column
    signal_count INTEGER DEFAULT 0,  -- new expected column
    signals_data JSONB,              -- new expected column
    config_data JSONB,               -- new expected column
    reasoning TEXT,
    is_active BOOLEAN DEFAULT true,
    status VARCHAR(20) DEFAULT 'ACTIVE',  -- new expected column
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- ML predictions
CREATE TABLE IF NOT EXISTS ml_predictions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    model_name VARCHAR(100),
    prediction_type VARCHAR(50),
    predicted_value DECIMAL(10,4),
    confidence DECIMAL(3,2),
    input_features JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recommendation tracking table
CREATE TABLE IF NOT EXISTS recommendation_tracking (
    id SERIAL PRIMARY KEY,
    recommendation_id INTEGER NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    hours_after INTEGER NOT NULL,
    price DECIMAL(10,2) NOT NULL,             -- legacy column
    price_at_hour DECIMAL(10,2) NOT NULL,     -- expected column
    volume_at_hour BIGINT DEFAULT 0,
    profit_loss_percent DECIMAL(8,4),
    profit_loss_amount DECIMAL(10,2),
    tracked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recommendation_id) REFERENCES recommendations (id),
    UNIQUE(recommendation_id, hours_after)
);

-- Recommendation results table
CREATE TABLE IF NOT EXISTS recommendation_results (
    id SERIAL PRIMARY KEY,
    recommendation_id INTEGER NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    final_price DECIMAL(10,2),
    final_profit_loss_percent DECIMAL(8,4),   -- legacy column
    profit_loss_percent DECIMAL(8,4),         -- expected column
    final_profit_loss_amount DECIMAL(10,2),
    max_profit_percent DECIMAL(8,4) DEFAULT 0.0,
    max_loss_percent DECIMAL(8,4) DEFAULT 0.0,
    duration_hours INTEGER,
    was_successful BOOLEAN,                    -- legacy column
    success BOOLEAN,                           -- expected column
    evaluation_reason VARCHAR(100),            -- legacy column
    exit_reason VARCHAR(100),                  -- expected column
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recommendation_id) REFERENCES recommendations (id)
);

-- Daily stats table for recommendation performance
CREATE TABLE IF NOT EXISTS daily_stats (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_recommendations INTEGER DEFAULT 0,
    successful_count INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    avg_profit_loss DECIMAL(8,4) DEFAULT 0.0,
    avg_confidence DECIMAL(5,2) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notification settings
CREATE TABLE IF NOT EXISTS notification_settings (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) DEFAULT 'default',
    telegram_chat_id VARCHAR(50),
    email VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    notification_types JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Import jobs tracking
CREATE TABLE IF NOT EXISTS import_jobs (
    id SERIAL PRIMARY KEY,
    job_id UUID DEFAULT uuid_generate_v4(),
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    ticker VARCHAR(10),
    start_date DATE,
    end_date DATE,
    records_processed INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    error_details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_quotes_daily_company_date ON quotes_daily(company_id, date);
CREATE INDEX IF NOT EXISTS idx_quotes_intraday_company_datetime ON quotes_intraday(company_id, datetime);
CREATE INDEX IF NOT EXISTS idx_companies_ticker ON companies(ticker);
CREATE INDEX IF NOT EXISTS idx_ticker_mappings_ticker ON ticker_mappings(ticker);
CREATE INDEX IF NOT EXISTS idx_recommendations_ticker ON recommendations(ticker);
CREATE INDEX IF NOT EXISTS idx_recommendations_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recommendations_recommendation ON recommendations(recommendation);
CREATE INDEX IF NOT EXISTS idx_recommendation_tracking_rec_id ON recommendation_tracking(recommendation_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_tracking_hours ON recommendation_tracking(hours_after);
CREATE INDEX IF NOT EXISTS idx_recommendation_tracking_price_at_hour ON recommendation_tracking(price_at_hour);
CREATE INDEX IF NOT EXISTS idx_recommendation_results_success ON recommendation_results(success);
CREATE INDEX IF NOT EXISTS idx_recommendation_results_profit_loss ON recommendation_results(profit_loss_percent);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_ticker ON ml_predictions(ticker);

-- Insert some sample data
INSERT INTO companies (ticker, name, sector, industry) VALUES 
    ('PKN', 'PKN Orlen S.A.', 'Energy', 'Oil & Gas'),
    ('PKNM', 'PKN Orlen S.A. (prawa poboru)', 'Energy', 'Oil & Gas'),
    ('PZU', 'Powszechny Zakład Ubezpieczeń S.A.', 'Financial', 'Insurance'),
    ('KGHM', 'KGHM Polska Miedź S.A.', 'Materials', 'Mining'),
    ('PEKAO', 'Bank Pekao S.A.', 'Financial', 'Banking'),
    ('LPP', 'LPP S.A.', 'Consumer Discretionary', 'Retail'),
    ('CCC', 'CCC S.A.', 'Consumer Discretionary', 'Retail'),
    ('ALLEGRO', 'Allegro.eu S.A.', 'Technology', 'E-commerce'),
    ('CDPROJEKT', 'CD Projekt S.A.', 'Technology', 'Gaming'),
    ('DIINO', 'Diino S.A.', 'Technology', 'Software'),
    ('JSW', 'Jastrzębska Spółka Węglowa S.A.', 'Materials', 'Mining'),
    ('MBANK', 'mBank S.A.', 'Financial', 'Banking')
ON CONFLICT (ticker) DO NOTHING;

INSERT INTO ticker_mappings (ticker, source_ticker, source) VALUES
    ('PKN', 'pknorlen', 'bankier'),
    ('PZU', 'pzu', 'bankier'),
    ('KGHM', 'kghm', 'bankier'),
    ('PEKAO', 'pekao', 'bankier'),
    ('LPP', 'lpp', 'bankier'),
    ('CCC', 'ccc', 'bankier'),
    ('ALLEGRO', 'allegro', 'bankier'),
    ('CDPROJEKT', 'cdprojekt', 'bankier'),
    ('DIINO', 'diino', 'bankier'),
    ('JSW', 'jsw', 'bankier'),
    ('MBANK', 'mbank', 'bankier'),
    ('PKNM', 'pknm', 'bankier')
ON CONFLICT DO NOTHING;

-- Create health check table
CREATE TABLE IF NOT EXISTS health_check (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(50) NOT NULL,
    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'healthy'
);

INSERT INTO health_check (service_name, status) VALUES ('database', 'healthy')
ON CONFLICT DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gpw_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gpw_user;

-- Update timestamps function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at
DROP TRIGGER IF EXISTS update_companies_updated_at ON companies;
CREATE TRIGGER update_companies_updated_at 
    BEFORE UPDATE ON companies 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_ticker_mappings_updated_at ON ticker_mappings;
CREATE TRIGGER update_ticker_mappings_updated_at 
    BEFORE UPDATE ON ticker_mappings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;
