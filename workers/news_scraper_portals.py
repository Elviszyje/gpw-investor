#!/usr/bin/env python3
"""
News Scraper - Scraper artykułów z portali finansowych
Pobiera artykuły z Bankier, Money.pl, Parkiet.com i innych portali
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
from urllib.parse import urljoin, urlparse
import hashlib

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NewsScraperPortals:
    """Scraper artykułów z portali finansowych"""
    
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
        
        # Konfiguracja portali finansowych
        self.portals = {
            'BANKIER': {
                'name': 'Bankier.pl',
                'rss_urls': [
                    'https://www.bankier.pl/rss/wiadomosci.xml',
                    'https://www.bankier.pl/rss/gielda.xml',
                    'https://www.bankier.pl/rss/spolki.xml'
                ],
                'base_url': 'https://www.bankier.pl',
                'content_selectors': [
                    'article p',  # Paragrafy w article
                    'article',    # Cały article jako fallback
                    '.article-content',
                    '.entry-content', 
                    '.content',
                    '#article-body',
                    '.article-body'
                ]
            },
            'MONEY': {
                'name': 'Money.pl',
                'rss_urls': [
                    'https://www.money.pl/rss/',
                ],
                'base_url': 'https://www.money.pl',
                'content_selectors': [
                    '.article-content',
                    '.entry-content',
                    '.content-body',
                    '.article-body'
                ]
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
        
        # Lista aktywnych tickerów (dla filtrowania artykułów)
        self.active_tickers = []
        self.load_active_tickers()
        
        logger.info("✓ News Scraper zainicjalizowany")
    
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
    
    def extract_tickers_from_content(self, title: str, content: str) -> List[str]:
        """Wyciąga tickery spółek z tytułu i treści artykułu"""
        found_tickers = []
        text_to_search = f"{title} {content}".upper()
        
        # Szukaj tickerów z naszej listy aktywnych
        for ticker in self.active_tickers:
            patterns = [
                f"\\b{ticker}\\b",  # Exact match
                f"\\b{ticker}\\s+S\\.A\\.",  # TICKER S.A.
                f"\\({ticker}\\)",  # (TICKER)
            ]
            
            for pattern in patterns:
                if re.search(pattern, text_to_search):
                    if ticker not in found_tickers:
                        found_tickers.append(ticker)
                    break
        
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
                    
                    article = {
                        'title': title.strip(),
                        'link': link,
                        'description': description.strip() if description else "",
                        'publication_date': pub_date,
                        'portal': portal_name,
                        'content': "",  # Będzie pobrane osobno
                        'tickers': []   # Będą wyciągnięte po pobraniu treści
                    }
                    
                    articles.append(article)
                    logger.debug(f"✓ Dodano artykuł: {title[:60]}...")
                    
                except Exception as e:
                    logger.debug(f"⚠️ Błąd przetwarzania wpisu RSS: {e}")
                    continue
            
            logger.info(f"✅ Przetworzone {len(articles)} artykułów z RSS {portal_name}")
            return articles
            
        except Exception as e:
            logger.error(f"❌ Błąd pobierania RSS feed {portal_name}: {e}")
            return []
    
    def extract_article_content(self, url: str, portal_name: str) -> Optional[str]:
        """Wyciąga pełną treść artykułu ze strony"""
        if not url:
            return None
        
        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            
            # Proste ustawienie kodowania
            if not response.encoding or response.encoding == 'ISO-8859-1':
                response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Pobierz selektory dla danego portalu
            portal_config = self.portals.get(portal_name, {})
            content_selectors = portal_config.get('content_selectors', ['.article-content', '.content'])
            
            content = None
            
            # Specjalna obsługa dla paragrafów w article (głównie dla Bankier)
            if portal_name == 'BANKIER':
                try:
                    article_elements = soup.select('article p')
                    if article_elements:
                        content = '\n\n'.join([p.get_text(strip=True) for p in article_elements if p.get_text(strip=True)])
                        if len(content) > 100:
                            return self._clean_content(content)
                except Exception:
                    pass  # Ignoruj błędy i przejdź do innych selektorów
            
            # Próbuj inne selektory
            for selector in content_selectors:
                elem = soup.select_one(selector)
                if elem:
                    # Usuń niepotrzebne elementy
                    for unwanted in elem.find_all(['script', 'style', 'nav', 'aside', 'footer']):
                        if hasattr(unwanted, 'decompose'):
                            unwanted.decompose()
                    
                    content = elem.get_text(strip=True)
                    if len(content) > 100:  # Sprawdź czy treść ma sens
                        break
            
            # Jeśli nie znaleziono konkretnego selektora, spróbuj ogólnie
            if not content or len(content) < 100:
                # Usuń niepotrzebne sekcje
                for unwanted in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    if hasattr(unwanted, 'decompose'):
                        unwanted.decompose()
                
                # Spróbuj głównych kontenerów treści
                main_selectors = ['main', 'article', '.main-content', '#main', '#content']
                for selector in main_selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        content = elem.get_text(strip=True)
                        if len(content) > 100:
                            break
            
            return self._clean_content(content) if content else None
            
        except Exception as e:
            logger.debug(f"⚠️ Błąd pobierania treści z {url}: {e}")
            return None
    
    def _clean_content(self, content: str) -> str:
        """Oczyszcza treść artykułu"""
        if not content:
            return ""
        
        # Usuń nadmiarowe whitespace
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'\n\s*\n', '\n\n', content)
        
        # Ogranicz długość
        if len(content) > 10000:
            content = content[:10000] + "..."
        
        return content.strip()
    
    def generate_article_id(self, title: str, url: str) -> str:
        """Generuje unikalny ID artykułu"""
        content_hash = hashlib.md5(f"{title}{url}".encode()).hexdigest()[:10]
        return f"NEWS_{content_hash}"
    
    def save_article(self, article: Dict) -> bool:
        """Zapisuje artykuł do bazy danych"""
        try:
            with self.engine.connect() as conn:
                # Generuj ID artykułu
                article_id = self.generate_article_id(article['title'], article['link'])
                
                # Sprawdź czy artykuł już istnieje (na podstawie URL)
                existing = conn.execute(text("""
                    SELECT id FROM news 
                    WHERE source = :source AND title = :title
                """), {
                    'source': article['link'],
                    'title': article['title']
                })
                
                if existing.fetchone():
                    logger.debug(f"📋 Artykuł już istnieje: {article['title'][:50]}...")
                    return False
                
                # Jeśli artykuł ma tickery, zapisz dla każdego
                if article['tickers']:
                    for ticker in article['tickers']:
                        # Pobierz company_id dla tickera
                        company_result = conn.execute(text("""
                            SELECT id FROM companies WHERE ticker = :ticker
                        """), {'ticker': ticker})
                        company_row = company_result.fetchone()
                        company_id = company_row[0] if company_row else None
                        
                        # Zapisz artykuł
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
                            'content': article['content']
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
                        'content': article['content']
                    })
                
                conn.commit()
                logger.info(f"✅ Zapisano artykuł: {article['title'][:50]}... (tickery: {', '.join(article['tickers']) if article['tickers'] else 'brak'})")
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd zapisu artykułu: {e}")
            return False
    
    def scrape_portal_articles(self, portal_name: str, days_back: int = 3) -> Dict[str, int]:
        """Scrapuje artykuły z konkretnego portalu"""
        portal_config = self.portals.get(portal_name)
        if not portal_config:
            logger.error(f"❌ Nieznany portal: {portal_name}")
            return {'total': 0, 'saved': 0}
        
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
        
        # Pobierz pełną treść i zapisz artykuły
        saved_count = 0
        
        for i, article in enumerate(recent_articles, 1):
            try:
                logger.info(f"📄 Przetwarzanie artykułu {i}/{len(recent_articles)}: {article['title'][:50]}...")
                
                # Pobierz pełną treść artykułu
                content = self.extract_article_content(article['link'], portal_name)
                if content:
                    article['content'] = content
                    
                    # Wyciągnij tickery z tytułu i treści
                    article['tickers'] = self.extract_tickers_from_content(article['title'], content)
                    
                    # Zapisz artykuł do bazy
                    if self.save_article(article):
                        saved_count += 1
                
                # Krótka przerwa między requestami
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Błąd przetwarzania artykułu: {e}")
                continue
        
        logger.info(f"🎉 Portal {portal_config['name']}: zapisano {saved_count}/{len(recent_articles)} artykułów")
        
        return {
            'total': len(recent_articles),
            'saved': saved_count
        }
    
    def scrape_all_portals(self, days_back: int = 3) -> Dict[str, Dict[str, int]]:
        """Scrapuje artykuły ze wszystkich skonfigurowanych portali"""
        logger.info(f"🌐 Rozpoczynam scrapowanie artykułów ze wszystkich portali (ostatnie {days_back} dni)")
        
        results = {}
        total_saved = 0
        
        for portal_name in self.portals.keys():
            try:
                portal_results = self.scrape_portal_articles(portal_name, days_back)
                results[portal_name] = portal_results
                total_saved += portal_results['saved']
                
                # Przerwa między portalami
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Błąd scrapowania portalu {portal_name}: {e}")
                results[portal_name] = {'total': 0, 'saved': 0}
        
        logger.info(f"🎉 Łącznie zapisano {total_saved} nowych artykułów ze wszystkich portali")
        
        # Dodaj podsumowanie
        results['SUMMARY'] = {
            'total_saved': total_saved,
            'portals_count': len([r for r in results.values() if isinstance(r, dict) and r.get('saved', 0) > 0])
        }
        
        return results

def main():
    """Funkcja główna - test scrapera artykułów"""
    print("🚀 News Scraper Portals - Test")
    print("=" * 50)
    
    try:
        scraper = NewsScraperPortals()
        
        # Test scrapowania artykułów
        print("\n📊 Rozpoczynam scrapowanie artykułów z portali finansowych...")
        results = scraper.scrape_all_portals(days_back=2)
        
        print(f"\n📈 Wyniki scrapowania portali:")
        for portal, stats in results.items():
            if portal != 'SUMMARY' and isinstance(stats, dict):
                print(f"   {portal}: {stats.get('saved', 0)}/{stats.get('total', 0)} artykułów")
        
        if 'SUMMARY' in results:
            summary = results['SUMMARY']
            print(f"\n🎯 Podsumowanie:")
            print(f"   Łącznie zapisanych artykułów: {summary.get('total_saved', 0)}")
            print(f"   Aktywnych portali: {summary.get('portals_count', 0)}")
        
        print("\n🎉 Test scrapera artykułów zakończony pomyślnie!")
        
    except Exception as e:
        print(f"❌ Błąd podczas testowania scrapera artykułów: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
