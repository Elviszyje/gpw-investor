"""
Error handling utilities dla GPW Investor
Zawiera funkcje pomocnicze do obsługi błędów i graceful degradation
"""

import logging
from functools import wraps
from flask import jsonify, render_template, flash
from sqlalchemy.exc import SQLAlchemyError
import traceback

logger = logging.getLogger(__name__)

def handle_db_errors(fallback_template=None, fallback_data=None):
    """
    Decorator do obsługi błędów bazy danych z graceful degradation
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except SQLAlchemyError as e:
                logger.error(f"Database error in {func.__name__}: {e}")
                
                # Jeśli to endpoint API, zwróć JSON
                if '/api/' in str(func):
                    return jsonify({
                        'error': 'Database connection error',
                        'message': 'Database is not available. Please try again later.',
                        'status': 'error'
                    }), 500
                
                # Jeśli to endpoint web, pokaż template z komunikatem
                flash('⚠️ Problem z połączeniem do bazy danych. Spróbuj ponownie później.', 'warning')
                if fallback_template:
                    return render_template(fallback_template, **(fallback_data or {}))
                else:
                    return render_template('errors/500.html'), 500
                    
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {e}")
                logger.error(traceback.format_exc())
                
                if '/api/' in str(func):
                    return jsonify({
                        'error': 'Internal server error',
                        'message': 'An unexpected error occurred.',
                        'status': 'error'
                    }), 500
                
                flash('❌ Wystąpił nieoczekiwany błąd. Spróbuj ponownie.', 'danger')
                if fallback_template:
                    return render_template(fallback_template, **(fallback_data or {}))
                else:
                    return render_template('errors/500.html'), 500
        
        return wrapper
    return decorator

def safe_db_operation(operation, fallback_value=None, error_message="Database operation failed"):
    """
    Bezpieczne wykonanie operacji na bazie danych z fallback
    """
    try:
        return operation()
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        logger.error(traceback.format_exc())
        return fallback_value
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
        return fallback_value

def get_companies_safe():
    """
    Bezpieczne pobieranie listy spółek z fallback na przykładowe dane
    """
    from workers.quotes_daily import get_companies
    
    def _get_companies():
        return get_companies()
    
    companies = safe_db_operation(_get_companies, [])
    
    # Jeśli baza jest pusta, zwróć przykładowe dane
    if not companies:
        return [
            {'ticker': 'PKN', 'name': 'PKN Orlen S.A.'},
            {'ticker': 'PZU', 'name': 'Powszechny Zakład Ubezpieczeń S.A.'},
            {'ticker': 'KGHM', 'name': 'KGHM Polska Miedź S.A.'},
            {'ticker': 'PEKAO', 'name': 'Bank Pekao S.A.'},
            {'ticker': 'LPP', 'name': 'LPP S.A.'},
        ]
    
    return companies

def get_ticker_mappings_safe():
    """
    Bezpieczne pobieranie mapowań tickerów
    """
    try:
        from workers.quotes_daily import engine
        from sqlalchemy import text
        
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT ticker 
                FROM ticker_mappings 
                WHERE is_active = true
                ORDER BY ticker
            """))
            tickers = [row[0] for row in result.fetchall()]
            return tickers
    except Exception as e:
        logger.error(f"Error getting ticker mappings: {e}")
        # Fallback do podstawowych tickerów
        return ['PKN', 'PZU', 'KGHM', 'PEKAO', 'LPP', 'CCC', 'ALLEGRO', 'CDPROJEKT']

def get_daily_quotes_safe(ticker):
    """
    Bezpieczne pobieranie notowań dziennych
    """
    if not ticker:
        return []
        
    from workers.quotes_daily import get_daily_quotes
    
    def _get_quotes():
        return get_daily_quotes(ticker)
    
    quotes = safe_db_operation(_get_quotes, [])
    return quotes or []

def get_intraday_quotes_safe(ticker, limit=100):
    """
    Bezpieczne pobieranie notowań intraday
    """
    if not ticker:
        return []
        
    try:
        from workers.quotes_intraday import get_intraday_quotes
        return get_intraday_quotes(ticker, limit)
    except Exception as e:
        logger.error(f"Error getting intraday quotes: {e}")
        return []

def check_ml_availability():
    """
    Sprawdza dostępność bibliotek ML
    """
    try:
        import sklearn
        return True
    except ImportError:
        return False

def get_ml_status():
    """
    Zwraca status funkcjonalności ML
    """
    if not check_ml_availability():
        return {
            'available': False,
            'message': 'Machine Learning libraries not installed',
            'status': 'warning'
        }
    
    try:
        # Sprawdź czy są dostępne modele
        import os
        models_dir = 'models'
        if os.path.exists(models_dir) and os.listdir(models_dir):
            return {
                'available': True,
                'message': 'ML models available',
                'status': 'ready'
            }
        else:
            return {
                'available': True,
                'message': 'ML libraries available but no trained models',
                'status': 'not_trained'
            }
    except Exception as e:
        logger.error(f"Error checking ML status: {e}")
        return {
            'available': False,
            'message': 'ML status check failed',
            'status': 'error'
        }

def format_error_message(error_type, details=None):
    """
    Formatuje komunikaty błędów dla użytkownika
    """
    messages = {
        'db_connection': 'Problem z połączeniem do bazy danych. Sprawdź konfigurację.',
        'empty_data': 'Brak danych do wyświetlenia. Spróbuj zaimportować dane lub wybierz inny ticker.',
        'invalid_ticker': 'Nieprawidłowy symbol spółki. Sprawdź czy ticker jest poprawny.',
        'ml_not_available': 'Funkcje Machine Learning nie są dostępne. Skontaktuj się z administratorem.',
        'import_error': 'Błąd podczas importu danych. Sprawdź źródło danych i spróbuj ponownie.',
        'unknown': 'Wystąpił nieoczekiwany błąd. Spróbuj ponownie lub skontaktuj się z administratorem.'
    }
    
    base_message = messages.get(error_type, messages['unknown'])
    
    if details:
        return f"{base_message} Szczegóły: {details}"
    
    return base_message
