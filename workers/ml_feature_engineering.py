#!/usr/bin/env python3
"""
Feature Engineering dla modelu ML intraday
Przygotowuje cechy na podstawie danych cenowych i wskaźników technicznych
Autor: GPW Investor System
Data: 2025-06-25
"""

import numpy as np
import pandas as pd
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import ta  # Technical Analysis library
from scipy import stats
from sklearn.preprocessing import StandardScaler, LabelEncoder

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MLFeatureEngineer:
    """Klasa do tworzenia cech dla modelu ML intraday trading"""
    
    def __init__(self, db_path: str = "gpw_data.db"):
        """
        Inicjalizacja feature engineera
        
        Args:
            db_path: Ścieżka do bazy danych SQLite
        """
        self.db_path = db_path
        self.scaler = StandardScaler()
        self.feature_names = []
        
        logger.info("✓ ML Feature Engineer zainicjalizowany")
    
    def extract_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ekstraktuje cechy cenowe z danych OHLCV
        
        Args:
            df: DataFrame z kolumnami ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            DataFrame z cechami cenowymi
        """
        features = df.copy()
        
        # Podstawowe cechy cenowe
        features['price_change'] = (features['close'] - features['open']) / features['open']
        features['price_range'] = (features['high'] - features['low']) / features['open']
        features['upper_shadow'] = (features['high'] - np.maximum(features['open'], features['close'])) / features['open']
        features['lower_shadow'] = (np.minimum(features['open'], features['close']) - features['low']) / features['open']
        features['body_size'] = np.abs(features['close'] - features['open']) / features['open']
        
        # Relacje cenowe
        features['close_to_high'] = features['close'] / features['high']
        features['close_to_low'] = features['close'] / features['low']
        features['open_to_high'] = features['open'] / features['high']
        features['open_to_low'] = features['open'] / features['low']
        
        # Volatility
        features['volatility'] = features['price_range']
        features['log_return'] = np.log(features['close'] / features['open'])
        
        return features
    
    def extract_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ekstraktuje cechy wolumenowe
        
        Args:
            df: DataFrame z kolumną 'volume'
            
        Returns:
            DataFrame z cechami wolumenowymi
        """
        features = df.copy()
        
        # Cechy wolumenowe
        features['volume_sma_5'] = features['volume'].rolling(window=5).mean()
        features['volume_sma_20'] = features['volume'].rolling(window=20).mean()
        features['volume_ratio_5'] = features['volume'] / features['volume_sma_5']
        features['volume_ratio_20'] = features['volume'] / features['volume_sma_20']
        
        # Volume-Price Trend (VPT)
        features['vpt'] = (features['volume'] * features['price_change']).cumsum()
        
        # On-Balance Volume (OBV)
        features['obv'] = np.where(features['close'] > features['close'].shift(1), 
                                  features['volume'], 
                                  -features['volume']).cumsum()
        
        # Volume oszylator
        features['volume_oscillator'] = (features['volume_sma_5'] - features['volume_sma_20']) / features['volume_sma_20']
        
        return features
    
    def extract_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ekstraktuje wskaźniki techniczne
        
        Args:
            df: DataFrame z danymi OHLCV
            
        Returns:
            DataFrame z wskaźnikami technicznymi
        """
        features = df.copy()
        
        # Moving Averages
        features['sma_5'] = ta.trend.sma_indicator(features['close'], window=5)
        features['sma_10'] = ta.trend.sma_indicator(features['close'], window=10)
        features['sma_20'] = ta.trend.sma_indicator(features['close'], window=20)
        features['ema_5'] = ta.trend.ema_indicator(features['close'], window=5)
        features['ema_10'] = ta.trend.ema_indicator(features['close'], window=10)
        
        # RSI
        features['rsi'] = ta.momentum.rsi(features['close'], window=14)
        features['rsi_sma'] = features['rsi'].rolling(window=5).mean()
        
        # MACD
        macd = ta.trend.MACD(features['close'])
        features['macd'] = macd.macd()
        features['macd_signal'] = macd.macd_signal()
        features['macd_diff'] = macd.macd_diff()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(features['close'])
        features['bb_upper'] = bb.bollinger_hband()
        features['bb_lower'] = bb.bollinger_lband()
        features['bb_middle'] = bb.bollinger_mavg()
        features['bb_width'] = (features['bb_upper'] - features['bb_lower']) / features['bb_middle']
        features['bb_position'] = (features['close'] - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'])
        
        # Stochastic
        stoch = ta.momentum.StochasticOscillator(features['high'], features['low'], features['close'])
        features['stoch_k'] = stoch.stoch()
        features['stoch_d'] = stoch.stoch_signal()
        
        # ATR (Average True Range)
        features['atr'] = ta.volatility.average_true_range(features['high'], features['low'], features['close'])
        features['atr_ratio'] = features['atr'] / features['close']
        
        # Williams %R
        features['williams_r'] = ta.momentum.williams_r(features['high'], features['low'], features['close'])
        
        # Momentum
        features['momentum'] = features['close'] / features['close'].shift(10) - 1
        
        # Price relative to moving averages
        features['price_to_sma5'] = features['close'] / features['sma_5']
        features['price_to_sma10'] = features['close'] / features['sma_10']
        features['price_to_sma20'] = features['close'] / features['sma_20']
        
        return features
    
    def extract_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ekstraktuje cechy czasowe (godzina, dzień tygodnia, etc.)
        
        Args:
            df: DataFrame z indeksem datetime
            
        Returns:
            DataFrame z cechami czasowymi
        """
        features = df.copy()
        
        if not isinstance(features.index, pd.DatetimeIndex):
            logger.warning("Index nie jest typu DatetimeIndex, pomijam cechy czasowe")
            return features
        
        # Cechy czasowe
        features['hour'] = features.index.hour
        features['minute'] = features.index.minute
        features['day_of_week'] = features.index.dayofweek
        features['is_morning'] = (features.index.hour < 12).astype(int)
        features['is_afternoon'] = (features.index.hour >= 12).astype(int)
        features['is_near_open'] = (features.index.hour == 9).astype(int)
        features['is_near_close'] = (features.index.hour >= 16).astype(int)
        
        # Sesja tradingowa
        features['session_time'] = features.index.hour + features.index.minute / 60.0
        features['time_to_close'] = 17.0 - features['session_time']  # Zakładając zamknięcie o 17:00
        
        return features
    
    def extract_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ekstraktuje cechy wzorców świecowych i formacji
        
        Args:
            df: DataFrame z danymi OHLCV
            
        Returns:
            DataFrame z cechami wzorców
        """
        features = df.copy()
        
        # Doji (cena otwarcia ≈ cena zamknięcia)
        features['is_doji'] = (np.abs(features['close'] - features['open']) / features['open'] < 0.001).astype(int)
        
        # Hammer/Shooting star
        body_size = np.abs(features['close'] - features['open'])
        upper_shadow = features['high'] - np.maximum(features['open'], features['close'])
        lower_shadow = np.minimum(features['open'], features['close']) - features['low']
        
        features['is_hammer'] = ((lower_shadow > 2 * body_size) & (upper_shadow < body_size)).astype(int)
        features['is_shooting_star'] = ((upper_shadow > 2 * body_size) & (lower_shadow < body_size)).astype(int)
        
        # Engulfing patterns
        prev_body = np.abs(features['close'].shift(1) - features['open'].shift(1))
        curr_body = np.abs(features['close'] - features['open'])
        
        features['is_bullish_engulfing'] = (
            (features['close'] > features['open']) &  # Obecna świeca zielona
            (features['close'].shift(1) < features['open'].shift(1)) &  # Poprzednia świeca czerwona
            (features['open'] < features['close'].shift(1)) &  # Otwarcie poniżej poprzedniego zamknięcia
            (features['close'] > features['open'].shift(1)) &  # Zamknięcie powyżej poprzedniego otwarcia
            (curr_body > prev_body)  # Obecny korpus większy
        ).astype(int)
        
        features['is_bearish_engulfing'] = (
            (features['close'] < features['open']) &  # Obecna świeca czerwona
            (features['close'].shift(1) > features['open'].shift(1)) &  # Poprzednia świeca zielona
            (features['open'] > features['close'].shift(1)) &  # Otwarcie powyżej poprzedniego zamknięcia
            (features['close'] < features['open'].shift(1)) &  # Zamknięcie poniżej poprzedniego otwarcia
            (curr_body > prev_body)  # Obecny korpus większy
        ).astype(int)
        
        return features
    
    def extract_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ekstraktuje cechy momentum i trend
        
        Args:
            df: DataFrame z danymi cenowymi
            
        Returns:
            DataFrame z cechami momentum
        """
        features = df.copy()
        
        # Rate of Change (ROC)
        for period in [3, 5, 10]:
            features[f'roc_{period}'] = ((features['close'] - features['close'].shift(period)) / 
                                        features['close'].shift(period)) * 100
        
        # Trend strength
        features['trend_5'] = np.where(features['close'] > features['sma_5'], 1, 
                                      np.where(features['close'] < features['sma_5'], -1, 0))
        features['trend_10'] = np.where(features['close'] > features['sma_10'], 1, 
                                       np.where(features['close'] < features['sma_10'], -1, 0))
        
        # Consecutive ups/downs
        price_change = features['close'] - features['close'].shift(1)
        features['consecutive_ups'] = (price_change > 0).astype(int).groupby((price_change <= 0).cumsum()).cumcount()
        features['consecutive_downs'] = (price_change < 0).astype(int).groupby((price_change >= 0).cumsum()).cumcount()
        
        # Volatility measures
        features['volatility_5'] = features['close'].rolling(window=5).std()
        features['volatility_10'] = features['close'].rolling(window=10).std()
        features['volatility_ratio'] = features['volatility_5'] / features['volatility_10']
        
        return features
    
    def create_intraday_features(self, ticker: str, date: str, lookback_days: int = 30) -> Optional[pd.DataFrame]:
        """
        Tworzy kompletny zestaw cech dla danej spółki i dnia
        
        Args:
            ticker: Symbol spółki
            date: Data w formacie YYYY-MM-DD
            lookback_days: Ile dni wstecz pobrać dla kontekstu
            
        Returns:
            DataFrame z cechami lub None jeśli brak danych
        """
        try:
            # Pobierz dane historyczne
            end_date = datetime.strptime(date, '%Y-%m-%d')
            start_date = end_date - timedelta(days=lookback_days)
            
            # Najpierw spróbuj pobrać dane dzienne
            df_daily = self._get_daily_data(ticker, start_date.strftime('%Y-%m-%d'), date)
            
            if df_daily is None or len(df_daily) < 10:
                logger.warning(f"Zbyt mało danych dziennych dla {ticker} w okolicach {date}")
                return None
            
            # Spróbuj pobrać dane intraday dla danego dnia
            df_intraday = self._get_intraday_data(ticker, date)
            
            if df_intraday is not None and len(df_intraday) > 0:
                # Użyj danych intraday jako głównych
                df = df_intraday.copy()
                logger.info(f"✓ Używam danych intraday dla {ticker} na {date}: {len(df)} rekordów")
            else:
                # Fallback do danych dziennych
                df = df_daily[df_daily['date'] == date].copy()
                if len(df) == 0:
                    logger.warning(f"Brak danych dla {ticker} na {date}")
                    return None
                logger.info(f"✓ Używam danych dziennych dla {ticker} na {date}")
            
            # Ustaw indeks datetime
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
            elif 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
            
            # Połącz z kontekstem historycznym dla wskaźników technicznych
            df_context = df_daily.copy()
            df_context['date'] = pd.to_datetime(df_context['date'])
            df_context = df_context.set_index('date')
            
            # Ekstraktuj wszystkie typy cech
            df = self.extract_price_features(df)
            df = self.extract_volume_features(df)
            
            # Dla wskaźników technicznych użyj kontekstu historycznego
            df_context = self.extract_technical_indicators(df_context)
            
            # Dodaj wskaźniki techniczne z ostatniego dnia
            if date in df_context.index.strftime('%Y-%m-%d'):
                tech_features = df_context.loc[df_context.index.strftime('%Y-%m-%d') == date]
                for col in tech_features.columns:
                    if col.startswith(('rsi', 'macd', 'bb_', 'sma_', 'ema_', 'stoch_', 'atr', 'williams_r', 'momentum')):
                        df[col] = tech_features[col].iloc[0] if len(tech_features) > 0 else np.nan
            
            df = self.extract_time_features(df)
            df = self.extract_pattern_features(df)
            df = self.extract_momentum_features(df)
            
            # Usuń nieskończone i NaN wartości
            df = df.replace([np.inf, -np.inf], np.nan)
            
            # Zapisz nazwy cech
            self.feature_names = [col for col in df.columns if col not in ['open', 'high', 'low', 'close', 'volume']]
            
            logger.info(f"✓ Utworzono {len(self.feature_names)} cech dla {ticker} na {date}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Błąd tworzenia cech dla {ticker} na {date}: {e}")
            return None
    
    def _get_daily_data(self, ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Pobiera dane dzienne z bazy"""
        try:
            from workers.quotes_daily import get_daily_quotes_range
            
            # Spróbuj użyć istniejącej funkcji
            quotes = get_daily_quotes_range(ticker, start_date, end_date)
            
            if quotes and len(quotes) > 0:
                df = pd.DataFrame(quotes)
                # Upewnij się, że mamy wymagane kolumny
                required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                if all(col in df.columns for col in required_cols):
                    return df[required_cols]
            
            logger.warning(f"Brak danych dziennych dla {ticker} z zakresu {start_date} - {end_date}")
            return None
            
        except Exception as e:
            logger.error(f"Błąd pobierania danych dziennych: {e}")
            return None
    
    def _get_intraday_data(self, ticker: str, date: str) -> Optional[pd.DataFrame]:
        """Pobiera dane intraday z bazy"""
        try:
            from workers.quotes_intraday import get_intraday_quotes_for_date
            
            # Spróbuj pobrać dane intraday
            quotes = get_intraday_quotes_for_date(ticker, date)
            
            if quotes and len(quotes) > 0:
                df = pd.DataFrame(quotes)
                
                # Sprawdź czy mamy kompletne dane OHLCV
                if all(col in df.columns for col in ['datetime', 'price']):
                    # Konwertuj pojedyncze ceny na format OHLCV
                    df['open'] = df['price']
                    df['high'] = df['price']
                    df['low'] = df['price']
                    df['close'] = df['price']
                    df['volume'] = df.get('volume', 1000)  # Domyślny wolumen jeśli brak
                    
                    return df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
            
            return None
            
        except Exception as e:
            logger.warning(f"Brak danych intraday dla {ticker} na {date}: {e}")
            return None
    
    def extract_features_for_ticker(self, ticker: str, date: Optional[str] = None) -> pd.DataFrame:
        """
        Ekstraktuje cechy dla konkretnego tickera (wrapper dla API)
        
        Args:
            ticker: Symbol spółki
            date: Data (domyślnie dzisiaj)
            
        Returns:
            DataFrame z cechami
        """
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
                
            features = self.create_intraday_features(ticker, date)
            
            if features is not None and len(features) > 0:
                return features
            else:
                logger.warning(f"Brak cech dla {ticker} na {date}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Błąd ekstraktowania cech dla {ticker}: {e}")
            return pd.DataFrame()
    
    def prepare_training_data(self, tickers: List[str], start_date: str, end_date: str, 
                            days_back: Optional[int] = None) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Przygotowuje dane treningowe dla listy tickerów (wersja kompatybilna z API)
        
        Args:
            tickers: Lista tickerów
            start_date: Data początkowa
            end_date: Data końcowa
            days_back: Alternatywnie - liczba dni wstecz od dzisiaj
            
        Returns:
            Tuple (X - cechy, y - etykiety)
        """
        try:
            if days_back is not None:
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            # Wywołaj oryginalną metodę
            X, y = self.prepare_training_data_original(tickers, start_date, end_date)
            return X, y
            
        except Exception as e:
            logger.error(f"Błąd przygotowania danych treningowych: {e}")
            return pd.DataFrame(), pd.Series()
    
    def prepare_training_data_original(self, tickers: List[str], start_date: str, end_date: str) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Oryginalna metoda przygotowania danych treningowych
        """
        all_features = []
        all_labels = []
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        for ticker in tickers:
            logger.info(f"🔄 Przetwarzam {ticker}...")
            
            for date in date_range:
                date_str = date.strftime('%Y-%m-%d')
                
                # Pomiń weekendy (może nie być danych)
                if date.weekday() >= 5:
                    continue
                
                # Stwórz cechy
                features_df = self.create_intraday_features(ticker, date_str)
                
                if features_df is not None and len(features_df) > 0:
                    # Stwórz etykiety (czy warto było kupić)
                    labels = self._create_labels(features_df, ticker, date_str)
                    
                    if labels is not None:
                        # Dodaj ticker jako cechę
                        features_df['ticker'] = ticker
                        
                        # Dodaj do zbiorów
                        all_features.append(features_df)
                        all_labels.extend(labels)
        
        if not all_features:
            logger.error("❌ Brak danych do treningu")
            return pd.DataFrame(), pd.Series()
        
        # Połącz wszystkie dane
        combined_features = pd.concat(all_features, ignore_index=True)
        combined_labels = pd.Series(all_labels)
        
        # Enkoduj ticker
        le = LabelEncoder()
        combined_features['ticker_encoded'] = le.fit_transform(combined_features['ticker'])
        combined_features = combined_features.drop('ticker', axis=1)
        
        # Usuń wiersze z brakującymi danymi
        valid_mask = ~(combined_features.isna().any(axis=1) | combined_labels.isna())
        combined_features = combined_features[valid_mask]
        combined_labels = combined_labels[valid_mask]
        
        logger.info(f"✅ Przygotowano {len(combined_features)} próbek treningowych")
        logger.info(f"   📊 Rozkład etykiet: {combined_labels.value_counts().to_dict()}")
        
        return combined_features, combined_labels
    
    def _create_labels(self, df: pd.DataFrame, ticker: str, date: str) -> Optional[List[int]]:
        """
        Tworzy etykiety dla danych (czy warto było kupić)
        
        Logika:
        - 1 (BUY) jeśli w ciągu następnych 1-4h cena wzrosła o min. 2% i można było sprzedać z zyskiem
        - 0 (HOLD) w przeciwnym razie
        
        Args:
            df: DataFrame z cechami dla danego dnia
            ticker: Symbol spółki
            date: Data
            
        Returns:
            Lista etykiet (0 lub 1) dla każdego rekordu
        """
        try:
            labels = []
            
            for i in range(len(df)):
                current_price = df.iloc[i]['close']
                
                # Sprawdź cenę w kolejnych godzinach (maksymalnie 4h)
                max_future_price = current_price
                future_horizon = min(4, len(df) - i - 1)  # Maksymalnie 4h lub do końca danych
                
                for j in range(1, future_horizon + 1):
                    if i + j < len(df):
                        future_price = df.iloc[i + j]['close']
                        max_future_price = max(max_future_price, future_price)
                
                # Oblicz potencjalny zysk
                potential_profit = (max_future_price - current_price) / current_price
                
                # Etykieta: 1 jeśli można było zarobić min. 2%
                if potential_profit >= 0.02:  # 2% zysk
                    labels.append(1)
                else:
                    labels.append(0)
            
            return labels
            
        except Exception as e:
            logger.error(f"Błąd tworzenia etykiet dla {ticker} na {date}: {e}")
            return None


def main():
    """Funkcja testowa"""
    engineer = MLFeatureEngineer()
    
    # Test tworzenia cech
    print("=== TEST FEATURE ENGINEERING ===")
    
    # Test dla jednego dnia
    features = engineer.create_intraday_features('CDR', '2025-06-24')
    
    if features is not None:
        print(f"✅ Utworzono {len(features)} rekordów z {len(engineer.feature_names)} cechami")
        print("Przykładowe cechy:")
        for i, feature in enumerate(engineer.feature_names[:10]):
            print(f"  {i+1}. {feature}")
        
        if len(engineer.feature_names) > 10:
            print(f"  ... i {len(engineer.feature_names) - 10} więcej")
    else:
        print("❌ Nie udało się utworzyć cech")
    
    # Test przygotowania danych treningowych
    print("\n=== TEST DANYCH TRENINGOWYCH ===")
    
    test_tickers = ['CDR', 'PKN']
    start_date = '2025-06-20'
    end_date = '2025-06-24'
    
    X, y = engineer.prepare_training_data(test_tickers, start_date, end_date)
    
    if len(X) > 0:
        print(f"✅ Przygotowano dane treningowe: {X.shape}")
        print(f"   Cechy: {X.shape[1]}")
        print(f"   Próbki: {X.shape[0]}")
        print(f"   Rozkład etykiet: {y.value_counts().to_dict()}")
    else:
        print("❌ Brak danych treningowych")


if __name__ == "__main__":
    main()
