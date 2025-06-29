#!/usr/bin/env python3
"""
Moduł analizy technicznej dla systemu GPW Investor
Oblicza wskaźniki techniczne na podstawie danych historycznych
Autor: GPW Investor System
Data: 2025-06-24
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import os
import sys

# Dodaj ścieżkę do głównego katalogu
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ładuj zmienne środowiskowe
load_dotenv()

class TechnicalAnalyzer:
    """Klasa do analizy technicznej akcji GPW"""
    
    def __init__(self):
        """Inicjalizacja analizera technicznego"""
        self.engine = self._get_db_engine()
        logger.info("✓ Technical Analyzer zainicjalizowany")
    
    def _get_db_engine(self):
        """Utwórz połączenie z bazą danych"""
        try:
            db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
            engine = create_engine(db_url)
            return engine
        except Exception as e:
            logger.error(f"❌ Błąd połączenia z bazą danych: {e}")
            raise e
    
    def get_historical_data(self, ticker: str, days_back: int = 100) -> pd.DataFrame:
        """
        Pobierz dane historyczne dla spółki
        
        Args:
            ticker: Symbol spółki (np. 'PKN')
            days_back: Liczba dni wstecz
            
        Returns:
            DataFrame z kolumnami: date, open, high, low, close, volume
        """
        try:
            import psycopg2
            
            # Połączenie bezpośrednie z psycopg2
            conn = psycopg2.connect(
                dbname=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                host=os.getenv('DB_HOST'),
                port=os.getenv('DB_PORT')
            )
            
            query = """
            SELECT 
                qd.date,
                qd.open,
                qd.high,
                qd.low,
                qd.close,
                qd.volume,
                c.ticker
            FROM quotes_daily qd
            JOIN companies c ON qd.company_id = c.id
            WHERE c.ticker = %s
                AND qd.date >= %s
            ORDER BY qd.date ASC
            """
            
            start_date = datetime.now().date() - timedelta(days=days_back)
            
            df = pd.read_sql_query(query, conn, params=[ticker, start_date])
            conn.close()
            
            if df.empty:
                logger.warning(f"⚠️ Brak danych historycznych dla {ticker}")
                return pd.DataFrame()
            
            # Konwersje typów
            df['date'] = pd.to_datetime(df['date'])
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.sort_values('date').reset_index(drop=True)
            
            logger.info(f"✓ Pobrano {len(df)} dni danych dla {ticker}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Błąd pobierania danych dla {ticker}: {e}")
            return pd.DataFrame()
    
    def calculate_sma(self, data: pd.Series, period: int) -> pd.Series:
        """Oblicz Simple Moving Average (SMA)"""
        return data.rolling(window=period, min_periods=1).mean()
    
    def calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """Oblicz Exponential Moving Average (EMA)"""
        return data.ewm(span=period, adjust=False).mean()
    
    def calculate_rsi(self, data: pd.Series, period: int = 14) -> pd.Series:
        """
        Oblicz Relative Strength Index (RSI)
        
        Args:
            data: Serie cen zamknięcia
            period: Okres obliczania (domyślnie 14)
            
        Returns:
            Serie z wartościami RSI (0-100)
        """
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """
        Oblicz MACD (Moving Average Convergence Divergence)
        
        Args:
            data: Serie cen zamknięcia
            fast: Okres szybkiej EMA (domyślnie 12)
            slow: Okres wolnej EMA (domyślnie 26)
            signal: Okres sygnalnej EMA (domyślnie 9)
            
        Returns:
            Słownik z MACD, sygnałem i histogramem
        """
        ema_fast = self.calculate_ema(data, fast)
        ema_slow = self.calculate_ema(data, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    def calculate_bollinger_bands(self, data: pd.Series, period: int = 20, std_dev: float = 2) -> Dict[str, pd.Series]:
        """
        Oblicz Bollinger Bands
        
        Args:
            data: Serie cen zamknięcia
            period: Okres SMA (domyślnie 20)
            std_dev: Liczba odchyleń standardowych (domyślnie 2)
            
        Returns:
            Słownik z górnym, dolnym pasmem i SMA
        """
        sma = self.calculate_sma(data, period)
        std = data.rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band
        }
    
    def calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
        """
        Oblicz Stochastic Oscillator
        
        Args:
            high: Serie cen maksymalnych
            low: Serie cen minimalnych
            close: Serie cen zamknięcia
            k_period: Okres %K (domyślnie 14)
            d_period: Okres %D (domyślnie 3)
            
        Returns:
            Słownik z %K i %D
        """
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return {
            'k_percent': k_percent,
            'd_percent': d_percent
        }
    
    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        Oblicz Average True Range (ATR)
        
        Args:
            high: Serie cen maksymalnych
            low: Serie cen minimalnych
            close: Serie cen zamknięcia
            period: Okres obliczania (domyślnie 14)
            
        Returns:
            Serie z wartościami ATR
        """
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    def calculate_williams_r(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        Oblicz Williams %R
        
        Args:
            high: Serie cen maksymalnych
            low: Serie cen minimalnych
            close: Serie cen zamknięcia
            period: Okres obliczania (domyślnie 14)
            
        Returns:
            Serie z wartościami Williams %R (-100 do 0)
        """
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        
        williams_r = -100 * ((highest_high - close) / (highest_high - lowest_low))
        
        return williams_r
    
    def calculate_volume_sma(self, volume: pd.Series, period: int = 20) -> pd.Series:
        """Oblicz średni wolumen"""
        return volume.rolling(window=period).mean()
    
    def detect_volume_spike(self, volume: pd.Series, volume_sma: pd.Series, threshold: float = 2.0) -> pd.Series:
        """
        Wykryj skok wolumenu
        
        Args:
            volume: Serie wolumenu
            volume_sma: Serie średniego wolumenu
            threshold: Próg wykrycia (domyślnie 2.0x średnia)
            
        Returns:
            Serie boolean - True gdy wolumen > threshold * średnia
        """
        return volume > (volume_sma * threshold)
    
    def calculate_price_change(self, close: pd.Series, periods: int = 1) -> Dict[str, pd.Series]:
        """
        Oblicz zmiany ceny
        
        Args:
            close: Serie cen zamknięcia
            periods: Liczba okresów (domyślnie 1)
            
        Returns:
            Słownik ze zmianami absolutnymi i procentowymi
        """
        price_change_abs = close.diff(periods)
        price_change_pct = close.pct_change(periods) * 100
        
        return {
            'absolute': price_change_abs,
            'percentage': price_change_pct
        }
    
    def analyze_ticker(self, ticker: str, days_back: int = 100) -> Dict:
        """
        Przeprowadź pełną analizę techniczną spółki
        
        Args:
            ticker: Symbol spółki
            days_back: Liczba dni historycznych
            
        Returns:
            Słownik z wszystkimi wskaźnikami technicznymi
        """
        logger.info(f"📊 Rozpoczynam analizę techniczną dla {ticker}")
        
        # Pobierz dane historyczne
        df = self.get_historical_data(ticker, days_back)
        if df.empty:
            return {}
        
        # Oblicz wskaźniki techniczne
        analysis = {
            'ticker': ticker,
            'data_points': len(df),
            'date_from': df['date'].min(),
            'date_to': df['date'].max(),
            'current_price': float(df['close'].iloc[-1]),
        }
        
        # Moving Averages
        analysis['sma_5'] = float(self.calculate_sma(df['close'], 5).iloc[-1])
        analysis['sma_10'] = float(self.calculate_sma(df['close'], 10).iloc[-1])
        analysis['sma_20'] = float(self.calculate_sma(df['close'], 20).iloc[-1])
        analysis['sma_50'] = float(self.calculate_sma(df['close'], 50).iloc[-1])
        
        analysis['ema_12'] = float(self.calculate_ema(df['close'], 12).iloc[-1])
        analysis['ema_26'] = float(self.calculate_ema(df['close'], 26).iloc[-1])
        
        # RSI
        rsi = self.calculate_rsi(df['close'])
        analysis['rsi'] = float(rsi.iloc[-1]) if not rsi.empty else None
        
        # MACD
        macd = self.calculate_macd(df['close'])
        analysis['macd'] = float(macd['macd'].iloc[-1]) if not macd['macd'].empty else None
        analysis['macd_signal'] = float(macd['signal'].iloc[-1]) if not macd['signal'].empty else None
        analysis['macd_histogram'] = float(macd['histogram'].iloc[-1]) if not macd['histogram'].empty else None
        
        # Bollinger Bands
        bb = self.calculate_bollinger_bands(df['close'])
        analysis['bb_upper'] = float(bb['upper'].iloc[-1]) if not bb['upper'].empty else None
        analysis['bb_middle'] = float(bb['middle'].iloc[-1]) if not bb['middle'].empty else None
        analysis['bb_lower'] = float(bb['lower'].iloc[-1]) if not bb['lower'].empty else None
        
        # Stochastic
        if len(df) >= 14:  # Potrzebujemy przynajmniej 14 dni
            stoch = self.calculate_stochastic(df['high'], df['low'], df['close'])
            analysis['stoch_k'] = float(stoch['k_percent'].iloc[-1]) if not stoch['k_percent'].empty else None
            analysis['stoch_d'] = float(stoch['d_percent'].iloc[-1]) if not stoch['d_percent'].empty else None
        
        # ATR
        if len(df) >= 14:
            atr = self.calculate_atr(df['high'], df['low'], df['close'])
            analysis['atr'] = float(atr.iloc[-1]) if not atr.empty else None
        
        # Williams %R
        if len(df) >= 14:
            williams = self.calculate_williams_r(df['high'], df['low'], df['close'])
            analysis['williams_r'] = float(williams.iloc[-1]) if not williams.empty else None
        
        # Volume Analysis
        analysis['current_volume'] = float(df['volume'].iloc[-1])
        analysis['volume_sma_20'] = float(self.calculate_volume_sma(df['volume'], 20).iloc[-1])
        
        volume_spike = self.detect_volume_spike(
            df['volume'], 
            self.calculate_volume_sma(df['volume'], 20)
        )
        analysis['volume_spike'] = bool(volume_spike.iloc[-1]) if not volume_spike.empty else False
        
        # Price Changes
        changes_1d = self.calculate_price_change(df['close'], 1)
        changes_5d = self.calculate_price_change(df['close'], 5)
        
        analysis['price_change_1d'] = float(changes_1d['percentage'].iloc[-1]) if not changes_1d['percentage'].empty else None
        analysis['price_change_5d'] = float(changes_5d['percentage'].iloc[-1]) if not changes_5d['percentage'].empty else None
        
        # Trend Analysis
        analysis['trend_sma'] = self._analyze_trend(analysis['current_price'], analysis['sma_20'])
        analysis['trend_ema'] = self._analyze_trend(analysis['current_price'], analysis['ema_12'])
        
        logger.info(f"✅ Analiza techniczna zakończona dla {ticker}")
        return analysis
    
    def _analyze_trend(self, current_price: float, ma_price: float) -> str:
        """Określ trend na podstawie pozycji ceny względem średniej"""
        if current_price > ma_price * 1.02:  # 2% powyżej
            return "strong_uptrend"
        elif current_price > ma_price:
            return "uptrend"
        elif current_price < ma_price * 0.98:  # 2% poniżej
            return "strong_downtrend"
        else:
            return "downtrend"
    
    def get_market_overview(self, tickers: List[str]) -> Dict:
        """
        Pobierz przegląd rynkowy dla listy spółek
        
        Args:
            tickers: Lista symboli spółek
            
        Returns:
            Słownik z analizą dla każdej spółki
        """
        logger.info(f"📈 Przegląd rynkowy dla {len(tickers)} spółek")
        
        overview = {}
        for ticker in tickers:
            try:
                overview[ticker] = self.analyze_ticker(ticker, days_back=50)
            except Exception as e:
                logger.error(f"❌ Błąd analizy {ticker}: {e}")
                overview[ticker] = {}
        
        return overview


def main():
    """Funkcja główna - test analizy technicznej"""
    logger.info("🧪 Test analizy technicznej")
    
    analyzer = TechnicalAnalyzer()
    
    # Test dla pojedynczej spółki
    test_ticker = "PKN"
    analysis = analyzer.analyze_ticker(test_ticker)
    
    if analysis:
        logger.info(f"📊 Analiza {test_ticker}:")
        logger.info(f"   Cena: {analysis['current_price']:.2f} PLN")
        logger.info(f"   RSI: {analysis.get('rsi', 'N/A')}")
        logger.info(f"   SMA20: {analysis.get('sma_20', 'N/A'):.2f}")
        logger.info(f"   Trend: {analysis.get('trend_sma', 'N/A')}")
        logger.info(f"   Zmiana 1d: {analysis.get('price_change_1d', 'N/A'):.2f}%")
    
    # Test przeglądu rynkowego
    tickers = ["PKN", "CDR", "PKO"]
    overview = analyzer.get_market_overview(tickers)
    
    logger.info(f"📈 Przegląd rynkowy dla {len(overview)} spółek")
    for ticker, data in overview.items():
        if data:
            logger.info(f"   {ticker}: {data.get('current_price', 'N/A'):.2f} PLN, RSI: {data.get('rsi', 'N/A')}")


if __name__ == "__main__":
    main()
