"""
Recommendations Blueprint - analiza rekomendacji i skanowanie rynku
Obsługuje: recommendations, intraday recommendations, market scanning, tracking
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import logging
from workers.quotes_daily import get_companies
from workers.recommendation_engine import RecommendationEngine
from workers.intraday_recommendation_engine import IntradayRecommendationEngine

recommendations_bp = Blueprint('recommendations', __name__)
logger = logging.getLogger(__name__)

@recommendations_bp.route("/recommendations", methods=["GET", "POST"])
def recommendations():
    """Analiza rekomendacji dla wybranej spółki"""
    companies = get_companies()
    
    if request.method == "POST":
        ticker = request.form.get("ticker")
        new_ticker = request.form.get("new_ticker")
        ticker = new_ticker.strip().upper() if new_ticker else ticker
        
        if not ticker:
            flash("❌ Nie wybrano ani nie wpisano spółki.", "danger")
            return render_template("recommendations.html", companies=companies)
        
        try:
            engine = RecommendationEngine()
            result = engine.analyze_ticker(ticker)
            
            flash(f"✅ Analiza rekomendacji dla {ticker} zakończona: {result['final_recommendation']}", "success")
            return render_template("recommendations.html", 
                                 companies=companies, 
                                 result=result, 
                                 selected_ticker=ticker)
        except Exception as e:
            flash(f"❌ Błąd podczas analizy rekomendacji: {e}", "danger")
            return render_template("recommendations.html", companies=companies)
    
    return render_template("recommendations.html", companies=companies)

@recommendations_bp.route("/intraday_recommendations", methods=["GET", "POST"])
def intraday_recommendations():
    """Analiza rekomendacji intraday dla wybranej spółki"""
    companies = get_companies()
    
    if request.method == "POST":
        ticker = request.form.get("ticker")
        new_ticker = request.form.get("new_ticker")
        entry_price = request.form.get("entry_price")
        has_position = request.form.get("has_position") == "on"
        
        ticker = new_ticker.strip().upper() if new_ticker else ticker
        
        if not ticker:
            flash("❌ Nie wybrano ani nie wpisano spółki.", "danger")
            return render_template("intraday_recommendations.html", companies=companies)
        
        try:
            # Utwórz silnik z włączonymi powiadomieniami
            engine = IntradayRecommendationEngine(enable_tracking=True, enable_notifications=True)
            
            # Jeśli ma pozycję, przekaż cenę wejścia
            if has_position and entry_price:
                from datetime import datetime, timedelta
                entry_price_float = float(entry_price)
                entry_time = datetime.now() - timedelta(hours=2)  # Przykładowe 2h temu
                result = engine.analyze_ticker_intraday(ticker, entry_price_float, entry_time)
            else:
                result = engine.analyze_ticker_intraday(ticker)
            
            recommendation = result.get('final_recommendation', result.get('recommendation', 'UNKNOWN'))
            
            if 'error' in result:
                flash(f"⚠️ {result['error']} dla {ticker}: {recommendation}", "warning")
            else:
                flash(f"✅ Analiza intraday dla {ticker} zakończona: {recommendation}", "success")
            
            return render_template("intraday_recommendations.html", 
                                 companies=companies, 
                                 result=result, 
                                 selected_ticker=ticker,
                                 has_position=has_position,
                                 entry_price=entry_price)
        except Exception as e:
            flash(f"❌ Błąd podczas analizy intraday: {e}", "danger")
            return render_template("intraday_recommendations.html", companies=companies)
    
    return render_template("intraday_recommendations.html", companies=companies)

@recommendations_bp.route("/intraday_scan", methods=["GET", "POST"])
def intraday_scan():
    """Skanowanie całego rynku w poszukiwaniu okazji intraday"""
    try:
        # Utwórz silnik z włączonymi powiadomieniami
        engine = IntradayRecommendationEngine(enable_tracking=True, enable_notifications=True)
        
        if request.method == "POST":
            # Podstawowe parametry
            limit = int(request.form.get("limit", 10))
            scan_all = request.form.get("scan_all") == "on"
            
            max_workers = int(request.form.get("max_workers", 5))
            max_companies = int(request.form.get("max_companies", 50))
            min_buy_confidence = float(request.form.get("min_buy_confidence", 0.0))
            min_sell_confidence = float(request.form.get("min_sell_confidence", 0.0))
            filter_recommendation = request.form.get("filter_recommendation", "ALL")
            
            # Opcje sortowania
            sort_by = request.form.get("sort_by", "confidence")
            
            if scan_all:
                # Skanuj wszystkie spółki z parametrami
                from workers.quotes_daily import get_companies
                companies = get_companies()
                tickers = [company['ticker'] for company in companies]
                
                # Ogranicz liczbę spółek
                tickers = tickers[:max_companies]
                
                # Przygotuj konfigurację dla silnika
                scan_config = {
                    "name": "Skanowanie z panelu",
                    "price_drop_analysis": {
                        "enabled": request.form.get("enable_price_drop_analysis") == "on",
                        "threshold_percent": float(request.form.get("price_drop_threshold", 2.5)),
                        "timeframe_minutes": int(request.form.get("price_drop_timeframe", 30)),
                        "min_volume_multiplier": float(request.form.get("min_volume_multiplier", 1.8))
                    },
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
                
                # Aplikuj konfigurację do silnika
                engine.apply_config_overrides(scan_config)
                
                results = engine.scan_market_intraday(tickers, max_workers=max_workers)
                
                # Filtruj wyniki według pewności
                filtered_results = []
                for result in results:
                    buy_conf = result.get("buy_analysis", {}).get("total_confidence", 0)
                    sell_conf = result.get("sell_analysis", {}).get("total_confidence", 0)
                    recommendation = result.get('final_recommendation', result.get('recommendation', 'WAIT'))
                    
                    # Filtr po pewności
                    if buy_conf >= min_buy_confidence or sell_conf >= min_sell_confidence:
                        # Filtr po typie rekomendacji
                        if filter_recommendation == "ALL" or recommendation == filter_recommendation:
                            filtered_results.append(result)
                
                # Sortowanie wyników
                if sort_by == "confidence":
                    filtered_results.sort(key=lambda x: max(
                        x.get("buy_analysis", {}).get("total_confidence", 0),
                        x.get("sell_analysis", {}).get("total_confidence", 0)
                    ), reverse=True)
                elif sort_by == "price_change":
                    filtered_results.sort(key=lambda x: abs(
                        x.get("technical_analysis", {}).get("price_change_1d", 0)
                    ), reverse=True)
                
                results = filtered_results
                flash(f"✅ Przeskanowano {len(tickers)} spółek, znaleziono {len(results)} okazji", "success")
            else:
                # Skanuj tylko top okazje
                results = engine.get_top_intraday_opportunities(limit)
                flash(f"✅ Znaleziono {len(results)} okazji intraday", "success")
            
            return render_template("intraday_scan.html", 
                                 results=results, 
                                 limit=limit,
                                 scan_all=scan_all,
                                 max_workers=max_workers,
                                 max_companies=max_companies,
                                 min_buy_confidence=min_buy_confidence,
                                 min_sell_confidence=min_sell_confidence,
                                 filter_recommendation=filter_recommendation,
                                 sort_by=sort_by)
        
        # GET request - pokaż formularz (może z parametrami z URL)
        session_summary = engine.get_session_summary()
        
        # Sprawdź czy są parametry z URL (przesłane z panelu konfiguracji)
        url_params = {}
        if request.args.get('scan_all'):
            url_params['scan_all'] = request.args.get('scan_all') == 'on'
            url_params['max_workers'] = int(request.args.get('max_workers', 5))
            url_params['max_companies'] = int(request.args.get('max_companies', 50))
            url_params['min_buy_confidence'] = float(request.args.get('min_buy_confidence', 0.0))
            url_params['min_sell_confidence'] = float(request.args.get('min_sell_confidence', 0.0))
            url_params['filter_recommendation'] = request.args.get('filter_recommendation', 'ALL')
            url_params['sort_by'] = request.args.get('sort_by', 'confidence')
            
            # Nowe parametry
            url_params['enable_price_drop_analysis'] = request.args.get('enable_price_drop_analysis', 'on') == 'on'
            url_params['price_drop_threshold'] = float(request.args.get('price_drop_threshold', 2.5))
            url_params['price_drop_timeframe'] = int(request.args.get('price_drop_timeframe', 30))
            url_params['min_volume_multiplier'] = float(request.args.get('min_volume_multiplier', 1.8))
            
            url_params['enable_rsi'] = request.args.get('enable_rsi', 'on') == 'on'
            url_params['rsi_oversold'] = int(request.args.get('rsi_oversold', 35))
            url_params['rsi_overbought'] = int(request.args.get('rsi_overbought', 65))
            
            url_params['enable_bollinger'] = request.args.get('enable_bollinger', 'on') == 'on'
            url_params['bollinger_periods'] = int(request.args.get('bollinger_periods', 20))
            
            url_params['enable_macd'] = request.args.get('enable_macd', 'on') == 'on'
            url_params['macd_fast'] = int(request.args.get('macd_fast', 5))
            url_params['macd_slow'] = int(request.args.get('macd_slow', 10))
            url_params['macd_signal'] = int(request.args.get('macd_signal', 3))
            
            # Parametry weryfikacji komunikatów
            url_params['enable_news_verification'] = request.args.get('enable_news_verification', 'off') == 'on'
            url_params['news_timeframe'] = int(request.args.get('news_timeframe', 24))
            url_params['news_strategy'] = request.args.get('news_strategy', 'neutral')
            url_params['sentiment_weight'] = float(request.args.get('sentiment_weight', 1.0))
            url_params['min_news_impact'] = float(request.args.get('min_news_impact', 0.1))
        url_params['days_back'] = int(request.args.get('days_back', 30))
        
        return render_template("intraday_scan.html", 
                             session_summary=session_summary,
                             **url_params)
    
    except Exception as e:
        flash(f"❌ Błąd podczas skanowania: {e}", "danger")
        return render_template("intraday_scan.html")

@recommendations_bp.route("/recommendations_tracking")
def recommendations_tracking():
    """Panel trackingu rekomendacji"""
    return render_template("recommendations_tracking.html")

# === API ENDPOINTS ===

@recommendations_bp.route("/api/intraday_monitor", methods=["GET"])
def api_intraday_monitor():
    """API endpoint do monitorowania aktywnych pozycji intraday"""
    try:
        engine = IntradayRecommendationEngine()
        monitoring_result = engine.monitor_active_positions()
        return jsonify(monitoring_result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@recommendations_bp.route('/api/recommendations/auto_evaluate', methods=['POST'])
def auto_evaluate_recommendations():
    """API endpoint do automatycznej oceny rekomendacji"""
    try:
        from workers.intraday_recommendation_engine import IntradayRecommendationEngine
        
        engine = IntradayRecommendationEngine()
        results = engine.auto_evaluate_recommendations()
        
        return jsonify({
            'success': True,
            'results': results,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Błąd automatycznej oceny rekomendacji: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@recommendations_bp.route('/api/recommendations/stats')
def get_recommendation_stats():
    """API endpoint do pobierania statystyk rekomendacji"""
    try:
        days_back = request.args.get('days_back', 7, type=int)
        
        from workers.intraday_recommendation_engine import IntradayRecommendationEngine
        
        engine = IntradayRecommendationEngine()
        stats = engine.get_tracking_stats(days_back=days_back)
        
        return jsonify({
            'success': True,
            'stats': stats,
            'days_back': days_back,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Błąd pobierania statystyk rekomendacji: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@recommendations_bp.route('/api/recommendations/history')
def get_recommendations_history():
    """API endpoint do pobierania historii rekomendacji"""
    try:
        limit = request.args.get('limit', 50, type=int)
        status = request.args.get('status', 'all')  # all, active, closed
        
        from workers.recommendation_tracker_postgresql import RecommendationTracker
        
        tracker = RecommendationTracker()
        
        if status == 'active':
            recommendations = tracker.get_active_recommendations(max_age_hours=24)
        else:
            # Pobierz historię z bazy (możemy dodać metodę do trackera)
            recommendations = []
        
        return jsonify({
            'success': True,
            'recommendations': recommendations,
            'count': len(recommendations),
            'status_filter': status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Błąd pobierania historii rekomendacji: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@recommendations_bp.route("/api/recommendations_with_tracking")
def api_recommendations_with_tracking():
    """API endpoint zwracający rekomendacje z pełnym trackingiem"""
    try:
        import os
        from dotenv import load_dotenv
        from sqlalchemy import create_engine, text
        from workers.recommendation_tracker_postgresql import RecommendationTracker
        
        load_dotenv('.env')
        
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_name = os.getenv('DB_NAME')
        
        engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')
        tracker = RecommendationTracker()
        
        with engine.connect() as conn:            
            # Pobierz rekomendacje z pełnymi danymi
            result = conn.execute(text("""
                SELECT 
                    r.id, r.ticker, r.recommendation, r.entry_price,
                    r.target_price, r.stop_loss, r.buy_confidence, r.sell_confidence,
                    r.signal_count, r.status, r.created_at,
                    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - r.created_at)) / 3600 as age_hours
                FROM recommendations r
                WHERE r.created_at >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY r.created_at DESC
            """))
            
            recommendations = []
            for row in result.fetchall():
                rec_id, ticker, recommendation, entry_price, target_price, stop_loss, \
                buy_conf, sell_conf, signal_count, status, created_at, age_hours = row
                
                # Pobierz tracking dla tej rekomendacji
                track_result = conn.execute(text("""
                    SELECT hours_after, price_at_hour, profit_loss_percent, tracked_at
                    FROM recommendation_tracking 
                    WHERE recommendation_id = :rec_id
                    ORDER BY hours_after
                """), {"rec_id": rec_id})
                
                tracking_data = []
                for track_row in track_result.fetchall():
                    hours, price, profit_pct, tracked_at = track_row
                    tracking_data.append({
                        'hours_after': hours,
                        'price': float(price),
                        'profit_loss_percent': float(profit_pct),
                        'tracked_at': tracked_at.isoformat() if tracked_at else None
                    })
                
                # Pobierz wynik końcowy jeśli istnieje
                result_query = conn.execute(text("""
                    SELECT profit_loss_percent, success, exit_reason, evaluated_at
                    FROM recommendation_results 
                    WHERE recommendation_id = :rec_id
                """), {"rec_id": rec_id})
                
                result_data = None
                result_row = result_query.fetchone()
                if result_row:
                    profit_pct, success, exit_reason, evaluated_at = result_row
                    result_data = {
                        'profit_loss_percent': float(profit_pct),
                        'success': success,
                        'exit_reason': exit_reason,
                        'evaluated_at': evaluated_at.isoformat() if evaluated_at else None
                    }
                
                recommendations.append({
                    'id': rec_id,
                    'ticker': ticker,
                    'recommendation': recommendation,
                    'entry_price': float(entry_price) if entry_price else 0,
                    'target_price': float(target_price) if target_price else None,
                    'stop_loss': float(stop_loss) if stop_loss else None,
                    'buy_confidence': float(buy_conf) if buy_conf else 0,
                    'sell_confidence': float(sell_conf) if sell_conf else 0,
                    'signal_count': signal_count,
                    'status': status,
                    'created_at': created_at.isoformat() if created_at else None,
                    'age_hours': float(age_hours) if age_hours else 0,
                    'tracking': tracking_data,
                    'result': result_data
                })
            
            return jsonify({
                'success': True,
                'count': len(recommendations),
                'recommendations': recommendations
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
