#!/usr/bin/env python3
"""
Scraper komunikatów ESPI/EBI z GPW
Pobiera komunikaty giełdowe poprzez RSS feed i zapisuje do bazy danych
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


class ESPIScraper:
    """Scraper komunikatów ESPI/EBI z GPW"""
    
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
        
        # URLs do stron z komunikatami GPW (zamiast RSS)
        self.communication_urls = {
            'ESPI': 'https://www.gpw.pl/komunikaty-espi',
            'EBI': 'https://www.gpw.pl/komunikaty-ebi'
        }
        
        # Headers dla requestów
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache'
        }
        
        # Lista aktywnych tickerów (będzie ładowana z bazy)
        self.active_tickers = []
        self.load_active_tickers()
        
        logger.info("✓ ESPI Scraper zainicjalizowany")
    
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
            self.active_tickers = []
    
    def extract_ticker_from_title(self, title: str) -> Optional[str]:
        """Wyciąga ticker spółki z tytułu komunikatu"""
        # Wzorce do wyszukiwania tickerów w tytule
        patterns = [
            r'\b([A-Z]{2,10})\s*[-–]\s*',  # TICKER - tytuł
            r'^\s*([A-Z]{2,10})\s*:',      # TICKER: tytuł
            r'\(([A-Z]{2,10})\)',          # (TICKER)
            r'\b([A-Z]{2,10})\s+S\.A\.',   # TICKER S.A.
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                potential_ticker = match.group(1)
                # Sprawdź czy to jeden z naszych aktywnych tickerów
                if potential_ticker in self.active_tickers:
                    return potential_ticker
        
        # Jeśli nie znaleziono w tytule, spróbuj dopasować do nazw spółek
        title_upper = title.upper()
        
        # Mapowanie nazw na tickery (można rozszerzyć)
        name_mapping = {
            'PKN ORLEN': 'PKN',
            'CD PROJEKT': 'CDPROJEKT',
            'KGHM': 'KGHM',
            'JSW': 'JSW',
            'CCC': 'CCC'
        }
        
        for name, ticker in name_mapping.items():
            if name in title_upper and ticker in self.active_tickers:
                return ticker
        
        return None
    
    def scrape_gpw_page(self, page_url: str, communication_type: str) -> List[Dict]:
        """Scrapuje stronę GPW z komunikatami zamiast RSS"""
        try:
            logger.info(f"📡 Scraping {communication_type} z {page_url}")
            
            response = requests.get(page_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            communications = []
            
            # Szukaj tabeli z komunikatami (może wymagać dostosowania do aktualnej struktury GPW)
            table_selectors = [
                'table.table-communications',
                'table.espi-table',
                'table.ebi-table',
                '.communications-table',
                'table tbody tr',
                '.table tbody tr'
            ]
            
            rows = []
            for selector in table_selectors:
                rows = soup.select(selector)
                if rows:
                    logger.info(f"✓ Znaleziono {len(rows)} wierszy z selektorem: {selector}")
                    break
            
            if not rows:
                # Jeśli nie ma tabeli, szukaj innych struktur
                comm_selectors = [
                    '.communication-item',
                    '.espi-item',
                    '.ebi-item',
                    '.news-item',
                    'article'
                ]
                
                for selector in comm_selectors:
                    items = soup.select(selector)
                    if items:
                        logger.info(f"✓ Znaleziono {len(items)} elementów z selektorem: {selector}")
                        rows = items
                        break
            
            # Procesuj znalezione elementy
            for i, row in enumerate(rows[:20]):  # Maksymalnie 20 najnowszych
                try:
                    # Szukaj tytułu/linku w bardziej bezpieczny sposób
                    title_elem = row.find('a')
                    title = ""
                    link = ""
                    
                    if title_elem:
                        try:
                            title = title_elem.get_text(strip=True)
                            link = title_elem.attrs.get('href', '') if title_elem.attrs else ""
                        except AttributeError:
                            title = str(title_elem).strip()
                    else:
                        # Jeśli nie ma linka, weź pierwszy tekst
                        title = row.get_text(strip=True)
                    
                    if not title or len(title) < 10:
                        continue
                    
                    # Spróbuj wyciągnąć datę
                    date_elem = row.find(class_=re.compile(r'date|time')) or row.find('time')
                    pub_date = datetime.now()  # Domyślnie obecna data
                    
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        # Spróbuj sparsować datę (może wymagać dostosowania)
                        try:
                            pub_date = datetime.strptime(date_text, '%Y-%m-%d')
                        except:
                            try:
                                pub_date = datetime.strptime(date_text, '%d.%m.%Y')
                            except:
                                pass
                    
                    # Wyciągnij ticker
                    ticker = self.extract_ticker_from_title(title)
                    if not ticker:
                        continue
                    
                    # Utwórz unikalny ID
                    comm_id = f"{communication_type}_{ticker}_{pub_date.strftime('%Y%m%d')}_{abs(hash(title)) % 10000}"
                    
                    # Pobierz pełną treść jeśli jest link
                    full_url = link
                    if link and not link.startswith('http'):
                        full_url = f"https://www.gpw.pl{link}"
                    
                    content = self.extract_communication_content(full_url) if full_url else None
                    
                    communication = {
                        'ticker': ticker,
                        'communication_id': comm_id,
                        'publication_date': pub_date,
                        'title': title,
                        'content': content,
                        'communication_type': communication_type,
                        'url': full_url
                    }
                    
                    communications.append(communication)
                    logger.info(f"✓ Przetworzone {communication_type} dla {ticker}: {title[:50]}...")
                    
                except Exception as e:
                    logger.debug(f"⚠️ Błąd przetwarzania elementu {i}: {e}")
                    continue
            
            logger.info(f"✅ Znaleziono {len(communications)} komunikatów {communication_type}")
            return communications
            
        except Exception as e:
            logger.error(f"❌ Błąd scrapowania strony {communication_type}: {e}")
            return []
    
    def extract_communication_content(self, url: str) -> Optional[str]:
        """Wyciąga treść komunikatu ze strony GPW"""
        if not url:
            return None
        
        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Spróbuj znaleźć treść komunikatu (może wymagać dostosowania do struktury GPW)
            content_selectors = [
                '.communication-content',
                '.espi-content',
                '.ebi-content',
                '.main-content',
                '.content-body',
                'article',
                '.post-content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    return content_elem.get_text(strip=True)
            
            # Jeśli nie znaleziono specyficznego selektora, weź tekst z body
            body = soup.find('body')
            if body:
                text = body.get_text(strip=True)
                # Ogranicz długość do rozumnej wartości
                return text[:5000] if len(text) > 5000 else text
            
        except Exception as e:
            logger.warning(f"⚠️ Nie udało się pobrać treści z {url}: {e}")
        
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
        """Scrapuje wszystkie komunikaty ESPI/EBI z ostatnich dni"""
        logger.info(f"🚀 Rozpoczynam scrapowanie komunikatów z ostatnich {days_back} dni")
        
        results = {'ESPI': 0, 'EBI': 0, 'total': 0}
        
        for comm_type, page_url in self.communication_urls.items():
            logger.info(f"\n📊 Przetwarzanie {comm_type}...")
            
            communications = self.scrape_gpw_page(page_url, comm_type)
            
            # Filtruj komunikaty z ostatnich X dni
            cutoff_date = datetime.now() - timedelta(days=days_back)
            recent_communications = [
                comm for comm in communications 
                if comm['publication_date'] >= cutoff_date
            ]
            
            # Zapisz do bazy danych
            saved_count = 0
            for comm in recent_communications:
                if self.save_communication(comm):
                    saved_count += 1
                
                # Krótka przerwa między zapisami
                time.sleep(0.1)
            
            results[comm_type] = saved_count
            results['total'] += saved_count
            
            logger.info(f"✅ Zapisano {saved_count} nowych komunikatów {comm_type}")
            
            # Przerwa między różnymi typami komunikatów
            time.sleep(1)
        
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


def main():
    """Funkcja główna - test scrapera"""
    print("🚀 ESPI/EBI Scraper - Test")
    print("=" * 50)
    
    try:
        scraper = ESPIScraper()
        
        # Test scrapowania komunikatów
        print("\n📊 Rozpoczynam scrapowanie komunikatów...")
        results = scraper.scrape_all_communications(days_back=30)
        
        print(f"\n📈 Wyniki scrapowania:")
        print(f"   ESPI: {results['ESPI']} nowych komunikatów")
        print(f"   EBI: {results['EBI']} nowych komunikatów")
        print(f"   Łącznie: {results['total']} komunikatów")
        
        # Pokaż najnowsze komunikaty
        print(f"\n📋 Najnowsze komunikaty:")
        recent = scraper.get_recent_communications(limit=10)
        for comm in recent:
            print(f"   {comm['publication_date'].strftime('%Y-%m-%d %H:%M')} | {comm['ticker']} | {comm['communication_type']} | {comm['title'][:50]}...")
        
        print("\n🎉 Test zakończony pomyślnie!")
        
    except Exception as e:
        print(f"❌ Błąd podczas testowania: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
