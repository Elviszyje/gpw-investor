#!/usr/bin/env python3
"""
News Scraper Offline - Scraper artykułów z portali finansowych z zapisem lokalnym
Pobiera artykuły z Bankier, Money.pl i zapisuje kopie HTML lokalnie
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
from typing import List, Dict, Optional, Any, Union
import time
import logging
from urllib.parse import urljoin, urlparse
import hashlib
from pathlib import Path

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NewsScraperOffline:
    """Scraper artykułów z portali finansowych z zapisem lokalnym"""
    
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
        
        # Katalog do przechowywania plików HTML (container-safe path)
        self.storage_dir = Path('/app/storage/articles')
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Konfiguracja portali finansowych
        self.portals = {
            'BANKIER': {
                'name': 'Bankier.pl',
                'rss_urls': [
                    'https://www.bankier.pl/rss/wiadomosci.xml',
                    'https://www.bankier.pl/rss/gielda.xml',
                    'https://www.bankier.pl/rss/spolki.xml'
                ],
                'base_url': 'https://www.bankier.pl'
            },
            'MONEY': {
                'name': 'Money.pl',
                'rss_urls': [
                    'https://www.money.pl/rss/',
                ],
                'base_url': 'https://www.money.pl'
            }
        }
        
        # Headers dla requestów
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Lista aktywnych tickerów (będzie ładowana z bazy)
        self.active_tickers = []
        self.load_active_tickers()
        
        logger.info("✓ News Scraper Offline zainicjalizowany")
        logger.info(f"✓ Katalog storage: {self.storage_dir}")
    
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
    
    def extract_tickers_from_content(self, title: str, content: str = "") -> List[str]:
        """Wyciąga tickery spółek z tytułu i treści"""
        text_to_search = f"{title} {content}".upper()
        found_tickers = []
        
        # Wzorce do wyszukiwania tickerów
        ticker_patterns = [
            r'\b([A-Z]{2,10})\s*[-–]\s*',  # TICKER - tytuł
            r'^\s*([A-Z]{2,10})\s*:',      # TICKER: tytuł
            r'\(([A-Z]{2,10})\)',          # (TICKER)
            r'\b([A-Z]{2,10})\s+S\.A\.',   # TICKER S.A.
            r'^([A-Z]{2,10})\s+',          # TICKER na początku
        ]
        
        for pattern in ticker_patterns:
            matches = re.findall(pattern, text_to_search)
            for match in matches:
                if match in self.active_tickers and match not in found_tickers:
                    found_tickers.append(match)
        
        # Mapowanie pełnych nazw na tickery
        name_mapping = {
            'PKN ORLEN': 'PKN',
            'PKNORLEN': 'PKN',
            'CD PROJEKT': 'CDPROJEKT',
            'CDPROJEKT': 'CDPROJEKT',
            'KGHM POLSKA MIEDŹ': 'KGHM',
            'JASTRZĘBSKA SPÓŁKA WĘGLOWA': 'JSW',
            'POLISH GAMES': 'PGS',
            'ALLEGRO': 'ALE'
        }
        
        for name, ticker in name_mapping.items():
            if name in text_to_search and ticker not in found_tickers and ticker in self.active_tickers:
                found_tickers.append(ticker)
        
        return found_tickers
    
    def parse_rss_feed(self, rss_url: str, portal_name: str) -> List[Dict]:
        """Parsuje RSS feed z artykułami"""
        try:
            logger.info(f"📡 Pobieranie RSS feed {portal_name} z {rss_url}")
            
            # Pobierz RSS feed
            response = requests.get(rss_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # Parsuj feed
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                logger.warning(f"⚠️ Brak wpisów w RSS feed {portal_name}")
                return []
            
            logger.info(f"✓ Znaleziono {len(feed.entries)} artykułów w RSS feed {portal_name}")
            
            articles = []
            
            for entry in feed.entries:
                try:
                    # Wyciągnij podstawowe dane z RSS
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
                    
                    # Utwórz ID artykułu na podstawie URL
                    article_id = hashlib.md5(link.encode()).hexdigest()[:12]
                    
                    article = {
                        'id': article_id,
                        'title': title.strip(),
                        'link': link,
                        'description': description,
                        'publication_date': pub_date,
                        'portal': portal_name,
                        'tickers': []  # Będą wyciągnięte po zapisaniu HTML
                    }
                    
                    articles.append(article)
                    
                except Exception as e:
                    logger.debug(f"⚠️ Błąd przetwarzania wpisu RSS: {e}")
                    continue
            
            logger.info(f"✅ Przetworzone {len(articles)} artykułów z RSS {portal_name}")
            return articles
            
        except Exception as e:
            logger.error(f"❌ Błąd pobierania RSS feed {portal_name}: {e}")
            return []
    
    def save_article_html(self, article: Dict) -> Optional[str]:
        """Pobiera i zapisuje HTML artykułu lokalnie"""
        try:
            url = article['link']
            article_id = article['id']
            portal = article['portal']
            
            # Utwórz ścieżkę do pliku
            date_str = article['publication_date'].strftime('%Y-%m-%d')
            filename = f"{date_str}_{portal}_{article_id}.html"
            file_path = self.storage_dir / filename
            
            # Sprawdź czy plik już istnieje
            if file_path.exists():
                logger.debug(f"📁 HTML już istnieje: {filename}")
                return str(file_path)
            
            # Pobierz stronę
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            
            # Lepsze zarządzanie kodowaniem - ważne dla skompresowanych odpowiedzi
            response.encoding = response.apparent_encoding or 'utf-8'
            
            # Zapisz HTML do pliku używając response.text (nie response.content)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            logger.info(f"💾 Zapisano HTML: {filename} ({len(response.text)} znaków)")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"❌ Błąd zapisu HTML dla {article['title'][:50]}...: {e}")
            return None
    
    def extract_content_from_html(self, html_path: str, portal_name: str) -> str:
        """Wyciąga treść z zapisanego pliku HTML"""
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Różne strategie dla różnych portali
            if portal_name == 'BANKIER':
                # Dla Bankier próbuj paragrafów w article
                article_elements = soup.select('article p')
                if article_elements:
                    content = '\n\n'.join([p.get_text(strip=True) for p in article_elements if p.get_text(strip=True)])
                    if len(content) > 100:
                        return content[:2000]  # Ogranicz długość
            
            # Ogólne selektory dla innych portali
            selectors = ['.article-content', '.entry-content', '.content-body', '.article-body', 'article', 'main']
            
            for selector in selectors:
                elem = soup.select_one(selector)
                if elem:
                    # Usuń niepotrzebne elementy
                    for unwanted in elem.find_all(['script', 'style', 'nav', 'aside', 'footer']):
                        if hasattr(unwanted, 'decompose'):
                            unwanted.decompose()
                    
                    content = elem.get_text(strip=True)
                    if len(content) > 100:
                        return content[:2000]  # Ogranicz długość
            
            # Fallback - weź tekst z body
            body = soup.find('body')
            if body and hasattr(body, 'find_all'):
                try:
                    # Usuń niepotrzebne elementy używając selektorów CSS
                    for unwanted in soup.select('script, style, nav, header, footer, aside'):
                        if hasattr(unwanted, 'decompose'):
                            unwanted.decompose()
                    content = body.get_text(strip=True)
                    return content[:2000] if content else ""
                except Exception:
                    # Jeśli nie można usunąć elementów, po prostu weź tekst
                    content = body.get_text(strip=True)
                    return content[:2000] if content else ""
            
            return ""
            
        except Exception as e:
            logger.error(f"❌ Błąd wyciągania treści z {html_path}: {e}")
            return ""
    
    def save_article_to_db(self, article: Dict, html_path: str) -> bool:
        """Zapisuje artykuł do bazy danych"""
        try:
            # Wyciągnij treść z zapisanego HTML
            content = self.extract_content_from_html(html_path, article['portal'])
            
            # Wyciągnij tickery z tytułu i treści
            tickers = self.extract_tickers_from_content(article['title'], content)
            
            with self.engine.connect() as conn:
                # Sprawdź czy artykuł już istnieje
                existing = conn.execute(text("""
                    SELECT id FROM news 
                    WHERE source = :source
                """), {'source': article['link']})
                
                if existing.fetchone():
                    logger.debug(f"📋 Artykuł już istnieje: {article['id']}")
                    return False
                
                # Zapisz artykuł - jeśli są tickery, zapisz osobno dla każdego
                if tickers:
                    for ticker in tickers:
                        # Znajdź company_id dla tickera
                        ticker_result = conn.execute(text("""
                            SELECT company_id FROM ticker_mappings 
                            WHERE ticker = :ticker AND is_active = true
                            LIMIT 1
                        """), {'ticker': ticker})
                        
                        ticker_row = ticker_result.fetchone()
                        if ticker_row:
                            company_id = ticker_row[0]
                            
                            conn.execute(text("""
                                INSERT INTO news 
                                (company_id, date, source, title, content)
                                VALUES 
                                (:company_id, :date, :source, :title, :content)
                            """), {
                                'company_id': company_id,
                                'date': article['publication_date'],
                                'source': article['link'],
                                'title': article['title'],
                                'content': content[:1000]  # Ogranicz treść w bazie
                            })
                else:
                    # Zapisz artykuł bez powiązania ze spółką
                    conn.execute(text("""
                        INSERT INTO news 
                        (company_id, date, source, title, content)
                        VALUES 
                        (:company_id, :date, :source, :title, :content)
                    """), {
                        'company_id': None,
                        'date': article['publication_date'],
                        'source': article['link'],
                        'title': article['title'],
                        'content': content[:1000]  # Ogranicz treść w bazie
                    })
                
                conn.commit()
                
                ticker_info = f" (tickery: {', '.join(tickers)})" if tickers else " (brak tickerów)"
                logger.info(f"✅ Zapisano artykuł: {article['title'][:50]}...{ticker_info}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd zapisu artykułu do bazy: {e}")
            return False
    
    def scrape_portal_articles(self, portal_name: str, days_back: int = 3) -> Dict[str, int]:
        """Scrapuje artykuły z konkretnego portalu"""
        portal_config = self.portals.get(portal_name)
        if not portal_config:
            logger.error(f"❌ Nieznany portal: {portal_name}")
            return {'total': 0, 'saved': 0, 'html_saved': 0}
        
        logger.info(f"🚀 Rozpoczynam scrapowanie artykułów z {portal_config['name']}")
        
        all_articles = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Pobierz artykuły ze wszystkich RSS feedów portalu
        for rss_url in portal_config['rss_urls']:
            articles = self.parse_rss_feed(rss_url, portal_name)
            all_articles.extend(articles)
        
        # Filtruj artykuły z ostatnich X dni
        recent_articles = [
            article for article in all_articles 
            if article['publication_date'] >= cutoff_date
        ]
        
        logger.info(f"✓ Znaleziono {len(recent_articles)} artykułów z ostatnich {days_back} dni")
        
        # Zapisz HTML i artykuły do bazy
        saved_count = 0
        html_saved_count = 0
        
        for i, article in enumerate(recent_articles, 1):
            try:
                logger.info(f"📄 Przetwarzanie artykułu {i}/{len(recent_articles)}: {article['title'][:50]}...")
                
                # Zapisz HTML artykułu
                html_path = self.save_article_html(article)
                if html_path:
                    html_saved_count += 1
                    
                    # Zapisz artykuł do bazy danych
                    if self.save_article_to_db(article, html_path):
                        saved_count += 1
                
                # Krótka przerwa między requestami
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Błąd przetwarzania artykułu: {e}")
                continue
        
        logger.info(f"🎉 Portal {portal_config['name']}: zapisano {html_saved_count} HTML, {saved_count} do bazy z {len(recent_articles)} artykułów")
        
        return {
            'total': len(recent_articles),
            'saved': saved_count,
            'html_saved': html_saved_count
        }
    
    def scrape_all_portals(self, days_back: int = 3) -> Dict[str, Dict[str, int]]:
        """Scrapuje artykuły ze wszystkich skonfigurowanych portali"""
        logger.info(f"🌐 Rozpoczynam scrapowanie artykułów ze wszystkich portali (ostatnie {days_back} dni)")
        
        results = {}
        total_saved = 0
        total_html_saved = 0
        
        for portal_name in self.portals.keys():
            try:
                portal_results = self.scrape_portal_articles(portal_name, days_back)
                results[portal_name] = portal_results
                total_saved += portal_results['saved']
                total_html_saved += portal_results['html_saved']
                
                # Przerwa między portalami
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Błąd scrapowania portalu {portal_name}: {e}")
                results[portal_name] = {'total': 0, 'saved': 0, 'html_saved': 0}
        
        logger.info(f"🎉 Łącznie zapisano {total_html_saved} plików HTML i {total_saved} artykułów do bazy")
        
        # Dodaj podsumowanie
        results['SUMMARY'] = {
            'total_saved': total_saved,
            'total_html_saved': total_html_saved,
            'portals_count': len([r for r in results.values() if isinstance(r, dict) and r.get('saved', 0) > 0])
        }
        
        return results
    
    def get_recent_news(self, source_filter: str = "", ticker_filter: str = "", days_back: int = 7, limit: int = 100) -> List[Dict]:
        """Pobiera najnowsze newsy z bazy danych z filtrowaniem"""
        try:
            # Dostosowano do struktury starej tabeli news
            base_query = """
                SELECT id, title, source, date, content
                FROM news 
                WHERE date >= :cutoff_date
            """
            
            cutoff_date = datetime.now() - timedelta(days=days_back)
            query_params: Dict[str, Any] = {'cutoff_date': cutoff_date}
            
            # Dodaj filtry - dla starej tabeli source jest URL więc szukamy po fragmencie
            if source_filter:
                base_query += " AND source LIKE :source_filter"
                query_params['source_filter'] = f"%{source_filter.lower()}%"
                
            # Note: stara tabela nie ma kolumny tickers, więc pomijamy ticker_filter
            
            base_query += " ORDER BY date DESC LIMIT :limit"
            query_params['limit'] = limit
            
            with self.engine.connect() as conn:
                result = conn.execute(text(base_query), query_params)
                
                news = []
                for row in result.fetchall():
                    # Wyciągnij nazwę portalu z URL
                    source_url = row[2] if row[2] else ""
                    portal_name = self._extract_portal_name(source_url)
                    
                    news.append({
                        'id': row[0],
                        'title': row[1] if row[1] else "Brak tytułu",
                        'url': source_url,  # Użyj pełnego URL z bazy
                        'source': portal_name,  # Wyciągnij nazwę portalu
                        'source_css': self._get_css_class_for_source(portal_name),  # Klasa CSS
                        'publication_date': row[3],
                        'tickers': [],  # Stara tabela nie ma tickerów
                        'html_path': None,  # Stara tabela nie ma html_path
                        'content_preview': row[4][:200] if row[4] else "",
                        'is_processed': True  # Zakładamy że stare są przetworzone
                    })
                
                return news
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania newsów: {e}")
            return []
    
    def _extract_portal_name(self, url: str) -> str:
        """Wyciąga nazwę portalu z URL"""
        if not url:
            return "Nieznane źródło"
        
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            
            # Mapowanie domen na czytelne nazwy
            domain_mapping = {
                'www.bankier.pl': 'Bankier.pl',
                'bankier.pl': 'Bankier.pl',
                'www.money.pl': 'Money.pl', 
                'money.pl': 'Money.pl',
                'www.parkiet.com': 'Parkiet.com',
                'parkiet.com': 'Parkiet.com'
            }
            
            return domain_mapping.get(domain, domain.replace('www.', '').title())
            
        except Exception:
            return "Nieznane źródło"
    
    def _get_css_class_for_source(self, source: str) -> str:
        """Konwertuje nazwę źródła na klasę CSS"""
        source_lower = source.lower()
        if 'bankier' in source_lower:
            return 'bankier'
        elif 'money' in source_lower:
            return 'money'
        elif 'parkiet' in source_lower:
            return 'parkiet'
        else:
            return 'other'
    
    def get_news_stats(self) -> Dict:
        """Pobiera statystyki newsów"""
        try:
            with self.engine.connect() as conn:
                # Ogólne statystyki
                total_result = conn.execute(text("SELECT COUNT(*) FROM news"))
                total_row = total_result.fetchone()
                total = total_row[0] if total_row else 0
                
                # Statystyki per źródło
                source_result = conn.execute(text("""
                    SELECT source, COUNT(*) 
                    FROM news 
                    GROUP BY source
                    ORDER BY COUNT(*) DESC
                """))
                
                source_stats = {}
                for row in source_result.fetchall():
                    portal_name = self._extract_portal_name(row[0])
                    if portal_name in source_stats:
                        source_stats[portal_name] += row[1]
                    else:
                        source_stats[portal_name] = row[1]
                
                # Najnowszy artykuł
                newest_result = conn.execute(text("""
                    SELECT date FROM news 
                    ORDER BY date DESC LIMIT 1
                """))
                newest_row = newest_result.fetchone()
                newest = newest_row[0] if newest_row else None
                
                # Artykuły z ostatnich 24h
                today_result = conn.execute(text("""
                    SELECT COUNT(*) FROM news 
                    WHERE date >= :cutoff_date
                """), {'cutoff_date': datetime.now() - timedelta(days=1)})
                today_row = today_result.fetchone()
                today_count = today_row[0] if today_row else 0
                
                return {
                    'total': total,
                    'by_source': source_stats,
                    'newest_date': newest,
                    'today_count': today_count
                }
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania statystyk newsów: {e}")
            return {'total': 0, 'by_source': {}, 'newest_date': None, 'today_count': 0}
    
    def get_available_sources(self) -> List[str]:
        """Pobiera listę dostępnych źródeł newsów"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT DISTINCT source 
                    FROM news 
                    WHERE source IS NOT NULL
                    ORDER BY source
                """))
                
                # Wyciągnij unikalne nazwy portali z URL-i
                sources = set()
                for row in result.fetchall():
                    portal_name = self._extract_portal_name(row[0])
                    if portal_name != "Nieznane źródło":
                        sources.add(portal_name)
                
                return sorted(list(sources))
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania źródeł: {e}")
            return []
    
    def get_active_tickers(self) -> List[str]:
        """Pobiera listę aktywnych tickerów (alias dla kompatybilności)"""
        return self.active_tickers
    
    def scrape_all_news(self, days_back: int = 3) -> Dict[str, int]:
        """Scrapuje newsy ze wszystkich portali (alias dla kompatybilności)"""
        results = self.scrape_all_portals(days_back=days_back)
        
        # Przekształć wyniki do prostszego formatu
        simple_results = {}
        for portal, stats in results.items():
            simple_results[portal] = stats.get('saved', 0)
        
        return simple_results
    


def main():
    """Funkcja główna - test scrapera offline"""
    print("🚀 News Scraper Offline - Test")
    print("=" * 50)
    
    try:
        scraper = NewsScraperOffline()
        
        # Test scrapowania artykułów
        print("\n📊 Rozpoczynam scrapowanie artykułów z portali finansowych...")
        results = scraper.scrape_all_portals(days_back=1)
        
        print(f"\n📈 Wyniki scrapowania portali:")
        for portal, stats in results.items():
            if portal != 'SUMMARY' and isinstance(stats, dict):
                print(f"   {portal}: {stats.get('html_saved', 0)} HTML, {stats.get('saved', 0)}/{stats.get('total', 0)} do bazy")
        
        if 'SUMMARY' in results:
            summary = results['SUMMARY']
            print(f"\n🎯 Podsumowanie:")
            print(f"   Łącznie zapisanych plików HTML: {summary.get('total_html_saved', 0)}")
            print(f"   Łącznie zapisanych do bazy: {summary.get('total_saved', 0)}")
            print(f"   Aktywnych portali: {summary.get('portals_count', 0)}")
            print(f"   Katalog storage: {scraper.storage_dir}")
        
        print("\n🎉 Test scrapera offline zakończony pomyślnie!")
        
    except Exception as e:
        print(f"❌ Błąd podczas testowania scrapera offline: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
