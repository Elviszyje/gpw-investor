#!/usr/bin/env python3
"""
Integracja ML z silnikiem rekomendacji intraday
Łączy predykcje ML z regułami technicznymi
Autor: GPW Investor System
Data: 2025-06-25
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MLIntegratedEngine:
    """Silnik rekomendacji z integracją ML i reguł technicznych"""
    
    def __init__(self, rules_config_path: Optional[str] = None, ml_model_path: Optional[str] = None):
        """
        Inicjalizacja zintegrowanego silnika
        
        Args:
            rules_config_path: Ścieżka do konfiguracji reguł
            ml_model_path: Ścieżka do modelu ML
        """
        # Importuj komponenty
        from workers.intraday_recommendation_engine import IntradayRecommendationEngine
        
        self.traditional_engine = IntradayRecommendationEngine(rules_config_path)
        self.ml_model = None
        self.ml_available = False
        
        # Spróbuj załadować model ML
        try:
            from workers.ml_intraday_model import IntradayMLModel
            
            model_path = ml_model_path or "models/intraday_ml_model.pkl"
            self.ml_model = IntradayMLModel(model_path)
            
            if self.ml_model.is_trained:
                self.ml_available = True
                logger.info("✓ Model ML załadowany i gotowy")
            else:
                logger.warning("⚠️ Model ML nie jest wytrenowany")
        except Exception as e:
            logger.warning(f"⚠️ Nie można załadować modelu ML: {e}")
        
        # Konfiguracja wag dla różnych źródeł sygnałów
        self.weights = {
            'traditional_rules': 0.6,  # 60% waga dla reguł tradycyjnych
            'ml_predictions': 0.4,     # 40% waga dla predykcji ML
            'news_impact': 0.1         # Dodatkowy wpływ newsów
        }
        
        logger.info("✓ ML Integrated Engine zainicjalizowany")
    
    def analyze_ticker_integrated(self, ticker: str, entry_price: Optional[float] = None, 
                                entry_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Główna metoda analizy łącząca reguły tradycyjne z ML
        
        Args:
            ticker: Symbol spółki
            entry_price: Cena wejścia (jeśli mamy pozycję)
            entry_time: Czas wejścia (jeśli mamy pozycję)
            
        Returns:
            Zintegrowane wyniki analizy
        """
        logger.info(f"🤖 Zintegrowana analiza dla {ticker}")
        
        try:
            # 1. Analiza tradycyjna (reguły techniczne)
            traditional_result = self.traditional_engine.analyze_ticker_intraday(
                ticker, entry_price, entry_time
            )
            
            if 'error' in traditional_result:
                logger.warning(f"⚠️ Błąd analizy tradycyjnej: {traditional_result['error']}")
                return traditional_result
            
            # 2. Analiza ML (jeśli dostępna)
            ml_result = None
            if self.ml_available:
                try:
                    date = datetime.now().strftime('%Y-%m-%d')
                    ml_result = self.ml_model.predict_single_ticker(ticker, date)
                    
                    if 'error' in ml_result:
                        logger.warning(f"⚠️ Błąd predykcji ML: {ml_result['error']}")
                        ml_result = None
                    else:
                        logger.info(f"✓ Predykcja ML dla {ticker}: {ml_result.get('buy_signals', 0)} sygnałów BUY")
                
                except Exception as e:
                    logger.warning(f"⚠️ Błąd ML dla {ticker}: {e}")
                    ml_result = None
            
            # 3. Integracja wyników
            integrated_result = self._integrate_analyses(traditional_result, ml_result, ticker)
            
            # 4. Dodaj metadane
            integrated_result['analysis_components'] = {
                'traditional_available': True,
                'ml_available': ml_result is not None,
                'integration_weights': self.weights.copy()
            }
            
            integrated_result['timestamp'] = datetime.now().isoformat()
            
            logger.info(f"✅ Zintegrowana analiza zakończona: {ticker} -> {integrated_result.get('final_recommendation')}")
            
            return integrated_result
            
        except Exception as e:
            logger.error(f"❌ Błąd zintegrowanej analizy {ticker}: {e}")
            return {
                'ticker': ticker,
                'error': f"Błąd zintegrowanej analizy: {str(e)}",
                'recommendation': 'SKIP',
                'timestamp': datetime.now().isoformat()
            }
    
    def _integrate_analyses(self, traditional_result: Dict, ml_result: Optional[Dict], 
                          ticker: str) -> Dict[str, Any]:
        """
        Integruje wyniki analizy tradycyjnej z predykcjami ML
        
        Args:
            traditional_result: Wyniki analizy tradycyjnej
            ml_result: Wyniki predykcji ML (może być None)
            ticker: Symbol spółki
            
        Returns:
            Zintegrowane wyniki
        """
        # Rozpocznij od wyników tradycyjnych
        integrated = traditional_result.copy()
        
        # Pobierz bazowe pewności
        traditional_buy_confidence = traditional_result.get('buy_analysis', {}).get('total_confidence', 0)
        traditional_sell_confidence = traditional_result.get('sell_analysis', {}).get('total_confidence', 0)
        traditional_recommendation = traditional_result.get('final_recommendation', 'WAIT')
        
        # Jeśli brak ML, użyj tylko tradycyjnych
        if ml_result is None:
            integrated['integration_method'] = 'traditional_only'
            integrated['ml_component'] = {'available': False, 'reason': 'ML not available'}
            return integrated
        
        # Pobierz wyniki ML
        ml_predictions = ml_result.get('detailed_predictions', [])
        ml_buy_signals = ml_result.get('buy_signals', 0)
        ml_total_predictions = ml_result.get('total_predictions', 1)
        
        # Oblicz średnią pewność ML dla sygnałów BUY
        ml_buy_confidence = 0
        if ml_predictions:
            buy_confidences = [pred['confidence'] for pred in ml_predictions if pred['prediction'] == 1]
            ml_buy_confidence = sum(buy_confidences) / len(buy_confidences) if buy_confidences else 0
            ml_buy_confidence *= 2  # Przeskaluj do zakresu podobnego do tradycyjnego (0-2)
        
        # Oblicz ML recommendation
        ml_buy_ratio = ml_buy_signals / ml_total_predictions if ml_total_predictions > 0 else 0
        
        if ml_buy_ratio > 0.6 and ml_buy_confidence > 0.7:
            ml_recommendation = 'BUY'
        elif ml_buy_ratio < 0.3:
            ml_recommendation = 'SELL'
        else:
            ml_recommendation = 'WAIT'
        
        # Integracja z wagami
        integrated_buy_confidence = (
            traditional_buy_confidence * self.weights['traditional_rules'] +
            ml_buy_confidence * self.weights['ml_predictions']
        )
        
        integrated_sell_confidence = (
            traditional_sell_confidence * self.weights['traditional_rules']
            # ML obecnie nie predykcji SELL, więc nie dodajemy
        )
        
        # Określ finalną rekomendację
        final_recommendation = self._determine_final_recommendation(
            traditional_recommendation, ml_recommendation,
            integrated_buy_confidence, integrated_sell_confidence,
            traditional_result.get('has_position', False)
        )
        
        # Aktualizuj wyniki
        integrated['buy_analysis']['total_confidence'] = integrated_buy_confidence
        integrated['sell_analysis']['total_confidence'] = integrated_sell_confidence
        integrated['final_recommendation'] = final_recommendation
        
        # Dodaj komponenty ML
        integrated['ml_component'] = {
            'available': True,
            'ml_recommendation': ml_recommendation,
            'ml_buy_confidence': ml_buy_confidence,
            'ml_buy_signals': ml_buy_signals,
            'ml_total_predictions': ml_total_predictions,
            'ml_buy_ratio': ml_buy_ratio,
            'ml_predictions': ml_predictions[:5]  # Pierwsze 5 predykcji dla debugowania
        }
        
        # Informacje o integracji
        integrated['integration_method'] = 'weighted_combination'
        integrated['confidence_boost'] = {
            'traditional_to_integrated_buy': integrated_buy_confidence - traditional_buy_confidence,
            'traditional_to_integrated_sell': integrated_sell_confidence - traditional_sell_confidence
        }
        
        # Dodaj sygnały ML do analizy kupna
        if ml_buy_confidence > 0:
            ml_signal = {
                'rule': 'ml_prediction',
                'name': 'Predykcja Machine Learning',
                'value': ml_buy_confidence,
                'threshold': 0.5,
                'confidence': ml_buy_confidence,
                'details': f"ML przewiduje {ml_buy_signals}/{ml_total_predictions} sygnałów BUY (pewność: {ml_buy_confidence:.2f})"
            }
            
            if 'signals' not in integrated['buy_analysis']:
                integrated['buy_analysis']['signals'] = []
            integrated['buy_analysis']['signals'].append(ml_signal)
        
        return integrated
    
    def _determine_final_recommendation(self, traditional_rec: str, ml_rec: str,
                                      buy_confidence: float, sell_confidence: float,
                                      has_position: bool) -> str:
        """
        Określa finalną rekomendację na podstawie wszystkich czynników
        
        Args:
            traditional_rec: Rekomendacja tradycyjna
            ml_rec: Rekomendacja ML
            buy_confidence: Zintegrowana pewność kupna
            sell_confidence: Zintegrowana pewność sprzedaży
            has_position: Czy mamy pozycję
            
        Returns:
            Finalna rekomendacja
        """
        # Progi pewności
        min_buy_confidence = 1.2
        min_sell_confidence = 1.0
        
        # Jeśli mamy pozycję, priorytet ma sprzedaż
        if has_position:
            if sell_confidence >= min_sell_confidence:
                return 'SELL'
            elif sell_confidence > 0.5:
                return 'HOLD'
            else:
                return 'HOLD'
        
        # Jeśli nie mamy pozycji
        # Silne zgodne sygnały
        if traditional_rec == 'BUY' and ml_rec == 'BUY' and buy_confidence >= min_buy_confidence:
            return 'BUY'
        
        # Tradycyjny BUY wspierany przez ML
        if traditional_rec == 'BUY' and ml_rec in ['BUY', 'WAIT'] and buy_confidence >= min_buy_confidence:
            return 'BUY'
        
        # ML BUY wspierany przez tradycyjny
        if ml_rec == 'BUY' and traditional_rec in ['BUY', 'WAIT'] and buy_confidence >= min_buy_confidence * 0.8:
            return 'BUY'
        
        # Sygnały sprzedaży
        if sell_confidence >= min_sell_confidence:
            return 'WAIT'  # Nie kupuj gdy są sygnały sprzedaży
        
        # Domyślnie czekaj
        return 'WAIT'
    
    def scan_market_integrated(self, tickers: List[str], max_workers: int = 3) -> List[Dict]:
        """
        Skanuje rynek używając zintegrowanej analizy
        
        Args:
            tickers: Lista symboli spółek
            max_workers: Maksymalna liczba wątków
            
        Returns:
            Lista rekomendacji posortowana według pewności
        """
        import concurrent.futures
        
        logger.info(f"🚀 Zintegrowane skanowanie dla {len(tickers)} spółek")
        
        recommendations = []
        failed_tickers = []
        
        def analyze_single_ticker(ticker: str) -> Optional[Dict]:
            """Analizuj pojedynczą spółkę"""
            try:
                result = self.analyze_ticker_integrated(ticker)
                if "error" not in result:
                    return result
                else:
                    failed_tickers.append((ticker, result.get("error", "Unknown error")))
            except Exception as e:
                failed_tickers.append((ticker, str(e)))
                logger.error(f"❌ Błąd analizy {ticker}: {e}")
            return None
        
        # Przetwarzanie równoległe (zmniejszona liczba wątków dla ML)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(analyze_single_ticker, ticker): ticker 
                for ticker in tickers
            }
            
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    result = future.result()
                    if result:
                        recommendations.append(result)
                        logger.info(f"✓ {ticker}: {result.get('final_recommendation', 'N/A')}")
                except Exception as e:
                    failed_tickers.append((ticker, str(e)))
                    logger.error(f"❌ Błąd wątku dla {ticker}: {e}")
        
        # Sortuj według zintegrowanej pewności
        def sort_key(x):
            recommendation = x.get('final_recommendation', 'WAIT')
            buy_confidence = x.get("buy_analysis", {}).get("total_confidence", 0)
            sell_confidence = x.get("sell_analysis", {}).get("total_confidence", 0)
            
            if recommendation == 'BUY':
                return (3, buy_confidence)
            elif recommendation == 'SELL':
                return (2, sell_confidence)
            else:
                return (1, max(buy_confidence, sell_confidence))
        
        recommendations.sort(key=sort_key, reverse=True)
        
        # Statystyki
        buy_count = sum(1 for r in recommendations if r.get('final_recommendation') == 'BUY')
        sell_count = sum(1 for r in recommendations if r.get('final_recommendation') == 'SELL')
        ml_used_count = sum(1 for r in recommendations if r.get('ml_component', {}).get('available', False))
        
        logger.info(f"✅ Zintegrowane skanowanie zakończone:")
        logger.info(f"   📊 Przeanalizowano: {len(recommendations)}/{len(tickers)} spółek")
        logger.info(f"   🟢 Sygnały BUY: {buy_count}")
        logger.info(f"   🔴 Sygnały SELL: {sell_count}")
        logger.info(f"   🤖 Z ML: {ml_used_count}")
        logger.info(f"   ❌ Błędy: {len(failed_tickers)}")
        
        return recommendations
    
    def get_ml_training_recommendations(self, min_samples: int = 100) -> Dict[str, Any]:
        """
        Dostarcza rekomendacje dotyczące treningu modelu ML
        
        Args:
            min_samples: Minimalna liczba próbek do treningu
            
        Returns:
            Rekomendacje i status
        """
        recommendations = {
            'ml_status': 'not_available' if not self.ml_available else 'available',
            'recommendations': [],
            'required_actions': []
        }
        
        if not self.ml_available:
            recommendations['recommendations'].extend([
                "Model ML nie jest dostępny",
                "Zainstaluj biblioteki: pip install scikit-learn xgboost lightgbm numpy pandas ta",
                "Zbierz dane historyczne (min. 30 dni dla każdej spółki)",
                "Uruchom trening modelu ML"
            ])
            
            recommendations['required_actions'].extend([
                "install_ml_libraries",
                "collect_historical_data",
                "train_initial_model"
            ])
        
        elif self.ml_model and not self.ml_model.is_trained:
            recommendations['recommendations'].extend([
                "Model ML nie jest wytrenowany",
                f"Zbierz minimum {min_samples} próbek danych",
                "Uruchom proces treningu",
                "Wykonaj walidację na danych testowych"
            ])
            
            recommendations['required_actions'].extend([
                "collect_training_data",
                "train_model",
                "validate_model"
            ])
        
        else:
            # Model jest dostępny i wytrenowany
            model_info = self.ml_model.get_model_info()
            
            recommendations['recommendations'].extend([
                f"Model ML aktywny ({model_info.get('model_type', 'unknown')})",
                f"Accuracy: {model_info.get('accuracy', 'unknown')}",
                f"Liczba cech: {model_info.get('feature_count', 'unknown')}",
                "Regularnie aktualizuj model z nowymi danymi"
            ])
            
            recommendations['required_actions'].extend([
                "monitor_model_performance",
                "schedule_retraining"
            ])
            
            # Sprawdź wiek modelu
            trained_date = model_info.get('trained_date')
            if trained_date:
                try:
                    trained_dt = datetime.fromisoformat(trained_date.replace('Z', '+00:00'))
                    days_old = (datetime.now() - trained_dt).days
                    
                    if days_old > 30:
                        recommendations['recommendations'].append(
                            f"Model ma {days_old} dni - rozważ ponowny trening"
                        )
                        recommendations['required_actions'].append("retrain_model")
                except:
                    pass
        
        return recommendations
    
    def update_integration_weights(self, traditional_weight: float = 0.6, 
                                 ml_weight: float = 0.4, news_weight: float = 0.1) -> bool:
        """
        Aktualizuje wagi dla różnych komponentów analizy
        
        Args:
            traditional_weight: Waga analizy tradycyjnej
            ml_weight: Waga predykcji ML
            news_weight: Waga wpływu newsów
            
        Returns:
            True jeśli zaktualizowano pomyślnie
        """
        try:
            # Walidacja wag
            total_main_weight = traditional_weight + ml_weight
            if abs(total_main_weight - 1.0) > 0.01:
                logger.warning(f"⚠️ Suma głównych wag ({total_main_weight}) powinna być ~1.0")
            
            self.weights['traditional_rules'] = traditional_weight
            self.weights['ml_predictions'] = ml_weight
            self.weights['news_impact'] = news_weight
            
            logger.info(f"✅ Zaktualizowano wagi integracji: Tradycyjne: {traditional_weight}, ML: {ml_weight}, News: {news_weight}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd aktualizacji wag: {e}")
            return False
    
    def get_integrated_recommendation(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Pobiera zintegrowaną rekomendację dla tickera (wrapper dla API)
        
        Args:
            ticker: Symbol spółki
            
        Returns:
            Rekomendacja lub None w przypadku błędu
        """
        try:
            result = self.analyze_ticker_integrated(ticker)
            
            # Filtruj tylko rekomendacje BUY/SELL
            recommendation = result.get('final_recommendation')
            if recommendation in ['BUY', 'SELL']:
                return {
                    'ticker': ticker,
                    'recommendation': recommendation,
                    'confidence': result.get('buy_analysis', {}).get('total_confidence', 0),
                    'price': result.get('price', 0),
                    'reasons': result.get('buy_analysis', {}).get('reasons', []),
                    'ml_enabled': result.get('analysis_components', {}).get('ml_available', False),
                    'timestamp': result.get('timestamp')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Błąd pobierania rekomendacji dla {ticker}: {e}")
            return None


def main():
    """Funkcja testowa"""
    print("=== ML INTEGRATED ENGINE TEST ===")
    
    # Inicjalizacja
    engine = MLIntegratedEngine()
    
    # Test analizy
    result = engine.analyze_ticker_integrated("CDR")
    print(f"\n=== WYNIK ZINTEGROWANEJ ANALIZY ===")
    print(f"Ticker: {result['ticker']}")
    print(f"Rekomendacja: {result.get('final_recommendation', 'N/A')}")
    print(f"ML dostępne: {result.get('analysis_components', {}).get('ml_available', False)}")
    
    if 'ml_component' in result:
        ml_comp = result['ml_component']
        print(f"ML rekomendacja: {ml_comp.get('ml_recommendation', 'N/A')}")
        print(f"ML sygnały BUY: {ml_comp.get('ml_buy_signals', 0)}/{ml_comp.get('ml_total_predictions', 0)}")
    
    # Test rekomendacji ML
    print(f"\n=== REKOMENDACJE ML ===")
    ml_recommendations = engine.get_ml_training_recommendations()
    print(f"Status ML: {ml_recommendations['ml_status']}")
    for rec in ml_recommendations['recommendations']:
        print(f"- {rec}")
    
    # Test skanowania (mała lista)
    print(f"\n=== TEST SKANOWANIA ===")
    test_tickers = ['CDR', 'PKN']
    scan_results = engine.scan_market_integrated(test_tickers, max_workers=2)
    
    print(f"Wyniki skanowania: {len(scan_results)} spółek")
    for result in scan_results:
        rec = result.get('final_recommendation', 'N/A')
        ml_available = result.get('ml_component', {}).get('available', False)
        print(f"- {result['ticker']}: {rec} (ML: {'✓' if ml_available else '✗'})")
    
    print("\n✅ Test zakończony")


if __name__ == "__main__":
    main()
