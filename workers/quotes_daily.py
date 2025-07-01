import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from database_config import get_database_engine, get_database_connection
import logging

logger = logging.getLogger(__name__)

# Use centralized database configuration
engine = get_database_engine()

def fetch_stooq_data(ticker: str, interval: str = "d"):
    url = f"https://stooq.pl/q/d/l/?s={ticker}&i={interval}"
    print(f"Pobieram dane z: {url}")
    try:
        df = pd.read_csv(url)
        if df.empty:
            print(f"❌ Brak danych z Stooq dla: {ticker} ({interval})")
            return None
        df.columns = [col.strip().lower() for col in df.columns]
        # Mapowanie polskich nagłówków na angielskie
        col_map = {
            'data': 'date',
            'otwarcie': 'open',
            'najwyzszy': 'high',
            'najnizszy': 'low',
            'zamkniecie': 'close',
            'wolumen': 'volume'
        }
        df = df.rename(columns=col_map)
        print(f"Kolumny po mapowaniu: {df.columns}")
        return df
    except Exception as e:
        print(f"Błąd przy pobieraniu danych: {e}")
        return None

def ensure_company_exists(ticker: str, name: str = "", sector: str = ""):
    with engine.begin() as conn:
        result = conn.execute(text("SELECT id FROM companies WHERE ticker = :ticker"), {"ticker": ticker})
        row = result.fetchone()
        if row:
            return row[0]
        res = conn.execute(
            text("INSERT INTO companies (ticker, name, sector) VALUES (:ticker, :name, :sector) RETURNING id"),
            {"ticker": ticker, "name": name, "sector": sector}
        )
        return res.fetchone()[0]

def save_daily_quotes(ticker: str):
    df = fetch_stooq_data(ticker, "d")
    if df is None:
        return 0

    company_id = ensure_company_exists(ticker.upper(), "CD Projekt", "Gry komputerowe")

    required = {'date', 'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(set(df.columns)):
        print("❌ Brak wymaganych kolumn w danych.")
        print(df.columns)
        return 0

    df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
    df['company_id'] = company_id

    # Liczba rekordów przed zapisem
    from sqlalchemy import text
    with engine.begin() as conn:
        before = conn.execute(text("SELECT COUNT(*) FROM quotes_daily WHERE company_id = :cid"), {"cid": company_id}).scalar()

    try:
        df.to_sql("quotes_daily", engine, if_exists="append", index=False, method="multi")
    except IntegrityError:
        print("⚠️ Część danych już istnieje – pomijam.")
    except Exception as e:
        print(f"Błąd zapisu do bazy: {e}")
        return 0

    # Liczba rekordów po zapisie
    with engine.begin() as conn:
        after = conn.execute(text("SELECT COUNT(*) FROM quotes_daily WHERE company_id = :cid"), {"cid": company_id}).scalar()

    # Obsługa None (gdy tabela pusta)
    before = before or 0
    after = after or 0
    added = after - before
    print(f"✅ Dodano {added} nowych rekordów do quotes_daily.")
    return added

def get_companies():
    from sqlalchemy import text
    with engine.begin() as conn:
        result = conn.execute(text("SELECT ticker, name FROM companies ORDER BY ticker"))
        return [dict(ticker=row[0], name=row[1]) for row in result]

def get_daily_quotes(ticker):
    if not ticker:
        return None
    from sqlalchemy import text
    with engine.begin() as conn:
        result = conn.execute(text("SELECT date, open, high, low, close, volume FROM quotes_daily q JOIN companies c ON q.company_id = c.id WHERE c.ticker = :ticker ORDER BY date DESC LIMIT 30"), {"ticker": ticker})
        return [dict(date=row[0], open=row[1], high=row[2], low=row[3], close=row[4], volume=row[5]) for row in result]
    
def get_daily_quotes_range(ticker: str, start_date: str, end_date: str):
    """
    Pobiera dane dzienne dla tickera w określonym zakresie dat
    
    Args:
        ticker: Symbol spółki
        start_date: Data początkowa (YYYY-MM-DD)
        end_date: Data końcowa (YYYY-MM-DD)
        
    Returns:
        Lista słowników z danymi
    """
    try:
        with engine.begin() as conn:
            query = text("""
                SELECT c.ticker, q.date, q.open, q.high, q.low, q.close, q.volume
                FROM quotes_daily q
                JOIN companies c ON q.company_id = c.id
                WHERE c.ticker = :ticker AND q.date BETWEEN :start_date AND :end_date
                ORDER BY q.date ASC
            """)
            
            result = conn.execute(query, {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date
            })
            
            rows = result.fetchall()
            
            result_list = []
            for row in rows:
                result_list.append({
                    'ticker': row[0],
                    'date': row[1],
                    'open': row[2],
                    'high': row[3],
                    'low': row[4],
                    'close': row[5],
                    'volume': row[6]
                })
            
            return result_list
        
    except Exception as e:
        print(f"❌ Błąd pobierania danych dziennych {ticker}: {e}")
        return []

def get_intraday_quotes_range(ticker: str, start_date: str, end_date: str):
    """
    Pobiera dane intraday dla tickera w określonym zakresie dat
    
    Args:
        ticker: Symbol spółki  
        start_date: Data początkowa (YYYY-MM-DD)
        end_date: Data końcowa (YYYY-MM-DD)
        
    Returns:
        Lista słowników z danymi
    """
    try:
        with engine.begin() as conn:
            query = text("""
                SELECT c.ticker, qi.datetime, qi.price, qi.volume
                FROM quotes_intraday qi
                JOIN companies c ON qi.company_id = c.id
                WHERE c.ticker = :ticker AND DATE(qi.datetime) BETWEEN :start_date AND :end_date
                ORDER BY qi.datetime ASC
            """)
            
            result = conn.execute(query, {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date
            })
            
            rows = result.fetchall()
            
            result_list = []
            for row in rows:
                result_list.append({
                    'ticker': row[0],
                    'datetime': row[1],
                    'price': row[2],
                    'volume': row[3]
                })
            
            return result_list
        
    except Exception as e:
        print(f"❌ Błąd pobierania danych intraday {ticker}: {e}")
        return []