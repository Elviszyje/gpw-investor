#!/usr/bin/env python3
"""
System reguł rekomendacyjnych dla GPW Investor
Zawiera konfigurowalne kryteria sygnałów kupna i sprzedaży
Autor: GPW Investor System
Data: 2025-06-24
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging

# Dodaj ścieżkę do głównego katalogu
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workers.technical_analysis import TechnicalAnalyzer

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RecommendationEngine:
    """Silnik rekomendacji inwestycyjnych oparty na regułach"""
    
    def __init__(self, rules_config_path: Optional[str] = None):
        """
        Inicjalizacja silnika rekomendacji
        
        Args:
            rules_config_path: Ścieżka do pliku konfiguracyjnego z regułami
        """
        self.technical_analyzer = TechnicalAnalyzer()
        self.rules_config_path = rules_config_path or self._get_default_config_path()
        self.rules = self._load_rules_config()
        logger.info("✓ Recommendation Engine zainicjalizowany")
    
    def _get_default_config_path(self) -> str:
        """Pobierz domyślną ścieżkę do pliku konfiguracyjnego"""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'rules_config.json'
        )
    
    def _load_rules_config(self) -> Dict:
        """Wczytaj konfigurację reguł z pliku JSON"""
        default_rules = self._get_default_rules()
        
        if not os.path.exists(self.rules_config_path):
            logger.info(f"📝 Tworzę domyślny plik konfiguracyjny: {self.rules_config_path}")
            self._save_rules_config(default_rules)
            return default_rules
        
        try:
            with open(self.rules_config_path, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            logger.info(f"✓ Wczytano reguły z: {self.rules_config_path}")
            return rules
        except Exception as e:
            logger.error(f"❌ Błąd wczytywania reguł: {e}")
            return default_rules
    
    def _save_rules_config(self, rules: Dict) -> bool:
        """Zapisz konfigurację reguł do pliku JSON"""
        try:
            with open(self.rules_config_path, 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ Zapisano reguły do: {self.rules_config_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Błąd zapisywania reguł: {e}")
            return False
    
    def _get_default_rules(self) -> Dict:
        """Pobierz domyślne reguły rekomendacyjne"""
        return {
            "meta": {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "description": "Domyślne reguły rekomendacyjne GPW Investor"
            },
            "buy_rules": {
                "price_drop": {
                    "enabled": True,
                    "name": "Duży spadek ceny",
                    "description": "Sygnał kupna gdy cena spada >= threshold w ciągu 1 dnia",
                    "threshold_percent": -4.0,
                    "min_volume_multiplier": 1.5,
                    "confidence_weight": 1.0
                },
                "oversold_rsi": {
                    "enabled": True,
                    "name": "RSI wyprzedanie",
                    "description": "Sygnał kupna gdy RSI < threshold",
                    "threshold": 30,
                    "confidence_weight": 0.8
                },
                "bullish_macd": {
                    "enabled": True,
                    "name": "Bycza dywergencja MACD",
                    "description": "MACD przekracza linię sygnałową (trend wzrostowy)",
                    "confidence_weight": 0.7
                },
                "price_above_support": {
                    "enabled": True,
                    "name": "Cena powyżej wsparcia",
                    "description": "Cena odbija się od dolnego pasma Bollingera",
                    "confidence_weight": 0.6
                },
                "volume_breakout": {
                    "enabled": True,
                    "name": "Wybicie wolumenowe",
                    "description": "Wysoki wolumen + wzrost ceny",
                    "volume_multiplier": 2.0,
                    "min_price_change": 2.0,
                    "confidence_weight": 0.8
                }
            },
            "sell_rules": {
                "quick_profit": {
                    "enabled": True,
                    "name": "Szybki zysk",
                    "description": "Sprzedaż gdy zysk >= threshold w ciągu krótkiego czasu",
                    "profit_threshold_percent": 2.0,
                    "max_hold_hours": 6,
                    "confidence_weight": 1.0
                },
                "overbought_rsi": {
                    "enabled": True,
                    "name": "RSI wykupienie",
                    "description": "Sygnał sprzedaży gdy RSI > threshold",
                    "threshold": 70,
                    "confidence_weight": 0.8
                },
                "bearish_macd": {
                    "enabled": True,
                    "name": "Niedźwiedzia dywergencja MACD",
                    "description": "MACD spada poniżej linii sygnałowej",
                    "confidence_weight": 0.7
                },
                "resistance_level": {
                    "enabled": True,
                    "name": "Poziom oporu",
                    "description": "Cena zbliża się do górnego pasma Bollingera",
                    "confidence_weight": 0.6
                },
                "stop_loss": {
                    "enabled": True,
                    "name": "Stop Loss",
                    "description": "Ochrona przed stratą",
                    "loss_threshold_percent": -3.0,
                    "confidence_weight": 1.0
                }
            },
            "general_settings": {
                "min_confidence_buy": 0.6,
                "min_confidence_sell": 0.5,
                "max_recommendations_per_day": 10,
                "blacklist_tickers": [],
                "whitelist_tickers": [],
                "trading_hours": {
                    "start": "09:00",
                    "end": "17:00"
                }
            }
        }
    
    def evaluate_buy_signals(self, ticker: str, analysis: Dict) -> Dict:
        """
        Oceń sygnały kupna dla danej spółki
        
        Args:
            ticker: Symbol spółki
            analysis: Wyniki analizy technicznej
            
        Returns:
            Słownik z sygnałami kupna i oceną pewności
        """
        if not analysis:
            return {"signals": [], "total_confidence": 0.0, "recommendation": "HOLD"}
        
        buy_rules = self.rules["buy_rules"]
        signals = []
        total_confidence = 0.0
        
        # 1. Duży spadek ceny
        if buy_rules["price_drop"]["enabled"]:
            price_change = analysis.get("price_change_1d", 0)
            threshold = buy_rules["price_drop"]["threshold_percent"]
            
            if price_change <= threshold:
                volume_spike = analysis.get("volume_spike", False)
                confidence = buy_rules["price_drop"]["confidence_weight"]
                
                if volume_spike:
                    confidence *= 1.2  # Bonus za wysoką wolumen
                
                signals.append({
                    "rule": "price_drop",
                    "name": buy_rules["price_drop"]["name"],
                    "value": price_change,
                    "threshold": threshold,
                    "confidence": confidence,
                    "details": f"Spadek {price_change:.2f}% {'z wysokim wolumenem' if volume_spike else ''}"
                })
                total_confidence += confidence
        
        # 2. RSI wyprzedanie
        if buy_rules["oversold_rsi"]["enabled"]:
            rsi = analysis.get("rsi")
            threshold = buy_rules["oversold_rsi"]["threshold"]
            
            if rsi and rsi < threshold:
                confidence = buy_rules["oversold_rsi"]["confidence_weight"]
                # Im niższe RSI, tym wyższa pewność
                confidence *= (1.0 + (threshold - rsi) / 100)
                
                signals.append({
                    "rule": "oversold_rsi",
                    "name": buy_rules["oversold_rsi"]["name"],
                    "value": rsi,
                    "threshold": threshold,
                    "confidence": confidence,
                    "details": f"RSI {rsi:.1f} - wyprzedane"
                })
                total_confidence += confidence
        
        # 3. Bycza dywergencja MACD
        if buy_rules["bullish_macd"]["enabled"]:
            macd = analysis.get("macd")
            macd_signal = analysis.get("macd_signal")
            macd_histogram = analysis.get("macd_histogram")
            
            if all([macd is not None, macd_signal is not None, macd_histogram is not None]):
                # MACD powyżej sygnału i histogram rośnie
                if macd > macd_signal and macd_histogram > 0:
                    confidence = buy_rules["bullish_macd"]["confidence_weight"]
                    
                    signals.append({
                        "rule": "bullish_macd",
                        "name": buy_rules["bullish_macd"]["name"],
                        "value": macd,
                        "threshold": macd_signal,
                        "confidence": confidence,
                        "details": f"MACD {macd:.3f} > Sygnał {macd_signal:.3f}"
                    })
                    total_confidence += confidence
        
        # 4. Cena powyżej wsparcia (Bollinger Bands)
        if buy_rules["price_above_support"]["enabled"]:
            current_price = analysis.get("current_price")
            bb_lower = analysis.get("bb_lower")
            bb_middle = analysis.get("bb_middle")
            
            if all([current_price is not None, bb_lower is not None, bb_middle is not None]):
                # Cena blisko dolnego pasma lub odskakuje od niego
                distance_to_lower = (current_price - bb_lower) / bb_lower * 100
                
                if 0 <= distance_to_lower <= 5:  # W granicach 5% od dolnego pasma
                    confidence = buy_rules["price_above_support"]["confidence_weight"]
                    
                    signals.append({
                        "rule": "price_above_support",
                        "name": buy_rules["price_above_support"]["name"],
                        "value": current_price,
                        "threshold": bb_lower,
                        "confidence": confidence,
                        "details": f"Cena {distance_to_lower:.1f}% od dolnego BB"
                    })
                    total_confidence += confidence
        
        # 5. Wybicie wolumenowe
        if buy_rules["volume_breakout"]["enabled"]:
            volume_spike = analysis.get("volume_spike", False)
            price_change = analysis.get("price_change_1d", 0)
            min_change = buy_rules["volume_breakout"]["min_price_change"]
            
            if volume_spike and price_change >= min_change:
                confidence = buy_rules["volume_breakout"]["confidence_weight"]
                
                signals.append({
                    "rule": "volume_breakout",
                    "name": buy_rules["volume_breakout"]["name"],
                    "value": price_change,
                    "threshold": min_change,
                    "confidence": confidence,
                    "details": f"Wybicie +{price_change:.2f}% z wysokim wolumenem"
                })
                total_confidence += confidence
        
        # Oceń końcową rekomendację
        min_confidence = self.rules["general_settings"]["min_confidence_buy"]
        recommendation = "BUY" if total_confidence >= min_confidence else "HOLD"
        
        return {
            "ticker": ticker,
            "signals": signals,
            "total_confidence": round(total_confidence, 2),
            "recommendation": recommendation,
            "signal_count": len(signals),
            "timestamp": datetime.now().isoformat()
        }
    
    def evaluate_sell_signals(self, ticker: str, analysis: Dict, buy_price: Optional[float] = None, buy_time: Optional[datetime] = None) -> Dict:
        """
        Oceń sygnały sprzedaży dla danej spółki
        
        Args:
            ticker: Symbol spółki
            analysis: Wyniki analizy technicznej
            buy_price: Cena zakupu (jeśli posiadamy akcje)
            buy_time: Czas zakupu (jeśli posiadamy akcje)
            
        Returns:
            Słownik z sygnałami sprzedaży i oceną pewności
        """
        if not analysis:
            return {"signals": [], "total_confidence": 0.0, "recommendation": "HOLD"}
        
        sell_rules = self.rules["sell_rules"]
        signals = []
        total_confidence = 0.0
        current_price = analysis.get("current_price", 0)
        
        # 1. Szybki zysk (jeśli posiadamy akcje)
        if sell_rules["quick_profit"]["enabled"] and buy_price and buy_time:
            profit_pct = (current_price - buy_price) / buy_price * 100
            hours_held = (datetime.now() - buy_time).total_seconds() / 3600
            
            profit_threshold = sell_rules["quick_profit"]["profit_threshold_percent"]
            max_hours = sell_rules["quick_profit"]["max_hold_hours"]
            
            if profit_pct >= profit_threshold and hours_held <= max_hours:
                confidence = sell_rules["quick_profit"]["confidence_weight"]
                
                signals.append({
                    "rule": "quick_profit",
                    "name": sell_rules["quick_profit"]["name"],
                    "value": profit_pct,
                    "threshold": profit_threshold,
                    "confidence": confidence,
                    "details": f"Zysk {profit_pct:.2f}% po {hours_held:.1f}h"
                })
                total_confidence += confidence
        
        # 2. Stop Loss (jeśli posiadamy akcje)
        if sell_rules["stop_loss"]["enabled"] and buy_price:
            loss_pct = (current_price - buy_price) / buy_price * 100
            loss_threshold = sell_rules["stop_loss"]["loss_threshold_percent"]
            
            if loss_pct <= loss_threshold:
                confidence = sell_rules["stop_loss"]["confidence_weight"]
                
                signals.append({
                    "rule": "stop_loss",
                    "name": sell_rules["stop_loss"]["name"],
                    "value": loss_pct,
                    "threshold": loss_threshold,
                    "confidence": confidence,
                    "details": f"Strata {loss_pct:.2f}% - Stop Loss"
                })
                total_confidence += confidence
        
        # 3. RSI wykupienie
        if sell_rules["overbought_rsi"]["enabled"]:
            rsi = analysis.get("rsi")
            threshold = sell_rules["overbought_rsi"]["threshold"]
            
            if rsi and rsi > threshold:
                confidence = sell_rules["overbought_rsi"]["confidence_weight"]
                # Im wyższe RSI, tym wyższa pewność
                confidence *= (1.0 + (rsi - threshold) / 100)
                
                signals.append({
                    "rule": "overbought_rsi",
                    "name": sell_rules["overbought_rsi"]["name"],
                    "value": rsi,
                    "threshold": threshold,
                    "confidence": confidence,
                    "details": f"RSI {rsi:.1f} - wykupione"
                })
                total_confidence += confidence
        
        # 4. Niedźwiedzia dywergencja MACD
        if sell_rules["bearish_macd"]["enabled"]:
            macd = analysis.get("macd")
            macd_signal = analysis.get("macd_signal")
            macd_histogram = analysis.get("macd_histogram")
            
            if all([macd is not None, macd_signal is not None, macd_histogram is not None]):
                # MACD poniżej sygnału i histogram spada
                if macd < macd_signal and macd_histogram < 0:
                    confidence = sell_rules["bearish_macd"]["confidence_weight"]
                    
                    signals.append({
                        "rule": "bearish_macd",
                        "name": sell_rules["bearish_macd"]["name"],
                        "value": macd,
                        "threshold": macd_signal,
                        "confidence": confidence,
                        "details": f"MACD {macd:.3f} < Sygnał {macd_signal:.3f}"
                    })
                    total_confidence += confidence
        
        # 5. Poziom oporu (Bollinger Bands)
        if sell_rules["resistance_level"]["enabled"]:
            bb_upper = analysis.get("bb_upper")
            bb_middle = analysis.get("bb_middle")
            
            if all([current_price is not None, bb_upper is not None, bb_middle is not None]):
                # Cena blisko górnego pasma
                distance_to_upper = (bb_upper - current_price) / current_price * 100
                
                if 0 <= distance_to_upper <= 3:  # W granicach 3% od górnego pasma
                    confidence = sell_rules["resistance_level"]["confidence_weight"]
                    
                    signals.append({
                        "rule": "resistance_level",
                        "name": sell_rules["resistance_level"]["name"],
                        "value": current_price,
                        "threshold": bb_upper,
                        "confidence": confidence,
                        "details": f"Cena {distance_to_upper:.1f}% od górnego BB"
                    })
                    total_confidence += confidence
        
        # Oceń końcową rekomendację
        min_confidence = self.rules["general_settings"]["min_confidence_sell"]
        recommendation = "SELL" if total_confidence >= min_confidence else "HOLD"
        
        return {
            "ticker": ticker,
            "signals": signals,
            "total_confidence": round(total_confidence, 2),
            "recommendation": recommendation,
            "signal_count": len(signals),
            "timestamp": datetime.now().isoformat()
        }
    
    def analyze_ticker(self, ticker: str, days_back: int = 100) -> Dict:
        """
        Przeprowadź pełną analizę i oceń rekomendacje dla spółki
        
        Args:
            ticker: Symbol spółki
            days_back: Liczba dni historycznych
            
        Returns:
            Słownik z analizą techniczną i rekomendacjami
        """
        logger.info(f"🔍 Analiza rekomendacji dla {ticker}")
        
        # Pobierz analizę techniczną
        technical_analysis = self.technical_analyzer.analyze_ticker(ticker, days_back)
        
        if not technical_analysis:
            return {
                "ticker": ticker,
                "error": "Brak danych technicznych",
                "timestamp": datetime.now().isoformat()
            }
        
        # Oceń sygnały
        buy_signals = self.evaluate_buy_signals(ticker, technical_analysis)
        sell_signals = self.evaluate_sell_signals(ticker, technical_analysis)
        
        # Połącz wyniki
        result = {
            "ticker": ticker,
            "technical_analysis": technical_analysis,
            "buy_analysis": buy_signals,
            "sell_analysis": sell_signals,
            "final_recommendation": self._get_final_recommendation(buy_signals, sell_signals),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"✅ Analiza zakończona: {ticker} -> {result['final_recommendation']}")
        return result
    
    def _get_final_recommendation(self, buy_signals: Dict, sell_signals: Dict) -> str:
        """Określ końcową rekomendację na podstawie sygnałów kupna i sprzedaży"""
        buy_confidence = buy_signals.get("total_confidence", 0)
        sell_confidence = sell_signals.get("total_confidence", 0)
        
        if buy_confidence > sell_confidence and buy_signals.get("recommendation") == "BUY":
            return "BUY"
        elif sell_confidence > buy_confidence and sell_signals.get("recommendation") == "SELL":
            return "SELL"
        else:
            return "HOLD"
    
    def scan_market(self, tickers: List[str]) -> List[Dict]:
        """
        Skanuj rynek w poszukiwaniu okazji inwestycyjnych
        
        Args:
            tickers: Lista symboli spółek do przeskanowania
            
        Returns:
            Lista rekomendacji posortowana według pewności
        """
        logger.info(f"🔍 Skanowanie rynku dla {len(tickers)} spółek")
        
        recommendations = []
        
        for ticker in tickers:
            try:
                analysis = self.analyze_ticker(ticker)
                if "error" not in analysis:
                    recommendations.append(analysis)
            except Exception as e:
                logger.error(f"❌ Błąd analizy {ticker}: {e}")
        
        # Sortuj według pewności rekomendacji
        recommendations.sort(
            key=lambda x: max(
                x.get("buy_analysis", {}).get("total_confidence", 0),
                x.get("sell_analysis", {}).get("total_confidence", 0)
            ),
            reverse=True
        )
        
        logger.info(f"✅ Skanowanie zakończone: {len(recommendations)} analizowanych spółek")
        return recommendations
    
    def update_rules(self, new_rules: Dict) -> bool:
        """
        Aktualizuj reguły rekomendacyjne
        
        Args:
            new_rules: Nowe reguły do zapisania
            
        Returns:
            True jeśli sukces, False w przeciwnym razie
        """
        try:
            # Walidacja podstawowa
            required_sections = ["buy_rules", "sell_rules", "general_settings"]
            for section in required_sections:
                if section not in new_rules:
                    raise ValueError(f"Brak wymaganej sekcji: {section}")
            
            self.rules = new_rules
            success = self._save_rules_config(new_rules)
            
            if success:
                logger.info("✅ Reguły zaktualizowane")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Błąd aktualizacji reguł: {e}")
            return False
    
    def get_rules_summary(self) -> Dict:
        """Pobierz podsumowanie aktualnych reguł"""
        buy_enabled = sum(1 for rule in self.rules["buy_rules"].values() if rule.get("enabled", False))
        sell_enabled = sum(1 for rule in self.rules["sell_rules"].values() if rule.get("enabled", False))
        
        return {
            "total_buy_rules": len(self.rules["buy_rules"]),
            "enabled_buy_rules": buy_enabled,
            "total_sell_rules": len(self.rules["sell_rules"]),
            "enabled_sell_rules": sell_enabled,
            "min_confidence_buy": self.rules["general_settings"]["min_confidence_buy"],
            "min_confidence_sell": self.rules["general_settings"]["min_confidence_sell"],
            "config_path": self.rules_config_path
        }


def main():
    """Funkcja główna - test systemu rekomendacji"""
    logger.info("🧪 Test systemu rekomendacji")
    
    engine = RecommendationEngine()
    
    # Test pojedynczej spółki
    test_ticker = "CDR"
    analysis = engine.analyze_ticker(test_ticker)
    
    if "error" not in analysis:
        logger.info(f"📊 Rekomendacja dla {test_ticker}:")
        logger.info(f"   Finalna rekomendacja: {analysis['final_recommendation']}")
        logger.info(f"   Sygnały kupna: {analysis['buy_analysis']['signal_count']}")
        logger.info(f"   Pewność kupna: {analysis['buy_analysis']['total_confidence']}")
        logger.info(f"   Sygnały sprzedaży: {analysis['sell_analysis']['signal_count']}")
        logger.info(f"   Pewność sprzedaży: {analysis['sell_analysis']['total_confidence']}")
    
    # Test skanowania rynku
    tickers = ["CDR", "PKN", "PKO"]
    recommendations = engine.scan_market(tickers)
    
    logger.info(f"📈 Top rekomendacje:")
    for i, rec in enumerate(recommendations[:3], 1):
        logger.info(f"   {i}. {rec['ticker']}: {rec['final_recommendation']}")
    
    # Podsumowanie reguł
    summary = engine.get_rules_summary()
    logger.info(f"📋 Podsumowanie reguł: {summary['enabled_buy_rules']}/{summary['total_buy_rules']} kupna, {summary['enabled_sell_rules']}/{summary['total_sell_rules']} sprzedaży")


if __name__ == "__main__":
    main()
