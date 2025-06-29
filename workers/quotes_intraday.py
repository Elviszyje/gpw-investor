"""
Moduł do obsługi danych intraday
Funkcje do zapisu i odczytu danych śróddziennych z tabeli quotes_intraday
"""

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

# Dodaj ścieżkę do postgresql_ticker_manager
sys.path.append(str(Path(__file__).parent.parent))

try:
    from postgresql_ticker_manager import PostgreSQLTickerManager
    TICKER_MANAGER_AVAILABLE = True
except ImportError:
    TICKER_MANAGER_AVAILABLE = False
    print("⚠️ PostgreSQL Ticker Manager niedostępny - rejestracja tickerów wyłączona")

load_dotenv('.env')

# Konfiguracja bazy danych
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

# Walidacja zmiennych środowiskowych
assert db_user is not None, "DB_USER nie jest ustawiony!"
assert db_password is not None, "DB_PASSWORD nie jest ustawiony!"
assert db_host is not None, "DB_HOST nie jest ustawiony!"
assert db_port is not None, "DB_PORT nie jest ustawiony!"
assert db_name is not None, "DB_NAME nie jest ustawiony!"

db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
engine = create_engine(db_uri)

def ensure_company_exists(ticker: str) -> Optional[int]:
    """Sprawdza czy firma istnieje w tabeli companies, jeśli nie - dodaje ją"""
    try:
        with engine.begin() as conn:
            # Sprawdź czy firma już istnieje
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

def save_intraday_quotes(ticker: str, price: Optional[float] = None, volume: Optional[int] = None) -> bool:
    """
    Zapisuje dane intraday do bazy danych
    """
    try:
        # Auto-rejestracja tickera z PostgreSQL Ticker Manager
        if TICKER_MANAGER_AVAILABLE:
            try:
                from postgresql_ticker_manager import auto_register_ticker_from_scraping
                auto_register_ticker_from_scraping(
                    ticker=ticker,
                    source_name="quotes_intraday"
                )
            except Exception as e:
                print(f"⚠️ Błąd auto-rejestracji tickera {ticker}: {e}")
        
        company_id = ensure_company_exists(ticker)
        if not company_id:
            print(f"❌ Nie można znaleźć/utworzyć firmy dla tickera: {ticker}")
            return False
        
        # Jeśli nie podano danych, użyj wartości domyślnych
        if price is None:
            print(f"⚠️ Brak ceny dla {ticker}, pomijam zapis")
            return False
        
        if volume is None:
            volume = 0
        
        # Zapisz do bazy
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO quotes_intraday (datetime, price, volume, company_id)
                VALUES (:dt, :price, :volume, :company_id)
            """), {
                "dt": datetime.now(),
                "price": price,
                "volume": volume,
                "company_id": company_id
            })
        
        print(f"✅ Zapisano dane intraday dla {ticker}: {price} PLN (volume: {volume:,})")
        return True
        
    except Exception as e:
        print(f"❌ Błąd zapisu danych intraday dla {ticker}: {e}")
        return False

def get_intraday_quotes(ticker: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Pobiera dane intraday dla podanego tickera
    
    Args:
        ticker: Symbol tickera (np. 'PKN')
        limit: Maksymalna liczba rekordów do pobrania
    
    Returns:
        Lista słowników z danymi intraday
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT qi.datetime, qi.price, qi.volume, c.ticker, c.name
                FROM quotes_intraday qi
                JOIN companies c ON qi.company_id = c.id
                WHERE c.ticker = :ticker
                ORDER BY qi.datetime DESC
                LIMIT :limit
            """)
            
            result = conn.execute(query, {"ticker": ticker.upper(), "limit": limit})
            
            quotes = []
            for row in result:
                quotes.append({
                    'datetime': row[0],
                    'price': float(row[1]) if row[1] else 0.0,
                    'volume': int(row[2]) if row[2] else 0,
                    'ticker': row[3],
                    'company_name': row[4] or row[3]
                })
            
            return quotes
            
    except Exception as e:
        print(f"❌ Błąd pobierania danych intraday dla {ticker}: {e}")
        return []

def get_all_intraday_companies() -> List[Dict[str, Any]]:
    """
    Pobiera listę wszystkich firm, które mają dane intraday
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT DISTINCT c.ticker, c.name, 
                       COUNT(qi.id) as records_count,
                       MAX(qi.datetime) as last_update
                FROM companies c
                JOIN quotes_intraday qi ON c.id = qi.company_id
                GROUP BY c.ticker, c.name
                ORDER BY c.ticker
            """)
            
            result = conn.execute(query)
            
            companies = []
            for row in result:
                companies.append({
                    'ticker': row[0],
                    'name': row[1] or row[0],
                    'records_count': row[2],
                    'last_update': row[3]
                })
            
            return companies
            
    except Exception as e:
        print(f"❌ Błąd pobierania listy firm intraday: {e}")
        return []

def get_latest_intraday_quotes(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Pobiera najnowsze dane intraday ze wszystkich firm
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT qi.datetime, qi.price, qi.volume, c.ticker, c.name
                FROM quotes_intraday qi
                JOIN companies c ON qi.company_id = c.id
                ORDER BY qi.datetime DESC
                LIMIT :limit
            """)
            
            result = conn.execute(query, {"limit": limit})
            
            quotes = []
            for row in result:
                quotes.append({
                    'datetime': row[0],
                    'price': float(row[1]) if row[1] else 0.0,
                    'volume': int(row[2]) if row[2] else 0,
                    'ticker': row[3],
                    'company_name': row[4] or row[3]
                })
            
            return quotes
            
    except Exception as e:
        print(f"❌ Błąd pobierania najnowszych danych intraday: {e}")
        return []

# Testowanie modułu
if __name__ == "__main__":
    print("=== Test modułu quotes_intraday ===")
    
    # Test zapisu danych
    print("\n1. Test zapisu danych:")
    success = save_intraday_quotes("PKN", 45.50, 1000000)
    print(f"Zapis PKN: {'✅ OK' if success else '❌ BŁĄD'}")
    
    # Test odczytu danych
    print("\n2. Test odczytu danych:")
    quotes = get_intraday_quotes("PKN", limit=5)
    print(f"Pobrane dane PKN: {len(quotes)} rekordów")
    for quote in quotes[:3]:  # Pokaż pierwsze 3
        print(f"  {quote['datetime']}: {quote['price']} PLN (vol: {quote['volume']:,})")
    
    # Test listy firm
    print("\n3. Test listy firm:")
    companies = get_all_intraday_companies()
    print(f"Firmy z danymi intraday: {len(companies)}")
    for company in companies[:5]:  # Pokaż pierwsze 5
        print(f"  {company['ticker']}: {company['records_count']} rekordów")