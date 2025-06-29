import psycopg2
from datetime import datetime, timedelta
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

def detect_price_drop_alert(ticker="CDR", threshold=-0.04):
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    cur = conn.cursor()

    cur.execute("SELECT id FROM companies WHERE ticker = %s", (ticker,))
    company = cur.fetchone()
    if not company:
        print(f"Spółka {ticker} nie znaleziona.")
        return
    company_id = company[0]

    cur.execute(
        "SELECT date, close, open FROM quotes_daily WHERE company_id = %s AND date IN (%s, %s)",
        (company_id, yesterday, today)
    )
    rows = cur.fetchall()
    if len(rows) < 2:
        print("Brakuje danych dziennych dla wczoraj i dziś.")
        return

    data_dict = {r[0]: {'close': r[1], 'open': r[2]} for r in rows}
    close_yesterday = data_dict[yesterday]['close']
    open_today = data_dict[today]['open']

    if open_today < close_yesterday:
        print("Dzisiejsze otwarcie niższe niż wczorajsze zamknięcie – brak alertu.")
        return

    cur.execute(
        "SELECT datetime, price FROM quotes_intraday WHERE company_id = %s AND datetime::date = %s ORDER BY price ASC LIMIT 1",
        (company_id, today)
    )
    intraday_min = cur.fetchone()
    if not intraday_min:
        print("Brak danych intraday.")
        return

    min_time, min_price = intraday_min
    drop_pct = (min_price - close_yesterday) / close_yesterday

    print(f"Spadek względem wczoraj: {drop_pct*100:.2f}% (minimum o {min_time.time()})")

    if drop_pct <= threshold:
        cur.execute(
            "INSERT INTO alerts (company_id, source, type, timestamp, price, confidence, comment) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                company_id,
                'rule',
                'buy',
                min_time,
                min_price,
                abs(drop_pct) * 100,
                f"Spadek >= {abs(threshold*100):.1f}% względem wczorajszego zamknięcia"
            )
        )
        conn.commit()
        print("Alert kupna zapisany.")
    else:
        print("Brak alertu – spadek zbyt mały.")

    cur.close()
    conn.close()