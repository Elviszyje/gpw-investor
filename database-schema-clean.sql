-- =====================================================
-- GPW INVESTOR - CLEAN DATABASE SCHEMA (Production)
-- =====================================================
-- Wersja produkcyjna bez RAISE NOTICE - kompatybilna z PostgreSQL
-- Idempotentna - można uruchamiać wielokrotnie
-- =====================================================

-- Podstawowa konfiguracja
SET client_encoding = 'UTF8';
SET timezone = 'Europe/Warsaw';

-- Optymalizacje wydajnościowe PostgreSQL
SET shared_buffers = '256MB';
SET effective_cache_size = '1GB';
SET maintenance_work_mem = '64MB';

-- Wyłącz automatyczny commit dla atomowości
BEGIN;

-- Rozszerzenia
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- GŁÓWNE TABELE APLIKACJI
-- =====================================================

-- Tabela firm
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255),
    sector VARCHAR(100),
    industry VARCHAR(100),
    data_source VARCHAR(50) DEFAULT 'manual',
    first_data_date DATE,
    last_data_date DATE,
    total_records INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Mapowania tickerów dla różnych źródeł danych
CREATE TABLE IF NOT EXISTS ticker_mappings (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    bankier_symbol VARCHAR(50),
    stooq_symbol VARCHAR(50),
    gpw_symbol VARCHAR(50),
    source_ticker VARCHAR(50),
    source VARCHAR(20) DEFAULT 'manual',
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notowania dzienne
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

-- Notowania intraday
CREATE TABLE IF NOT EXISTS quotes_intraday (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    datetime TIMESTAMP NOT NULL,
    open_price DECIMAL(10,4),
    high_price DECIMAL(10,4),
    low_price DECIMAL(10,4),
    price DECIMAL(10,4),
    volume BIGINT,
    turnover DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, datetime)
);

