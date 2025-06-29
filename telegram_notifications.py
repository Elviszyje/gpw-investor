#!/usr/bin/env python3
"""
Telegram Notifications System - System powiadomień przez Telegram
Obsługuje wysyłanie powiadomień o alertach i zdarzeniach na rynku
Autor: GPW Investor System
Data: 2025-06-25
"""

import logging
import requests
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TelegramNotificationManager:
    """Manager powiadomień Telegram"""
    
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
        
        # Konfiguracja Telegram
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.default_chat_id = os.getenv('TELEGRAM_DEFAULT_CHAT_ID')
        
        if not self.bot_token:
            logger.warning("⚠️ Brak TELEGRAM_BOT_TOKEN w konfiguracji")
        
        # Połączenie PostgreSQL
        db_uri = f"postgresql://{self.pg_config['user']}:{self.pg_config['password']}@{self.pg_config['host']}:{self.pg_config['port']}/{self.pg_config['database']}"
        self.engine = create_engine(db_uri)
        
        # Utwórz tabele powiadomień
        self._create_notification_tables()
    
    def _create_notification_tables(self):
        """Tworzy tabele do zarządzania powiadomieniami"""
        try:
            with self.engine.connect() as conn:
                # Tabela subskrypcji
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS telegram_subscriptions (
                        id SERIAL PRIMARY KEY,
                        chat_id VARCHAR(50) NOT NULL UNIQUE,
                        username VARCHAR(100),
                        first_name VARCHAR(100),
                        last_name VARCHAR(100),
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Tabela typów powiadomień
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS notification_types (
                        id SERIAL PRIMARY KEY,
                        type_name VARCHAR(50) NOT NULL UNIQUE,
                        display_name VARCHAR(100) NOT NULL,
                        description TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Tabela preferencji powiadomień
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS notification_preferences (
                        id SERIAL PRIMARY KEY,
                        chat_id VARCHAR(50) NOT NULL,
                        notification_type_id INTEGER NOT NULL,
                        is_enabled BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (notification_type_id) REFERENCES notification_types(id),
                        UNIQUE(chat_id, notification_type_id)
                    )
                """))
                
                # Tabela historii powiadomień
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS notification_history (
                        id SERIAL PRIMARY KEY,
                        chat_id VARCHAR(50) NOT NULL,
                        notification_type VARCHAR(50) NOT NULL,
                        title VARCHAR(200),
                        message TEXT NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending',
                        error_message TEXT,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ticker VARCHAR(20),
                        metadata JSONB
                    )
                """))
                
                conn.commit()
                
                # Dodaj domyślne typy powiadomień
                self._insert_default_notification_types()
                
                logger.info("✅ Tabele powiadomień utworzone/sprawdzone")
                
        except Exception as e:
            logger.error(f"❌ Błąd tworzenia tabel powiadomień: {e}")
    
    def _insert_default_notification_types(self):
        """Dodaje domyślne typy powiadomień"""
        try:
            with self.engine.connect() as conn:
                notification_types = [
                    ('price_alert', 'Alerty cenowe', 'Powiadomienia o przekroczeniu progów cenowych'),
                    ('volume_alert', 'Alerty wolumenu', 'Powiadomienia o nietypowym wolumenie transakcji'),
                    ('technical_alert', 'Alerty techniczne', 'Powiadomienia o sygnałach analizy technicznej'),
                    ('news_alert', 'Alerty informacyjne', 'Powiadomienia o ważnych wydarzeniach'),
                    ('system_alert', 'Alerty systemowe', 'Powiadomienia o stanie systemu i błędach'),
                    ('daily_summary', 'Podsumowanie dzienne', 'Codzienny raport z rynku'),
                    ('weekly_summary', 'Podsumowanie tygodniowe', 'Tygodniowy raport z rynku'),
                    ('intraday_recommendation', 'Rekomendacje intraday', 'Powiadomienia o rekomendacjach trading intraday'),
                    ('intraday_scan_summary', 'Skanowanie intraday', 'Podsumowanie skanowania okazji intraday'),
                    ('weekly_summary', 'Podsumowanie tygodniowe', 'Tygodniowy raport z rynku')
                ]
                
                for type_name, display_name, description in notification_types:
                    conn.execute(text("""
                        INSERT INTO notification_types (type_name, display_name, description)
                        VALUES (:type_name, :display_name, :description)
                        ON CONFLICT (type_name) DO NOTHING
                    """), {
                        'type_name': type_name,
                        'display_name': display_name,
                        'description': description
                    })
                
                conn.commit()
                logger.info("✅ Domyślne typy powiadomień dodane")
                
        except Exception as e:
            logger.error(f"❌ Błąd dodawania typów powiadomień: {e}")
    
    def send_message(self, chat_id: str, message: str, title: str = None, 
                    notification_type: str = 'system_alert', ticker: str = None,
                    metadata: Dict = None) -> bool:
        """Wysyła wiadomość przez Telegram"""
        if not self.bot_token:
            logger.error("❌ Brak konfiguracji Telegram Bot Token")
            return False
        
        try:
            # Formatuj wiadomość
            formatted_message = self._format_message(message, title, ticker)
            
            # Wyślij przez Telegram API
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': formatted_message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                # Zapisz w historii
                self._save_notification_history(
                    chat_id=chat_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    status='sent',
                    ticker=ticker,
                    metadata=metadata
                )
                logger.info(f"✅ Wiadomość wysłana do {chat_id}")
                return True
            else:
                error_msg = f"Błąd API Telegram: {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                
                # Zapisz błąd w historii
                self._save_notification_history(
                    chat_id=chat_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    status='failed',
                    error_message=error_msg,
                    ticker=ticker,
                    metadata=metadata
                )
                return False
                
        except Exception as e:
            error_msg = f"Błąd wysyłania: {e}"
            logger.error(f"❌ {error_msg}")
            
            # Zapisz błąd w historii
            self._save_notification_history(
                chat_id=chat_id,
                notification_type=notification_type,
                title=title,
                message=message,
                status='failed',
                error_message=error_msg,
                ticker=ticker,
                metadata=metadata
            )
            return False
    
    def _format_message(self, message: str, title: str = None, ticker: str = None) -> str:
        """Formatuje wiadomość do wysłania"""
        formatted = ""
        
        # Dodaj tytuł
        if title:
            formatted += f"<b>📊 {title}</b>\n\n"
        
        # Dodaj ticker jeśli podany
        if ticker:
            formatted += f"<b>📈 Ticker:</b> {ticker}\n"
        
        # Dodaj wiadomość
        formatted += message
        
        # Dodaj timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted += f"\n\n<i>🕐 {timestamp}</i>"
        
        return formatted
    
    def _save_notification_history(self, chat_id: str, notification_type: str,
                                 title: str, message: str, status: str,
                                 error_message: str = None, ticker: str = None,
                                 metadata: Dict = None):
        """Zapisuje historię powiadomienia"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO notification_history 
                    (chat_id, notification_type, title, message, status, error_message, ticker, metadata)
                    VALUES (:chat_id, :notification_type, :title, :message, :status, :error_message, :ticker, :metadata)
                """), {
                    'chat_id': chat_id,
                    'notification_type': notification_type,
                    'title': title,
                    'message': message,
                    'status': status,
                    'error_message': error_message,
                    'ticker': ticker,
                    'metadata': json.dumps(metadata) if metadata else None
                })
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Błąd zapisywania historii: {e}")
    
    def broadcast_message(self, message: str, title: str = None, 
                         notification_type: str = 'system_alert',
                         ticker: str = None, metadata: Dict = None) -> Dict[str, int]:
        """Wysyła wiadomość do wszystkich aktywnych subskrybentów"""
        try:
            with self.engine.connect() as conn:
                # Pobierz aktywne subskrypcje z włączonym typem powiadomienia
                subscriptions = conn.execute(text("""
                    SELECT DISTINCT ts.chat_id
                    FROM telegram_subscriptions ts
                    LEFT JOIN notification_preferences np ON ts.chat_id = np.chat_id
                    LEFT JOIN notification_types nt ON np.notification_type_id = nt.id
                    WHERE ts.is_active = TRUE 
                    AND (np.is_enabled = TRUE OR np.is_enabled IS NULL)
                    AND (nt.type_name = :notification_type OR nt.type_name IS NULL)
                """), {'notification_type': notification_type}).fetchall()
                
                sent_count = 0
                failed_count = 0
                
                for sub in subscriptions:
                    chat_id = sub[0]
                    if self.send_message(
                        chat_id=chat_id,
                        message=message,
                        title=title,
                        notification_type=notification_type,
                        ticker=ticker,
                        metadata=metadata
                    ):
                        sent_count += 1
                    else:
                        failed_count += 1
                
                logger.info(f"✅ Broadcast: wysłano {sent_count}, błędów {failed_count}")
                return {'sent': sent_count, 'failed': failed_count}
                
        except Exception as e:
            logger.error(f"❌ Błąd broadcast: {e}")
            return {'sent': 0, 'failed': 0}
    
    def subscribe_chat(self, chat_id: str, username: str = None, 
                      first_name: str = None, last_name: str = None) -> bool:
        """Dodaje subskrypcję czatu"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO telegram_subscriptions (chat_id, username, first_name, last_name)
                    VALUES (:chat_id, :username, :first_name, :last_name)
                    ON CONFLICT (chat_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        is_active = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                """), {
                    'chat_id': chat_id,
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name
                })
                conn.commit()
                
                logger.info(f"✅ Subskrypcja dodana: {chat_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd dodawania subskrypcji: {e}")
            return False
    
    def unsubscribe_chat(self, chat_id: str) -> bool:
        """Usuwa subskrypcję czatu"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    UPDATE telegram_subscriptions 
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE chat_id = :chat_id
                """), {'chat_id': chat_id})
                conn.commit()
                
                logger.info(f"✅ Subskrypcja usunięta: {chat_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd usuwania subskrypcji: {e}")
            return False
    
    def get_subscriptions(self) -> List[Dict[str, Any]]:
        """Pobiera listę subskrypcji"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT chat_id, username, first_name, last_name, is_active, 
                           created_at, updated_at
                    FROM telegram_subscriptions
                    ORDER BY created_at DESC
                """))
                
                subscriptions = []
                for row in result:
                    subscriptions.append({
                        'chat_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'is_active': row[4],
                        'created_at': row[5],
                        'updated_at': row[6]
                    })
                
                return subscriptions
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania subskrypcji: {e}")
            return []
    
    def get_notification_types(self) -> List[Dict[str, Any]]:
        """Pobiera typy powiadomień"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT id, type_name, display_name, description, is_active
                    FROM notification_types
                    WHERE is_active = TRUE
                    ORDER BY display_name
                """))
                
                types = []
                for row in result:
                    types.append({
                        'id': row[0],
                        'type_name': row[1],
                        'display_name': row[2],
                        'description': row[3],
                        'is_active': row[4]
                    })
                
                return types
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania typów powiadomień: {e}")
            return []
    
    def get_notification_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Pobiera historię powiadomień"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT chat_id, notification_type, title, message, status, 
                           error_message, sent_at, ticker, metadata
                    FROM notification_history
                    ORDER BY sent_at DESC
                    LIMIT :limit
                """), {'limit': limit})
                
                history = []
                for row in result:
                    history.append({
                        'chat_id': row[0],
                        'notification_type': row[1],
                        'title': row[2],
                        'message': row[3],
                        'status': row[4],
                        'error_message': row[5],
                        'sent_at': row[6],
                        'ticker': row[7],
                        'metadata': json.loads(row[8]) if row[8] else None
                    })
                
                return history
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania historii: {e}")
            return []
    
    def test_connection(self) -> Dict[str, Any]:
        """Testuje połączenie z Telegram Bot API"""
        if not self.bot_token:
            return {'success': False, 'error': 'Brak Bot Token'}
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                bot_info = response.json()
                return {
                    'success': True,
                    'bot_info': bot_info.get('result', {}),
                    'message': 'Połączenie z Telegram Bot API działa'
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

def main():
    """Funkcja testowa"""
    print("🤖 TELEGRAM NOTIFICATIONS MANAGER")
    print("=" * 50)
    
    try:
        manager = TelegramNotificationManager()
        
        # Test połączenia
        print("\n🔄 Testowanie połączenia z Telegram...")
        test_result = manager.test_connection()
        if test_result['success']:
            print(f"✅ {test_result['message']}")
            bot_info = test_result.get('bot_info', {})
            print(f"   Bot: @{bot_info.get('username', 'N/A')} ({bot_info.get('first_name', 'N/A')})")
        else:
            print(f"❌ {test_result['error']}")
        
        # Wyświetl statystyki
        subscriptions = manager.get_subscriptions()
        notification_types = manager.get_notification_types()
        
        print(f"\n📊 Statystyki:")
        print(f"   Subskrypcje: {len(subscriptions)}")
        print(f"   Typy powiadomień: {len(notification_types)}")
        
        if subscriptions:
            active_subs = len([s for s in subscriptions if s['is_active']])
            print(f"   Aktywne subskrypcje: {active_subs}")
        
    except Exception as e:
        print(f"❌ Błąd: {e}")

if __name__ == "__main__":
    main()
