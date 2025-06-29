#!/usr/bin/env python3
"""
Uproszczony Feature Engineering dla ML (tylko dane intraday)
Dla testów systemu ML day tradingu
Autor: GPW Investor System
Data: 2025-06-25
"""

import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleMLFeatures:
    """Uproszczony feature engineering tylko z danych intraday"""
    
    def __init__(self):
        # Konfiguracja PostgreSQL
        load_dotenv('.env')
        
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_name = os.getenv('DB_NAME')
        
        db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        self.engine = create_engine(db_uri)
        
        logger.info("✓ Simple ML Features zainicjalizowany (PostgreSQL)")
    
    def create_simple_features(self, ticker: str, date: str) -> Optional[pd.DataFrame]:
        """
        Tworzy proste cechy z danych intraday
        
        Args:
            ticker: Symbol spółki
            date: Data
            
        Returns:
            DataFrame z cechami lub None
        """
        try:
            # Pobierz dane intraday z PostgreSQL
            query = text("""
                SELECT qi.datetime, qi.price, qi.volume, 
                       qi.open as open_price, qi.high as high_price, qi.low as low_price
                FROM quotes_intraday qi
                JOIN companies c ON qi.company_id = c.id
                WHERE c.ticker = :ticker AND DATE(qi.datetime) = :date
                ORDER BY qi.datetime ASC
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql_query(query, conn, params={"ticker": ticker, "date": date})
            
            if len(df) < 3:
                logger.warning(f"Za mało danych dla {ticker} na {date}: {len(df)} rekordów")
                return None
            
            # Podstawowe cechy
            df['price_change'] = df['price'].pct_change()
            df['price_change_abs'] = df['price'].diff()
            
            # Moving averages
            df['ma_3'] = df['price'].rolling(window=3).mean()
            df['ma_5'] = df['price'].rolling(window=min(5, len(df))).mean()
            
            # Volatility
            df['volatility'] = df['price'].rolling(window=3).std()
            
            # Volume features
            df['volume_change'] = df['volume'].pct_change() if 'volume' in df.columns else 0
            df['volume_ma'] = df['volume'].rolling(window=3).mean() if 'volume' in df.columns else 0
            
            # Price position
            if 'high_price' in df.columns and 'low_price' in df.columns:
                df['price_range'] = df['high_price'] - df['low_price']
                df['price_position'] = (df['price'] - df['low_price']) / (df['price_range'] + 0.001)
            else:
                df['price_range'] = 0
                df['price_position'] = 0.5
            
            # Trend indicators
            df['trend_3'] = (df['price'] > df['ma_3']).astype(int)
            df['trend_5'] = (df['price'] > df['ma_5']).astype(int)
            
            # Momentum
            df['momentum_3'] = df['price'] - df['price'].shift(3)
            df['momentum_5'] = df['price'] - df['price'].shift(min(5, len(df)-1))
            
            # Clean data
            df = df.fillna(0)
            df = df.replace([np.inf, -np.inf], 0)
            
            # Select features
            feature_cols = [
                'price_change', 'price_change_abs', 'ma_3', 'ma_5', 'volatility',
                'volume_change', 'volume_ma', 'price_range', 'price_position',
                'trend_3', 'trend_5', 'momentum_3', 'momentum_5'
            ]
            
            features = df[feature_cols].copy()
            features['ticker'] = ticker
            features['datetime'] = df['datetime']
            features['price'] = df['price']
            
            logger.info(f"✅ Utworzono {len(features)} cech dla {ticker} na {date}")
            return features
            
        except Exception as e:
            logger.error(f"Błąd tworzenia cech dla {ticker}: {e}")
            return None
    
    def create_labels(self, ticker: str, date: str, profit_threshold: float = 0.02) -> Optional[pd.Series]:
        """
        Tworzy etykiety dla danych (1 = BUY opportunity, 0 = no opportunity)
        
        Args:
            ticker: Symbol spółki
            date: Data
            profit_threshold: Próg zysku (domyślnie 2%)
            
        Returns:
            Series z etykietami lub None
        """
        try:
            query = text("""
                SELECT qi.datetime, qi.price
                FROM quotes_intraday qi
                JOIN companies c ON qi.company_id = c.id
                WHERE c.ticker = :ticker AND DATE(qi.datetime) = :date
                ORDER BY qi.datetime ASC
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql_query(query, conn, params={"ticker": ticker, "date": date})
            
            if len(df) < 3:
                return None
            
            labels = []
            
            for i in range(len(df)):
                current_price = df.iloc[i]['price']
                
                # Znajdź maksymalną cenę w następnych punktach
                future_prices = df.iloc[i+1:]['price'] if i+1 < len(df) else []
                
                if len(future_prices) > 0:
                    max_future_price = future_prices.max()
                    potential_profit = (max_future_price - current_price) / current_price
                    
                    # 1 jeśli można było zarobić >= profit_threshold
                    label = 1 if potential_profit >= profit_threshold else 0
                else:
                    label = 0
                
                labels.append(label)
            
            return pd.Series(labels)
            
        except Exception as e:
            logger.error(f"Błąd tworzenia etykiet dla {ticker}: {e}")
            return None
    
    def prepare_training_data(self, tickers: List[str], dates: List[str]) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Przygotowuje dane treningowe dla wielu tickerów i dat
        
        Args:
            tickers: Lista tickerów
            dates: Lista dat
            
        Returns:
            Tuple (X - cechy, y - etykiety)
        """
        all_features = []
        all_labels = []
        
        for ticker in tickers:
            for date in dates:
                try:
                    features = self.create_simple_features(ticker, date)
                    labels = self.create_labels(ticker, date)
                    
                    if features is not None and labels is not None and len(features) == len(labels):
                        all_features.append(features)
                        all_labels.append(labels)
                        logger.info(f"✅ Dodano dane {ticker} {date}: {len(features)} próbek")
                    else:
                        logger.warning(f"⚠️ Pominięto {ticker} {date}: niezgodność danych")
                        
                except Exception as e:
                    logger.error(f"Błąd przetwarzania {ticker} {date}: {e}")
                    continue
        
        if not all_features:
            logger.error("❌ Brak danych do treningu")
            return pd.DataFrame(), pd.Series()
        
        # Połącz wszystkie dane
        X = pd.concat(all_features, ignore_index=True)
        y = pd.concat(all_labels, ignore_index=True)
        
        # Usuń kolumny identyfikacyjne z cech
        feature_cols = [col for col in X.columns if col not in ['ticker', 'datetime', 'price']]
        X_clean = X[feature_cols]
        
        logger.info(f"🎯 Przygotowano dane treningowe: {X_clean.shape[0]} próbek, {X_clean.shape[1]} cech")
        logger.info(f"📊 Rozkład etykiet: {dict(y.value_counts())}")
        
        return X_clean, y
    
    def get_available_dates(self, tickers: Optional[List[str]] = None, days_back: int = 30) -> List[str]:
        """
        Pobiera dostępne daty z bazy danych
        
        Args:
            tickers: Lista tickerów (opcjonalne)
            days_back: Ile dni wstecz szukać
            
        Returns:
            Lista dostępnych dat
        """
        try:
            if tickers:
                # Przygotuj parametry dla wielu tickerów
                params_dict = {}
                ticker_placeholders = []
                for i, ticker in enumerate(tickers):
                    param_name = f'ticker_{i}'
                    params_dict[param_name] = ticker
                    ticker_placeholders.append(f':{param_name}')
                
                ticker_params = ','.join(ticker_placeholders)
                
                query = text(f"""
                    SELECT DISTINCT DATE(qi.datetime) as date
                    FROM quotes_intraday qi
                    JOIN companies c ON qi.company_id = c.id
                    WHERE c.ticker IN ({ticker_params})
                    AND qi.datetime IS NOT NULL
                    AND DATE(qi.datetime) >= CURRENT_DATE - INTERVAL '{days_back} days'
                    ORDER BY date DESC
                """)
                
                params = params_dict
            else:
                query = text(f"""
                    SELECT DISTINCT DATE(qi.datetime) as date
                    FROM quotes_intraday qi
                    WHERE qi.datetime IS NOT NULL
                    AND DATE(qi.datetime) >= CURRENT_DATE - INTERVAL '{days_back} days'
                    ORDER BY date DESC
                """)
                
                params = {}
            
            with self.engine.connect() as conn:
                result = conn.execute(query, params)
                dates = [str(row[0]) for row in result.fetchall() if row[0] is not None]
            
            logger.info(f"✓ Znaleziono {len(dates)} dostępnych dat: {dates}")
            return dates
            
        except Exception as e:
            logger.error(f"Błąd pobierania dostępnych dat: {e}")
            return []

def test_simple_features():
    """Test funkcji"""
    print("=== TEST SIMPLE FEATURES ===")
    
    features = SimpleMLFeatures()
    
    # Test dla CDR
    result = features.create_simple_features('CDR', '2025-06-24')
    if result is not None:
        print(f"✅ Cechy CDR: {len(result)} rekordów, {len(result.columns)} kolumn")
        print(f"📊 Kolumny: {list(result.columns)}")
    else:
        print("❌ Brak cech dla CDR")
    
    # Test etykiet
    labels = features.create_labels('CDR', '2025-06-24')
    if labels is not None:
        print(f"✅ Etykiety CDR: {len(labels)} etykiet")
        print(f"📊 Rozkład: {dict(labels.value_counts())}")
    else:
        print("❌ Brak etykiet dla CDR")
    
    # Test danych treningowych
    X, y = features.prepare_training_data(['CDR', 'PKN'], ['2025-06-24'])
    print(f"🎯 Dane treningowe: X={X.shape}, y={y.shape}")
    
    # Test dostępnych dat
    available_dates = features.get_available_dates(['CDR', 'PKN'], 7)
    print(f"📅 Dostępne daty: {available_dates}")


if __name__ == "__main__":
    test_simple_features()
