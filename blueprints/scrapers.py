"""
Scrapers Blueprint - selenium scraper, schedulers, news, communications
Obsługuje: selenium scraper, multi-ticker scheduler, news scheduler, ESPI scheduler
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import logging
from workers.quotes_daily import get_companies
from scheduler.multi_ticker_scheduler import (
    get_multi_scheduler, start_multi_ticker_scraping, stop_multi_ticker_scraping, 
    get_scheduler_status, run_manual_multi_scrape
)
from scheduler.espi_scheduler import (
    get_espi_scheduler, start_espi_scraping, stop_espi_scraping, 
    get_espi_scheduler_status, run_manual_espi_scrape, update_espi_interval
)
from scheduler.news_scheduler import (
    get_news_scheduler, start_news_scraping, stop_news_scraping,
    get_news_scheduler_status, run_manual_news_scrape, run_manual_espi_scrape as run_manual_espi_scrape_news,
    update_news_interval, update_espi_interval as update_espi_interval_news,
    update_news_days_back, update_espi_days_back
)
from workers.espi_scraper_rss import ESPIScraperRSS
from workers.news_scraper_offline import NewsScraperOffline

scrapers_bp = Blueprint('scrapers', __name__)
logger = logging.getLogger(__name__)

# ================================
# SELENIUM SCRAPER MANAGEMENT
# ================================

@scrapers_bp.route("/selenium_scraper", methods=["GET", "POST"])
def selenium_scraper():
    """Strona do obsługi Selenium scrapera"""
    scheduler = get_multi_scheduler()
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "manual_scrape":
            # Ręczne scrapowanie
            ticker = request.form.get("ticker")
            new_ticker = request.form.get("new_ticker")
            ticker = new_ticker.strip().upper() if new_ticker else ticker
            
            if not ticker:
                flash("❌ Nie wybrano ani nie wpisano spółki.", "danger")
            else:
                try:
                    results = run_manual_multi_scrape([ticker])
                    if ticker in results['success']:
                        flash(f"✅ Dane dla {ticker} zostały pobrane przez Selenium scraper.", "success")
                    else:
                        flash(f"⚠️ Nie udało się pobrać danych dla {ticker}.", "warning")
                except Exception as e:
                    flash(f"❌ Błąd podczas scrapowania Selenium: {e}", "danger")
        
        elif action == "manual_multi_scrape":
            # Ręczne scrapowanie wszystkich aktywnych tickerów
            try:
                results = run_manual_multi_scrape()
                total_success = len(results['success'])
                total_failed = len(results['failed'])
                
                if total_success > 0:
                    flash(f"✅ Pobrano dane dla {total_success} tickerów: {', '.join(results['success'])}", "success")
                
                if total_failed > 0:
                    flash(f"⚠️ Błędy dla {total_failed} tickerów: {', '.join(results['failed'])}", "warning")
                
                if total_success == 0:
                    flash("❌ Nie udało się pobrać danych dla żadnego tickera.", "danger")
                    
            except Exception as e:
                flash(f"❌ Błąd podczas scrapowania wielu tickerów: {e}", "danger")
        
        elif action == "add_ticker":
            # Dodanie nowego tickera
            new_ticker = request.form.get("add_ticker")
            if new_ticker:
                new_ticker = new_ticker.strip().upper()
                if scheduler.add_ticker(new_ticker):
                    flash(f"✅ Dodano ticker {new_ticker} do listy aktywnych.", "success")
                else:
                    flash(f"⚠️ Ticker {new_ticker} już istnieje w liście.", "warning")
            else:
                flash("❌ Nie podano tickera do dodania.", "danger")
        
        elif action == "remove_ticker":
            # Usunięcie tickera
            remove_ticker = request.form.get("remove_ticker")
            if remove_ticker:
                if scheduler.remove_ticker(remove_ticker):
                    flash(f"✅ Usunięto ticker {remove_ticker} z listy aktywnych.", "success")
                else:
                    flash(f"⚠️ Ticker {remove_ticker} nie istnieje w liście.", "warning")
            else:
                flash("❌ Nie wybrano tickera do usunięcia.", "danger")
        
        elif action == "start_scheduler":
            # Uruchomienie cyklicznego scrapowania
            if start_multi_ticker_scraping():
                flash("✅ Cykliczne scrapowanie zostało uruchomione.", "success")
            else:
                flash("⚠️ Cykliczne scrapowanie już jest uruchomione.", "warning")
        
        elif action == "stop_scheduler":
            # Zatrzymanie cyklicznego scrapowania
            if stop_multi_ticker_scraping():
                flash("✅ Cykliczne scrapowanie zostało zatrzymane.", "success")
            else:
                flash("⚠️ Cykliczne scrapowanie nie było uruchomione.", "warning")
        
        elif action == "update_interval":
            # Aktualizacja interwału
            try:
                new_interval = int(request.form.get("interval_minutes", 15))
                if new_interval < 1:
                    flash("❌ Interwał musi być większy niż 0 minut.", "danger")
                else:
                    scheduler.update_scraping_interval(new_interval)
                    flash(f"✅ Interwał scrapowania został zmieniony na {new_interval} minut.", "success")
            except (ValueError, TypeError):
                flash("❌ Nieprawidłowa wartość interwału.", "danger")
        
        return redirect(url_for('scrapers.selenium_scraper'))
    
    # GET request - wyświetlenie strony
    companies = get_companies()
    status = get_scheduler_status()
    active_tickers = scheduler.get_active_tickers()
    
    return render_template("selenium_scraper.html", 
                         companies=companies, 
                         status=status, 
                         active_tickers=active_tickers)

# ================================
# COMMUNICATIONS (ESPI/EBI)
# ================================

@scrapers_bp.route("/communications")
def show_communications():
    """Strona wyświetlania komunikatów ESPI/EBI"""
    try:
        scraper = ESPIScraperRSS()
        
        # Pobierz filtry z parametrów URL
        ticker_filter = request.args.get('ticker', '')
        comm_type_filter = request.args.get('type', '')
        days_back = int(request.args.get('days', 30))
        
        # Pobierz komunikaty
        if ticker_filter:
            communications = scraper.get_communications_for_ticker(ticker_filter, days_back)
        else:
            communications = scraper.get_recent_communications(limit=100)
        
        # Filtruj po typie jeśli wybrano
        if comm_type_filter:
            communications = [c for c in communications if c['communication_type'] == comm_type_filter]
        
        # Pobierz statystyki
        stats = scraper.get_communications_stats()
        
        # Pobierz listę aktywnych tickerów
        active_tickers = scraper.active_tickers
        
        return render_template("communications.html", 
                             communications=communications,
                             stats=stats,
                             active_tickers=active_tickers,
                             current_ticker=ticker_filter,
                             current_type=comm_type_filter,
                             current_days=days_back)
        
    except Exception as e:
        flash(f"❌ Błąd pobierania komunikatów: {e}", "danger")
        return redirect(url_for('index'))

@scrapers_bp.route("/communications/scrape", methods=["POST"])
def scrape_communications():
    """Uruchamia scrapowanie komunikatów ESPI/EBI"""
    try:
        days_back = int(request.form.get('days_back', 7))
        
        scraper = ESPIScraperRSS()
        results = scraper.scrape_all_communications(days_back=days_back)
        
        flash(f"✅ Pobrano {results['total']} nowych komunikatów (ESPI: {results['ESPI']}, EBI: {results['EBI']})", "success")
        
    except Exception as e:
        flash(f"❌ Błąd podczas scrapowania komunikatów: {e}", "danger")
    
    return redirect(url_for('scrapers.show_communications'))

# ================================
# NEWS MANAGEMENT
# ================================

@scrapers_bp.route("/news")
def show_news():
    """Strona wyświetlania newsów z portali finansowych"""
    try:
        scraper = NewsScraperOffline()
        
        # Pobierz filtry z parametrów URL
        source_filter = request.args.get('source', '')
        ticker_filter = request.args.get('ticker', '')
        days_back = int(request.args.get('days', 7))
        
        # Pobierz newsy
        news = scraper.get_recent_news(
            source_filter=source_filter,
            ticker_filter=ticker_filter,
            days_back=days_back,
            limit=100
        )
        
        # Pobierz statystyki
        stats = scraper.get_news_stats()
        
        # Pobierz listę dostępnych źródeł
        sources = scraper.get_available_sources()
        
        # Pobierz listę aktywnych tickerów  
        active_tickers = scraper.get_active_tickers()
        
        return render_template("news.html", 
                             news=news,
                             stats=stats,
                             sources=sources,
                             active_tickers=active_tickers,
                             current_source=source_filter,
                             current_ticker=ticker_filter,
                             current_days=days_back)
        
    except Exception as e:
        flash(f"❌ Błąd pobierania newsów: {e}", "danger")
        return redirect(url_for('index'))

@scrapers_bp.route("/news/scrape", methods=["POST"])
def scrape_news():
    """Uruchamia scrapowanie newsów z portali finansowych"""
    try:
        days_back = int(request.form.get('days_back', 3))
        
        scraper = NewsScraperOffline()
        results = scraper.scrape_all_news(days_back=days_back)
        
        total_new = sum(results.values())
        sources_info = ', '.join([f"{source}: {count}" for source, count in results.items() if count > 0])
        
        if total_new > 0:
            flash(f"✅ Pobrano {total_new} nowych artykułów ({sources_info})", "success")
        else:
            flash("ℹ️ Brak nowych artykułów do pobrania", "info")
        
    except Exception as e:
        flash(f"❌ Błąd podczas scrapowania newsów: {e}", "danger")
    
    return redirect(url_for('scrapers.show_news'))

@scrapers_bp.route("/news_scheduler")
def news_scheduler_config():
    """Strona konfiguracji news schedulera"""
    try:
        status = get_news_scheduler_status()
        return render_template("news_scheduler.html", status=status)
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"❌ Błąd podczas pobierania statusu news schedulera: {e}", "danger")
        return redirect(url_for('index'))

# ================================
# MONITORING
# ================================

@scrapers_bp.route("/monitoring/schedulers")
def scheduler_monitoring():
    """Strona monitorowania wszystkich schedulerów"""
    try:
        # Pobierz status wszystkich schedulerów
        multi_status = get_scheduler_status()
        news_status = get_news_scheduler_status()
        espi_status = get_espi_scheduler_status()
        
        # Sprawdź status analizy intraday
        analysis_status = {}
        try:
            from workers.intraday_recommendation_engine import IntradayRecommendationEngine
            engine = IntradayRecommendationEngine()
            analysis_status = {
                'available': True,
                'last_scan': 'N/A',
                'recommendations_today': 0
            }
        except Exception as e:
            analysis_status = {
                'available': False,
                'error': str(e)
            }
        
        # Sprawdź uptime systemu
        import psutil
        import os
        try:
            process = psutil.Process(os.getpid())
            system_uptime = datetime.now() - datetime.fromtimestamp(process.create_time())
            uptime_str = f"{int(system_uptime.total_seconds() // 3600)}h {int((system_uptime.total_seconds() % 3600) // 60)}m"
        except:
            uptime_str = "N/A"
        
        # Sprawdź metryki systemu
        import threading
        active_threads = threading.active_count()
        
        # Sprawdź ostatnie błędy z logów (jeśli istnieją)
        recent_errors = []
        try:
            import glob
            log_files = glob.glob('*.log')
            if log_files:
                with open(log_files[0], 'r') as f:
                    lines = f.readlines()[-20:]  # Ostatnie 20 linii
                    recent_errors = [line.strip() for line in lines if 'ERROR' in line or 'CRITICAL' in line][-5:]
        except:
            pass
        
        return render_template("scheduler_monitoring.html",
                             multi_status=multi_status,
                             news_status=news_status,
                             espi_status=espi_status,
                             analysis_status=analysis_status,
                             system_uptime=uptime_str,
                             active_threads=active_threads,
                             recent_errors=recent_errors,
                             current_time=datetime.now())
    
    except Exception as e:
        logger.error(f"Błąd strony monitorowania: {e}")
        flash(f"❌ Błąd ładowania strony monitorowania: {e}", "danger")
        return redirect(url_for('index'))

# ================================
# API ENDPOINTS
# ================================

@scrapers_bp.route("/api/scheduler_status")
def api_scheduler_status():
    """API endpoint do pobierania statusu schedulera"""
    status = get_scheduler_status()
    return jsonify(status)

@scrapers_bp.route("/api/communications_stats")
def api_communications_stats():
    """API endpoint do pobierania statystyk komunikatów"""
    try:
        scraper = ESPIScraperRSS()
        stats = scraper.get_communications_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scrapers_bp.route("/api/espi_scheduler_status")
def api_espi_scheduler_status():
    """API endpoint do pobierania statusu schedulera komunikatów"""
    try:
        status = get_espi_scheduler_status()
        # Konwertuj datetime na string dla JSON
        if status.get('last_run'):
            status['last_run'] = status['last_run'].isoformat()
        if status.get('next_run'):
            status['next_run'] = status['next_run'].isoformat()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scrapers_bp.route("/api/espi_scheduler/start", methods=["POST"])
def api_start_espi_scheduler():
    """API endpoint do uruchamiania schedulera komunikatów"""
    try:
        success = start_espi_scraping()
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scrapers_bp.route("/api/espi_scheduler/stop", methods=["POST"])
def api_stop_espi_scheduler():
    """API endpoint do zatrzymywania schedulera komunikatów"""
    try:
        success = stop_espi_scraping()
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scrapers_bp.route("/api/espi_scheduler/interval", methods=["POST"])
def api_update_espi_interval():
    """API endpoint do zmiany interwału schedulera komunikatów"""
    try:
        data = request.get_json()
        hours = data.get('hours', 1)
        success = update_espi_interval(hours)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scrapers_bp.route("/api/espi_scheduler/manual", methods=["POST"])
def api_manual_espi_scrape():
    """API endpoint do ręcznego scrapowania komunikatów"""
    try:
        results = run_manual_espi_scrape()
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scrapers_bp.route("/api/news_stats")
def api_news_stats():
    """API endpoint do pobierania statystyk newsów"""
    try:
        scraper = NewsScraperOffline()
        stats = scraper.get_news_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === NEWS SCHEDULER API ENDPOINTS ===

@scrapers_bp.route("/api/news_scheduler_status")
def api_news_scheduler_status():
    """API endpoint do pobierania statusu news schedulera"""
    try:
        status = get_news_scheduler_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scrapers_bp.route("/api/news_scheduler/start", methods=["POST"])
def api_start_news_scheduler():
    """API endpoint do uruchamiania news schedulera"""
    try:
        success = start_news_scraping()
        if success:
            return jsonify({'status': 'success', 'message': 'News scheduler uruchomiony'})
        else:
            return jsonify({'status': 'error', 'message': 'Nie udało się uruchomić news schedulera'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scrapers_bp.route("/api/news_scheduler/stop", methods=["POST"])
def api_stop_news_scheduler():
    """API endpoint do zatrzymywania news schedulera"""
    try:
        success = stop_news_scraping()
        if success:
            return jsonify({'status': 'success', 'message': 'News scheduler zatrzymany'})
        else:
            return jsonify({'status': 'error', 'message': 'Nie udało się zatrzymać news schedulera'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scrapers_bp.route("/api/news_scheduler/interval", methods=["POST"])
def api_update_news_scheduler_interval():
    """API endpoint do zmiany interwału news schedulera"""
    try:
        data = request.get_json()
        news_interval = data.get('news_interval')
        espi_interval = data.get('espi_interval')
        
        results = []
        
        if news_interval is not None:
            success = update_news_interval(int(news_interval))
            results.append(f"News interval: {'✅' if success else '❌'}")
        
        if espi_interval is not None:
            success = update_espi_interval_news(int(espi_interval))
            results.append(f"ESPI interval: {'✅' if success else '❌'}")
        
        message = " | ".join(results)
        return jsonify({"status": "success", "message": message})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Błąd: {str(e)}"})

@scrapers_bp.route("/api/news_scheduler/manual_news", methods=["POST"])
def api_manual_news_scrape():
    """API endpoint do manualnego scrapowania newsów"""
    try:
        success = run_manual_news_scrape()
        if success:
            return jsonify({'status': 'success', 'message': 'Scrapowanie newsów uruchomione'})
        else:
            return jsonify({'status': 'error', 'message': 'Nie udało się uruchomić scrapowania newsów'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scrapers_bp.route("/api/news_scheduler/manual_espi", methods=["POST"])
def api_manual_espi_scrape_news():
    """API endpoint do manualnego scrapowania komunikatów ESPI/EBI przez news scheduler"""
    try:
        success = run_manual_espi_scrape_news()
        if success:
            return jsonify({'status': 'success', 'message': 'Scrapowanie komunikatów ESPI/EBI uruchomione'})
        else:
            return jsonify({'status': 'error', 'message': 'Nie udało się uruchomić scrapowania ESPI/EBI'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scrapers_bp.route("/api/monitoring/schedulers")
def api_scheduler_monitoring():
    """API endpoint dla monitorowania schedulerów (AJAX)"""
    try:
        # Pobierz status wszystkich schedulerów
        multi_status = get_scheduler_status()
        news_status = get_news_scheduler_status()
        espi_status = get_espi_scheduler_status()
        
        # Metryki systemu
        import threading
        import psutil
        import os
        
        active_threads = threading.active_count()
        
        try:
            process = psutil.Process(os.getpid())
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
        except:
            cpu_percent = 0
            memory_mb = 0
        
        return jsonify({
            'success': True,
            'schedulers': {
                'multi_ticker': multi_status,
                'news': news_status,
                'espi': espi_status
            },
            'system': {
                'active_threads': active_threads,
                'cpu_percent': cpu_percent,
                'memory_mb': memory_mb
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
