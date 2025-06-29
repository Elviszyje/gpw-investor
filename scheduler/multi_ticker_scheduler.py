#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import sys
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Dodanie ścieżki do workers
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'workers'))

from bankier_scraper import BankierScraper


class MultiTickerScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.config = self.load_config()
        self.is_running = False
        
        # Inicjalizuj scraper do pobierania tickerów z bazy
        try:
            settings = self.config.get('scraping_settings', {})
            self.scraper = BankierScraper(
                use_selenium=False,  # Do pobierania listy tickerów nie trzeba Selenium
                headless=True
            )
        except Exception as e:
            print(f"⚠️ Błąd inicjalizacji scrapera: {e}")
            self.scraper = None
    
    def load_config(self):
        """Ładuje konfigurację tickerów z pliku JSON"""
        # Try multiple possible locations for tickers_config.json
        possible_paths = [
            '/app/tickers_config.json',  # Docker app root (first priority)
            os.path.join(os.getcwd(), 'tickers_config.json'),  # Current working directory
            os.path.join(os.path.dirname(__file__), '..', 'tickers_config.json'),  # Original path
        ]
        
        config = None
        config_path = None
        
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if config_path:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    print(f"✅ Załadowano konfigurację z {config_path}")
                    if 'active_tickers' in config:
                        print(f"📋 Znaleziono {len(config['active_tickers'])} aktywnych tickerów")
                    return config
            except Exception as e:
                print(f"❌ Błąd ładowania konfiguracji z {config_path}: {e}")
        
        print(f"⚠️ Nie znaleziono pliku tickers_config.json, używam domyślnej konfiguracji")
        # Domyślna konfiguracja
        return {
            "active_tickers": ["PKN", "CDR", "PKO"],
            "scraping_settings": {
                "interval_minutes": 15,
                "use_selenium": True,
                    "headless": True,
                    "max_retries": 3
                }
            }
    
    def save_config(self):
        """Zapisuje konfigurację do pliku JSON"""
        # Try multiple possible locations for tickers_config.json
        possible_paths = [
            '/app/tickers_config.json',  # Docker app root (first priority)
            os.path.join(os.getcwd(), 'tickers_config.json'),  # Current working directory
            os.path.join(os.path.dirname(__file__), '..', 'tickers_config.json'),  # Original path
        ]
        
        # Try to save to first writable location
        for config_path in possible_paths:
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=4, ensure_ascii=False)
                    print(f"✅ Konfiguracja zapisana pomyślnie do {config_path}")
                    return True
            except Exception as e:
                print(f"⚠️ Nie można zapisać do {config_path}: {e}")
                continue
        
        print(f"❌ Nie można zapisać konfiguracji do żadnej z lokalizacji")
        return False
    
    def add_ticker(self, ticker):
        """Dodaje ticker do listy aktywnych - modyfikuje bazę danych"""
        ticker = ticker.upper()
        
        # Jeśli mamy dostęp do bazy danych, używaj jej
        if self.scraper and hasattr(self.scraper, 'engine') and self.scraper.engine:
            try:
                from sqlalchemy import text
                from datetime import datetime
                
                with self.scraper.engine.connect() as conn:
                    # Sprawdź czy ticker już istnieje
                    result = conn.execute(text(
                        "SELECT ticker, is_active FROM ticker_mappings WHERE ticker = :ticker"
                    ), {"ticker": ticker})
                    
                    existing = result.fetchone()
                    
                    if existing:
                        # Ticker istnieje - aktywuj go jeśli nieaktywny
                        if not existing[1]:  # is_active = False
                            conn.execute(text("""
                                UPDATE ticker_mappings 
                                SET is_active = true, updated_at = :updated_at 
                                WHERE ticker = :ticker
                            """), {
                                'ticker': ticker,
                                'updated_at': datetime.utcnow()
                            })
                            conn.commit()
                            print(f"Aktywowano istniejący ticker: {ticker}")
                            return True
                        else:
                            print(f"Ticker {ticker} już jest aktywny")
                            return False
                    else:
                        # Ticker nie istnieje - dodaj nowy
                        conn.execute(text("""
                            INSERT INTO ticker_mappings (ticker, bankier_symbol, description, is_active, created_at, updated_at)
                            VALUES (:ticker, :bankier_symbol, :description, :is_active, :created_at, :updated_at)
                        """), {
                            'ticker': ticker,
                            'bankier_symbol': ticker,  # Domyślnie symbol = ticker
                            'description': f'Automatycznie dodany ticker {ticker}',
                            'is_active': True,
                            'created_at': datetime.utcnow(),
                            'updated_at': datetime.utcnow()
                        })
                        conn.commit()
                        print(f"Dodano nowy ticker do bazy: {ticker}")
                        return True
                        
            except Exception as e:
                print(f"Błąd podczas dodawania tickera do bazy: {e}")
                # Fallback do pliku JSON
                pass
        
        # Fallback - użyj pliku JSON
        if ticker not in self.config['active_tickers']:
            self.config['active_tickers'].append(ticker)
            self.save_config()
            print(f"Dodano ticker do pliku JSON: {ticker}")
            return True
        else:
            print(f"Ticker {ticker} już istnieje w pliku JSON")
            return False
    
    def remove_ticker(self, ticker):
        """Usuwa ticker z listy aktywnych - modyfikuje bazę danych"""
        ticker = ticker.upper()
        
        # Jeśli mamy dostęp do bazy danych, używaj jej
        if self.scraper and hasattr(self.scraper, 'engine') and self.scraper.engine:
            try:
                from sqlalchemy import text
                from datetime import datetime
                
                with self.scraper.engine.connect() as conn:
                    # Sprawdź czy ticker istnieje i jest aktywny
                    result = conn.execute(text(
                        "SELECT ticker, is_active FROM ticker_mappings WHERE ticker = :ticker"
                    ), {"ticker": ticker})
                    
                    existing = result.fetchone()
                    
                    if existing and existing[1]:  # istnieje i is_active = True
                        # Deaktywuj ticker (nie usuwaj, żeby zachować dane historyczne)
                        conn.execute(text("""
                            UPDATE ticker_mappings 
                            SET is_active = false, updated_at = :updated_at 
                            WHERE ticker = :ticker
                        """), {
                            'ticker': ticker,
                            'updated_at': datetime.utcnow()
                        })
                        conn.commit()
                        print(f"Deaktywowano ticker w bazie: {ticker}")
                        return True
                    elif existing and not existing[1]:
                        print(f"Ticker {ticker} już jest nieaktywny")
                        return False
                    else:
                        print(f"Ticker {ticker} nie istnieje w bazie")
                        return False
                        
            except Exception as e:
                print(f"Błąd podczas usuwania tickera z bazy: {e}")
                # Fallback do pliku JSON
                pass
        
        # Fallback - użyj pliku JSON
        if ticker in self.config['active_tickers']:
            self.config['active_tickers'].remove(ticker)
            self.save_config()
            print(f"Usunięto ticker z pliku JSON: {ticker}")
            return True
        else:
            print(f"Ticker {ticker} nie istnieje w pliku JSON")
            return False
    
    def get_active_tickers(self):
        """Pobiera listę aktywnych tickerów"""
        # Spróbuj pobrać z bazy danych przez scraper
        if self.scraper:
            try:
                db_tickers = self.scraper.get_active_tickers()
                if db_tickers:
                    print(f"✓ Pobrano {len(db_tickers)} tickerów z bazy danych")
                    return db_tickers
            except Exception as e:
                print(f"⚠️ Błąd pobierania tickerów z bazy: {e}")
        
        # Fallback - użyj konfiguracji z pliku
        return self.config.get('active_tickers', [])
    
    def update_scraping_interval(self, minutes):
        """Aktualizuje interwał scrapowania"""
        self.config['scraping_settings']['interval_minutes'] = minutes
        self.save_config()
        
        # Restart schedulera jeśli jest uruchomiony
        if self.is_running:
            success = self.restart()
            if success:
                print(f"Zaktualizowano interwał na {minutes} minut i restartowano scheduler")
            else:
                print(f"Zaktualizowano interwał na {minutes} minut ale błąd restartu schedulera")
        else:
            print(f"Zaktualizowano interwał na {minutes} minut")
    
    def scrape_job(self):
        """Funkcja wykonywana przez scheduler - scrapuje wszystkie aktywne tickery"""
        try:
            # Sprawdź czy scheduler nie został zatrzymany w międzyczasie
            if not self.is_running:
                print("Scheduler został zatrzymany - anulowanie zadania")
                return
            
            print(f"\n=== Cykliczne scrapowanie - {datetime.now()} ===")
            
            active_tickers = self.get_active_tickers()
            
            if not active_tickers:
                print("Brak aktywnych tickerów do scrapowania")
                return
            
            # Sprawdź ponownie czy scheduler nie został zatrzymany
            if not self.is_running:
                print("Scheduler został zatrzymany podczas pobierania tickerów - anulowanie")
                return
            
            # Inicjalizacja scrapera do scrapowania (z Selenium) jeśli potrzeba
            settings = self.config['scraping_settings']
            
            # Sprawdź czy scraper istnieje i jest sprawny
            if not hasattr(self, 'scraping_scraper') or not self.scraping_scraper:
                if not self.is_running:  # Sprawdź przed inicjalizacją
                    return
                    
                try:
                    self.scraping_scraper = BankierScraper(
                        use_selenium=settings.get('use_selenium', True),
                        headless=settings.get('headless', True)
                    )
                except Exception as e:
                    print(f"Błąd inicjalizacji scrapera: {e}")
                    return
            
            # Ostatnie sprawdzenie przed scrapowaniem
            if not self.is_running:
                print("Scheduler zatrzymany przed rozpoczęciem scrapowania")
                return
            
            results = self.scraping_scraper.scrape_multiple_tickers(active_tickers)
            
            # Sprawdź czy nadal działamy przed wypisaniem wyników
            if self.is_running:
                print(f"Cykliczne scrapowanie zakończone:")
                print(f"  Udane: {len(results['success'])} tickerów")
                print(f"  Nieudane: {len(results['failed'])} tickerów")
                
                if results['failed']:
                    print(f"  Błędy dla: {', '.join(results['failed'])}")
                
        except Exception as e:
            print(f"Błąd podczas cyklicznego scrapowania: {e}")
            
            # W przypadku poważnego błędu, spróbuj zrestartować scraper
            if hasattr(self, 'scraping_scraper') and self.scraping_scraper:
                try:
                    self.scraping_scraper.close()
                    self.scraping_scraper = None
                except:
                    pass
    
    def start(self):
        """Uruchamia cykliczne scrapowanie"""
        if self.is_running:
            print("Scheduler już jest uruchomiony")
            return False
        
        try:
            # Bezpieczne zamknięcie poprzedniego schedulera jeśli istnieje
            if hasattr(self, 'scheduler') and self.scheduler:
                try:
                    if self.scheduler.running:
                        self.scheduler.shutdown(wait=False)
                except:
                    pass
            
            # Utworzenie nowego schedulera
            self.scheduler = BackgroundScheduler()
            
            interval_minutes = self.config['scraping_settings']['interval_minutes']
            
            # Sprawdzenie czy interwał nie jest zbyt krótki
            if interval_minutes < 3:
                print(f"⚠️ Ostrzeżenie: Interwał {interval_minutes} min może być zbyt krótki. Zalecane minimum: 3 min")
            
            # Dodanie zadania do schedulera
            self.scheduler.add_job(
                func=self.scrape_job,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id='multi_ticker_scrape',
                name='Multi Ticker Scraping',
                replace_existing=True,
                max_instances=1,  # Tylko jedna instancja na raz
                coalesce=True,    # Jeśli zadanie się opóźni, nie uruchamiaj kolejnego
                misfire_grace_time=30  # 30 sekund tolerancji na opóźnienie
            )
            
            # Uruchomienie schedulera
            self.scheduler.start()
            self.is_running = True
            
            print(f"Cykliczne scrapowanie uruchomione (interwał: {interval_minutes} min)")
            print(f"Aktywne tickery: {', '.join(self.get_active_tickers())}")
            
            return True
            
        except Exception as e:
            print(f"Błąd podczas uruchamiania schedulera: {e}")
            self.is_running = False
            return False
    
    def stop(self):
        """Zatrzymuje cykliczne scrapowanie"""
        if not self.is_running:
            print("Scheduler nie jest uruchomiony")
            return False
        
        try:
            # Oznacz jako zatrzymany przed shutdown
            self.is_running = False
            
            # Usuń wszystkie zadania przed shutdown
            if hasattr(self, 'scheduler') and self.scheduler:
                if self.scheduler.running:
                    try:
                        self.scheduler.remove_all_jobs()
                    except:
                        pass
                    
                    # Zatrzymaj scheduler bez oczekiwania na zadania
                    try:
                        self.scheduler.shutdown(wait=False)
                    except:
                        pass
            
            # Zamknięcie scraperow
            if hasattr(self, 'scraping_scraper') and self.scraping_scraper:
                try:
                    self.scraping_scraper.close()
                except:
                    pass
                self.scraping_scraper = None
                
            if self.scraper:
                try:
                    self.scraper.close()
                except:
                    pass
                self.scraper = None
            
            print("Cykliczne scrapowanie zatrzymane")
            return True
            
        except Exception as e:
            print(f"Błąd podczas zatrzymywania schedulera: {e}")
            self.is_running = False
            return False
    
    def restart(self):
        """Bezpieczny restart schedulera"""
        try:
            print("Restartowanie schedulera...")
            was_running = self.is_running
            
            if was_running:
                self.stop()
                
            # Krótka przerwa żeby wszystko się wyczyściło
            import time
            time.sleep(2)
            
            if was_running:
                return self.start()
            else:
                print("Scheduler nie był uruchomiony - brak restartu")
                return True
                
        except Exception as e:
            print(f"Błąd podczas restartu schedulera: {e}")
            return False
    
    def safe_shutdown(self):
        """Bezpieczne zamknięcie schedulera z obsługą błędów"""
        try:
            if self.is_running and self.scheduler.running:
                # Usuń wszystkie zadania
                self.scheduler.remove_all_jobs()
                
                # Zatrzymaj scheduler
                self.scheduler.shutdown(wait=True)
                
            self.is_running = False
            
            # Zamknij wszystkie scrapery
            if hasattr(self, 'scraping_scraper') and self.scraping_scraper:
                try:
                    self.scraping_scraper.close()
                except:
                    pass
                self.scraping_scraper = None
                
            if self.scraper:
                try:
                    self.scraper.close()
                except:
                    pass
                self.scraper = None
                
            print("Scheduler bezpiecznie zamknięty")
            return True
            
        except Exception as e:
            print(f"Błąd podczas bezpiecznego zamykania: {e}")
            self.is_running = False
            return False
    
    def status(self):
        """Zwraca status schedulera"""
        return {
            'is_running': self.is_running,
            'active_tickers': self.get_active_tickers(),
            'interval_minutes': self.config['scraping_settings']['interval_minutes'],
            'use_selenium': self.config['scraping_settings']['use_selenium'],
            'next_run': None if not self.is_running else 'N/A'  # APScheduler nie udostępnia łatwo next_run
        }
    
    def run_manual_scrape(self, tickers=None):
        """Uruchamia ręczne scrapowanie dla wybranych tickerów"""
        if tickers is None:
            tickers = self.get_active_tickers()
        
        if not tickers:
            print("Brak tickerów do scrapowania")
            return {'success': [], 'failed': []}
        
        print(f"Ręczne scrapowanie tickerów: {', '.join(tickers)}")
        
        # Tymczasowy scraper dla ręcznego scrapowania
        settings = self.config['scraping_settings']
        temp_scraper = BankierScraper(
            use_selenium=settings.get('use_selenium', True),
            headless=settings.get('headless', True)
        )
        
        try:
            results = temp_scraper.scrape_multiple_tickers(tickers)
            return results
        finally:
            temp_scraper.close()


# Globalna instancja schedulera
multi_scheduler = MultiTickerScheduler()


def get_multi_scheduler():
    """Zwraca globalną instancję schedulera"""
    return multi_scheduler


def start_multi_ticker_scraping():
    """Uruchamia cykliczne scrapowanie wielu tickerów"""
    return multi_scheduler.start()


def stop_multi_ticker_scraping():
    """Zatrzymuje cykliczne scrapowanie"""
    return multi_scheduler.stop()


def get_scheduler_status():
    """Zwraca status schedulera"""
    return multi_scheduler.status()


def run_manual_multi_scrape(tickers=None):
    """Uruchamia ręczne scrapowanie"""
    return multi_scheduler.run_manual_scrape(tickers)


if __name__ == "__main__":
    # Test schedulera
    print("=== Test Multi Ticker Scheduler ===")
    
    scheduler = MultiTickerScheduler()
    
    # Wyświetlenie statusu
    status = scheduler.status()
    print(f"Status: {status}")
    
    # Test ręcznego scrapowania
    print("\nTest ręcznego scrapowania 2 tickerów...")
    results = scheduler.run_manual_scrape(['PKN', 'CDR'])
    print(f"Wyniki: {results}")
    
    print("\nTest zakończony")
