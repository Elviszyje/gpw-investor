#!/usr/bin/env python3
"""
Uproszczony model ML dla day tradingu
Test implementacji ML dla GPW
Autor: GPW Investor System
Data: 2025-06-25
"""

import numpy as np
import pandas as pd
import pickle
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.preprocessing import StandardScaler
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

from workers.simple_ml_features import SimpleMLFeatures

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleMLModel:
    """Uproszczony model ML dla testów"""
    
    def __init__(self, model_path: str = "models/simple_ml_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.feature_names = []
        
        # Stwórz katalog models
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Spróbuj załadować model
        self.load_model()
        
        logger.info("✓ Simple ML Model zainicjalizowany")
    
    def train_model(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """
        Trenuje model ML
        
        Args:
            X: Cechy
            y: Etykiety
            
        Returns:
            Wyniki treningu
        """
        try:
            if not ML_AVAILABLE:
                return {'error': 'Biblioteki ML nie są dostępne'}
            
            if len(X) < 5:
                return {'error': 'Za mało danych do treningu'}
            
            logger.info(f"🤖 Rozpoczynam trening modelu: {X.shape[0]} próbek, {X.shape[1]} cech")
            
            # Zapisz nazwy cech
            self.feature_names = list(X.columns)
            
            # Podział danych
            if len(X) > 10:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42, stratify=y if len(y.unique()) > 1 else None
                )
            else:
                # Za mało danych na podział
                X_train, X_test, y_train, y_test = X, X, y, y
            
            # Normalizacja
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Trening modelu
            self.model = RandomForestClassifier(
                n_estimators=50,
                max_depth=10,
                random_state=42,
                min_samples_split=2,
                min_samples_leaf=1
            )
            
            self.model.fit(X_train_scaled, y_train)
            
            # Ewaluacja
            y_pred = self.model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            
            # Zapisz model
            self.is_trained = True
            self.save_model()
            
            results = {
                'success': True,
                'accuracy': accuracy,
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'features_count': len(self.feature_names),
                'feature_importance': dict(zip(self.feature_names, self.model.feature_importances_)),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Trening zakończony: accuracy={accuracy:.3f}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Błąd treningu: {e}")
            return {'error': str(e)}
    
    def predict_intraday(self, ticker: str, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Predykcja dla tickera
        
        Args:
            ticker: Symbol spółki
            date: Data (domyślnie dzisiaj)
            
        Returns:
            Wyniki predykcji
        """
        try:
            if not self.is_trained:
                return {'error': 'Model nie został wytrenowany'}
            
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            # Pobierz cechy
            features_engine = SimpleMLFeatures()
            features = features_engine.create_simple_features(ticker, date)
            
            if features is None or len(features) == 0:
                return {'error': f'Brak danych dla {ticker} na {date}'}
            
            # Przygotuj dane
            feature_cols = [col for col in features.columns if col not in ['ticker', 'datetime', 'price']]
            X = features[feature_cols]
            
            # Sprawdź zgodność cech
            if list(X.columns) != self.feature_names:
                logger.warning("⚠️ Niezgodność cech, próbuję dopasować...")
                # Spróbuj dopasować cechy
                missing_cols = set(self.feature_names) - set(X.columns)
                extra_cols = set(X.columns) - set(self.feature_names)
                
                if missing_cols:
                    for col in missing_cols:
                        X[col] = 0
                
                X = X[self.feature_names]  # Uporządkuj kolumny
            
            # Normalizacja i predykcja
            X_scaled = self.scaler.transform(X)
            predictions = self.model.predict(X_scaled)
            probabilities = self.model.predict_proba(X_scaled)
            
            # Analiza wyników
            buy_signals = sum(predictions)
            total_predictions = len(predictions)
            buy_ratio = buy_signals / total_predictions if total_predictions > 0 else 0
            
            # Średnia pewność dla sygnałów BUY
            if probabilities.shape[1] > 1:
                buy_confidences = [probabilities[i][1] for i in range(len(predictions)) if predictions[i] == 1]
                avg_confidence = sum(buy_confidences) / len(buy_confidences) if buy_confidences else 0
            else:
                avg_confidence = 0
            
            # Rekomendacja
            if buy_ratio > 0.6 and avg_confidence > 0.6:
                recommendation = 'BUY'
            elif buy_ratio < 0.3:
                recommendation = 'SELL'
            else:
                recommendation = 'WAIT'
            
            return {
                'ticker': ticker,
                'date': date,
                'buy_signals': int(buy_signals),
                'total_predictions': int(total_predictions),
                'buy_ratio': buy_ratio,
                'average_confidence': avg_confidence,
                'recommendation': recommendation,
                'predictions': predictions.tolist(),
                'probabilities': probabilities.tolist(),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Błąd predykcji dla {ticker}: {e}")
            return {'error': str(e)}
    
    def save_model(self) -> bool:
        """Zapisuje model"""
        try:
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'is_trained': self.is_trained,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(self.model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"✅ Model zapisany: {self.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd zapisu modelu: {e}")
            return False
    
    def load_model(self) -> bool:
        """Ładuje model"""
        try:
            if not os.path.exists(self.model_path):
                logger.info("ℹ️ Brak zapisanego modelu")
                return False
            
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']
            self.is_trained = model_data['is_trained']
            
            logger.info(f"✅ Model załadowany: {self.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd ładowania modelu: {e}")
            return False
    
    def evaluate_on_backtest(self, tickers: List[str], start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Backtest modelu
        
        Args:
            tickers: Lista tickerów
            start_date: Data początkowa
            end_date: Data końcowa
            
        Returns:
            Wyniki backtestingu
        """
        try:
            if not self.is_trained:
                return {'error': 'Model nie został wytrenowany'}
            
            results = []
            
            for ticker in tickers:
                pred_result = self.predict_intraday(ticker, start_date)
                if 'error' not in pred_result:
                    results.append(pred_result)
            
            if not results:
                return {'error': 'Brak wyników do backtestingu'}
            
            # Statystyki
            total_predictions = sum(r['total_predictions'] for r in results)
            total_buy_signals = sum(r['buy_signals'] for r in results)
            avg_confidence = sum(r['average_confidence'] for r in results) / len(results)
            
            return {
                'tickers': tickers,
                'start_date': start_date,
                'end_date': end_date,
                'total_predictions': total_predictions,
                'total_buy_signals': total_buy_signals,
                'buy_ratio': total_buy_signals / total_predictions if total_predictions > 0 else 0,
                'average_confidence': avg_confidence,
                'individual_results': results,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Błąd backtestingu: {e}")
            return {'error': str(e)}


def test_simple_model():
    """Test modelu"""
    print("=== TEST SIMPLE ML MODEL ===")
    
    # Test danych
    features_engine = SimpleMLFeatures()
    X, y = features_engine.prepare_training_data(['CDR', 'PKN', 'CCC'], ['2025-06-24'])
    
    if len(X) == 0:
        print("❌ Brak danych treningowych")
        return
    
    print(f"📊 Dane treningowe: {X.shape}")
    
    # Test modelu
    model = SimpleMLModel()
    
    # Trening
    train_results = model.train_model(X, y)
    print(f"🤖 Trening: {train_results}")
    
    # Predykcja
    if model.is_trained:
        pred_results = model.predict_intraday('CDR', '2025-06-24')
        print(f"🔮 Predykcja CDR: {pred_results}")
        
        # Backtest
        backtest_results = model.evaluate_on_backtest(['CDR', 'PKN'], '2025-06-24', '2025-06-24')
        print(f"📈 Backtest: {backtest_results}")


if __name__ == "__main__":
    test_simple_model()
