#!/usr/bin/env python3
"""
Scheduler dla komunikatów ESPI/EBI
Automatyczne pobieranie komunikatów giełdowych w regularnych odstępach
Autor: System GPW Investor
Data: 2025-06-24
"""

import os
import sys
import time
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

# Dodaj ścieżkę do modułów
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workers.espi_scraper_rss import ESPIScraperRSS

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ESPIScheduler:
    """Scheduler dla automatycznego pobierania komunikatów ESPI/EBI"""
    
    def __init__(self):
        """Inicjalizacja schedulera"""
        self.scheduler = BackgroundScheduler()
        self.scraper = ESPIScraperRSS()
        self.is_running = False
        self.last_run = None
        self.last_results = {'ESPI': 0, 'EBI': 0, 'total': 0}
        self.interval_hours = 1  # Domyślnie co godzinę
        
        logger.info("✓ ESPI Scheduler zainicjalizowany")
    
    def communication_scraping_job(self):
        """Job do scrapowania komunikatów"""
        try:
            logger.info("🚀 Rozpoczynam automatyczne scrapowanie komunikatów ESPI/EBI")
            
            # Pobierz komunikaty z ostatnich 2 dni (żeby nie przegapić niczego)
            results = self.scraper.scrape_all_communications(days_back=2)
            
            self.last_run = datetime.now()
            self.last_results = results
            
            if results['total'] > 0:
                logger.info(f"✅ Pobrano {results['total']} nowych komunikatów (ESPI: {results['ESPI']}, EBI: {results['EBI']})")
            else:
                logger.info("📋 Brak nowych komunikatów do pobrania")
                
        except Exception as e:
            logger.error(f"❌ Błąd podczas automatycznego scrapowania komunikatów: {e}")
    
    def start_scheduler(self) -> bool:
        """Uruchamia automatyczne scrapowanie komunikatów"""
        if self.is_running:
            logger.warning("⚠️ Scheduler komunikatów już jest uruchomiony")
            return False
        
        try:
            # Dodaj job do schedulera
            self.scheduler.add_job(
                func=self.communication_scraping_job,
                trigger=IntervalTrigger(hours=self.interval_hours),
                id='espi_scraping_job',
                name='Scrapowanie komunikatów ESPI/EBI',
                replace_existing=True
            )
            
            # Uruchom scheduler
            self.scheduler.start()
            self.is_running = True
            
            logger.info(f"✅ Scheduler komunikatów uruchomiony (interwał: {self.interval_hours}h)")
            
            # Wykonaj pierwszy run od razu
            threading.Thread(target=self.communication_scraping_job, daemon=True).start()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd uruchamiania schedulera komunikatów: {e}")
            return False
    
    def stop_scheduler(self) -> bool:
        """Zatrzymuje automatyczne scrapowanie komunikatów"""
        if not self.is_running:
            logger.warning("⚠️ Scheduler komunikatów nie jest uruchomiony")
            return False
        
        try:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("✅ Scheduler komunikatów zatrzymany")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd zatrzymywania schedulera komunikatów: {e}")
            return False
    
    def update_interval(self, hours: int) -> bool:
        """Aktualizuje interwał scrapowania"""
        try:
            self.interval_hours = max(1, min(24, hours))  # Min 1h, max 24h
            
            if self.is_running:
                # Zatrzymaj i uruchom ponownie z nowym interwałem
                self.scheduler.remove_job('espi_scraping_job')
                self.scheduler.add_job(
                    func=self.communication_scraping_job,
                    trigger=IntervalTrigger(hours=self.interval_hours),
                    id='espi_scraping_job',
                    name='Scrapowanie komunikatów ESPI/EBI',
                    replace_existing=True
                )
            
            logger.info(f"✅ Interwał scrapowania komunikatów zmieniony na {self.interval_hours}h")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd zmiany interwału: {e}")
            return False
    
    def get_status(self) -> dict:
        """Zwraca status schedulera"""
        next_run = None
        if self.is_running and self.scheduler.get_jobs():
            job = self.scheduler.get_job('espi_scraping_job')
            if job and job.next_run_time:
                next_run = job.next_run_time
        
        return {
            'is_running': self.is_running,
            'interval_hours': self.interval_hours,
            'last_run': self.last_run,
            'next_run': next_run,
            'last_results': self.last_results
        }
    
    def manual_run(self) -> dict:
        """Ręczne uruchomienie scrapowania"""
        logger.info("🔧 Ręczne uruchomienie scrapowania komunikatów")
        
        try:
            results = self.scraper.scrape_all_communications(days_back=7)
            self.last_run = datetime.now()
            self.last_results = results
            
            logger.info(f"✅ Ręczne scrapowanie zakończone: {results['total']} komunikatów")
            return results
            
        except Exception as e:
            logger.error(f"❌ Błąd ręcznego scrapowania: {e}")
            return {'ESPI': 0, 'EBI': 0, 'total': 0, 'error': str(e)}


# Globalna instancja schedulera
_espi_scheduler = None

def get_espi_scheduler() -> ESPIScheduler:
    """Zwraca globalną instancję schedulera komunikatów"""
    global _espi_scheduler
    if _espi_scheduler is None:
        _espi_scheduler = ESPIScheduler()
    return _espi_scheduler

def start_espi_scraping() -> bool:
    """Uruchamia automatyczne scrapowanie komunikatów"""
    scheduler = get_espi_scheduler()
    return scheduler.start_scheduler()

def stop_espi_scraping() -> bool:
    """Zatrzymuje automatyczne scrapowanie komunikatów"""
    scheduler = get_espi_scheduler()
    return scheduler.stop_scheduler()

def get_espi_scheduler_status() -> dict:
    """Zwraca status schedulera komunikatów"""
    scheduler = get_espi_scheduler()
    return scheduler.get_status()

def run_manual_espi_scrape() -> dict:
    """Uruchamia ręczne scrapowanie komunikatów"""
    scheduler = get_espi_scheduler()
    return scheduler.manual_run()

def update_espi_interval(hours: int) -> bool:
    """Aktualizuje interwał scrapowania komunikatów"""
    scheduler = get_espi_scheduler()
    return scheduler.update_interval(hours)


def main():
    """Funkcja główna - test schedulera"""
    print("🚀 ESPI Scheduler - Test")
    print("=" * 50)
    
    try:
        scheduler = get_espi_scheduler()
        
        # Test statusu
        status = scheduler.get_status()
        print(f"\n📊 Status początkowy:")
        print(f"   Uruchomiony: {status['is_running']}")
        print(f"   Interwał: {status['interval_hours']}h")
        
        # Test ręcznego uruchomienia
        print(f"\n🔧 Test ręcznego scrapowania...")
        results = scheduler.manual_run()
        print(f"   Wyniki: ESPI={results['ESPI']}, EBI={results['EBI']}, Łącznie={results['total']}")
        
        # Test uruchomienia schedulera
        print(f"\n⏰ Test uruchomienia schedulera...")
        if scheduler.start_scheduler():
            print("   ✅ Scheduler uruchomiony")
            
            # Poczekaj chwilę i sprawdź status
            time.sleep(2)
            status = scheduler.get_status()
            print(f"   Status: {status['is_running']}")
            if status['next_run']:
                print(f"   Następne uruchomienie: {status['next_run']}")
            
            # Zatrzymaj scheduler
            print(f"\n🛑 Zatrzymywanie schedulera...")
            if scheduler.stop_scheduler():
                print("   ✅ Scheduler zatrzymany")
        
        print("\n🎉 Test zakończony pomyślnie!")
        
    except Exception as e:
        print(f"❌ Błąd podczas testowania: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