-- Reguły alertów cenowych
CREATE TABLE IF NOT EXISTS price_rules (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    threshold_value DECIMAL(10,4),
    comparison_operator VARCHAR(10) DEFAULT '>',
    is_active BOOLEAN DEFAULT true,
    notification_sent BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    triggered_at TIMESTAMP NULL,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABELE ML I REKOMENDACJI
-- =====================================================

-- Rekomendacje z ML
CREATE TABLE IF NOT EXISTS recommendations (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    recommendation VARCHAR(20) NOT NULL,
    signal VARCHAR(20),
    entry_price DECIMAL(10,4),
    target_price DECIMAL(10,4),
    stop_loss DECIMAL(10,4),
    buy_confidence DECIMAL(5,2),
    sell_confidence DECIMAL(5,2),
    signal_count INTEGER DEFAULT 0,
    signals_data JSONB,
    config_data JSONB,
    reasoning TEXT,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    recommendation_type VARCHAR(50),
    price DECIMAL(10,4),
    confidence DECIMAL(3,2)
);

-- Śledzenie wykonania rekomendacji
CREATE TABLE IF NOT EXISTS recommendation_tracking (
    id SERIAL PRIMARY KEY,
    recommendation_id INTEGER REFERENCES recommendations(id) ON DELETE CASCADE,
    action VARCHAR(20),
    old_values JSONB,
    new_values JSONB,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Wyniki rekomendacji
CREATE TABLE IF NOT EXISTS recommendation_results (
    id SERIAL PRIMARY KEY,
    recommendation_id INTEGER REFERENCES recommendations(id) ON DELETE CASCADE,
    executed_at TIMESTAMP,
    execution_price DECIMAL(10,4),
    profit_loss DECIMAL(10,4),
    profit_loss_percent DECIMAL(5,2),
    duration_days INTEGER,
    success BOOLEAN,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Predykcje ML
CREATE TABLE IF NOT EXISTS ml_predictions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    model_name VARCHAR(100),
    prediction_type VARCHAR(50),
    predicted_value DECIMAL(10,4),
    confidence DECIMAL(5,2),
    prediction_horizon_days INTEGER DEFAULT 1,
    features_data JSONB,
    model_version VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP
);

-- =====================================================
-- TABELE WIADOMOŚCI I ANALIZ
-- =====================================================

-- Artykuły i wiadomości
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    url VARCHAR(500),
    source VARCHAR(100),
    author VARCHAR(200),
    published_at TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ticker VARCHAR(10),
    sentiment_score DECIMAL(3,2),
    is_processed BOOLEAN DEFAULT false
);

-- Komunikaty ESPI
CREATE TABLE IF NOT EXISTS espi_reports (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    report_number VARCHAR(50),
    title TEXT,
    content TEXT,
    published_at TIMESTAMP,
    report_type VARCHAR(100),
    is_current BOOLEAN DEFAULT true,
    url VARCHAR(500),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABELE SYSTEMOWE
-- =====================================================

-- Health check dla monitorowania
CREATE TABLE IF NOT EXISTS health_check (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'healthy',
    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Logi operacji
CREATE TABLE IF NOT EXISTS operation_logs (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(50),
    status VARCHAR(20),
    message TEXT,
    details JSONB,
    duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Konfiguracja aplikacji
CREATE TABLE IF NOT EXISTS app_config (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- INDEKSY DLA WYDAJNOŚCI
-- =====================================================

-- Podstawowe indeksy
CREATE INDEX IF NOT EXISTS idx_companies_ticker ON companies(ticker);
CREATE INDEX IF NOT EXISTS idx_quotes_daily_company_date ON quotes_daily(company_id, date);
CREATE INDEX IF NOT EXISTS idx_quotes_intraday_company_datetime ON quotes_intraday(company_id, datetime);
CREATE INDEX IF NOT EXISTS idx_recommendations_ticker ON recommendations(ticker);
CREATE INDEX IF NOT EXISTS idx_recommendations_active ON recommendations(is_active, status);
CREATE INDEX IF NOT EXISTS idx_articles_ticker ON articles(ticker);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_espi_ticker ON espi_reports(ticker);
CREATE INDEX IF NOT EXISTS idx_operation_logs_type_status ON operation_logs(operation_type, status);

-- Indeksy wydajnościowe
CREATE INDEX IF NOT EXISTS idx_quotes_daily_date ON quotes_daily(date DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_intraday_datetime ON quotes_intraday(datetime DESC);
CREATE INDEX IF NOT EXISTS idx_price_rules_active ON price_rules(is_active, ticker) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_price_rules_last_checked ON price_rules(last_checked);
CREATE INDEX IF NOT EXISTS idx_recommendations_created ON recommendations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendations_expires ON recommendations(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ml_predictions_valid ON ml_predictions(valid_until) WHERE valid_until > CURRENT_TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_ml_predictions_ticker_type ON ml_predictions(ticker, prediction_type);
CREATE INDEX IF NOT EXISTS idx_articles_scraped ON articles(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_sentiment ON articles(sentiment_score) WHERE sentiment_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_espi_published ON espi_reports(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_ticker_mappings_bankier ON ticker_mappings(bankier_symbol) WHERE bankier_symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ticker_mappings_active ON ticker_mappings(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_health_check_service ON health_check(service_name, last_check DESC);
CREATE INDEX IF NOT EXISTS idx_operation_logs_created ON operation_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_daily_ticker_date ON quotes_daily(company_id, date DESC, close_price);
CREATE INDEX IF NOT EXISTS idx_recommendations_ticker_status ON recommendations(ticker, status, created_at DESC);

-- =====================================================
-- DANE PRZYKŁADOWE I KONFIGURACJA
-- =====================================================

-- Przykładowe firmy GPW
INSERT INTO companies (ticker, name, sector, industry, data_source) VALUES
    ('PKN', 'PKN Orlen S.A.', 'Energy', 'Oil & Gas', 'manual'),
    ('PKO', 'PKO Bank Polski S.A.', 'Financial', 'Banking', 'manual'),
    ('PZU', 'Powszechny Zakład Ubezpieczeń S.A.', 'Financial', 'Insurance', 'manual'),
    ('LPP', 'LPP S.A.', 'Consumer Discretionary', 'Retail', 'manual'),
    ('CDR', 'CD Projekt S.A.', 'Communication Services', 'Entertainment', 'manual'),
    ('ALE', 'Allegro.eu S.A.', 'Consumer Discretionary', 'E-commerce', 'manual'),
    ('JSW', 'Jastrzębska Spółka Węglowa S.A.', 'Materials', 'Mining', 'manual'),
    ('CCC', 'CCC S.A.', 'Consumer Discretionary', 'Footwear', 'manual'),
    ('DNP', 'Dino Polska S.A.', 'Consumer Staples', 'Food Retail', 'manual'),
    ('PEP', 'Pepco Group N.V.', 'Consumer Discretionary', 'Retail', 'manual')
ON CONFLICT (ticker) DO NOTHING;

-- Przykładowe mapowania
INSERT INTO ticker_mappings (ticker, bankier_symbol, stooq_symbol, gpw_symbol, source) VALUES
    ('PKN', 'PKN', 'PKN.WA', 'PKNORLEN', 'manual'),
    ('PKO', 'PKO', 'PKO.WA', 'PKOBP', 'manual'),
    ('PZU', 'PZU', 'PZU.WA', 'PZU', 'manual'),
    ('LPP', 'LPP', 'LPP.WA', 'LPP', 'manual'),
    ('CDR', 'CDR', 'CDR.WA', 'CDPROJEKT', 'manual')
ON CONFLICT (ticker) DO NOTHING;

-- Health check initial data
INSERT INTO health_check (service_name, status, details) VALUES 
    ('database', 'healthy', '{"initialized_at": "' || CURRENT_TIMESTAMP || '"}'),
    ('schema', 'ready', '{"version": "1.0", "tables": 15}')
ON CONFLICT DO NOTHING;

-- Podstawowa konfiguracja
INSERT INTO app_config (config_key, config_value, description) VALUES
    ('app_version', '1.0.0', 'Current application version'),
    ('db_schema_version', '1.0', 'Database schema version'),
    ('default_scraping_interval', '300', 'Default scraping interval in seconds'),
    ('max_recommendations_per_ticker', '5', 'Maximum active recommendations per ticker'),
    ('ml_prediction_horizon_days', '7', 'Default ML prediction horizon')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    updated_at = CURRENT_TIMESTAMP;

-- =====================================================
-- UPRAWNIENIA
-- =====================================================

-- Przyznaj wszystkie uprawnienia użytkownikowi aplikacji
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gpw_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gpw_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO gpw_user;

-- Przyszłe uprawnienia
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO gpw_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO gpw_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON FUNCTIONS TO gpw_user;

-- =====================================================
-- MIGRACJE SCHEMATÓW (IDEMPOTENTNE)
-- =====================================================

-- Dodaj brakujące kolumny do tabeli companies
DO $$
BEGIN
    -- Dodaj kolumnę data_source
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'data_source') THEN
        ALTER TABLE companies ADD COLUMN data_source VARCHAR(50) DEFAULT 'manual';
    END IF;
    
    -- Dodaj kolumnę first_data_date
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'first_data_date') THEN
        ALTER TABLE companies ADD COLUMN first_data_date DATE;
    END IF;
    
    -- Dodaj kolumnę last_data_date
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'last_data_date') THEN
        ALTER TABLE companies ADD COLUMN last_data_date DATE;
    END IF;
    
    -- Dodaj kolumnę total_records
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'total_records') THEN
        ALTER TABLE companies ADD COLUMN total_records INTEGER DEFAULT 0;
    END IF;
    
    -- Aktualizacja istniejących rekordów
    UPDATE companies SET data_source = 'manual' WHERE data_source IS NULL OR data_source = '';
END $$;

-- VACUUM i ANALYZE dla optymalizacji
VACUUM ANALYZE;

-- Potwierdź wszystkie zmiany
COMMIT;
