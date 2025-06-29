from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import re
import random
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv('.env')

class BankierScraper:
    """
    Scraper dla danych giełdowych z Bankier.pl
    Obsługuje wiele tickerów z mapowaniem na właściwe symbole Bankier.pl
    """
    
    def __init__(self, use_selenium: bool = True, headless: bool = True):
        self.use_selenium = use_selenium
        self.headless = headless
        self.driver = None
        self.session = None
        
        self._setup_database()
        
        # Ładuj mapowanie tickerów z bazy danych
        self.ticker_mapping = self._load_ticker_mappings()
        
        if self.use_selenium:
            self._setup_selenium()
    
    def _setup_database(self):
        """Konfiguracja połączenia z bazą danych"""
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT")
        db_name = os.getenv("DB_NAME")
        
        if not all([db_user, db_password, db_host, db_port, db_name]):
            print("⚠️ Brakuje zmiennych środowiskowych dla bazy danych")
            self.engine = None
            return
            
        db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        self.engine = create_engine(db_uri)
        print("✓ Połączenie z bazą danych skonfigurowane")
    
    def _load_ticker_mappings(self) -> Dict[str, str]:
        """Ładuje mapowanie tickerów z bazy danych"""
        if not self.engine:
            print("⚠️ Brak połączenia z bazą danych, używam domyślnego mapowania")
            return {
                'PKN': 'PKNORLEN',
                'PKNORLEN': 'PKNORLEN',
                'CDR': 'CDPROJEKT', 
                'CDPROJEKT': 'CDPROJEKT',
                'PKO': 'PKOBP',
                'PKOBP': 'PKOBP',
                'PZU': 'PZU',
                'LPP': 'LPP',
                'KGHM': 'KGHM',
                'PGE': 'PGE',
                'JSW': 'JSW',
                'CCC': 'CCC'
            }
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT ticker, bankier_symbol 
                    FROM ticker_mappings 
                    WHERE is_active = true
                    ORDER BY ticker
                """))
                
                mappings = {}
                for row in result:
                    ticker, bankier_symbol = row
                    mappings[ticker] = bankier_symbol
                
                print(f"✓ Załadowano {len(mappings)} mapowań tickerów z bazy danych")
                return mappings
                
        except Exception as e:
            print(f"❌ Błąd ładowania mapowań z bazy: {e}")
            print("⚠️ Używam domyślnego mapowania")
            return {
                'PKN': 'PKNORLEN',
                'PKNORLEN': 'PKNORLEN',
                'CDR': 'CDPROJEKT', 
                'CDPROJEKT': 'CDPROJEKT',
                'PKO': 'PKOBP',
                'PKOBP': 'PKOBP',
                'PZU': 'PZU',
                'LPP': 'LPP',
                'KGHM': 'KGHM',
                'PGE': 'PGE',
                'JSW': 'JSW',
                'CCC': 'CCC'
            }
    
    def _setup_selenium(self):
        """Konfiguracja WebDriver"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
        
        chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("✓ Selenium WebDriver skonfigurowany")
        except Exception as e:
            print(f"❌ Błąd konfiguracji Selenium: {e}")
            self.use_selenium = False
    
    def get_bankier_symbol(self, ticker: str) -> Optional[str]:
        """Konwertuje ticker na symbol Bankier.pl"""
        return self.ticker_mapping.get(ticker.upper())
    
    def scrape_single_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Scrapuje dane dla pojedynczego tickera z Bankier.pl
        """
        bankier_symbol = self.get_bankier_symbol(ticker)
        if not bankier_symbol:
            print(f"❌ Nieznany ticker: {ticker}")
            return None
        
        url = f"https://www.bankier.pl/inwestowanie/profile/quote.html?symbol={bankier_symbol}"
        print(f"📡 Scrapowanie {ticker} ({bankier_symbol}) z: {url}")
        
        try:
            if not self.driver:
                print("❌ WebDriver nie jest dostępny")
                return None
            
            self.driver.get(url)
            time.sleep(random.uniform(3, 6))  # Losowe opóźnienie
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Sprawdź czy strona się załadowała poprawnie
            if "404" in soup.title.text if soup.title else "":
                print(f"❌ Strona nie znaleziona dla {ticker}")
                return None
            
            # Metoda 1: Dane z atrybutów data-*
            last_trade_element = soup.find('div', id=f'last-trade-{bankier_symbol}')
            if last_trade_element and hasattr(last_trade_element, 'attrs'):
                try:
                    attrs = last_trade_element.attrs
                    
                    # Bezpieczne pobieranie atrybutów z konwersją typów
                    def safe_float(value, default=0.0):
                        try:
                            return float(str(value)) if value else default
                        except (ValueError, TypeError):
                            return default
                    
                    def safe_int(value, default=0):
                        try:
                            return int(str(value)) if value else default
                        except (ValueError, TypeError):
                            return default
                    
                    data = {
                        'ticker': ticker.upper(),
                        'bankier_symbol': bankier_symbol,
                        'price': safe_float(attrs.get('data-last', '0')),
                        'open': safe_float(attrs.get('data-open', '0')),
                        'high': safe_float(attrs.get('data-high', '0')),
                        'low': safe_float(attrs.get('data-low', '0')),
                        'volume': safe_int(attrs.get('data-volume', '0')),
                        'date': str(attrs.get('data-last-date', '')),
                        'epoch': safe_int(attrs.get('data-last-epoch', '0')),
                        'source': 'bankier_data_attrs'
                    }
                    
                    if data['price'] > 0:
                        print(f"✅ {ticker}: {data['price']} PLN (vol: {data['volume']:,})")
                        return data
                except (ValueError, TypeError) as e:
                    print(f"⚠️ Błąd parsowania atrybutów data-*: {e}")
            
            # Metoda 2: Fallback - szukanie w selektorach CSS
            price_selectors = [
                '.profilLast',
                '.price',
                '.quote-price', 
                '.current-price',
                '[data-field="c"]',
                '.value',
                '.quote-value'
            ]
            
            for selector in price_selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        text = element.get_text(strip=True)
                        price_match = re.search(r'(\d+[,.]?\d*)', text)
                        if price_match:
                            price_str = price_match.group(1).replace(',', '.')
                            try:
                                price = float(price_str)
                                if 1 <= price <= 10000:  # Rozsądny zakres cen
                                    print(f"✅ {ticker}: {price} PLN (selector: {selector})")
                                    return {
                                        'ticker': ticker.upper(),
                                        'bankier_symbol': bankier_symbol,
                                        'price': price,
                                        'source': f'selector_{selector}'
                                    }
                            except ValueError:
                                continue
                except Exception as e:
                    continue
            
            print(f"❌ Nie znaleziono ceny dla {ticker}")
            return None
            
        except Exception as e:
            print(f"❌ Błąd podczas scrapowania {ticker}: {e}")
            return None
    
    def scrape_multiple_tickers(self, tickers: List[str]) -> Dict[str, List[str]]:
        """
        Scrapuje dane dla wielu tickerów
        """
        print(f"🚀 Rozpoczęcie scrapowania {len(tickers)} tickerów z Bankier.pl")
        
        results = {
            'success': [],
            'failed': [],
            'data': []
        }
        
        for i, ticker in enumerate(tickers):
            print(f"\n[{i+1}/{len(tickers)}] Scrapowanie {ticker}...")
            
            data = self.scrape_single_ticker(ticker)
            if data:
                results['success'].append(ticker)
                results['data'].append(data)
                
                # Zapis do bazy danych
                if self.engine:
                    self._save_to_database(data)
            else:
                results['failed'].append(ticker)
            
            # Opóźnienie między tickerami
            if i < len(tickers) - 1:
                delay = random.uniform(2, 5)
                print(f"💤 Czekanie {delay:.1f}s przed następnym tickerem...")
                time.sleep(delay)
        
        print(f"\n📊 Podsumowanie scrapowania:")
        print(f"  ✅ Udane: {len(results['success'])} tickerów")
        print(f"  ❌ Nieudane: {len(results['failed'])} tickerów")
        
        if results['failed']:
            print(f"  🔴 Błędy: {', '.join(results['failed'])}")
        
        return results
    
    def ensure_company_exists(self, ticker: str) -> Optional[int]:
        """Zapewnia istnienie firmy w tabeli companies"""
        if not self.engine:
            return None
            
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("SELECT id FROM companies WHERE ticker = :ticker"), 
                    {"ticker": ticker.upper()}
                )
                row = result.fetchone()
                if row:
                    return row[0]
                
                # Dodaj nową firmę
                res = conn.execute(
                    text("INSERT INTO companies (ticker, name, sector) VALUES (:ticker, :name, :sector) RETURNING id"),
                    {"ticker": ticker.upper(), "name": ticker.upper(), "sector": ""}
                )
                row = res.fetchone()
                return row[0] if row else None
        except Exception as e:
            print(f"❌ Błąd zapewnienia istnienia firmy {ticker}: {e}")
            return None
    
    def _save_to_database(self, data: Dict[str, Any]) -> bool:
        """Zapisuje dane do bazy"""
        if not self.engine:
            print("⚠️ Brak połączenia z bazą - pomijanie zapisu")
            return False
        
        try:
            company_id = self.ensure_company_exists(data['ticker'])
            if not company_id:
                return False
            
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO quotes_intraday (datetime, price, volume, company_id)
                    VALUES (:dt, :price, :volume, :company_id)
                """), {
                    "dt": datetime.now(),
                    "price": data['price'],
                    "volume": data.get('volume', 0),
                    "company_id": company_id
                })
            
            print(f"💾 Zapisano {data['ticker']} do bazy")
            return True
            
        except Exception as e:
            print(f"❌ Błąd zapisu do bazy {data['ticker']}: {e}")
            return False
    
    def close(self):
        """Zamyka WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            print("🔒 WebDriver zamknięty")
    
    def reload_ticker_mappings(self):
        """Odświeża mapowanie tickerów z bazy danych"""
        self.ticker_mapping = self._load_ticker_mappings()
        return len(self.ticker_mapping)
    
    def get_active_tickers(self) -> List[str]:
        """Pobiera listę aktywnych tickerów z bazy danych"""
        if not self.engine:
            return list(self.ticker_mapping.keys())
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT DISTINCT ticker 
                    FROM ticker_mappings 
                    WHERE is_active = true
                    ORDER BY ticker
                """))
                
                tickers = [row[0] for row in result]
                return tickers
                
        except Exception as e:
            print(f"❌ Błąd pobierania listy tickerów: {e}")
            return list(self.ticker_mapping.keys())
        

def test_bankier_scraper():
    """Testuje scraper Bankier.pl"""
    print("=== Test Bankier Scraper ===")
    
    scraper = BankierScraper(use_selenium=True, headless=False)
    
    try:
        # Test pojedynczego tickera
        print("\n1. Test pojedynczego tickera (PKN):")
        result = scraper.scrape_single_ticker("PKN")
        print(f"Wynik: {result}")
        
        # Test wielu tickerów
        print("\n2. Test wielu tickerów:")
        test_tickers = ["PKN", "CDR", "PKO", "PZU"]
        results = scraper.scrape_multiple_tickers(test_tickers)
        print(f"Wyniki: {results}")
        
    finally:
        scraper.close()


if __name__ == "__main__":
    test_bankier_scraper()
