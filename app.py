"""
Główny plik aplikacji Flask GPW Investor - Zrefaktoryzowany
Używa Flask Blueprints do organizacji kodu w logiczne moduły.

Struktura modułów:
- data_ops: podstawowe operacje na danych (quotes, rules)
- recommendations: rekomendacje, skanowanie rynku, tracking
- ml: machine learning, market pattern ML, training, prediction
- scrapers: selenium scraper, schedulers, news, communications
- import_config: import danych, zarządzanie tickerami, konfiguracja
- notifications: powiadomienia Telegram, alerty cenowe
"""

from flask import Flask, render_template
import logging
import os

# Import wszystkich blueprintów
from blueprints.data_ops import data_ops_bp
from blueprints.recommendations import recommendations_bp
from blueprints.ml import ml_bp
from blueprints.scrapers import scrapers_bp
from blueprints.import_config import import_config_bp
from blueprints.notifications import notifications_bp

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Utworzenie aplikacji Flask
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey-change-in-production')  # zmienne środowiskowe

# ================================
# REJESTRACJA BLUEPRINTÓW
# ================================

# Data Operations - podstawowe operacje na danych
app.register_blueprint(data_ops_bp)

# Recommendations - rekomendacje i analiza rynku
app.register_blueprint(recommendations_bp)

# Machine Learning - wszystkie funkcjonalności ML
app.register_blueprint(ml_bp)

# Scrapers - selenium, schedulers, news, communications
app.register_blueprint(scrapers_bp)

# Import/Config - zarządzanie danymi, import, konfiguracja
app.register_blueprint(import_config_bp)

# Notifications - powiadomienia i alerty
app.register_blueprint(notifications_bp)

# ================================
# GŁÓWNY ENDPOINT
# ================================

@app.route("/")
def index():
    """Strona główna aplikacji"""
    return render_template("index.html")

# ================================
# POMOCNICZE FUNKCJE
# ================================

def get_app_stats():
    """Zwraca podstawowe statystyki aplikacji"""
    try:
        import threading
        import psutil
        import os
        from datetime import datetime
        
        # Metryki systemu
        active_threads = threading.active_count()
        
        try:
            process = psutil.Process(os.getpid())
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            uptime = datetime.now() - datetime.fromtimestamp(process.create_time())
            uptime_str = f"{int(uptime.total_seconds() // 3600)}h {int((uptime.total_seconds() % 3600) // 60)}m"
        except:
            cpu_percent = 0
            memory_mb = 0
            uptime_str = "N/A"
        
        # Sprawdź liczbę zarejestrowanych endpointów
        endpoint_count = len(app.url_map._rules)
        
        return {
            'system': {
                'active_threads': active_threads,
                'cpu_percent': cpu_percent,
                'memory_mb': round(memory_mb, 1),
                'uptime': uptime_str
            },
            'app': {
                'endpoint_count': endpoint_count,
                'blueprints': len(app.blueprints),
                'debug_mode': app.debug
            },
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Błąd pobierania statystyk aplikacji: {e}")
        return {'error': str(e)}

@app.route("/api/app/stats")
def api_app_stats():
    """API endpoint dla statystyk aplikacji"""
    from flask import jsonify
    stats = get_app_stats()
    return jsonify(stats)

@app.route("/api/app/health")
def api_health_check():
    """Health check endpoint"""
    from flask import jsonify
    try:
        # Sprawdź podstawowe componenty
        health_status = {
            'status': 'healthy',
            'services': {
                'database': 'unknown',
                'schedulers': 'unknown',
                'ml_models': 'unknown'
            },
            'timestamp': 'unknown'
        }
        
        # Sprawdź połączenie z bazą danych
        try:
            from workers.quotes_daily import get_companies
            companies = get_companies()
            health_status['services']['database'] = 'healthy' if len(companies) > 0 else 'warning'
        except Exception as e:
            health_status['services']['database'] = f'error: {str(e)[:50]}'
        
        # Sprawdź schedulery
        try:
            from scheduler.multi_ticker_scheduler import get_scheduler_status
            scheduler_status = get_scheduler_status()
            health_status['services']['schedulers'] = 'healthy' if scheduler_status.get('is_running') else 'stopped'
        except Exception as e:
            health_status['services']['schedulers'] = f'error: {str(e)[:50]}'
        
        # Sprawdź modele ML
        try:
            from workers.market_pattern_ml import MarketPatternML
            ml_model = MarketPatternML()
            health_status['services']['ml_models'] = 'trained' if ml_model.is_trained else 'not_trained'
        except Exception as e:
            health_status['services']['ml_models'] = f'error: {str(e)[:50]}'
        
        from datetime import datetime
        health_status['timestamp'] = datetime.now().isoformat()
        
        # Określ ogólny status
        if any('error' in str(status) for status in health_status['services'].values()):
            health_status['status'] = 'degraded'
        
        return jsonify(health_status)
        
    except Exception as e:
        from flask import jsonify
        from datetime import datetime
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ================================
# ERROR HANDLERS
# ================================

@app.errorhandler(404)
def not_found_error(error):
    """Handler dla błędów 404"""
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handler dla błędów 500"""
    logger.error(f"Internal server error: {error}")
    return render_template('errors/500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """Ogólny handler dla nieoczekiwanych błędów"""
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    
    # Dla development - pokazuj szczegóły błędu
    if app.debug:
        raise e
    
    # Dla production - pokazuj ogólny błąd
    return render_template('errors/500.html'), 500

# ================================
# CONTEXT PROCESSORS
# ================================

@app.context_processor
def inject_app_info():
    """Wstrzykuje informacje o aplikacji do wszystkich szablonów"""
    return {
        'app_name': 'GPW Investor',
        'app_version': '2.0.0',
        'blueprint_count': len(app.blueprints),
        'endpoint_count': len(app.url_map._rules)
    }

# ================================
# FUNKCJA GŁÓWNA
# ================================

def main():
    """Główna funkcja uruchamiająca aplikację"""
    
    # Wyświetl informacje o startupie
    logger.info("🚀 Starting GPW Investor Application (Refactored)")
    logger.info(f"📦 Registered {len(app.blueprints)} blueprints:")
    
    for blueprint_name in app.blueprints:
        logger.info(f"   - {blueprint_name}")
    
    logger.info(f"🔗 Total endpoints: {len(app.url_map._rules)}")
    
    # Sprawdź czy są dostępne podstawowe moduły
    try:
        from workers.quotes_daily import get_companies
        companies_count = len(get_companies())
        logger.info(f"📊 Database: {companies_count} companies available")
    except Exception as e:
        logger.warning(f"⚠️ Database connection issue: {e}")
    
    try:
        from workers.market_pattern_ml import MarketPatternML
        ml_model = MarketPatternML()
        ml_status = "trained" if ml_model.is_trained else "not trained"
        logger.info(f"🤖 ML Model status: {ml_status}")
    except Exception as e:
        logger.warning(f"⚠️ ML Model issue: {e}")
    
    # Uruchom aplikację
    logger.info("🌐 Starting Flask development server...")
    app.run(debug=True, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
