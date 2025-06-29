#!/usr/bin/env python3
"""
Model Machine Learning dla intraday trading
Predykcja sygnałów BUY/SELL na podstawie cech technicznych
Autor: GPW Investor System
Data: 2025-06-25
"""

import numpy as np
import pandas as pd
import pickle
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import sqlite3
import json

# ML libraries będą instalowane później
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
    from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
    from sklearn.preprocessing import StandardScaler
    import xgboost as xgb
    import lightgbm as lgb
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("⚠️ Biblioteki ML nie są dostępne. Uruchom: pip install scikit-learn xgboost lightgbm")

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntradayMLModel:
    """Model ML do predykcji sygnałów intraday trading"""
    
    def __init__(self, model_path: str = "models/intraday_ml_model.pkl"):
        """
        Inicjalizacja modelu ML
        
        Args:
            model_path: Ścieżka do zapisanego modelu
        """
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.feature_names = []
        self.is_trained = False
        self.model_metadata = {}
        
        # Stwórz katalog models jeśli nie istnieje
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Spróbuj załadować istniejący model
        self.load_model()
        
        logger.info("✓ Intraday ML Model zainicjalizowany")
    
    def predict_intraday(self, ticker: str, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Predykcja dla tickera (wrapper dla API)
        
        Args:
            ticker: Symbol spółki
            date: Data (domyślnie dzisiaj)
            
        Returns:
            Wynik predykcji
        """
        try:
            if not self.is_trained:
                return {
                    'error': 'Model nie został jeszcze wytrenowany'
                }
            
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            # Wygeneruj cechy dla tickera
            from workers.ml_feature_engineering import MLFeatureEngineer
            engineer = MLFeatureEngineer()
            
            features = engineer.create_intraday_features(ticker, date)
            
            if features is None or len(features) == 0:
                return {
                    'error': f'Brak danych dla {ticker} na {date}'
                }
            
            # Przygotuj dane do predykcji
            X = features[self.feature_names] if all(col in features.columns for col in self.feature_names) else features
            
            # Normalizuj
            if self.scaler:
                X_scaled = self.scaler.transform(X)
            else:
                X_scaled = X
            
            # Predykcja
            predictions = self.model.predict(X_scaled)
            probabilities = self.model.predict_proba(X_scaled)
            
            # Analiza wyników
            buy_signals = sum(predictions)
            total_predictions = len(predictions)
            avg_confidence = probabilities[:, 1].mean() if len(probabilities.shape) > 1 else 0
            
            return {
                'ticker': ticker,
                'date': date,
                'buy_signals': int(buy_signals),
                'total_predictions': int(total_predictions),
                'buy_ratio': buy_signals / total_predictions if total_predictions > 0 else 0,
                'average_confidence': float(avg_confidence),
                'recommendation': 'BUY' if buy_signals / total_predictions > 0.6 else 'WAIT',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Błąd predykcji dla {ticker}: {e}")
            return {
                'error': f'Błąd predykcji: {str(e)}'
            }
    
    def prepare_training_data(self, tickers: List[str], start_date: str, end_date: str, 
                            min_samples_per_ticker: int = 50) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Przygotowuje dane treningowe używając feature engineering
        
        Args:
            tickers: Lista symboli spółek
            start_date: Data początkowa
            end_date: Data końcowa
            min_samples_per_ticker: Minimalna liczba próbek na ticker
            
        Returns:
            Tuple (features, labels)
        """
        try:
            # Importuj feature engineer (będzie dostępny lokalnie)
            from workers.ml_feature_engineering import MLFeatureEngineer
            
            engineer = MLFeatureEngineer()
            X, y = engineer.prepare_training_data(tickers, start_date, end_date)
            
            if len(X) == 0:
                logger.error("❌ Brak danych treningowych")
                return pd.DataFrame(), pd.Series()
            
            # Filtruj tickers z za małą liczbą próbek
            if 'ticker_encoded' in X.columns:
                ticker_counts = X['ticker_encoded'].value_counts()
                valid_tickers = ticker_counts[ticker_counts >= min_samples_per_ticker].index
                valid_mask = X['ticker_encoded'].isin(valid_tickers)
                X = X[valid_mask]
                y = y[valid_mask]
            
            # Zapisz nazwy cech
            self.feature_names = list(X.columns)
            
            logger.info(f"✅ Przygotowano dane treningowe: {X.shape[0]} próbek, {X.shape[1]} cech")
            logger.info(f"   📊 Rozkład klas: {dict(y.value_counts())}")
            
            return X, y
            
        except Exception as e:
            logger.error(f"❌ Błąd przygotowania danych treningowych: {e}")
            return pd.DataFrame(), pd.Series()
    
    def train_model(self, X: pd.DataFrame, y: pd.Series, model_type: str = 'xgboost') -> Dict[str, Any]:
        """
        Trenuje model ML
        
        Args:
            X: Cechy
            y: Etykiety
            model_type: Typ modelu ('xgboost', 'lightgbm', 'random_forest', 'gradient_boosting')
            
        Returns:
            Słownik z wynikami treningu
        """
        if not ML_AVAILABLE:
            logger.error("❌ Biblioteki ML nie są dostępne")
            return {'error': 'ML libraries not available'}
        
        try:
            # Podział na train/test
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Skalowanie cech
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Wybór modelu
            if model_type == 'xgboost':
                self.model = xgb.XGBClassifier(
                    n_estimators=200,
                    max_depth=6,
                    learning_rate=0.1,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    eval_metric='logloss'
                )
            elif model_type == 'lightgbm':
                self.model = lgb.LGBMClassifier(
                    n_estimators=200,
                    max_depth=6,
                    learning_rate=0.1,
                    feature_fraction=0.8,
                    bagging_fraction=0.8,
                    random_state=42
                )
            elif model_type == 'random_forest':
                self.model = RandomForestClassifier(
                    n_estimators=200,
                    max_depth=10,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=42
                )
            elif model_type == 'gradient_boosting':
                self.model = GradientBoostingClassifier(
                    n_estimators=200,
                    max_depth=6,
                    learning_rate=0.1,
                    subsample=0.8,
                    random_state=42
                )
            else:
                raise ValueError(f"Nieznany typ modelu: {model_type}")
            
            # Trenowanie
            logger.info(f"🚀 Rozpoczynam trening modelu {model_type}...")
            
            if model_type in ['xgboost', 'lightgbm']:
                # Dla gradient boosting używamy oryginalnych danych
                self.model.fit(X_train, y_train)
                y_pred = self.model.predict(X_test)
                y_pred_proba = self.model.predict_proba(X_test)[:, 1]
            else:
                # Dla innych modeli używamy skalowanych danych
                self.model.fit(X_train_scaled, y_train)
                y_pred = self.model.predict(X_test_scaled)
                y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]
            
            # Ewaluacja
            accuracy = accuracy_score(y_test, y_pred)
            classification_rep = classification_report(y_test, y_pred, output_dict=True)
            
            # Cross-validation
            if model_type in ['xgboost', 'lightgbm']:
                cv_scores = cross_val_score(self.model, X_train, y_train, cv=5)
            else:
                cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5)
            
            # Feature importance
            if hasattr(self.model, 'feature_importances_'):
                feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
                top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
            else:
                top_features = []
            
            # Przygotuj wyniki
            results = {
                'model_type': model_type,
                'accuracy': accuracy,
                'cv_mean': cv_scores.mean(),
                'cv_std': cv_scores.std(),
                'classification_report': classification_rep,
                'top_features': top_features,
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'feature_count': len(self.feature_names)
            }
            
            # Zapisz metadata
            self.model_metadata = {
                'model_type': model_type,
                'trained_date': datetime.now().isoformat(),
                'accuracy': accuracy,
                'cv_score': cv_scores.mean(),
                'features_count': len(self.feature_names),
                'train_samples': len(X_train)
            }
            
            self.is_trained = True
            logger.info(f"✅ Model wytrenowany: {model_type}")
            logger.info(f"   📊 Accuracy: {accuracy:.3f}")
            logger.info(f"   📊 CV Score: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Błąd treningu modelu: {e}")
            return {'error': str(e)}
    
    def predict(self, features: pd.DataFrame) -> Dict[str, Any]:
        """
        Wykonuje predykcję dla nowych danych
        
        Args:
            features: DataFrame z cechami
            
        Returns:
            Słownik z predykcjami
        """
        if not self.is_trained or self.model is None:
            return {'error': 'Model nie jest wytrenowany'}
        
        try:
            # Upewnij się, że mamy wszystkie wymagane cechy
            missing_features = set(self.feature_names) - set(features.columns)
            if missing_features:
                logger.warning(f"⚠️ Brakujące cechy: {missing_features}")
                # Dodaj brakujące cechy z wartościami 0
                for feature in missing_features:
                    features[feature] = 0
            
            # Uporządkuj cechy w odpowiedniej kolejności
            features_ordered = features[self.feature_names]
            
            # Skalowanie
            if self.scaler is not None:
                features_scaled = self.scaler.transform(features_ordered)
                predictions = self.model.predict(features_scaled)
                probabilities = self.model.predict_proba(features_scaled)
            else:
                predictions = self.model.predict(features_ordered)
                probabilities = self.model.predict_proba(features_ordered)
            
            # Przygotuj wyniki
            results = {
                'predictions': predictions.tolist(),
                'probabilities': probabilities.tolist(),
                'buy_signals': (predictions == 1).sum(),
                'total_predictions': len(predictions),
                'timestamp': datetime.now().isoformat()
            }
            
            # Dodaj szczegółowe predykcje
            detailed_predictions = []
            for i, (pred, prob) in enumerate(zip(predictions, probabilities)):
                detailed_predictions.append({
                    'index': i,
                    'prediction': int(pred),
                    'confidence': float(prob[1]),  # Prawdopodobieństwo klasy BUY
                    'signal': 'BUY' if pred == 1 else 'HOLD'
                })
            
            results['detailed_predictions'] = detailed_predictions
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Błąd predykcji: {e}")
            return {'error': str(e)}
    
    def predict_single_ticker(self, ticker: str, date: str = None) -> Dict[str, Any]:
        """
        Wykonuje predykcję dla pojedynczej spółki
        
        Args:
            ticker: Symbol spółki
            date: Data (domyślnie dzisiaj)
            
        Returns:
            Słownik z predykcją
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # Pobierz cechy
            from workers.ml_feature_engineering import MLFeatureEngineer
            
            engineer = MLFeatureEngineer()
            features_df = engineer.create_intraday_features(ticker, date)
            
            if features_df is None or len(features_df) == 0:
                return {'error': f'Brak danych dla {ticker} na {date}'}
            
            # Wykonaj predykcję
            prediction_results = self.predict(features_df)
            
            if 'error' in prediction_results:
                return prediction_results
            
            # Dodaj informacje o ticker i dacie
            prediction_results['ticker'] = ticker
            prediction_results['date'] = date
            prediction_results['current_price'] = features_df['close'].iloc[-1] if 'close' in features_df.columns else None
            
            return prediction_results
            
        except Exception as e:
            logger.error(f"❌ Błąd predykcji dla {ticker}: {e}")
            return {'error': str(e)}
    
    def save_model(self, filepath: str = None) -> bool:
        """
        Zapisuje wytrenowany model do pliku
        
        Args:
            filepath: Ścieżka do pliku (domyślnie self.model_path)
            
        Returns:
            True jeśli zapisano pomyślnie
        """
        if not self.is_trained:
            logger.warning("⚠️ Model nie jest wytrenowany")
            return False
        
        try:
            filepath = filepath or self.model_path
            
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'metadata': self.model_metadata
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"✅ Model zapisany: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd zapisu modelu: {e}")
            return False
    
    def load_model(self, filepath: str = None) -> bool:
        """
        Ładuje model z pliku
        
        Args:
            filepath: Ścieżka do pliku (domyślnie self.model_path)
            
        Returns:
            True jeśli załadowano pomyślnie
        """
        try:
            filepath = filepath or self.model_path
            
            if not os.path.exists(filepath):
                logger.info("ℹ️ Brak zapisanego modelu")
                return False
            
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']
            self.model_metadata = model_data.get('metadata', {})
            self.is_trained = True
            
            logger.info(f"✅ Model załadowany: {filepath}")
            logger.info(f"   📊 Typ: {self.model_metadata.get('model_type', 'unknown')}")
            logger.info(f"   📊 Accuracy: {self.model_metadata.get('accuracy', 'unknown')}")
            logger.info(f"   📊 Cech: {len(self.feature_names)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd ładowania modelu: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Zwraca informacje o modelu
        
        Returns:
            Słownik z informacjami o modelu
        """
        info = {
            'is_trained': self.is_trained,
            'model_path': self.model_path,
            'feature_count': len(self.feature_names),
            'ml_available': ML_AVAILABLE
        }
        
        if self.is_trained:
            info.update(self.model_metadata)
            info['model_type_actual'] = type(self.model).__name__ if self.model else 'Unknown'
        
        return info
    
    def hyperparameter_tuning(self, X: pd.DataFrame, y: pd.Series, model_type: str = 'xgboost') -> Dict[str, Any]:
        """
        Optymalizuje hiperparametry modelu
        
        Args:
            X: Cechy treningowe
            y: Etykiety
            model_type: Typ modelu do optymalizacji
            
        Returns:
            Najlepsze parametry i wyniki
        """
        if not ML_AVAILABLE:
            return {'error': 'ML libraries not available'}
        
        try:
            # Definicje siatek parametrów
            param_grids = {
                'xgboost': {
                    'n_estimators': [100, 200],
                    'max_depth': [4, 6, 8],
                    'learning_rate': [0.05, 0.1, 0.2],
                    'subsample': [0.8, 0.9],
                    'colsample_bytree': [0.8, 0.9]
                },
                'lightgbm': {
                    'n_estimators': [100, 200],
                    'max_depth': [4, 6, 8],
                    'learning_rate': [0.05, 0.1, 0.2],
                    'feature_fraction': [0.8, 0.9],
                    'bagging_fraction': [0.8, 0.9]
                },
                'random_forest': {
                    'n_estimators': [100, 200],
                    'max_depth': [8, 10, 12],
                    'min_samples_split': [2, 5],
                    'min_samples_leaf': [1, 2]
                }
            }
            
            if model_type not in param_grids:
                return {'error': f'Brak siatki parametrów dla {model_type}'}
            
            # Stwórz model
            if model_type == 'xgboost':
                base_model = xgb.XGBClassifier(random_state=42, eval_metric='logloss')
            elif model_type == 'lightgbm':
                base_model = lgb.LGBMClassifier(random_state=42)
            elif model_type == 'random_forest':
                base_model = RandomForestClassifier(random_state=42)
            
            # Grid search
            logger.info(f"🔍 Rozpoczynam optymalizację parametrów dla {model_type}...")
            
            grid_search = GridSearchCV(
                base_model,
                param_grids[model_type],
                cv=3,  # Zmniejszone CV dla szybszego działania
                scoring='accuracy',
                n_jobs=-1,
                verbose=0
            )
            
            # Przygotuj dane (skalowanie dla RF)
            if model_type == 'random_forest':
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
                grid_search.fit(X_scaled, y)
            else:
                grid_search.fit(X, y)
            
            results = {
                'best_params': grid_search.best_params_,
                'best_score': grid_search.best_score_,
                'best_model': grid_search.best_estimator_,
                'cv_results': grid_search.cv_results_
            }
            
            logger.info(f"✅ Optymalizacja zakończona")
            logger.info(f"   📊 Najlepszy wynik: {grid_search.best_score_:.3f}")
            logger.info(f"   📊 Najlepsze parametry: {grid_search.best_params_}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Błąd optymalizacji parametrów: {e}")
            return {'error': str(e)}
    
    def evaluate_on_backtest(self, tickers: List[str], start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Ewaluuje model na danych historycznych (backtest)
        
        Args:
            tickers: Lista tickerów do testowania
            start_date: Data początkowa
            end_date: Data końcowa
            
        Returns:
            Wyniki backtestingu
        """
        if not self.is_trained:
            return {'error': 'Model nie jest wytrenowany'}
        
        try:
            # Przygotuj dane testowe
            test_X, test_y = self.prepare_training_data(tickers, start_date, end_date)
            
            if len(test_X) == 0:
                return {'error': 'Brak danych testowych'}
            
            # Wykonaj predykcje
            predictions = self.predict(test_X)
            
            if 'error' in predictions:
                return predictions
            
            # Oblicz metryki
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
            
            pred_labels = predictions['predictions']
            accuracy = accuracy_score(test_y, pred_labels)
            precision = precision_score(test_y, pred_labels, average='weighted')
            recall = recall_score(test_y, pred_labels, average='weighted')
            f1 = f1_score(test_y, pred_labels, average='weighted')
            
            # Symulacja tradingu
            trading_results = self._simulate_trading(predictions, test_X, test_y)
            
            results = {
                'backtest_period': f"{start_date} to {end_date}",
                'test_samples': len(test_X),
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'trading_simulation': trading_results,
                'signal_distribution': {
                    'buy_signals': sum(pred_labels),
                    'hold_signals': len(pred_labels) - sum(pred_labels)
                }
            }
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Błąd backtestingu: {e}")
            return {'error': str(e)}
    
    def _simulate_trading(self, predictions: Dict, features: pd.DataFrame, actual_labels: pd.Series) -> Dict[str, Any]:
        """
        Symuluje trading na podstawie predykcji
        
        Args:
            predictions: Predykcje modelu
            features: Cechy
            actual_labels: Rzeczywiste etykiety
            
        Returns:
            Wyniki symulacji
        """
        try:
            buy_signals = predictions['predictions']
            confidences = [pred['confidence'] for pred in predictions['detailed_predictions']]
            
            # Symulacja prostej strategii
            total_trades = sum(buy_signals)
            successful_trades = sum([buy_signals[i] == 1 and actual_labels.iloc[i] == 1 for i in range(len(buy_signals))])
            
            win_rate = successful_trades / total_trades if total_trades > 0 else 0
            
            # Oszacowany P&L (zakładając 2% zysk przy sukcesie, -1% strata przy porażce)
            estimated_pnl = 0
            for i, signal in enumerate(buy_signals):
                if signal == 1:  # BUY signal
                    if actual_labels.iloc[i] == 1:  # Successful prediction
                        estimated_pnl += 2.0  # 2% profit
                    else:  # Failed prediction
                        estimated_pnl -= 1.0  # 1% loss
            
            return {
                'total_trades': total_trades,
                'successful_trades': successful_trades,
                'win_rate': win_rate,
                'estimated_pnl_percent': estimated_pnl,
                'avg_confidence': np.mean(confidences) if confidences else 0
            }
            
        except Exception as e:
            logger.warning(f"Błąd symulacji tradingu: {e}")
            return {'error': str(e)}


def main():
    """Funkcja testowa i demonstracyjna"""
    print("=== INTRADAY ML MODEL TEST ===")
    
    # Inicjalizacja
    ml_model = IntradayMLModel()
    
    # Informacje o modelu
    info = ml_model.get_model_info()
    print(f"Model info: {info}")
    
    if not ML_AVAILABLE:
        print("❌ Biblioteki ML nie są dostępne")
        print("Zainstaluj: pip install scikit-learn xgboost lightgbm numpy pandas")
        return
    
    # Test przygotowania danych (jeśli są dostępne)
    print("\n=== TEST PRZYGOTOWANIA DANYCH ===")
    test_tickers = ['CDR', 'PKN']
    start_date = '2025-06-20'
    end_date = '2025-06-24'
    
    X, y = ml_model.prepare_training_data(test_tickers, start_date, end_date)
    
    if len(X) > 0:
        print(f"✅ Dane treningowe: {X.shape}")
        print(f"   Rozkład klas: {dict(y.value_counts())}")
        
        # Test treningu modelu
        print("\n=== TEST TRENINGU MODELU ===")
        results = ml_model.train_model(X, y, model_type='random_forest')
        
        if 'error' not in results:
            print(f"✅ Model wytrenowany")
            print(f"   Accuracy: {results['accuracy']:.3f}")
            print(f"   CV Score: {results['cv_mean']:.3f}")
            
            # Test zapisu/ładowania
            print("\n=== TEST ZAPISU/ŁADOWANIA ===")
            if ml_model.save_model():
                print("✅ Model zapisany")
                
                # Stwórz nowy obiekt i załaduj
                new_model = IntradayMLModel()
                if new_model.load_model():
                    print("✅ Model załadowany")
                else:
                    print("❌ Błąd ładowania")
            
            # Test predykcji
            print("\n=== TEST PREDYKCJI ===")
            prediction = ml_model.predict_single_ticker('CDR', '2025-06-24')
            print(f"Predykcja dla CDR: {prediction}")
            
        else:
            print(f"❌ Błąd treningu: {results['error']}")
    
    else:
        print("❌ Brak danych treningowych")
    
    print("\n✅ Test zakończony")


if __name__ == "__main__":
    main()
