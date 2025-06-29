#!/usr/bin/env python3
"""
Prawdziwy scraper komunikatów ESPI/EBI z GPW RSS
Używa rzeczywistego RSS feed GPW i poprawnie parsuje linki
Autor: System GPW Investor
Data: 2025-06-24
"""

import os
import re
import sys
import requests
import feedparser
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from typing import List, Dict, Optional
import time
import logging

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ESPIScraperRSS:
    """Prawdziwy scraper komunikatów ESPI/EBI z GPW RSS"""
    
    def __init__(self):
        """Inicjalizacja scrapera"""
        load_dotenv('.env')
        
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD')
        self.db_host = os.getenv('DB_HOST')
        self.db_port = os.getenv('DB_PORT')
        self.db_name = os.getenv('DB_NAME')
        
        if not all([self.db_user, self.db_password, self.db_host, self.db_port, self.db_name]):
            raise ValueError("Brak kompletnej konfiguracji bazy danych w pliku .env")
        
        self.engine = create_engine(f'postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}')
        
        # RSS URLs dla komunikatów GPW - prawdziwe endpointy
        self.rss_urls = {
            'KOMUNIKATY_PRASOWE': 'https://www.gpw.pl/rss_komunikaty_prasowe',
            'AKTUALNOSCI': 'https://www.gpw.pl/rss_aktualnosci', 
            'KOMUNIKATY': 'https://www.gpw.pl/rss_komunikaty',  # Główne komunikaty ESPI/EBI
            'KOMUNIKATY_INDEKSOWE': 'https://www.gpw.pl/rss_komunikaty_indeksowe',
            'UCHWALY_ZARZAD': 'https://www.gpw.pl/rss_uchwaly_zarzad',
            'KALENDARIUM': 'https://www.gpw.pl/rss-kalendarium-zdarzen'
        }
        
        # Headers dla requestów
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
        
        # Lista aktywnych tickerów (będzie ładowana z bazy)
        self.active_tickers = []
        self.load_active_tickers()
        
        logger.info("✓ ESPI RSS Scraper zainicjalizowany")
    
    def load_active_tickers(self):
        """Ładuje listę aktywnych tickerów z bazy danych"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT DISTINCT ticker 
                    FROM ticker_mappings 
                    WHERE is_active = true
                    ORDER BY ticker
                """))
                
                self.active_tickers = [row[0] for row in result.fetchall()]
                logger.info(f"✓ Załadowano {len(self.active_tickers)} aktywnych tickerów")
                
        except Exception as e:
            logger.error(f"❌ Błąd ładowania tickerów: {e}")
            self.active_tickers = ['PKN', 'CDPROJEKT', 'KGHM', 'JSW', 'CCC', 'PGE', 'ALIOR']
    
    def extract_ticker_from_title(self, title: str) -> Optional[str]:
        """Wyciąga ticker spółki z tytułu komunikatu"""
        if not title:
            return None
            
        # Wzorce do wyszukiwania tickerów w tytule
        patterns = [
            r'\b([A-Z]{2,10})\s*[-–]\s*',  # TICKER - tytuł
            r'^\s*([A-Z]{2,10})\s*:',      # TICKER: tytuł
            r'\(([A-Z]{2,10})\)',          # (TICKER)
            r'\b([A-Z]{2,10})\s+S\.A\.',   # TICKER S.A.
            r'^([A-Z]{2,10})\s+',          # TICKER na początku
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title.upper())
            if match:
                potential_ticker = match.group(1)
                # Sprawdź czy to jeden z naszych aktywnych tickerów
                if potential_ticker in self.active_tickers:
                    return potential_ticker
        
        # Mapowanie pełnych nazw na tickery
        name_mapping = {
            'PKN ORLEN': 'PKN',
            'PKNORLEN': 'PKN', 
            'CD PROJEKT': 'CDPROJEKT',
            'CDPROJEKT': 'CDPROJEKT',
            'KGHM POLSKA MIEDŹ': 'KGHM',
            'KGHM': 'KGHM',
            'JASTRZĘBSKA SPÓŁKA WĘGLOWA': 'JSW',
            'JSW': 'JSW',
            'CCC': 'CCC',
            'POLSKA GRUPA ENERGETYCZNA': 'PGE',
            'PGE': 'PGE',
            'ALIOR BANK': 'ALIOR',
            'ALIOR': 'ALIOR'
        }
        
        title_upper = title.upper()
        for name, ticker in name_mapping.items():
            if name in title_upper and ticker in self.active_tickers:
                return ticker
        
        return None
    
    def parse_rss_feed(self, rss_url: str, feed_type: str) -> List[Dict]:
        """Parsuje RSS feed z komunikatami"""
        try:
            logger.info(f"📡 Pobieranie RSS feed {feed_type} z {rss_url}")
            
            # Pobierz RSS feed
            response = requests.get(rss_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # Parsuj feed
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                logger.warning(f"⚠️ Brak wpisów w RSS feed {feed_type}")
                return []
            
            logger.info(f"✓ Znaleziono {len(feed.entries)} wpisów w RSS feed {feed_type}")
            
            communications = []
            
            for entry in feed.entries:
                try:
                    # Wyciągnij dane z wpisu RSS
                    title = str(entry.title) if hasattr(entry, 'title') and entry.title else ""
                    link = str(entry.link) if hasattr(entry, 'link') and entry.link else ""
                    description = str(entry.description) if hasattr(entry, 'description') and entry.description else ""
                    
                    # Parsuj datę publikacji
                    pub_date = datetime.now()
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed and isinstance(entry.published_parsed, tuple):
                            pub_date = datetime(*entry.published_parsed[:6])
                        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed and isinstance(entry.updated_parsed, tuple):
                            pub_date = datetime(*entry.updated_parsed[:6])
                    except (TypeError, ValueError) as e:
                        logger.debug(f"⚠️ Błąd parsowania daty: {e}")
                        pub_date = datetime.now()
                    
                    # Sprawdź czy link jest poprawny
                    if not link or not link.startswith('http'):
                        logger.debug(f"⚠️ Niepoprawny link: {link}")
                        continue
                    
                    # Wyciągnij ticker z tytułu
                    ticker = self.extract_ticker_from_title(title)
                    if not ticker:
                        logger.debug(f"⚠️ Nie znaleziono tickera w tytule: {title}")
                        continue
                    
                    # Określ typ komunikatu na podstawie URL lub tytułu
                    communication_type = feed_type
                    if 'espi' in link.lower() or 'espi' in title.lower():
                        communication_type = 'ESPI'
                    elif 'ebi' in link.lower() or 'ebi' in title.lower():
                        communication_type = 'EBI'
                    
                    # Utwórz unikalny ID komunikatu
                    comm_id = f"{communication_type}_{ticker}_{pub_date.strftime('%Y%m%d_%H%M')}_{abs(hash(title)) % 10000}"
                    
                    # Pobierz pełną treść komunikatu ze strony
                    content = self.extract_communication_content(link)
                    if not content:
                        content = description  # Fallback na opis z RSS
                    
                    communication = {
                        'ticker': ticker,
                        'communication_id': comm_id,
                        'publication_date': pub_date,
                        'title': title.strip(),
                        'content': content.strip() if content else "",
                        'communication_type': communication_type,
                        'url': link
                    }
                    
                    communications.append(communication)
                    logger.info(f"✓ Przetworzone {communication_type} dla {ticker}: {title[:60]}...")
                    
                except Exception as e:
                    logger.debug(f"⚠️ Błąd przetwarzania wpisu RSS: {e}")
                    continue
            
            logger.info(f"✅ Przetworzone {len(communications)} komunikatów z RSS {feed_type}")
            return communications
            
        except Exception as e:
            logger.error(f"❌ Błąd pobierania RSS feed {feed_type}: {e}")
            return []
    
    def extract_communication_content(self, url: str) -> Optional[str]:
        """Wyciąga pełną treść komunikatu ze strony GPW"""
        if not url:
            return None
        
        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Szukaj głównej treści komunikatu
            content_selectors = [
                '.communication-content',
                '.espi-content',
                '.ebi-content',
                '.main-content',
                '.content',
                'main',
                '#content',
                '.article-content'
            ]
            
            content = None
            for selector in content_selectors:
                elem = soup.select_one(selector)
                if elem:
                    content = elem.get_text(strip=True)
                    if len(content) > 50:  # Sprawdź czy treść ma sens
                        break
            
            # Jeśli nie znaleziono konkretnego selektora, weź tekst z body
            if not content or len(content) < 50:
                body = soup.find('body')
                if body and hasattr(body, 'find_all'):
                    # Usuń skrypty i style
                    for script in body.find_all(["script", "style", "nav", "header", "footer"]):
                        script.decompose()
                    content = body.get_text(strip=True)
                elif body:
                    content = body.get_text(strip=True)
            
            # Ogranicz długość treści
            if content and len(content) > 2000:
                content = content[:2000] + "..."
            
            return content
            
        except Exception as e:
            logger.debug(f"⚠️ Błąd pobierania treści z {url}: {e}")
            return None
    
    def save_communication(self, communication: Dict) -> bool:
        """Zapisuje komunikat do bazy danych"""
        try:
            with self.engine.connect() as conn:
                # Sprawdź czy komunikat już istnieje
                existing = conn.execute(text("""
                    SELECT id FROM espi_communications 
                    WHERE communication_id = :comm_id
                """), {'comm_id': communication['communication_id']})
                
                if existing.fetchone():
                    logger.debug(f"📋 Komunikat już istnieje: {communication['communication_id']}")
                    return False
                
                # Zapisz nowy komunikat
                conn.execute(text("""
                    INSERT INTO espi_communications 
                    (ticker, communication_id, publication_date, title, content, 
                     communication_type, url, is_processed)
                    VALUES 
                    (:ticker, :communication_id, :publication_date, :title, :content,
                     :communication_type, :url, :is_processed)
                """), {
                    'ticker': communication['ticker'],
                    'communication_id': communication['communication_id'],
                    'publication_date': communication['publication_date'],
                    'title': communication['title'],
                    'content': communication['content'],
                    'communication_type': communication['communication_type'],
                    'url': communication['url'],
                    'is_processed': False
                })
                
                conn.commit()
                logger.info(f"✅ Zapisano komunikat {communication['communication_type']} dla {communication['ticker']}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd zapisu komunikatu: {e}")
            return False
    
    def scrape_all_communications(self, days_back: int = 7) -> Dict[str, int]:
        """Scrapuje wszystkie komunikaty z RSS feeds"""
        logger.info(f"🚀 Rozpoczynam scrapowanie komunikatów RSS z ostatnich {days_back} dni")
        
        results = {'KOMUNIKATY': 0, 'PRASOWE': 0, 'UCHWALY': 0, 'INDEKSOWE': 0, 'total': 0}
        cutoff_date = datetime.now() - timedelta(days=days_back)
        total_saved = 0
        
        # Scrapuj główne RSS feeds
        feeds_to_scrape = [
            ('KOMUNIKATY', 'KOMUNIKATY'),  # Główne komunikaty ESPI/EBI
            ('KOMUNIKATY_PRASOWE', 'PRASOWE'),
            ('UCHWALY_ZARZAD', 'UCHWALY'),
            ('KOMUNIKATY_INDEKSOWE', 'INDEKSOWE')
        ]
        
        for feed_key, result_key in feeds_to_scrape:
            feed_url = self.rss_urls[feed_key]
            logger.info(f"\n📊 Przetwarzanie RSS feed {feed_key}...")
            
            communications = self.parse_rss_feed(feed_url, feed_key)
            
            # Filtruj komunikaty z ostatnich X dni
            recent_communications = [
                comm for comm in communications 
                if comm['publication_date'] >= cutoff_date
            ]
            
            logger.info(f"✓ Znaleziono {len(recent_communications)} komunikatów z ostatnich {days_back} dni")
            
            # Zapisz do bazy danych
            saved_count = 0
            for comm in recent_communications:
                if self.save_communication(comm):
                    saved_count += 1
                
                # Krótka przerwa między zapisami
                time.sleep(0.2)
            
            results[result_key] = saved_count
            total_saved += saved_count
            
            logger.info(f"✅ Zapisano {saved_count} nowych komunikatów z {feed_key}")
        
        results['total'] = total_saved
        
        logger.info(f"🎉 Łącznie zapisano {total_saved} nowych komunikatów")
        logger.info(f"   Komunikaty: {results['KOMUNIKATY']}")
        logger.info(f"   Prasowe: {results['PRASOWE']}")
        logger.info(f"   Uchwały: {results['UCHWALY']}")
        logger.info(f"   Indeksowe: {results['INDEKSOWE']}")
        
        return results
    
    def get_communications_for_ticker(self, ticker: str, days_back: int = 30) -> List[Dict]:
        """Pobiera komunikaty dla konkretnego tickera z ostatnich dni"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT ticker, communication_id, publication_date, title, 
                           content, communication_type, url, is_processed
                    FROM espi_communications 
                    WHERE ticker = :ticker 
                    AND publication_date >= :cutoff_date
                    ORDER BY publication_date DESC
                """), {
                    'ticker': ticker,
                    'cutoff_date': datetime.now() - timedelta(days=days_back)
                })
                
                communications = []
                for row in result.fetchall():
                    communications.append({
                        'ticker': row[0],
                        'communication_id': row[1],
                        'publication_date': row[2],
                        'title': row[3],
                        'content': row[4],
                        'communication_type': row[5],
                        'url': row[6],
                        'is_processed': row[7]
                    })
                
                return communications
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania komunikatów dla {ticker}: {e}")
            return []

    def get_recent_communications(self, limit: int = 50) -> List[Dict]:
        """Pobiera najnowsze komunikaty ze wszystkich spółek"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT ticker, communication_id, publication_date, title, 
                           communication_type, url, is_processed
                    FROM espi_communications 
                    ORDER BY publication_date DESC
                    LIMIT :limit
                """), {'limit': limit})
                
                communications = []
                for row in result.fetchall():
                    communications.append({
                        'ticker': row[0],
                        'communication_id': row[1],
                        'publication_date': row[2],
                        'title': row[3],
                        'communication_type': row[4],
                        'url': row[5],
                        'is_processed': row[6]
                    })
                
                return communications
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania najnowszych komunikatów: {e}")
            return []

    def get_communications_stats(self) -> Dict:
        """Pobiera statystyki komunikatów"""
        try:
            with self.engine.connect() as conn:
                # Ogólne statystyki
                total_result = conn.execute(text("SELECT COUNT(*) FROM espi_communications"))
                total_row = total_result.fetchone()
                total = total_row[0] if total_row else 0
                
                # Statystyki per typ
                type_result = conn.execute(text("""
                    SELECT communication_type, COUNT(*) 
                    FROM espi_communications 
                    GROUP BY communication_type
                """))
                
                type_stats = {}
                for row in type_result.fetchall():
                    type_stats[row[0]] = row[1]
                
                # Najnowszy komunikat
                newest_result = conn.execute(text("""
                    SELECT publication_date FROM espi_communications 
                    ORDER BY publication_date DESC LIMIT 1
                """))
                newest_row = newest_result.fetchone()
                newest = newest_row[0] if newest_row else None
                
                return {
                    'total': total,
                    'by_type': type_stats,
                    'newest_date': newest
                }
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania statystyk: {e}")
            return {'total': 0, 'by_type': {}, 'newest_date': None}


