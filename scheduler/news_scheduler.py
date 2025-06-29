#!/usr/bin/env python3
"""
Scheduler dla newsów finansowych i komunikatów ESPI/EBI
Automatyczne pobieranie artykułów i komunikatów giełdowych w regularnych odstępach
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
from workers.news_scraper_offline import NewsScraperOffline
from workers.espi_scraper_rss import ESPIScraperRSS

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NewsScheduler:
    """Scheduler dla automatycznego pobierania newsów finansowych i komunikatów ESPI/EBI"""
    
    def __init__(self):
        """Inicjalizacja schedulera"""
        self.scheduler = BackgroundScheduler()
        self.news_scraper = NewsScraperOffline()
        self.espi_scraper = ESPIScraperRSS()
        
        # Statusy
        self.is_running = False
        self.last_news_run = None
        self.last_espi_run = None
        self.last_news_results = {'total': 0, 'by_portal': {}}
        self.last_espi_results = {'ESPI': 0, 'EBI': 0, 'total': 0}
        
        # Interwały (w minutach)
        self.news_interval_minutes = 30  # Co 30 minut newsów
        self.espi_interval_minutes = 60  # Co godzinę komunikaty ESPI/EBI
        
        # Ustawienia pobierania
        self.news_days_back = 1  # Pobieraj newsy z ostatniego dnia
        self.espi_days_back = 1  # Pobieraj komunikaty z ostatniego dnia
        
        logger.info("✓ News Scheduler zainicjalizowany")
    
    def news_scraping_job(self):
        """Job do scrapowania newsów finansowych"""
        try:
            logger.info("📰 Rozpoczynam automatyczne scrapowanie newsów finansowych")
            
            # Pobierz newsy z portali finansowych
            results = self.news_scraper.scrape_all_news(days_back=self.news_days_back)
            
            self.last_news_run = datetime.now()
            
            # Oblicz total
            total_articles = sum(results.values()) if isinstance(results, dict) else 0
            
            self.last_news_results = {
                'total': total_articles,
                'by_portal': results if isinstance(results, dict) else {}
            }
            
            logger.info(f"✅ Scrapowanie newsów zakończone. Pobrano {total_articles} artykułów")
            
            # Log szczegółów po portalach
            if isinstance(results, dict):
                for portal, count in results.items():
                    if count > 0:
                        logger.info(f"   📊 {portal}: {count} artykułów")
                    
        except Exception as e:
            logger.error(f"❌ Błąd podczas scrapowania newsów: {e}")
            self.last_news_results = {'total': 0, 'by_portal': {}, 'error': str(e)}
    
    def espi_scraping_job(self):
        """Job do scrapowania komunikatów ESPI/EBI"""
        try:
            logger.info("📋 Rozpoczynam automatyczne scrapowanie komunikatów ESPI/EBI")
            
            # Pobierz komunikaty ESPI/EBI
            results = self.espi_scraper.scrape_all_communications(days_back=self.espi_days_back)
            
            self.last_espi_run = datetime.now()
            self.last_espi_results = results
            
            total_communications = results.get('total', 0)
            logger.info(f"✅ Scrapowanie komunikatów zakończone. Pobrano {total_communications} komunikatów")
            
            # Log szczegółów po typach
            espi_count = results.get('ESPI', 0)
            ebi_count = results.get('EBI', 0)
            if espi_count > 0:
                logger.info(f"   📊 ESPI: {espi_count} komunikatów")
            if ebi_count > 0:
                logger.info(f"   📊 EBI: {ebi_count} komunikatów")
                    
        except Exception as e:
            logger.error(f"❌ Błąd podczas scrapowania komunikatów ESPI/EBI: {e}")
            self.last_espi_results = {'ESPI': 0, 'EBI': 0, 'total': 0, 'error': str(e)}
    
    def start_scraping(self):
        """Uruchom automatyczne scrapowanie"""
        if self.is_running:
            logger.warning("⚠️ Scheduler już działa")
            return False
        
        try:
            # Dodaj job dla newsów
            self.scheduler.add_job(
                func=self.news_scraping_job,
                trigger=IntervalTrigger(minutes=self.news_interval_minutes),
                id='news_scraping_job',
                name='Automatyczne pobieranie newsów finansowych',
                replace_existing=True,
                max_instances=1
            )
            
            # Dodaj job dla komunikatów ESPI/EBI
            self.scheduler.add_job(
                func=self.espi_scraping_job,
                trigger=IntervalTrigger(minutes=self.espi_interval_minutes),
                id='espi_scraping_job',
                name='Automatyczne pobieranie komunikatów ESPI/EBI',
                replace_existing=True,
                max_instances=1
            )
            
            self.scheduler.start()
            self.is_running = True
            
            logger.info(f"✅ News Scheduler uruchomiony:")
            logger.info(f"   📰 Newsy: co {self.news_interval_minutes} minut")
            logger.info(f"   📋 ESPI/EBI: co {self.espi_interval_minutes} minut")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd podczas uruchamiania schedulera: {e}")
            return False
    
    def stop_scraping(self):
        """Zatrzymaj automatyczne scrapowanie"""
        if not self.is_running:
            logger.warning("⚠️ Scheduler nie działa")
            return False
        
        try:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("✅ News Scheduler zatrzymany")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd podczas zatrzymywania schedulera: {e}")
            return False
    
    def update_news_interval(self, new_interval_minutes: int):
        """Aktualizuj interwał pobierania newsów"""
        if new_interval_minutes < 5:
            logger.warning("⚠️ Interwał newsów nie może być mniejszy niż 5 minut")
            return False
        
        self.news_interval_minutes = new_interval_minutes
        
        if self.is_running:
            # Usuń stary job i dodaj nowy z nowym interwałem
            self.scheduler.remove_job('news_scraping_job')
            self.scheduler.add_job(
                func=self.news_scraping_job,
                trigger=IntervalTrigger(minutes=self.news_interval_minutes),
                id='news_scraping_job',
                name='Automatyczne pobieranie newsów finansowych',
                replace_existing=True,
                max_instances=1
            )
        
        logger.info(f"✅ Interwał newsów zaktualizowany na {new_interval_minutes} minut")
        return True
    
    def update_espi_interval(self, new_interval_minutes: int):
        """Aktualizuj interwał pobierania komunikatów ESPI/EBI"""
        if new_interval_minutes < 15:
            logger.warning("⚠️ Interwał ESPI/EBI nie może być mniejszy niż 15 minut")
            return False
        
        self.espi_interval_minutes = new_interval_minutes
        
        if self.is_running:
            # Usuń stary job i dodaj nowy z nowym interwałem
            self.scheduler.remove_job('espi_scraping_job')
            self.scheduler.add_job(
                func=self.espi_scraping_job,
                trigger=IntervalTrigger(minutes=self.espi_interval_minutes),
                id='espi_scraping_job',
                name='Automatyczne pobieranie komunikatów ESPI/EBI',
                replace_existing=True,
                max_instances=1
            )
        
        logger.info(f"✅ Interwał ESPI/EBI zaktualizowany na {new_interval_minutes} minut")
        return True
    
    def update_news_days_back(self, new_days_back: int):
        """Aktualizuj liczbę dni wstecz dla newsów"""
        if new_days_back < 1 or new_days_back > 7:
            logger.warning("⚠️ Liczba dni dla newsów musi być między 1 a 7")
            return False
        
        self.news_days_back = new_days_back
        logger.info(f"✅ Zakres dni dla newsów zaktualizowany na {new_days_back} dni")
        return True
    
    def update_espi_days_back(self, new_days_back: int):
        """Aktualizuj liczbę dni wstecz dla komunikatów ESPI/EBI"""
        if new_days_back < 1 or new_days_back > 7:
            logger.warning("⚠️ Liczba dni dla ESPI/EBI musi być między 1 a 7")
            return False
        
        self.espi_days_back = new_days_back
        logger.info(f"✅ Zakres dni dla ESPI/EBI zaktualizowany na {new_days_back} dni")
        return True
    
    def run_manual_news_scrape(self):
        """Uruchom jednorazowe scrapowanie newsów"""
        try:
            logger.info("🔧 Uruchamianie manualnego scrapowania newsów")
            self.news_scraping_job()
            return True
        except Exception as e:
            logger.error(f"❌ Błąd podczas manualnego scrapowania newsów: {e}")
            return False
    
    def run_manual_espi_scrape(self):
        """Uruchom jednorazowe scrapowanie komunikatów ESPI/EBI"""
        try:
            logger.info("🔧 Uruchamianie manualnego scrapowania komunikatów ESPI/EBI")
            self.espi_scraping_job()
            return True
        except Exception as e:
            logger.error(f"❌ Błąd podczas manualnego scrapowania komunikatów ESPI/EBI: {e}")
            return False
    
    def get_status(self):
        """Pobierz status schedulera"""
        jobs = []
        if self.is_running and self.scheduler.get_jobs():
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'N/A'
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run': next_run
                })
        
        return {
            'is_running': self.is_running,
            'jobs': jobs,
            'news_interval_minutes': self.news_interval_minutes,
            'espi_interval_minutes': self.espi_interval_minutes,
            'news_days_back': self.news_days_back,
            'espi_days_back': self.espi_days_back,
            'last_news_run': self.last_news_run.strftime('%Y-%m-%d %H:%M:%S') if self.last_news_run else None,
            'last_espi_run': self.last_espi_run.strftime('%Y-%m-%d %H:%M:%S') if self.last_espi_run else None,
            'last_news_results': self.last_news_results,
            'last_espi_results': self.last_espi_results
        }


# Globalny singleton schedulera
_news_scheduler = None

def get_news_scheduler():
    """Pobierz instancję globalnego news schedulera"""
    global _news_scheduler
    if _news_scheduler is None:
        _news_scheduler = NewsScheduler()
    return _news_scheduler

def start_news_scraping():
    """Uruchom news scheduler"""
    scheduler = get_news_scheduler()
    return scheduler.start_scraping()

def stop_news_scraping():
    """Zatrzymaj news scheduler"""
    scheduler = get_news_scheduler()
    return scheduler.stop_scraping()

def get_news_scheduler_status():
    """Pobierz status news schedulera"""
    scheduler = get_news_scheduler()
    return scheduler.get_status()

def run_manual_news_scrape():
    """Uruchom manualne scrapowanie newsów"""
    scheduler = get_news_scheduler()
    return scheduler.run_manual_news_scrape()

def run_manual_espi_scrape():
    """Uruchom manualne scrapowanie komunikatów ESPI/EBI"""
    scheduler = get_news_scheduler()
    return scheduler.run_manual_espi_scrape()

def update_news_interval(new_interval_minutes: int):
    """Aktualizuj interwał newsów"""
    scheduler = get_news_scheduler()
    return scheduler.update_news_interval(new_interval_minutes)

def update_espi_interval(new_interval_minutes: int):
    """Aktualizuj interwał ESPI/EBI"""
    scheduler = get_news_scheduler()
    return scheduler.update_espi_interval(new_interval_minutes)

def update_news_days_back(new_days_back: int):
    """Aktualizuj zakres dni dla newsów"""
    scheduler = get_news_scheduler()
    return scheduler.update_news_days_back(new_days_back)

def update_espi_days_back(new_days_back: int):
    """Aktualizuj zakres dni dla ESPI/EBI"""
    scheduler = get_news_scheduler()
    return scheduler.update_espi_days_back(new_days_back)


if __name__ == "__main__":
    """Test schedulera"""
    logger.info("🧪 Test News Schedulera")
    
    scheduler = NewsScheduler()
    
    # Test manualny
    logger.info("📰 Test manualnego scrapowania newsów...")
    scheduler.run_manual_news_scrape()
    
    logger.info("📋 Test manualnego scrapowania ESPI/EBI...")
    scheduler.run_manual_espi_scrape()
    
    # Status
    status = scheduler.get_status()
    logger.info(f"📊 Status: {status}")
    
    logger.info("✅ Test zakończony")
