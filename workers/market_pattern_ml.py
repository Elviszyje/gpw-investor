#!/usr/bin/env python3
"""
Market Pattern ML - Model uczenia maszynowego wykrywający wzorce rynkowe
Analizuje WSZYSTKIE spółki razem, szuka wzorców typu "panika → dip → odbicie"
Autor: GPW Investor System
Data: 2025-06-27
"""

import numpy as np
import pandas as pd
import pickle
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ML libraries
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    from sklearn.preprocessing import StandardScaler
    ML_AVAILABLE = True
    logger.info("✓ ML libraries loaded successfully")
except ImportError as e:
    ML_AVAILABLE = False
    RandomForestClassifier = None
    train_test_split = None
    StandardScaler = None
    logger.warning(f"⚠️ ML libraries not available: {e}")

class MarketPatternML:
    """Model ML wykrywający wzorce zachowań rynkowych - panika, wyprzedaż, odbicia"""
    
    def __init__(self, model_path: str = "models/market_pattern_model.pkl"):
        """Inicjalizacja Market Pattern ML"""
        load_dotenv('.env')
        
        # PostgreSQL connection
        self.pg_config = {
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'host': os.getenv('DB_HOST'),
            'port': os.getenv('DB_PORT'),
            'database': os.getenv('DB_NAME')
        }
        
        # Create DB engine
        db_uri = f"postgresql://{self.pg_config['user']}:{self.pg_config['password']}@{self.pg_config['host']}:{self.pg_config['port']}/{self.pg_config['database']}"
        self.engine = create_engine(db_uri)
        
        # Model setup
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.feature_names = []
        self.is_trained = False
        
        # Create models directory
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Load existing model if available
        self.load_model()
        
        logger.info("✓ Market Pattern ML initialized")
    
    def get_market_data(self, tickers: List[str], days_back: int = 2000) -> pd.DataFrame:
        """
        Pobiera WSZYSTKIE dane 5-minutowe dla wszystkich spółek z ostatnich N dni
        Kluczowe: analizujemy wszystkie spółki razem w tym samym czasie!
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Zapytanie do PostgreSQL - pobieramy WSZYSTKIE dane intraday razem
            query = text("""
                SELECT 
                    qi.datetime,
                    c.ticker,
                    qi.price,
                    qi.volume,
                    qi.high,
                    qi.low,
                    qi.open
                FROM quotes_intraday qi
                JOIN companies c ON qi.company_id = c.id
                WHERE c.ticker = ANY(:tickers)
                  AND qi.datetime >= :start_date
                  AND qi.datetime <= :end_date
                ORDER BY qi.datetime, c.ticker
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query, {
                    'tickers': tickers,
                    'start_date': start_date,
                    'end_date': end_date
                })
                
                df = pd.DataFrame(result.fetchall(), columns=[
                    'datetime', 'ticker', 'price', 'volume', 'high', 'low', 'open'
                ])
            
            if len(df) == 0:
                logger.warning(f"Brak danych dla tickerów: {tickers}")
                return pd.DataFrame()
            
            logger.info(f"✓ Pobrano {len(df):,} rekordów dla {len(tickers)} spółek z {days_back} dni")
            return df
            
        except Exception as e:
            logger.error(f"Błąd pobierania danych rynkowych: {e}")
            return pd.DataFrame()
    
    def create_market_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Tworzy cechy rynkowe analizując WSZYSTKIE spółki razem w każdym momencie czasu
        Wykrywa wzorce typu: wyprzedaż, panika, odbicia na poziomie całego rynku
        """
        try:
            # Pivot data - każda kolumna to jedna spółka, każdy wiersz to moment czasowy
            df_pivot = df.pivot_table(
                index='datetime', 
                columns='ticker', 
                values=['price', 'volume'], 
                aggfunc='mean'
            )
            
            # Flatten column names
            df_pivot.columns = [f"{col[1]}_{col[0]}" for col in df_pivot.columns]
            
            # Reset index to make datetime a column
            df_pivot = df_pivot.reset_index()
            
            # Sort by datetime
            df_pivot = df_pivot.sort_values('datetime')
            
            logger.info(f"✓ Pivot table created: {df_pivot.shape[0]} time points, {df_pivot.shape[1]-1} ticker-features")
            
            # ========== MARKET-WIDE FEATURES ==========
            # Te cechy analizują zachowanie CAŁEGO RYNKU w każdym momencie
            
            # 1. Średnia cena wszystkich spółek w danym momencie
            price_cols = [col for col in df_pivot.columns if col.endswith('_price')]
            df_pivot['market_avg_price'] = df_pivot[price_cols].mean(axis=1)
            df_pivot['market_price_std'] = df_pivot[price_cols].std(axis=1)
            
            # 2. Zmiana średniej ceny rynku (czy spadek/wzrost)
            df_pivot['market_price_change'] = df_pivot['market_avg_price'].pct_change()
            df_pivot['market_price_change_1h'] = df_pivot['market_avg_price'].pct_change(periods=12)  # 1h = 12 x 5min
            df_pivot['market_price_change_2h'] = df_pivot['market_avg_price'].pct_change(periods=24)  # 2h = 24 x 5min
            
            # 3. Ile spółek spadło/wzrosło (sentiment rynku)
            for periods, label in [(1, '5min'), (12, '1h'), (24, '2h')]:
                changes = df_pivot[price_cols].pct_change(periods=periods)
                df_pivot[f'stocks_falling_{label}'] = (changes < 0).sum(axis=1)
                df_pivot[f'stocks_rising_{label}'] = (changes > 0).sum(axis=1)
                df_pivot[f'stocks_falling_pct_{label}'] = df_pivot[f'stocks_falling_{label}'] / len(price_cols)
                df_pivot[f'stocks_rising_pct_{label}'] = df_pivot[f'stocks_rising_{label}'] / len(price_cols)
            
            # 4. Volatility rynku (czy jest panika?)
            df_pivot['market_volatility'] = df_pivot[price_cols].pct_change().std(axis=1)
            df_pivot['market_volatility_1h'] = df_pivot[price_cols].pct_change(periods=12).std(axis=1)
            
            # 5. Wykrywanie wzorców wyprzedaży (OVERSOLD patterns)
            # Średnia ruchoma cen
            df_pivot['market_sma_20'] = df_pivot['market_avg_price'].rolling(window=20).mean()  # 20 x 5min = 100min
            df_pivot['market_sma_60'] = df_pivot['market_avg_price'].rolling(window=60).mean()  # 60 x 5min = 5h
            
            # Pozycja względem średnich (czy wyprzedane?)
            df_pivot['price_vs_sma20'] = (df_pivot['market_avg_price'] - df_pivot['market_sma_20']) / df_pivot['market_sma_20']
            df_pivot['price_vs_sma60'] = (df_pivot['market_avg_price'] - df_pivot['market_sma_60']) / df_pivot['market_sma_60']
            
            # 6. RSI dla całego rynku
            df_pivot['market_rsi'] = self._calculate_rsi(df_pivot['market_avg_price'])
            
            # 7. Wzorce cenowe (czy jest dip?)
            df_pivot['price_drop_0.5pct'] = (df_pivot['market_price_change'] < -0.005).astype(int)
            df_pivot['price_drop_1pct'] = (df_pivot['market_price_change'] < -0.01).astype(int)
            df_pivot['price_drop_2pct'] = (df_pivot['market_price_change_1h'] < -0.02).astype(int)
            
            # 8. Oversold conditions (potencjalne punkty wejścia)
            df_pivot['oversold_simple'] = ((df_pivot['price_vs_sma20'] < -0.02) & 
                                         (df_pivot['stocks_falling_pct_1h'] > 0.7)).astype(int)
            
            df_pivot['oversold_rsi'] = (df_pivot['market_rsi'] < 30).astype(int)
            
            # 9. Volume patterns (czy zwiększona aktywność?)
            volume_cols = [col for col in df_pivot.columns if col.endswith('_volume')]
            if volume_cols:
                df_pivot['market_avg_volume'] = df_pivot[volume_cols].mean(axis=1)
                df_pivot['market_volume_change'] = df_pivot['market_avg_volume'].pct_change()
                df_pivot['high_volume'] = (df_pivot['market_volume_change'] > 0.5).astype(int)
            
            # 10. Time features (kiedy w dniu)
            df_pivot['hour'] = pd.to_datetime(df_pivot['datetime']).dt.hour
            df_pivot['minute'] = pd.to_datetime(df_pivot['datetime']).dt.minute
            df_pivot['is_morning'] = (df_pivot['hour'] < 12).astype(int)
            df_pivot['is_afternoon'] = (df_pivot['hour'] >= 12).astype(int)
            
            # Remove individual ticker price columns (keep only market-wide features)
            feature_cols = [col for col in df_pivot.columns 
                          if not (col.endswith('_price') and not col.startswith('market_')) 
                          and not (col.endswith('_volume') and not col.startswith('market_'))]
            
            result_df = df_pivot[feature_cols].copy()
            
            # Clean data
            result_df = result_df.replace([np.inf, -np.inf], np.nan)
            result_df = result_df.ffill().fillna(0)
            
            # Store feature names (exclude datetime)
            self.feature_names = [col for col in result_df.columns if col != 'datetime']
            
            logger.info(f"✓ Created {len(self.feature_names)} market-wide features")
            logger.info(f"Sample features: {self.feature_names[:5]}")
            
            return result_df
            
        except Exception as e:
            logger.error(f"Błąd tworzenia cech rynkowych: {e}")
            return pd.DataFrame()
    
    def _calculate_rsi(self, prices: pd.Series, window: int = 14) -> pd.Series:
        """Calculate RSI for price series"""
        try:
            delta = prices.diff().astype(float)
            gain = delta.where(delta > 0, 0).rolling(window=window).mean()
            loss = (-delta).where(delta < 0, 0).rolling(window=window).mean()
            
            rs = gain / (loss + 1e-10)  # Add small number to avoid division by zero
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(50)
            
        except Exception as e:
            logger.warning(f"Error calculating RSI: {e}")
            return pd.Series([50] * len(prices), index=prices.index)
    
    def create_market_labels(self, df: pd.DataFrame) -> pd.Series:
        """
        Tworzy etykiety dla wzorców rynkowych
        Label = 1 jeśli w ciągu 1-4h nastąpi odbicie rynku o min 2%
        """
        try:
            labels = []
            
            for i in range(len(df)):
                current_price = df.iloc[i]['market_avg_price']
                
                # Sprawdź czy w następnych 1-4h (12-48 okresów 5-min) nastąpi odbicie
                max_future_price = current_price
                future_horizon = min(48, len(df) - i - 1)  # max 4h
                
                for j in range(12, future_horizon + 1):  # start from 1h
                    if i + j < len(df):
                        future_price = df.iloc[i + j]['market_avg_price']
                        max_future_price = max(max_future_price, future_price)
                
                # Oblicz potencjalny zysk z odbicia
                potential_profit = (max_future_price - current_price) / current_price
                
                # Label = 1 jeśli możliwe odbicie o min 2%
                if potential_profit >= 0.02:  # 2% zysk
                    labels.append(1)
                else:
                    labels.append(0)
            
            labels_series = pd.Series(labels)
            
            logger.info(f"✓ Created labels: {labels_series.value_counts().to_dict()}")
            return labels_series
            
        except Exception as e:
            logger.error(f"Błąd tworzenia etykiet: {e}")
            return pd.Series([0] * len(df))
    
    def prepare_training_data(self, tickers: List[str], days_back: int = 500) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Przygotowuje dane treningowe analizując WSZYSTKIE spółki razem przez N dni
        To jest właściwa metoda zgodna z Twoimi wymaganiami!
        """
        try:
            logger.info(f"🔄 Preparing training data for {len(tickers)} tickers, {days_back} days back")
            
            # 1. Pobierz wszystkie dane rynkowe razem
            df = self.get_market_data(tickers, days_back)
            
            if len(df) == 0:
                return pd.DataFrame(), pd.Series()
            
            # 2. Stwórz cechy rynkowe (analizuje wszystkie spółki razem)
            features_df = self.create_market_features(df)
            
            if len(features_df) == 0:
                return pd.DataFrame(), pd.Series()
            
            # 3. Stwórz etykiety (czy nastąpi odbicie rynku)
            labels = self.create_market_labels(features_df)
            
            # 4. Przygotuj finalne dane
            X = features_df[self.feature_names].copy()
            y = labels.copy()
            
            # Remove rows with missing data
            valid_mask = ~(X.isna().any(axis=1) | y.isna())
            X = X[valid_mask]
            y = y[valid_mask]
            
            logger.info(f"✅ Training data prepared: {X.shape[0]} samples, {X.shape[1]} features")
            logger.info(f"   📊 Label distribution: {y.value_counts().to_dict()}")
            
            return X, y
            
        except Exception as e:
            logger.error(f"Błąd przygotowania danych treningowych: {e}")
            return pd.DataFrame(), pd.Series()
    
    def train_model(self, tickers: List[str], days_back: int = 500) -> Dict[str, Any]:
        """Trenuje model na danych rynkowych"""
        try:
            if not ML_AVAILABLE or train_test_split is None or StandardScaler is None or RandomForestClassifier is None:
                return {'error': 'ML libraries not available'}
            
            logger.info(f"🤖 Training market pattern model...")
            
            # Prepare data
            X, y = self.prepare_training_data(tickers, days_back)
            
            if len(X) == 0:
                return {'error': 'No training data available'}
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                class_weight='balanced'
            )
            
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate
            train_score = self.model.score(X_train_scaled, y_train)
            test_score = self.model.score(X_test_scaled, y_test)
            
            # Feature importance
            feature_importance = pd.DataFrame({
                'feature': self.feature_names,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            # Save model
            self.save_model()
            self.is_trained = True
            
            result = {
                'success': True,
                'train_accuracy': train_score,
                'test_accuracy': test_score,
                'samples': len(X),
                'features': len(self.feature_names),
                'positive_samples': y.sum(),
                'positive_ratio': y.mean(),
                'top_features': feature_importance.head(10).to_dict('records')
            }
            
            logger.info(f"✅ Model trained successfully!")
            logger.info(f"   📊 Accuracy: {test_score:.3f}")
            logger.info(f"   📈 Samples: {len(X):,}")
            logger.info(f"   ⭐ Top features: {feature_importance.head(3)['feature'].tolist()}")
            
            return result
            
        except Exception as e:
            logger.error(f"Błąd trenowania modelu: {e}")
            return {'error': str(e)}
    
    def predict_current_market(self, tickers: List[str]) -> Dict[str, Any]:
        """Przewiduje czy obecnie są warunki do wejścia na rynek"""
        try:
            if not self.is_trained or self.model is None or self.scaler is None:
                return {'error': 'Model not trained'}
            
            # Get recent market data (last 2 days for context)
            df = self.get_market_data(tickers, days_back=2)
            
            if len(df) == 0:
                return {'error': 'No recent market data'}
            
            # Create features
            features_df = self.create_market_features(df)
            
            if len(features_df) == 0:
                return {'error': 'Could not create features'}
            
            # Get latest features
            latest_features = features_df[self.feature_names].iloc[-1:].copy()
            
            # Handle missing features
            for feature in self.feature_names:
                if feature not in latest_features.columns:
                    latest_features[feature] = 0
            
            latest_features = latest_features[self.feature_names]
            
            # Scale and predict
            latest_scaled = self.scaler.transform(latest_features)
            prediction = self.model.predict(latest_scaled)[0]
            probability = self.model.predict_proba(latest_scaled)[0]
            
            # Get current market status
            latest_row = features_df.iloc[-1]
            
            result = {
                'prediction': int(prediction),
                'probability_buy': float(probability[1]) if len(probability) > 1 else 0.0,
                'recommendation': 'BUY' if prediction == 1 and probability[1] > 0.6 else 'WAIT',
                'market_status': {
                    'avg_price': float(latest_row.get('market_avg_price', 0)),
                    'price_change_1h': float(latest_row.get('market_price_change_1h', 0)),
                    'stocks_falling_pct_1h': float(latest_row.get('stocks_falling_pct_1h', 0)),
                    'market_rsi': float(latest_row.get('market_rsi', 50)),
                    'oversold_simple': int(latest_row.get('oversold_simple', 0))
                },
                'timestamp': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Błąd predykcji: {e}")
            return {'error': str(e)}
    
    def save_model(self):
        """Save trained model"""
        try:
            if self.model is not None:
                model_data = {
                    'model': self.model,
                    'scaler': self.scaler,
                    'feature_names': self.feature_names,
                    'is_trained': True,
                    'timestamp': datetime.now().isoformat()
                }
                
                with open(self.model_path, 'wb') as f:
                    pickle.dump(model_data, f)
                
                logger.info(f"✓ Model saved to {self.model_path}")
                
        except Exception as e:
            logger.error(f"Error saving model: {e}")
    
    def load_model(self):
        """Load saved model"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    model_data = pickle.load(f)
                
                self.model = model_data.get('model')
                self.scaler = model_data.get('scaler')
                self.feature_names = model_data.get('feature_names', [])
                self.is_trained = model_data.get('is_trained', False)
                
                logger.info(f"✓ Model loaded from {self.model_path}")
                
        except Exception as e:
            logger.warning(f"Could not load model: {e}")


def main():
    """Test funkcja"""
    print("=== MARKET PATTERN ML TEST ===")
    
    ml = MarketPatternML()
    
    # Test data preparation
    test_tickers = ['CDR', 'PKN', 'PKO', 'CCC', 'ALE']
    
    print(f"\n1. Testing data preparation for {test_tickers}...")
    X, y = ml.prepare_training_data(test_tickers, days_back=10)
    
    if len(X) > 0:
        print(f"✅ Data prepared: {X.shape[0]} samples, {X.shape[1]} features")
        print(f"   Features: {list(X.columns)[:5]}...")
        print(f"   Labels: {y.value_counts().to_dict()}")
        
        # Test training
        print(f"\n2. Testing model training...")
        result = ml.train_model(test_tickers, days_back=10)
        
        if 'success' in result:
            print(f"✅ Model trained: {result['test_accuracy']:.3f} accuracy")
            
            # Test prediction
            print(f"\n3. Testing prediction...")
            pred_result = ml.predict_current_market(test_tickers)
            
            if 'prediction' in pred_result:
                print(f"✅ Prediction: {pred_result['recommendation']}")
                print(f"   Probability: {pred_result['probability_buy']:.3f}")
            else:
                print(f"❌ Prediction failed: {pred_result.get('error')}")
        else:
            print(f"❌ Training failed: {result.get('error')}")
    else:
        print("❌ No data prepared")


if __name__ == "__main__":
    main()
