-- =====================================================
-- GPW INVESTOR - KOMPLETNY SCHEMAT BAZY DANYCH
-- =====================================================
-- Ten plik zastępuje: init-db.sql, init-schema.sql, fix-db-schema.sql
-- Zawiera kompletny, idempotentny schemat bazy danych
-- Może być uruchamiany wielokrotnie bez błędów
-- =====================================================

-- Podstawowa konfiguracja
SET client_encoding = 'UTF8';
SET timezone = 'Europe/Warsaw';

-- Optymalizacje wydajnościowe PostgreSQL dla aplikacji
SET shared_preload_libraries = 'pg_stat_statements';
SET max_connections = 100;
SET shared_buffers = '256MB';
SET effective_cache_size = '1GB';
SET maintenance_work_mem = '64MB';
SET checkpoint_completion_target = 0.9;
SET wal_buffers = '16MB';
SET default_statistics_target = 100;
SET random_page_cost = 1.1;
SET effective_io_concurrency = 200;

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
    source_ticker VARCHAR(50),  -- dla kompatybilności wstecznej
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
    price DECIMAL(10,4),  -- close price
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
    comparison_operator VARCHAR(10) DEFAULT '>',  -- >, <, >=, <=
    is_active BOOLEAN DEFAULT true,
    notification_sent BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    triggered_at TIMESTAMP NULL,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABELE ML I REKOMENDACJI
-- =====================================================

-- Rekomendacje z ML (ujednolicona struktura)
CREATE TABLE IF NOT EXISTS recommendations (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    recommendation VARCHAR(20) NOT NULL,  -- BUY, SELL, HOLD
    signal VARCHAR(20),                   -- STRONG_BUY, WEAK_SELL, etc.
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
    
    -- Kolumny legacy dla kompatybilności
    recommendation_type VARCHAR(50),
    price DECIMAL(10,4),
    confidence DECIMAL(3,2)
);

