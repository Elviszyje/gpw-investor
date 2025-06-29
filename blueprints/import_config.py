"""
Import/Config Blueprint - zarządzanie danymi, importem, konfiguracją
Obsługuje: historical data import, ticker management, configuration, scanner config
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import logging
import json
import os
from workers.quotes_daily import get_companies
from import_historical_data import HistoricalDataImporter
from import_job_manager import job_manager, run_import_in_background
from analyze_data import DataAnalyzer

import_config_bp = Blueprint('import_config', __name__)
logger = logging.getLogger(__name__)

# ================================
# TICKER MANAGEMENT
# ================================

@import_config_bp.route("/manage/tickers")
def manage_tickers():
    """Panel zarządzania tickerami z tabeli companies"""
    try:
        # Użyj TickerManager do pobierania tickerów
        from ticker_manager import TickerManager
        manager = TickerManager()
        
        # Pobierz wszystkie tickery (włącznie z nieaktywnymi)
        tickers = manager.get_all_tickers(active_only=False)
        
        # Przekształć format dla szablonu
        mappings = []
        for ticker in tickers:
            mappings.append({
                'id': hash(ticker['ticker']) % 1000000,  # Fake ID dla kompatybilności z szablonem
                'ticker': ticker['ticker'],
                'bankier_symbol': ticker['ticker'],  # W nowym systemie ticker = symbol
                'is_active': ticker['is_active'],
                'description': f"{ticker['name']} - {ticker['sector']} ({ticker['data_source']})",
                'created_at': 'N/A',
                'updated_at': 'N/A',
                'total_records': ticker['total_records'],
                'first_date': ticker.get('first_date', 'N/A'),
                'last_date': ticker.get('last_date', 'N/A')
            })
        
        print(f"DEBUG: Found {len(mappings)} mappings")
        return render_template("manage_tickers.html", mappings=mappings, is_new_system=True)
        
    except Exception as e:
        print(f"ERROR in manage_tickers: {e}")
        import traceback
        traceback.print_exc()
        flash(f"❌ Błąd pobierania tickerów: {e}", "danger")
        return redirect(url_for('index'))

@import_config_bp.route("/manage/tickers/add", methods=["POST"])
def add_ticker_mapping():
    """Dodaje nowe mapowanie tickera"""
    try:
        ticker = request.form.get("ticker", "").strip().upper()
        bankier_symbol = request.form.get("bankier_symbol", "").strip().upper()
        description = request.form.get("description", "").strip()
        is_active = 'is_active' in request.form
        
        if not ticker or not bankier_symbol:
            flash("❌ Ticker i symbol Bankier.pl są wymagane.", "danger")
            return redirect(url_for('import_config.manage_tickers'))
        
        from sqlalchemy import create_engine, text
        import os
        from dotenv import load_dotenv
        from datetime import datetime
        
        load_dotenv('.env')
        
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_name = os.getenv('DB_NAME')
        
        engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')
        
        with engine.connect() as conn:
            # Sprawdź czy ticker już istnieje
            result = conn.execute(text("SELECT COUNT(*) FROM ticker_mappings WHERE ticker = :ticker"), 
                                {"ticker": ticker})
            count = result.fetchone()
            if count and count[0] > 0:
                flash(f"❌ Ticker {ticker} już istnieje.", "danger")
                return redirect(url_for('import_config.manage_tickers'))
            
            # Dodaj nowe mapowanie
            conn.execute(text("""
                INSERT INTO ticker_mappings (ticker, bankier_symbol, description, is_active, created_at, updated_at)
                VALUES (:ticker, :bankier_symbol, :description, :is_active, :created_at, :updated_at)
            """), {
                'ticker': ticker,
                'bankier_symbol': bankier_symbol,
                'description': description,
                'is_active': is_active,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            })
            conn.commit()
        
        flash(f"✅ Dodano mapowanie {ticker} → {bankier_symbol}", "success")
        
    except Exception as e:
        flash(f"❌ Błąd dodawania mapowania: {e}", "danger")
    
    return redirect(url_for('import_config.manage_tickers'))

@import_config_bp.route("/manage/tickers/edit/<int:mapping_id>", methods=["POST"])
def edit_ticker_mapping(mapping_id):
    """Edytuje istniejące mapowanie tickera"""
    try:
        ticker = request.form.get("ticker", "").strip().upper()
        bankier_symbol = request.form.get("bankier_symbol", "").strip().upper()
        description = request.form.get("description", "").strip()
        is_active = 'is_active' in request.form
        
        if not ticker or not bankier_symbol:
            flash("❌ Ticker i symbol Bankier.pl są wymagane.", "danger")
            return redirect(url_for('import_config.manage_tickers'))
        
        from sqlalchemy import create_engine, text
        import os
        from dotenv import load_dotenv
        from datetime import datetime
        
        load_dotenv('.env')
        
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_name = os.getenv('DB_NAME')
        
        engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')
        
        with engine.connect() as conn:
            # Sprawdź czy ticker już istnieje dla innego ID
            result = conn.execute(text(
                "SELECT COUNT(*) FROM ticker_mappings WHERE ticker = :ticker AND id != :id"
            ), {"ticker": ticker, "id": mapping_id})
            
            count = result.fetchone()
            if count and count[0] > 0:
                flash(f"❌ Ticker {ticker} już istnieje w innym mapowaniu.", "danger")
                return redirect(url_for('import_config.manage_tickers'))
            
            # Aktualizuj mapowanie
            conn.execute(text("""
                UPDATE ticker_mappings 
                SET ticker = :ticker, bankier_symbol = :bankier_symbol, 
                    description = :description, is_active = :is_active, updated_at = :updated_at
                WHERE id = :id
            """), {
                'ticker': ticker,
                'bankier_symbol': bankier_symbol,
                'description': description,
                'is_active': is_active,
                'updated_at': datetime.utcnow(),
                'id': mapping_id
            })
            conn.commit()
        
        flash(f"✅ Zaktualizowano mapowanie {ticker} → {bankier_symbol}", "success")
        
    except Exception as e:
        flash(f"❌ Błąd aktualizacji mapowania: {e}", "danger")
    
    return redirect(url_for('import_config.manage_tickers'))

@import_config_bp.route("/manage/tickers/delete/<int:mapping_id>", methods=["POST"])
def delete_ticker_mapping(mapping_id):
    """Usuwa mapowanie tickera"""
    try:
        from sqlalchemy import create_engine, text
        import os
        from dotenv import load_dotenv
        
        load_dotenv('.env')
        
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_name = os.getenv('DB_NAME')
        
        engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')
        
        with engine.connect() as conn:
            # Pobierz ticker przed usunięciem
            result = conn.execute(text("SELECT ticker FROM ticker_mappings WHERE id = :id"), 
                                {"id": mapping_id})
            row = result.fetchone()
            
            if not row:
                flash("❌ Mapowanie nie istnieje.", "danger")
                return redirect(url_for('import_config.manage_tickers'))
            
            ticker = row[0]
            
            # Usuń mapowanie
            conn.execute(text("DELETE FROM ticker_mappings WHERE id = :id"), {"id": mapping_id})
            conn.commit()
        
        flash(f"✅ Usunięto mapowanie dla {ticker}", "success")
        
    except Exception as e:
        flash(f"❌ Błąd usuwania mapowania: {e}", "danger")
    
    return redirect(url_for('import_config.manage_tickers'))

@import_config_bp.route("/manage/tickers/toggle/<int:mapping_id>", methods=["POST"])
def toggle_ticker_mapping(mapping_id):
    """Przełącza status aktywności mapowania tickera"""
    try:
        from sqlalchemy import create_engine, text
        import os
        from dotenv import load_dotenv
        from datetime import datetime
        
        load_dotenv('.env')
        
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_name = os.getenv('DB_NAME')
        
        engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')
        
        with engine.connect() as conn:
            # Pobierz obecny status
            result = conn.execute(text("SELECT ticker, is_active FROM ticker_mappings WHERE id = :id"), 
                                {"id": mapping_id})
            row = result.fetchone()
            
            if not row:
                flash("❌ Mapowanie nie istnieje.", "danger")
                return redirect(url_for('import_config.manage_tickers'))
            
            ticker, current_status = row
            new_status = not current_status
            
            # Przełącz status
            conn.execute(text("""
                UPDATE ticker_mappings 
                SET is_active = :is_active, updated_at = :updated_at 
                WHERE id = :id
            """), {
                'is_active': new_status,
                'updated_at': datetime.utcnow(),
                'id': mapping_id
            })
            conn.commit()
        
        status_text = "aktywny" if new_status else "nieaktywny"
        flash(f"✅ Ticker {ticker} jest teraz {status_text}", "success")
        
    except Exception as e:
        flash(f"❌ Błąd zmiany statusu: {e}", "danger")
    
    return redirect(url_for('import_config.manage_tickers'))

# ================================
# SCANNER CONFIGURATION
# ================================

@import_config_bp.route("/intraday_config", methods=["GET", "POST"])
def intraday_config():
    """Panel zarządzania konfiguracjami skanera intraday"""
    config_file = "scanner_configs.json"
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "save":
            # Zapisz nową konfigurację
            try:
                config_name = request.form.get("config_name", "").strip()
                if not config_name:
                    flash("❌ Nazwa konfiguracji jest wymagana", "danger")
                    return redirect(url_for('import_config.intraday_config'))
                
                new_config = {
                    "name": config_name,
                    "max_workers": int(request.form.get("max_workers", 5)),
                    "max_companies": int(request.form.get("max_companies", 50)),
                    "min_buy_confidence": float(request.form.get("min_buy_confidence", 1.0)),
                    "min_sell_confidence": float(request.form.get("min_sell_confidence", 1.0)),
                    "filter_recommendation": request.form.get("filter_recommendation", "ALL"),
                    "sort_by": request.form.get("sort_by", "confidence"),
                    "description": request.form.get("description", ""),
                    "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    
                    # Nowe parametry analizy spadków ceny
                    "price_drop_analysis": {
                        "enabled": request.form.get("enable_price_drop_analysis") == "on",
                        "threshold_percent": float(request.form.get("price_drop_threshold", 2.5)),
                        "timeframe_minutes": int(request.form.get("price_drop_timeframe", 30)),
                        "min_volume_multiplier": float(request.form.get("min_volume_multiplier", 1.8))
                    },
                    
                    # Parametry wskaźników technicznych
                    "technical_indicators": {
                        "rsi": {
                            "enabled": request.form.get("enable_rsi") == "on",
                            "oversold_threshold": int(request.form.get("rsi_oversold", 35)),
                            "overbought_threshold": int(request.form.get("rsi_overbought", 65))
                        },
                        "bollinger_bands": {
                            "enabled": request.form.get("enable_bollinger") == "on",
                            "periods": int(request.form.get("bollinger_periods", 20))
                        },
                        "macd": {
                            "enabled": request.form.get("enable_macd") == "on",
                            "fast_periods": int(request.form.get("macd_fast", 5)),
                            "slow_periods": int(request.form.get("macd_slow", 10)),
                            "signal_periods": int(request.form.get("macd_signal", 3))
                        }
                    },
                    
                    # Parametry weryfikacji komunikatów rynkowych
                    "news_verification": {
                        "enabled": request.form.get("enable_news_verification") == "on",
                        "timeframe_hours": int(request.form.get("news_timeframe", 24)),
                        "strategy": request.form.get("news_strategy", "neutral"),
                        "sentiment_weight": float(request.form.get("sentiment_weight", 1.0)),
                        "min_impact": float(request.form.get("min_news_impact", 0.1)),
                        "require_news_presence": request.form.get("news_strategy") == "require_news",
                        "avoid_recent_news": request.form.get("news_strategy") == "avoid_news"
                    }
                }
                
                # Wczytaj istniejące konfiguracje
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        configs = json.load(f)
                else:
                    configs = {}
                
                # Dodaj nową konfigurację
                config_key = config_name.lower().replace(" ", "_")
                configs[config_key] = new_config
                
                # Zapisz do pliku
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(configs, f, indent=2, ensure_ascii=False)
                
                flash(f"✅ Konfiguracja '{config_name}' została zapisana", "success")
                
            except Exception as e:
                flash(f"❌ Błąd podczas zapisywania: {e}", "danger")
        
        elif action == "delete":
            # Usuń konfigurację
            try:
                config_key = request.form.get("config_key")
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        configs = json.load(f)
                    
                    if config_key in configs:
                        config_name = configs[config_key].get("name", config_key)
                        del configs[config_key]
                        
                        with open(config_file, 'w', encoding='utf-8') as f:
                            json.dump(configs, f, indent=2, ensure_ascii=False)
                        
                        flash(f"✅ Konfiguracja '{config_name}' została usunięta", "success")
                    else:
                        flash("❌ Konfiguracja nie istnieje", "danger")
                        
            except Exception as e:
                flash(f"❌ Błąd podczas usuwania: {e}", "danger")
        
        elif action == "test":
            # Przetestuj konfigurację
            try:
                test_config = {
                    "max_workers": int(request.form.get("max_workers", 5)),
                    "max_companies": int(request.form.get("max_companies", 50)),
                    "min_buy_confidence": float(request.form.get("min_buy_confidence", 1.0)),
                    "min_sell_confidence": float(request.form.get("min_sell_confidence", 1.0)),
                    "filter_recommendation": request.form.get("filter_recommendation", "ALL")
                }
                
                # Wykonaj test skanowania z konfiguracją
                from workers.intraday_recommendation_engine import IntradayRecommendationEngine
                engine = IntradayRecommendationEngine()
                engine.is_trading_hours = lambda: True  # Wymuś dla testów
                
                from workers.quotes_daily import get_companies
                companies = get_companies()
                test_tickers = [c['ticker'] for c in companies[:min(5, test_config["max_companies"])]]
                
                import time
                start_time = time.time()
                results = engine.scan_market_intraday(test_tickers, max_workers=test_config["max_workers"])
                execution_time = time.time() - start_time
                
                # Filtruj wyniki zgodnie z konfiguracją
                filtered_results = []
                for result in results:
                    buy_conf = result.get("buy_analysis", {}).get("total_confidence", 0)
                    sell_conf = result.get("sell_analysis", {}).get("total_confidence", 0)
                    recommendation = result.get('final_recommendation', result.get('recommendation', 'WAIT'))
                    
                    if (buy_conf >= test_config["min_buy_confidence"] or 
                        sell_conf >= test_config["min_sell_confidence"]):
                        if (test_config["filter_recommendation"] == "ALL" or 
                            recommendation == test_config["filter_recommendation"]):
                            filtered_results.append(result)
                
                test_result = {
                    "total_analyzed": len(results),
                    "filtered_results": len(filtered_results),
                    "execution_time": round(execution_time, 2),
                    "tickers_tested": test_tickers,
                    "performance_score": round(len(filtered_results) / max(execution_time, 0.1), 2)
                }
                
                flash(f"✅ Test wykonany: {test_result['total_analyzed']} spółek przeanalizowanych w {test_result['execution_time']}s, znaleziono {test_result['filtered_results']} sygnałów", "success")
                return render_template("intraday_config.html", test_result=test_result)
                
            except Exception as e:
                flash(f"❌ Błąd podczas testowania: {e}", "danger")
    
    # Wczytaj istniejące konfiguracje
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            configs = json.load(f)
    else:
        # Domyślne konfiguracje
        configs = {
            "conservative": {
                "name": "Konserwatywna",
                "max_workers": 2,
                "max_companies": 20,
                "min_buy_confidence": 2.0,
                "min_sell_confidence": 2.0,
                "filter_recommendation": "ALL",
                "sort_by": "confidence",
                "description": "Bezpieczne ustawienia dla stabilnego systemu",
                "price_drop_analysis": {
                    "enabled": True,
                    "threshold_percent": 3.0,
                    "timeframe_minutes": 60,
                    "min_volume_multiplier": 2.0
                },
                "technical_indicators": {
                    "rsi": {"enabled": True, "oversold_threshold": 30, "overbought_threshold": 70},
                    "bollinger_bands": {"enabled": True, "periods": 20},
                    "macd": {"enabled": True, "fast_periods": 12, "slow_periods": 26, "signal_periods": 9}
                },
                "news_verification": {
                    "enabled": False,
                    "timeframe_hours": 24,
                    "strategy": "neutral",
                    "sentiment_weight": 1.0,
                    "min_impact": 0.1,
                    "require_news_presence": False,
                    "avoid_recent_news": False
                }
            },
            "balanced": {
                "name": "Zrównoważona",
                "max_workers": 5,
                "max_companies": 50,
                "min_buy_confidence": 1.0,
                "min_sell_confidence": 1.0,
                "filter_recommendation": "ALL",
                "sort_by": "confidence",
                "description": "Standardowe ustawienia dla większości przypadków",
                "price_drop_analysis": {
                    "enabled": True,
                    "threshold_percent": 2.5,
                    "timeframe_minutes": 30,
                    "min_volume_multiplier": 1.8
                },
                "technical_indicators": {
                    "rsi": {"enabled": True, "oversold_threshold": 35, "overbought_threshold": 65},
                    "bollinger_bands": {"enabled": True, "periods": 20},
                    "macd": {"enabled": True, "fast_periods": 5, "slow_periods": 10, "signal_periods": 3}
                },
                "news_verification": {
                    "enabled": False,
                    "timeframe_hours": 24,
                    "strategy": "neutral",
                    "sentiment_weight": 1.0,
                    "min_impact": 0.1,
                    "require_news_presence": False,
                    "avoid_recent_news": False
                }
            }
        }
    
    return render_template("intraday_config.html", configs=configs)

# ================================
# IMPORT MANAGEMENT
# ================================

@import_config_bp.route("/import")
def import_panel():
    """Panel importu danych historycznych"""
    return render_template("import_panel.html")

# ================================
# API ENDPOINTS
# ================================

@import_config_bp.route("/api/scanner_config", methods=["GET", "POST"])
def api_scanner_config():
    """API endpoint do zarządzania konfiguracjami skanera"""
    config_file = "scanner_configs.json"
    
    if request.method == "GET":
        # Pobierz zapisane konfiguracje
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                configs = json.load(f)
        else:
            configs = {
                "conservative": {
                    "name": "Konserwatywna",
                    "max_workers": 2,
                    "max_companies": 20,
                    "min_buy_confidence": 2.0,
                    "min_sell_confidence": 2.0,
                    "filter_recommendation": "ALL"
                },
                "balanced": {
                    "name": "Zrównoważona",
                    "max_workers": 5,
                    "max_companies": 50,
                    "min_buy_confidence": 1.0,
                    "min_sell_confidence": 1.0,
                    "filter_recommendation": "ALL"
                }
            }
        return jsonify(configs)
    
    elif request.method == "POST":
        # Zapisz nową konfigurację
        try:
            # Obsługa zarówno JSON API jak i danych z formularza
            if request.is_json:
                data = request.get_json()
                config_name = data.get("name")
                config_data = data.get("config")
            else:
                # Dane z formularza (podobnie jak w intraday_config)
                config_name = request.form.get("config_name", "").strip()
                if not config_name:
                    return jsonify({"error": "Nazwa konfiguracji jest wymagana"}), 400
                
                config_data = {
                    "name": config_name,
                    "max_workers": int(request.form.get("max_workers", 5)),
                    "max_companies": int(request.form.get("max_companies", 50)),
                    "min_buy_confidence": float(request.form.get("min_buy_confidence", 1.0)),
                    "min_sell_confidence": float(request.form.get("min_sell_confidence", 1.0)),
                    "filter_recommendation": request.form.get("filter_recommendation", "ALL"),
                    "sort_by": request.form.get("sort_by", "confidence"),
                    "description": request.form.get("description", ""),
                    "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    
                    # Parametry analizy spadków ceny
                    "price_drop_analysis": {
                        "enabled": request.form.get("enable_price_drop_analysis") == "on",
                        "threshold_percent": float(request.form.get("price_drop_threshold", 2.5)),
                        "timeframe_minutes": int(request.form.get("price_drop_timeframe", 30)),
                        "min_volume_multiplier": float(request.form.get("min_volume_multiplier", 1.8))
                    },
                    
                    # Parametry wskaźników technicznych
                    "technical_indicators": {
                        "rsi": {
                            "enabled": request.form.get("enable_rsi") == "on",
                            "oversold_threshold": int(request.form.get("rsi_oversold", 35)),
                            "overbought_threshold": int(request.form.get("rsi_overbought", 65))
                        },
                        "bollinger_bands": {
                            "enabled": request.form.get("enable_bollinger") == "on",
                            "periods": int(request.form.get("bollinger_periods", 20))
                        },
                        "macd": {
                            "enabled": request.form.get("enable_macd") == "on",
                            "fast_periods": int(request.form.get("macd_fast", 5)),
                            "slow_periods": int(request.form.get("macd_slow", 10)),
                            "signal_periods": int(request.form.get("macd_signal", 3))
                        }
                    },
                    
                    # Parametry weryfikacji komunikatów rynkowych
                    "news_verification": {
                        "enabled": request.form.get("enable_news_verification") == "on",
                        "timeframe_hours": int(request.form.get("news_timeframe", 24)),
                        "strategy": request.form.get("news_strategy", "neutral"),
                        "sentiment_weight": float(request.form.get("sentiment_weight", 1.0)),
                        "min_impact": float(request.form.get("min_news_impact", 0.1)),
                        "require_news_presence": request.form.get("news_strategy") == "require_news",
                        "avoid_recent_news": request.form.get("news_strategy") == "avoid_news"
                    }
                }
            
            # Wczytaj istniejące konfiguracje
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    configs = json.load(f)
            else:
                configs = {}
            
            # Dodaj nową konfigurację
            config_key = config_name.lower().replace(" ", "_")
            configs[config_key] = config_data
            
            # Zapisz do pliku
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=2, ensure_ascii=False)
            
            return jsonify({"success": True, "message": f"Konfiguracja '{config_name}' została zapisana"})
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@import_config_bp.route("/api/scanner_stats", methods=["GET"])
def api_scanner_stats():
    """API endpoint do statystyk skanera"""
    try:
        from workers.quotes_daily import get_companies
        companies = get_companies()
        
        # Podstawowe statystyki
        stats = {
            "total_companies": len(companies),
            "available_tickers": [c['ticker'] for c in companies[:10]],  # Przykład pierwszych 10
            "recommended_settings": {
                "low_load": {"max_workers": 2, "max_companies": 20},
                "medium_load": {"max_workers": 5, "max_companies": 50},
                "high_load": {"max_workers": 8, "max_companies": 100}
            }
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@import_config_bp.route("/api/import/status", methods=["GET"])
def api_import_status():
    """
    Endpoint do sprawdzania statusu bazy danych
    """
    try:
        analyzer = DataAnalyzer()
        
        # Podstawowe statystyki
        basic_stats = analyzer.get_basic_stats()
        
        # Oblicz łączne rekordy i sprawdź czy są dostępne dane
        intraday_records = basic_stats.get('quotes_intraday', {}).get('total_records', 0)
        daily_records = basic_stats.get('quotes_daily', {}).get('total_records', 0)
        total_records = intraday_records + daily_records
        total_tickers = basic_stats.get('companies', {}).get('total_count', 0)
        
        has_data = total_records > 0
        
        # Określ zakres dat
        intraday_data = basic_stats.get('quotes_intraday', {})
        daily_data = basic_stats.get('quotes_daily', {})
        
        date_range = {
            'min': None,
            'max': None
        }
        
        # Znajdź najwcześniejszą i najpóźniejszą datę
        dates = []
        if intraday_data.get('first_date'):
            dates.append(intraday_data['first_date'])
        if intraday_data.get('last_date'):
            dates.append(intraday_data['last_date'])
        if daily_data.get('first_date'):
            dates.append(daily_data['first_date'])
        if daily_data.get('last_date'):
            dates.append(daily_data['last_date'])
            
        if dates:
            date_range['min'] = min(dates)
            date_range['max'] = max(dates)
        
        return jsonify({
            'success': True,
            'has_data': has_data,
            'total_records': total_records,
            'total_tickers': total_tickers,
            'date_range': date_range,
            'breakdown': {
                'intraday_records': intraday_records,
                'daily_records': daily_records
            }
        })
        
    except Exception as e:
        logger.error(f"Błąd sprawdzania statusu importu: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@import_config_bp.route("/api/import/analyze", methods=["GET"])
def api_import_analyze():
    """
    Endpoint do szczegółowej analizy danych
    """
    try:
        analyzer = DataAnalyzer()
        
        # Pobierz kompletną analizę
        basic_stats = analyzer.get_basic_stats()
        data_quality = analyzer.analyze_data_quality()
        completeness = analyzer.analyze_completeness()
        ml_readiness = analyzer.generate_ml_readiness_report()
        
        return jsonify({
            'success': True,
            'basic_stats': basic_stats,
            'data_quality': data_quality,
            'completeness': completeness,
            'ml_readiness': ml_readiness,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Błąd analizy danych: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@import_config_bp.route("/api/import/backup", methods=["POST"])
def api_import_backup():
    """
    Endpoint do tworzenia backup bazy danych
    """
    try:
        importer = HistoricalDataImporter()
        
        # Sprawdź czy są dane do backup
        summary = importer.get_import_stats()
        if summary.get('total_records', 0) == 0:
            return jsonify({
                'success': False,
                'error': 'Baza danych jest pusta - brak danych do backup'
            }), 400
        
        # Utwórz backup
        backup_file = importer.backup_database()
        
        if backup_file:
            return jsonify({
                'success': True,
                'backup_file': backup_file,
                'message': f'Backup utworzony: {backup_file}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Nie udało się utworzyć backup'
            }), 500
        
    except Exception as e:
        logger.error(f"Błąd tworzenia backup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@import_config_bp.route("/api/import/clear", methods=["POST"])
def api_import_clear():
    """
    Endpoint do czyszczenia bazy danych
    """
    try:
        importer = HistoricalDataImporter()
        
        # Sprawdź czy są dane do usunięcia
        summary = importer.get_import_stats()
        if summary.get('total_records', 0) == 0:
            return jsonify({
                'success': True,
                'message': 'Baza danych jest już pusta'
            })
        
        # Sprawdź czy użytkownik chce backup
        create_backup = request.json.get('backup', True) if request.json else True
        backup_file = None
        
        if create_backup:
            backup_file = importer.backup_database()
            if not backup_file:
                return jsonify({
                    'success': False,
                    'error': 'Nie udało się utworzyć backup przed czyszczeniem'
                }), 500
        
        # Wyczyść bazę
        success = importer.clear_database(confirm=True)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Baza danych została wyczyszczona',
                'backup_file': backup_file
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Nie udało się wyczyścić bazy danych'
            }), 500
        
    except Exception as e:
        logger.error(f"Błąd czyszczenia bazy: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@import_config_bp.route("/api/import/upload", methods=["POST"])
def api_import_upload():
    """
    Endpoint do asynchronicznego importu danych z uploaded files
    """
    import threading
    
    try:
        if 'files' not in request.files:
            return jsonify({
                'success': False,
                'error': 'Brak plików do importu'
            }), 400
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({
                'success': False,
                'error': 'Nie wybrano plików'
            }), 400
        
        # Create new import job
        job_id = job_manager.create_job("file_import")
        
        # Prepare files data for background processing
        files_data = []
        for file in files:
            if file and file.filename and file.filename.endswith('.txt'):
                try:
                    content = file.read().decode('utf-8')
                    files_data.append({
                        'filename': file.filename,
                        'content': content
                    })
                except Exception as e:
                    logger.error(f"Error reading file {file.filename}: {e}")
                    return jsonify({
                        'success': False,
                        'error': f'Error reading file {file.filename}: {str(e)}'
                    }), 400
        
        if not files_data:
            return jsonify({
                'success': False,
                'error': 'No valid TXT files found'
            }), 400
        
        # Start background import
        importer = HistoricalDataImporter()
        thread = threading.Thread(
            target=run_import_in_background,
            args=(job_id, files_data, importer)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': f'Import started for {len(files_data)} files. Use job_id to check progress.',
            'files_count': len(files_data)
        })
        
    except Exception as e:
        logger.error(f"Błąd podczas rozpoczynania importu: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@import_config_bp.route("/api/import/status/<job_id>", methods=["GET"])
def api_import_job_status(job_id: str):
    """
    Get status of a specific import job
    """
    try:
        job_status = job_manager.get_job_status(job_id)
        
        if not job_status:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404
        
        # Convert datetime objects to strings for JSON serialization
        job_data = job_status.copy()
        for field in ['created_at', 'started_at', 'finished_at']:
            if job_data.get(field):
                job_data[field] = job_data[field].isoformat()
        
        return jsonify({
            'success': True,
            'job': job_data
        })
        
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@import_config_bp.route("/api/import/cancel/<job_id>", methods=["POST"])
def api_import_cancel_job(job_id: str):
    """
    Cancel a running import job
    """
    try:
        success = job_manager.cancel_job(job_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Job {job_id} cancelled successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Could not cancel job - job not found or not running'
            }), 400
        
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@import_config_bp.route("/api/import/jobs", methods=["GET"])
def api_import_list_jobs():
    """
    List all import jobs (for debugging)
    """
    try:
        # Check for timeouts before returning jobs
        job_manager.check_timeouts()
        
        jobs = job_manager.get_all_jobs()
        
        # Convert datetime objects to strings for JSON serialization
        jobs_data = {}
        for job_id, job in jobs.items():
            job_data = job.copy()
            for field in ['created_at', 'started_at', 'finished_at']:
                if job_data.get(field):
                    job_data[field] = job_data[field].isoformat()
            jobs_data[job_id] = job_data
        
        return jsonify({
            'success': True,
            'jobs': jobs_data,
            'count': len(jobs_data)
        })
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@import_config_bp.route("/api/import/test", methods=["POST"])
def api_import_test():
    """
    Test endpoint for debugging import process
    """
    try:
        # Test with the exact working format
        test_data = """CDR,5,20250627,093000,51.50,51.70,51.50,51.60,105,0
CDR,5,20250627,093500,51.60,51.80,51.60,51.70,110,0
CDR,5,20250627,094000,51.70,51.90,51.70,51.80,115,0"""
        
        import tempfile
        import os
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(test_data)
            temp_path = temp_file.name
        
        # Import directly
        importer = HistoricalDataImporter()
        result = importer.import_single_file(temp_path)
        
        # Clean up
        os.unlink(temp_path)
        
        return jsonify({
            'success': True,
            'import_result': result,
            'test_data_lines': test_data.count('\n') + 1
        })
        
    except Exception as e:
        logger.error(f"Test import failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
