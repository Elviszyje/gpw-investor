"""
Machine Learning Blueprint - wszystkie funkcjonalności ML
Obsługuje: market pattern ML, simple ML, integrated ML, training, prediction, backtesting
"""

from flask import Blueprint, render_template, request, jsonify, flash
from datetime import datetime
import logging
from utils.error_handlers import (
    handle_db_errors, get_ml_status, check_ml_availability, 
    format_error_message, get_companies_safe
)

ml_bp = Blueprint('ml', __name__)
logger = logging.getLogger(__name__)

def _get_ml_feature_engine():
    """Lazy import ML features"""
    if not check_ml_availability():
        raise ImportError("ML libraries not available")
    from workers.simple_ml_features import SimpleMLFeatures
    return SimpleMLFeatures()

def _get_ml_model():
    """Lazy import ML model"""
    if not check_ml_availability():
        raise ImportError("ML libraries not available")
    from workers.simple_ml_model import SimpleMLModel
    return SimpleMLModel()

def _get_ml_integrated_engine():
    """Lazy import ML integrated engine"""
    if not check_ml_availability():
        raise ImportError("ML libraries not available")
    from workers.ml_integrated_engine import MLIntegratedEngine
    return MLIntegratedEngine()

def _get_market_pattern_ml():
    """Lazy import Market Pattern ML"""
    if not check_ml_availability():
        raise ImportError("ML libraries not available")
    from workers.market_pattern_ml import MarketPatternML
    return MarketPatternML()

def handle_ml_errors(func):
    """Decorator do obsługi błędów ML z graceful degradation"""
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ImportError as e:
            logger.warning(f"ML libraries not available in {func.__name__}: {e}")
            return jsonify({
                'success': False,
                'error': 'ML libraries not available',
                'message': 'Biblioteki Machine Learning nie są zainstalowane. Funkcjonalność ML jest wyłączona.',
                'status': 'unavailable'
            }), 503
        except Exception as e:
            logger.error(f"ML error in {func.__name__}: {e}")
            return jsonify({
                'success': False,
                'error': 'ML operation failed',
                'message': f'Błąd funkcjonalności ML: {str(e)}',
                'status': 'error'
            }), 500
    
    return wrapper

@ml_bp.route("/ml")
@handle_db_errors(fallback_template="ml_panel.html")
def ml_panel():
    """Panel ML z sprawdzeniem dostępności"""
    ml_status = get_ml_status()
    companies = get_companies_safe()
    return render_template("ml_panel.html", ml_status=ml_status, companies=companies)

@ml_bp.route("/market-pattern")
@handle_db_errors(fallback_template="market_pattern.html")
def market_pattern_panel():
    """Panel Market Pattern ML z sprawdzeniem dostępności"""
    ml_status = get_ml_status()
    companies = get_companies_safe()
    
    if not ml_status['available']:
        flash(f"⚠️ {ml_status['message']}", "warning")
    
    return render_template("market_pattern.html", ml_status=ml_status, companies=companies)

# ================================
# SIMPLE ML API ENDPOINTS
# ================================