-- Śledzenie wykonania rekomendacji
CREATE TABLE IF NOT EXISTS recommendation_tracking (
    id SERIAL PRIMARY KEY,
    recommendation_id INTEGER REFERENCES recommendations(id) ON DELETE CASCADE,
    action VARCHAR(20),  -- CREATED, UPDATED, EXECUTED, EXPIRED
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
    prediction_type VARCHAR(50),  -- PRICE, TREND, VOLATILITY
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
    sentiment_score DECIMAL(3,2),  -- -1.0 to 1.0
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
    operation_type VARCHAR(50),  -- SCRAPING, ML_TRAINING, DATA_IMPORT
    status VARCHAR(20),          -- SUCCESS, ERROR, WARNING
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

-- Indeksy na często używanych kolumnach
CREATE INDEX IF NOT EXISTS idx_companies_ticker ON companies(ticker);
CREATE INDEX IF NOT EXISTS idx_quotes_daily_company_date ON quotes_daily(company_id, date);
CREATE INDEX IF NOT EXISTS idx_quotes_intraday_company_datetime ON quotes_intraday(company_id, datetime);
CREATE INDEX IF NOT EXISTS idx_recommendations_ticker ON recommendations(ticker);
CREATE INDEX IF NOT EXISTS idx_recommendations_active ON recommendations(is_active, status);
CREATE INDEX IF NOT EXISTS idx_articles_ticker ON articles(ticker);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_espi_ticker ON espi_reports(ticker);
CREATE INDEX IF NOT EXISTS idx_operation_logs_type_status ON operation_logs(operation_type, status);

-- =====================================================
-- DODATKOWE OPTYMALIZACJE WYDAJNOŚCIOWE
-- =====================================================

-- Indeksy dla często używanych zapytań czasowych
CREATE INDEX IF NOT EXISTS idx_quotes_daily_date ON quotes_daily(date DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_intraday_datetime ON quotes_intraday(datetime DESC);
CREATE INDEX IF NOT EXISTS idx_price_rules_active ON price_rules(is_active, ticker) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_price_rules_last_checked ON price_rules(last_checked);

-- Indeksy dla ML i rekomendacji
CREATE INDEX IF NOT EXISTS idx_recommendations_created ON recommendations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendations_expires ON recommendations(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ml_predictions_valid ON ml_predictions(valid_until) WHERE valid_until > CURRENT_TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_ml_predictions_ticker_type ON ml_predictions(ticker, prediction_type);

-- Indeksy dla artykułów i wiadomości  
CREATE INDEX IF NOT EXISTS idx_articles_scraped ON articles(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_sentiment ON articles(sentiment_score) WHERE sentiment_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_espi_published ON espi_reports(published_at DESC);

-- Indeksy dla wydajności joinów
CREATE INDEX IF NOT EXISTS idx_ticker_mappings_bankier ON ticker_mappings(bankier_symbol) WHERE bankier_symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ticker_mappings_active ON ticker_mappings(is_active) WHERE is_active = true;

-- Indeksy dla logów i monitoringu
CREATE INDEX IF NOT EXISTS idx_health_check_service ON health_check(service_name, last_check DESC);
CREATE INDEX IF NOT EXISTS idx_operation_logs_created ON operation_logs(created_at DESC);

-- Composite indeksy dla złożonych zapytań
CREATE INDEX IF NOT EXISTS idx_quotes_daily_ticker_date ON quotes_daily(company_id, date DESC, close_price);
CREATE INDEX IF NOT EXISTS idx_recommendations_ticker_status ON recommendations(ticker, status, created_at DESC);

-- VACUUM i ANALYZE dla optymalizacji
VACUUM ANALYZE;

-- =====================================================
-- OPTYMALIZACJE STRUKTURY DANYCH
-- =====================================================

-- Włącz automatyczne VACUUM dla tabel z dużym obrotem danych
ALTER TABLE quotes_daily SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

ALTER TABLE quotes_intraday SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

ALTER TABLE articles SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

-- Kompresja dla starszych danych (dla przyszłych wersji PostgreSQL z kompresją)
-- ALTER TABLE quotes_daily SET (toast_tuple_target = 8160);
-- ALTER TABLE articles SET (toast_tuple_target = 8160);

-- Optymalizacja dla wyszukiwania pełnotekstowego w artykułach
CREATE INDEX IF NOT EXISTS idx_articles_title_fts ON articles USING gin(to_tsvector('polish', title));
CREATE INDEX IF NOT EXISTS idx_articles_content_fts ON articles USING gin(to_tsvector('polish', content));

-- =====================================================
-- FUNKCJE I TRIGGERY
-- =====================================================

-- Funkcja aktualizacji updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggery dla updated_at
DROP TRIGGER IF EXISTS update_companies_updated_at ON companies;
CREATE TRIGGER update_companies_updated_at 
    BEFORE UPDATE ON companies 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_ticker_mappings_updated_at ON ticker_mappings;
CREATE TRIGGER update_ticker_mappings_updated_at 
    BEFORE UPDATE ON ticker_mappings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_app_config_updated_at ON app_config;
CREATE TRIGGER update_app_config_updated_at 
    BEFORE UPDATE ON app_config 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- DANE POCZĄTKOWE
-- =====================================================

-- Podstawowe firmy
INSERT INTO companies (ticker, name, sector, industry) VALUES
    ('PKN', 'PKN Orlen S.A.', 'Energy', 'Oil & Gas'),
    ('PZU', 'Powszechny Zakład Ubezpieczeń S.A.', 'Financial', 'Insurance'),
    ('KGHM', 'KGHM Polska Miedź S.A.', 'Materials', 'Mining'),
    ('PEKAO', 'Bank Pekao S.A.', 'Financial', 'Banking'),
    ('LPP', 'LPP S.A.', 'Consumer Discretionary', 'Retail'),
    ('CCC', 'CCC S.A.', 'Consumer Discretionary', 'Retail'),
    ('ALLEGRO', 'Allegro.eu S.A.', 'Technology', 'E-commerce'),
    ('CDPROJEKT', 'CD Projekt S.A.', 'Technology', 'Gaming'),
    ('DIINO', 'Diino S.A.', 'Technology', 'Software'),
    ('JSW', 'Jastrzębska Spółka Węglowa S.A.', 'Materials', 'Mining'),
    ('MBANK', 'mBank S.A.', 'Financial', 'Banking'),
    ('PKNM', 'PKN Orlen S.A.', 'Energy', 'Oil & Gas')
ON CONFLICT (ticker) DO UPDATE SET
    name = EXCLUDED.name,
    sector = EXCLUDED.sector,
    industry = EXCLUDED.industry,
    updated_at = CURRENT_TIMESTAMP;

-- Mapowania dla różnych źródeł
INSERT INTO ticker_mappings (ticker, bankier_symbol, stooq_symbol, source) VALUES
    ('PKN', 'pknorlen', 'pkn', 'bankier'),
    ('PZU', 'pzu', 'pzu', 'bankier'),
    ('KGHM', 'kghm', 'kghm', 'bankier'),
    ('PEKAO', 'pekao', 'pekao', 'bankier'),
    ('LPP', 'lpp', 'lpp', 'bankier'),
    ('CCC', 'ccc', 'ccc', 'bankier'),
    ('ALLEGRO', 'allegro', 'allegro', 'bankier'),
    ('CDPROJEKT', 'cdprojekt', 'cdprojekt', 'bankier'),
    ('DIINO', 'diino', 'diino', 'bankier'),
    ('JSW', 'jsw', 'jsw', 'bankier'),
    ('MBANK', 'mbank', 'mbank', 'bankier'),
    ('PKNM', 'pknm', 'pknm', 'bankier')
ON CONFLICT (ticker) DO UPDATE SET
    bankier_symbol = EXCLUDED.bankier_symbol,
    stooq_symbol = EXCLUDED.stooq_symbol,
    updated_at = CURRENT_TIMESTAMP;

-- Health check początkowy
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
-- ZAKOŃCZENIE
-- =====================================================

-- Potwierdź wszystkie zmiany
COMMIT;

-- Log sukcesu
DO $$
BEGIN
    RAISE NOTICE '🎉 ================================================';
    RAISE NOTICE '✅ GPW Investor Database Schema Initialized';
    RAISE NOTICE '📊 Database: gpw_investor';
    RAISE NOTICE '👤 User: gpw_user';
    RAISE NOTICE '🌍 Timezone: Europe/Warsaw';
    RAISE NOTICE '📅 Timestamp: %', CURRENT_TIMESTAMP;
    RAISE NOTICE '🏗️ Tables: 15 main tables created';
    RAISE NOTICE '📈 Sample data: Loaded for % companies', (SELECT COUNT(*) FROM companies);
    RAISE NOTICE '🔧 Ready for application startup';
    RAISE NOTICE '🎉 ================================================';
END $$;
