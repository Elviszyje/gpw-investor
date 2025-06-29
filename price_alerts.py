#!/usr/bin/env python3
"""
Price Alert System - System alertów cenowych z powiadomieniami Telegram
Monitoruje ceny tickerów i wysyła powiadomienia o przekroczeniach progów
Autor: GPW Investor System
Data: 2025-06-25
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from telegram_notifications import TelegramNotificationManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PriceAlertSystem:
    """System alertów cenowych"""
    
    def __init__(self):
        load_dotenv('.env')
        
        # Konfiguracja PostgreSQL
        self.pg_config = {
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'host': os.getenv('DB_HOST'),
            'port': os.getenv('DB_PORT'),
            'database': os.getenv('DB_NAME')
        }
        
        # Połączenie PostgreSQL
        db_uri = f"postgresql://{self.pg_config['user']}:{self.pg_config['password']}@{self.pg_config['host']}:{self.pg_config['port']}/{self.pg_config['database']}"
        self.engine = create_engine(db_uri)
        
        # Manager powiadomień Telegram
        self.telegram_manager = TelegramNotificationManager()
        
        # Utwórz tabele alertów
        self._create_alert_tables()
    
    def _create_alert_tables(self):
        """Tworzy tabele alertów cenowych"""
        try:
            with self.engine.connect() as conn:
                # Tabela alertów cenowych
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS price_alerts (
                        id SERIAL PRIMARY KEY,
                        ticker VARCHAR(20) NOT NULL,
                        alert_type VARCHAR(20) NOT NULL, -- 'above', 'below', 'change_percent'
                        threshold_value DECIMAL(10,2) NOT NULL,
                        current_price DECIMAL(10,2),
                        is_active BOOLEAN DEFAULT TRUE,
                        is_triggered BOOLEAN DEFAULT FALSE,
                        triggered_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        description TEXT,
                        metadata JSONB
                    )
                """))
                
                # Tabela historii triggerów
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS alert_triggers (
                        id SERIAL PRIMARY KEY,
                        alert_id INTEGER NOT NULL,
                        ticker VARCHAR(20) NOT NULL,
                        trigger_price DECIMAL(10,2) NOT NULL,
                        threshold_value DECIMAL(10,2) NOT NULL,
                        alert_type VARCHAR(20) NOT NULL,
                        triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notification_sent BOOLEAN DEFAULT FALSE,
                        metadata JSONB,
                        FOREIGN KEY (alert_id) REFERENCES price_alerts(id)
                    )
                """))
                
                conn.commit()
                logger.info("✅ Tabele alertów cenowych utworzone/sprawdzone")
                
        except Exception as e:
            logger.error(f"❌ Błąd tworzenia tabel alertów: {e}")
    
    def create_price_alert(self, ticker: str, alert_type: str, threshold_value: float,
                          description: str = None) -> int:
        """Tworzy nowy alert cenowy"""
        try:
            with self.engine.connect() as conn:
                # Sprawdź czy ticker istnieje
                ticker_exists = conn.execute(text("""
                    SELECT COUNT(*) FROM companies WHERE ticker = :ticker
                """), {"ticker": ticker.upper()}).scalar()
                
                if not ticker_exists:
                    raise ValueError(f"Ticker {ticker} nie istnieje w bazie")
                
                # Pobierz aktualną cenę
                current_price = self._get_current_price(ticker)
                
                # Utwórz alert
                result = conn.execute(text("""
                    INSERT INTO price_alerts (ticker, alert_type, threshold_value, current_price, description)
                    VALUES (:ticker, :alert_type, :threshold_value, :current_price, :description)
                    RETURNING id
                """), {
                    "ticker": ticker.upper(),
                    "alert_type": alert_type,
                    "threshold_value": threshold_value,
                    "current_price": current_price,
                    "description": description
                })
                
                alert_id = result.scalar()
                conn.commit()
                
                logger.info(f"✅ Alert cenowy utworzony: ID {alert_id} dla {ticker}")
                return alert_id
                
        except Exception as e:
            logger.error(f"❌ Błąd tworzenia alertu: {e}")
            return 0
    
    def _get_current_price(self, ticker: str) -> Optional[float]:
        """Pobiera aktualną cenę tickera"""
        try:
            with self.engine.connect() as conn:
                # Najpierw spróbuj intraday
                price = conn.execute(text("""
                    SELECT qi.price
                    FROM quotes_intraday qi
                    JOIN companies c ON qi.company_id = c.id
                    WHERE c.ticker = :ticker
                    ORDER BY qi.datetime DESC
                    LIMIT 1
                """), {"ticker": ticker.upper()}).scalar()
                
                if price:
                    return float(price)
                
                # Jeśli nie ma intraday, spróbuj daily
                price = conn.execute(text("""
                    SELECT qd.close
                    FROM quotes_daily qd
                    JOIN companies c ON qd.company_id = c.id
                    WHERE c.ticker = :ticker
                    ORDER BY qd.date DESC
                    LIMIT 1
                """), {"ticker": ticker.upper()}).scalar()
                
                if price:
                    return float(price)
                
                return None
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania ceny dla {ticker}: {e}")
            return None
    
    def check_alerts(self) -> Dict[str, Any]:
        """Sprawdza wszystkie aktywne alerty"""
        try:
            with self.engine.connect() as conn:
                # Pobierz aktywne alerty
                alerts = conn.execute(text("""
                    SELECT id, ticker, alert_type, threshold_value, current_price, description
                    FROM price_alerts
                    WHERE is_active = TRUE AND is_triggered = FALSE
                """)).fetchall()
                
                triggered_count = 0
                checked_count = 0
                
                for alert in alerts:
                    alert_id, ticker, alert_type, threshold_value, old_price, description = alert
                    
                    # Pobierz aktualną cenę
                    current_price = self._get_current_price(ticker)
                    if current_price is None:
                        continue
                    
                    checked_count += 1
                    
                    # Sprawdź czy alert został triggered
                    triggered = False
                    
                    if alert_type == 'above' and current_price > threshold_value:
                        triggered = True
                    elif alert_type == 'below' and current_price < threshold_value:
                        triggered = True
                    elif alert_type == 'change_percent' and old_price:
                        change_percent = ((current_price - old_price) / old_price) * 100
                        if abs(change_percent) >= threshold_value:
                            triggered = True
                    
                    if triggered:
                        self._trigger_alert(alert_id, ticker, current_price, threshold_value, alert_type, description)
                        triggered_count += 1
                    else:
                        # Aktualizuj aktualną cenę
                        conn.execute(text("""
                            UPDATE price_alerts 
                            SET current_price = :current_price, updated_at = CURRENT_TIMESTAMP
                            WHERE id = :alert_id
                        """), {"current_price": current_price, "alert_id": alert_id})
                
                conn.commit()
                
                result = {
                    'checked': checked_count,
                    'triggered': triggered_count,
                    'timestamp': datetime.now().isoformat()
                }
                
                logger.info(f"✅ Sprawdzono {checked_count} alertów, triggered: {triggered_count}")
                return result
                
        except Exception as e:
            logger.error(f"❌ Błąd sprawdzania alertów: {e}")
            return {'checked': 0, 'triggered': 0, 'error': str(e)}
    
    def _trigger_alert(self, alert_id: int, ticker: str, trigger_price: float,
                      threshold_value: float, alert_type: str, description: str = None):
        """Aktywuje alert i wysyła powiadomienie"""
        try:
            with self.engine.connect() as conn:
                # Oznacz alert jako triggered
                conn.execute(text("""
                    UPDATE price_alerts 
                    SET is_triggered = TRUE, triggered_at = CURRENT_TIMESTAMP, current_price = :price
                    WHERE id = :alert_id
                """), {"alert_id": alert_id, "price": trigger_price})
                
                # Zapisz trigger w historii
                conn.execute(text("""
                    INSERT INTO alert_triggers 
                    (alert_id, ticker, trigger_price, threshold_value, alert_type)
                    VALUES (:alert_id, :ticker, :trigger_price, :threshold_value, :alert_type)
                """), {
                    "alert_id": alert_id,
                    "ticker": ticker,
                    "trigger_price": trigger_price,
                    "threshold_value": threshold_value,
                    "alert_type": alert_type
                })
                
                conn.commit()
                
                # Wyślij powiadomienie Telegram
                self._send_alert_notification(ticker, trigger_price, threshold_value, alert_type, description)
                
                logger.info(f"✅ Alert triggered: {ticker} @ {trigger_price}")
                
        except Exception as e:
            logger.error(f"❌ Błąd triggeru alertu: {e}")
    
    def _send_alert_notification(self, ticker: str, trigger_price: float,
                               threshold_value: float, alert_type: str, description: str = None):
        """Wysyła powiadomienie o alertcie"""
        try:
            # Formatuj wiadomość
            if alert_type == 'above':
                message = f"Cena przekroczyła próg!\n\n"
                message += f"Aktualna cena: {trigger_price:.2f} PLN\n"
                message += f"Próg górny: {threshold_value:.2f} PLN"
            elif alert_type == 'below':
                message = f"Cena spadła poniżej progu!\n\n"
                message += f"Aktualna cena: {trigger_price:.2f} PLN\n"
                message += f"Próg dolny: {threshold_value:.2f} PLN"
            elif alert_type == 'change_percent':
                message = f"Znacząca zmiana ceny!\n\n"
                message += f"Aktualna cena: {trigger_price:.2f} PLN\n"
                message += f"Próg zmiany: ±{threshold_value:.1f}%"
            else:
                message = f"Alert cenowy triggered!\n\nCena: {trigger_price:.2f} PLN"
            
            if description:
                message += f"\n\nOpis: {description}"
            
            # Wyślij broadcast
            self.telegram_manager.broadcast_message(
                message=message,
                title=f"🚨 Alert Cenowy - {ticker}",
                notification_type='price_alert',
                ticker=ticker,
                metadata={
                    'alert_type': alert_type,
                    'trigger_price': trigger_price,
                    'threshold_value': threshold_value
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Błąd wysyłania powiadomienia: {e}")
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Pobiera aktywne alerty"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT id, ticker, alert_type, threshold_value, current_price,
                           is_triggered, created_at, description
                    FROM price_alerts
                    WHERE is_active = TRUE
                    ORDER BY created_at DESC
                """))
                
                alerts = []
                for row in result:
                    alerts.append({
                        'id': row[0],
                        'ticker': row[1],
                        'alert_type': row[2],
                        'threshold_value': float(row[3]) if row[3] else 0,
                        'current_price': float(row[4]) if row[4] else 0,
                        'is_triggered': row[5],
                        'created_at': row[6],
                        'description': row[7]
                    })
                
                return alerts
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania alertów: {e}")
            return []
    
    def get_alert_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Pobiera historię triggerów"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT ticker, trigger_price, threshold_value, alert_type, 
                           triggered_at, notification_sent
                    FROM alert_triggers
                    ORDER BY triggered_at DESC
                    LIMIT :limit
                """), {"limit": limit})
                
                history = []
                for row in result:
                    history.append({
                        'ticker': row[0],
                        'trigger_price': float(row[1]) if row[1] else 0,
                        'threshold_value': float(row[2]) if row[2] else 0,
                        'alert_type': row[3],
                        'triggered_at': row[4],
                        'notification_sent': row[5]
                    })
                
                return history
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania historii alertów: {e}")
            return []
    
    def delete_alert(self, alert_id: int) -> bool:
        """Usuwa alert"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    UPDATE price_alerts 
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :alert_id
                """), {"alert_id": alert_id})
                conn.commit()
                
                logger.info(f"✅ Alert {alert_id} usunięty")
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd usuwania alertu: {e}")
            return False

def main():
    """Funkcja testowa"""
    print("🚨 PRICE ALERT SYSTEM")
    print("=" * 50)
    
    try:
        alert_system = PriceAlertSystem()
        
        # Sprawdź alerty
        print("\n🔄 Sprawdzanie alertów...")
        result = alert_system.check_alerts()
        print(f"Sprawdzono: {result['checked']}, Triggered: {result['triggered']}")
        
        # Wyświetl aktywne alerty
        alerts = alert_system.get_active_alerts()
        print(f"\n📊 Aktywne alerty: {len(alerts)}")
        
        for alert in alerts[:5]:  # Pokaż pierwsze 5
            status = "🔴 TRIGGERED" if alert['is_triggered'] else "🟢 AKTYWNY"
            print(f"   {alert['ticker']}: {alert['alert_type']} {alert['threshold_value']:.2f} - {status}")
        
        # Wyświetl historię
        history = alert_system.get_alert_history(5)
        print(f"\n📈 Historia triggerów ({len(history)}):")
        for h in history:
            print(f"   {h['ticker']}: {h['trigger_price']:.2f} ({h['alert_type']}) - {h['triggered_at']}")
        
    except Exception as e:
        print(f"❌ Błąd: {e}")

if __name__ == "__main__":
    main()