@ml_bp.route("/api/ml/scan", methods=["GET"])
def api_ml_scan():
    """
    Endpoint do skanowania rynku z wykorzystaniem ML
    """
    # Sprawdź dostępność ML
    if not check_ml_availability():
        return jsonify({
            'success': False,
            'error': 'Machine Learning libraries not available',
            'message': 'Biblioteki ML nie są zainstalowane. Skontaktuj się z administratorem.'
        }), 503
    
    try:
        feature_engineer = _get_ml_feature_engine()
        
        tickers = request.args.getlist('ticker')
        if not tickers:
            # Użyj bezpiecznych funkcji do pobrania tickerów
            companies = get_companies_safe()
            tickers = [c['ticker'] for c in companies[:5]]  # Weź pierwsze 5
            
            if not tickers:
                return jsonify({
                    'success': False,
                    'error': 'Brak dostępnych tickerów w bazie danych'
                }), 400
        
        ml_engine = _get_ml_integrated_engine()
        recommendations = []
        
        for ticker in tickers:
            try:
                rec = ml_engine.get_integrated_recommendation(ticker)
                if rec:
                    recommendations.append(rec)
            except Exception as e:
                logger.error(f"Błąd ML dla {ticker}: {e}")
                continue
        
        return jsonify({
            'success': True,
            'recommendations': recommendations,
            'count': len(recommendations),
            'ml_enabled': True,
            'tickers_scanned': tickers,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Błąd ML scan: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ml_bp.route("/api/ml/prediction", methods=["POST"])
def api_ml_prediction():
    """
    Endpoint do predykcji ML dla konkretnego tickera
    """
    try:
        data = request.get_json()
        ticker = data.get('ticker')
        date = data.get('date')  # Opcjonalnie użytkownik może podać datę
        
        if not ticker:
            return jsonify({
                'success': False,
                'error': 'Brak parametru ticker'
            }), 400
        
        # Jeśli nie podano daty, użyj najnowszej dostępnej
        if not date:
            feature_engineer = _get_ml_feature_engine()
            available_dates = feature_engineer.get_available_dates([ticker], days_back=7)
            if not available_dates:
                return jsonify({
                    'success': False,
                    'error': f'Brak dostępnych danych dla tickera {ticker}'
                }), 400
            date = available_dates[0]  # Najnowsza data
        
        ml_model = _get_ml_model()
        
        # Sprawdź czy model istnieje
        if not ml_model.load_model():
            return jsonify({
                'success': False,
                'error': 'Model ML nie został jeszcze wytrenowany'
            }), 404
        
        # Wykonaj predykcję dla konkretnej daty
        prediction = ml_model.predict_intraday(ticker, date)
        
        return jsonify({
            'success': True,
            'ticker': ticker,
            'date': date,
            'prediction': prediction,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Błąd predykcji ML: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ml_bp.route("/api/ml/train", methods=["POST"])
def api_ml_train():
    """
    Endpoint do trenowania modelu ML
    """
    try:
        data = request.get_json() or {}
        tickers = data.get('tickers', ['CDR', 'PKN', 'CCC'])
        days_back = data.get('days_back', 30)
        force_retrain = data.get('force_retrain', False)
        
        ml_model = _get_ml_model()
        
        # Sprawdź czy model już istnieje i czy force_retrain=False
        if not force_retrain and ml_model.load_model():
            return jsonify({
                'success': True,
                'message': 'Model już istnieje. Użyj force_retrain=true aby przeuczyć.',
                'model_exists': True,
                'timestamp': datetime.now().isoformat()
            })
        
        # Przygotuj dane treningowe
        feature_engineer = _get_ml_feature_engine()
        
        # Pobierz dostępne daty
        available_dates = feature_engineer.get_available_dates(tickers, days_back)
        
        if not available_dates:
            return jsonify({
                'success': False,
                'error': f'Brak dostępnych danych dla tickerów {tickers} w ostatnich {days_back} dniach'
            }), 400
        
        # Przygotuj dane treningowe z dostępnych dat
        X, y = feature_engineer.prepare_training_data(tickers, available_dates)
        
        if len(X) == 0:
            return jsonify({
                'success': False,
                'error': 'Nie udało się przygotować danych treningowych z dostępnych dat'
            }), 400
        
        # Trenuj model
        results = ml_model.train_model(X, y)
        
        return jsonify({
            'success': True,
            'training_results': results,
            'tickers_trained': tickers,
            'dates_used': available_dates,
            'days_back': days_back,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Błąd trenowania ML: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ml_bp.route("/api/ml/backtest", methods=["POST"])
def api_ml_backtest():
    """
    Endpoint do backtestingu modelu ML
    """
    try:
        data = request.get_json() or {}
        ticker = data.get('ticker', 'CDR')
        days_back = data.get('days_back', 10)
        
        ml_model = _get_ml_model()
        
        # Sprawdź czy model istnieje
        if not ml_model.load_model():
            return jsonify({
                'success': False,
                'error': 'Model ML nie został jeszcze wytrenowany'
            }), 404
        
        # Pobierz dostępne daty
        feature_engineer = _get_ml_feature_engine()
        available_dates = feature_engineer.get_available_dates([ticker], days_back)
        
        if not available_dates:
            return jsonify({
                'success': False,
                'error': f'Brak dostępnych danych dla tickera {ticker} w ostatnich {days_back} dniach'
            }), 400
        
        # Użyj dostępnych dat do backtestingu
        start_date = available_dates[-1] if len(available_dates) > 1 else available_dates[0]
       
        end_date = available_dates[0]
        
        results = ml_model.evaluate_on_backtest([ticker], start_date, end_date)
        
        return jsonify({
            'success': True,
            'backtest_results': results,
            'ticker': ticker,
            'dates_used': available_dates,
            'start_date': start_date,
            'end_date': end_date,
            'days_back': days_back,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Błąd backtestingu ML: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ml_bp.route("/api/ml/features", methods=["POST"])
def api_ml_features():
    """
    Endpoint do generowania cech ML dla tickera
    """
    try:
        data = request.get_json()
        ticker = data.get('ticker')
        date = data.get('date')  # Opcjonalnie użytkownik może podać datę
        
        if not ticker:
            return jsonify({
                'success': False,
                'error': 'Brak parametru ticker'
            }), 400
        
        feature_engineer = _get_ml_feature_engine()
        
        # Jeśli nie podano daty, użyj najnowszej dostępnej
        if not date:
            available_dates = feature_engineer.get_available_dates([ticker], days_back=7)
            if not available_dates:
                return jsonify({
                    'success': False,
                    'error': f'Brak dostępnych danych dla tickera {ticker}'
                }), 400
            date = available_dates[0]  # Najnowsza data
        
        features = feature_engineer.create_simple_features(ticker, date)
        
        return jsonify({
            'success': True,
            'ticker': ticker,
            'date': date,
            'features': features.to_dict('records') if features is not None and len(features) > 0 else [],
            'feature_count': len(features.columns) if features is not None and len(features) > 0 else 0,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Błąd generowania cech ML: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ================================
# MARKET PATTERN ML ENDPOINTS
# ================================

@ml_bp.route("/api/ml/market-pattern/train", methods=["POST"])
def api_ml_market_pattern_train():
    """
    Trenuje Market Pattern ML model na danych rynkowych
    """
    try:
        data = request.get_json() or {}
        
        # Parametry treningu
        tickers = data.get('tickers', ['CDR', 'PKN', 'PKO', 'CCC', 'ALE', 'KGH', 'PGE', 'PZU'])
        days_back = data.get('days_back', 500)
        
        logger.info(f"🤖 Training Market Pattern ML for {len(tickers)} tickers, {days_back} days")
        
        # Inicjalizuj i trenuj model
        ml_model = _get_market_pattern_ml()
        result = ml_model.train_model(tickers, days_back)
        
        if 'success' in result:
            return jsonify({
                'success': True,
                'message': f'Model wytrenowany pomyślnie!',
                'accuracy': result['test_accuracy'],
                'samples': result['samples'],
                'features': result['features'],
                'positive_ratio': result['positive_ratio'],
                'top_features': result['top_features'][:5]
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown training error')
            }), 400
            
    except Exception as e:
        logger.error(f"Błąd trenowania Market Pattern ML: {e}")
        return jsonify({
            'success': False,
            'error': f'Błąd trenowania: {str(e)}'
        }), 500

@ml_bp.route("/api/ml/market-pattern/predict", methods=["POST"])
def api_ml_market_pattern_predict():
    """
    Przewiduje wzorce rynkowe dla aktualnej sytuacji
    """
    try:
        data = request.get_json() or {}
        
        # Parametry predykcji
        tickers = data.get('tickers', ['CDR', 'PKN', 'PKO', 'CCC', 'ALE', 'KGH', 'PGE', 'PZU'])
        
        logger.info(f"🔮 Predicting market patterns for {len(tickers)} tickers")
        
        # Inicjalizuj model i przewiduj
        ml_model = _get_market_pattern_ml()
        result = ml_model.predict_current_market(tickers)
        
        if 'error' not in result:
            return jsonify({
                'success': True,
                'prediction': result['prediction'],
                'recommendation': result['recommendation'],
                'probability_buy': result['probability_buy'],
                'market_status': result['market_status'],
                'timestamp': result['timestamp']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        logger.error(f"Błąd predykcji Market Pattern ML: {e}")
        return jsonify({
            'success': False,
            'error': f'Błąd predykcji: {str(e)}'
        }), 500

@ml_bp.route("/api/ml/market-pattern/status", methods=["GET"])
def api_ml_market_pattern_status():
    """
    Sprawdza status Market Pattern ML modelu
    """
    try:
        ml_model = _get_market_pattern_ml()
        
        return jsonify({
            'success': True,
            'is_trained': ml_model.is_trained,
            'feature_count': len(ml_model.feature_names),
            'features': ml_model.feature_names[:10] if ml_model.feature_names else [],
            'model_available': ml_model.model is not None,
            'scaler_available': ml_model.scaler is not None
        })
        
    except Exception as e:
        logger.error(f"Błąd sprawdzania statusu Market Pattern ML: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ml_bp.route("/api/ml/market-pattern/tickers", methods=["GET"])
def api_ml_market_pattern_tickers():
    """Pobiera listę dostępnych tickerów z danymi intraday"""
    try:
        from sqlalchemy import text
        import os
        from dotenv import load_dotenv
        from sqlalchemy import create_engine
        
        load_dotenv('.env')
        
        # PostgreSQL connection
        pg_config = {
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'host': os.getenv('DB_HOST'),
            'port': os.getenv('DB_PORT'),
            'database': os.getenv('DB_NAME')
        }
        
        # Create DB engine
        db_uri = f"postgresql://{pg_config['user']}:{pg_config['password']}@{pg_config['host']}:{pg_config['port']}/{pg_config['database']}"
        engine = create_engine(db_uri)
        
        # Query to get tickers with intraday data, ordered by record count
        query = text("""
            SELECT 
                c.ticker,
                COUNT(qi.id) as record_count,
                MIN(qi.datetime) as first_date,
                MAX(qi.datetime) as last_date,
                CASE 
                    WHEN MAX(qi.datetime) >= CURRENT_DATE - INTERVAL '30 days' THEN true
                    ELSE false
                END as has_recent_data
            FROM companies c
            INNER JOIN quotes_intraday qi ON c.id = qi.company_id
            GROUP BY c.ticker, c.id
            HAVING COUNT(qi.id) >= 100  -- Only tickers with at least 100 records
            ORDER BY COUNT(qi.id) DESC, c.ticker ASC
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query)
            tickers = []
            
            for row in result:
                tickers.append({
                    'ticker': row[0],
                    'record_count': row[1],
                    'first_date': str(row[2]) if row[2] else None,
                    'last_date': str(row[3]) if row[3] else None,
                    'has_recent_data': bool(row[4]),
                    'recommended': row[1] >= 1000  # Recommend tickers with 1000+ records
                })
        
        return jsonify({
            'success': True,
            'tickers': tickers,
            'count': len(tickers)
        })
        
    except Exception as e:
        logger.error(f"Error fetching available tickers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
