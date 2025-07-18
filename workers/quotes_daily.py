import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from dotenv import load_dotenv
import os

load_dotenv('.env')

# Poprawne nazwy zmiennych środowiskowych (duże litery, bez spacji i cudzysłowów w .env)
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

# Walidacja obecności zmiennych środowiskowych
assert db_user is not None, "DB_USER nie jest ustawiony!"
assert db_password is not None, "DB_PASSWORD nie jest ustawiony!"
assert db_host is not None, "DB_HOST nie jest ustawiony!"
assert db_port is not None, "DB_PORT nie jest ustawiony!"
assert db_name is not None, "DB_NAME nie jest ustawiony!"

db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
engine = create_engine(db_uri)

def fetch_stooq_data(ticker: str, interval: str = "d"):
    url = f"https://stooq.pl/q/d/l/?s={ticker}.pl&i={interval}"
    try:
        df = pd.read_csv(url)
        if df.empty:
            print(f"❌ Brak danych z Stooq dla: {ticker} ({interval})")
            return None
        df.columns = [col.strip().lower() for col in df.columns]
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
        return

    company_id = ensure_company_exists(ticker.upper(), "CD Projekt", "Gry komputerowe")

    required = {'date', 'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(set(df.columns)):
        print("❌ Brak wymaganych kolumn w danych.")
        print(df.columns)
        return

    df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
    df['company_id'] = company_id

    try:
        df.to_sql("quotes_daily", engine, if_exists="append", index=False, method="multi")
        print(f"✅ Dodano {len(df)} rekordów do quotes_daily.")
    except IntegrityError:
        print("⚠️ Część danych już istnieje – pomijam.")
    except Exception as e:
        print(f"Błąd zapisu do bazy: {e}")