def main():
    """Funkcja główna - test scrapera RSS"""
    print("🚀 ESPI/EBI RSS Scraper - Test")
    print("=" * 50)
    
    try:
        scraper = ESPIScraperRSS()
        
        # Test scrapowania komunikatów z RSS
        print("\n📊 Rozpoczynam scrapowanie komunikatów z RSS...")
        results = scraper.scrape_all_communications(days_back=7)
        
        print(f"\n📈 Wyniki scrapowania RSS:")
        print(f"   Komunikaty: {results['KOMUNIKATY']} nowych komunikatów")
        print(f"   Prasowe: {results['PRASOWE']} nowych komunikatów")
        print(f"   Uchwały: {results['UCHWALY']} nowych komunikatów")
        print(f"   Indeksowe: {results['INDEKSOWE']} nowych komunikatów")
        print(f"   Łącznie: {results['total']} komunikatów")
        
        # Test pobierania dla konkretnego tickera
        if scraper.active_tickers:
            test_ticker = scraper.active_tickers[0]
            print(f"\n📋 Komunikaty dla {test_ticker}:")
            ticker_comms = scraper.get_communications_for_ticker(test_ticker, days_back=30)
            for comm in ticker_comms[:5]:  # Pokaż 5 najnowszych
                print(f"   {comm['publication_date'].strftime('%Y-%m-%d %H:%M')} | {comm['communication_type']} | {comm['title'][:60]}...")
                print(f"     URL: {comm['url']}")
        
        print("\n🎉 Test RSS scrapera zakończony pomyślnie!")
        
    except Exception as e:
        print(f"❌ Błąd podczas testowania RSS scrapera: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
