#!/usr/bin/env python3
"""
System rekomendacji intraday dla GPW Investor
Zoptymalizowany pod trading w ramach jednej sesji giełdowej
Autor: GPW Investor System
Data: 2025-06-24
"""

import json
import os
import sys
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Any
import logging

# Dodaj ścieżkę do głównego katalogu
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workers.technical_analysis import TechnicalAnalyzer

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntradayRecommendationEngine:
    """Silnik rekomendacji intraday - trading w ramach jednej sesji"""
    
    def __init__(self, rules_config_path: Optional[str] = None, enable_tracking: bool = True, enable_notifications: bool = True):
        """
        Inicjalizacja silnika rekomendacji intraday
        
        Args:
            rules_config_path: Ścieżka do pliku konfiguracyjnego z regułami intraday
            enable_tracking: Czy włączyć śledzenie rekomendacji
            enable_notifications: Czy włączyć powiadomienia Telegram
        """
        self.technical_analyzer = TechnicalAnalyzer()
        self.rules_config_path = rules_config_path or self._get_default_config_path()
        self.rules = self._load_rules_config()
        self.session_start = None
        self.active_positions = {}  # ticker -> {'entry_price', 'entry_time', 'quantity'}
        self.current_config = None  # Przechowuje aktualną konfigurację użytkownika
        
        # Inicjalizuj tracker rekomendacji
        self.enable_tracking = enable_tracking
        if enable_tracking:
            try:
                from workers.recommendation_tracker_postgresql import RecommendationTracker
                self.recommendation_tracker = RecommendationTracker()
                logger.info("✓ Tracker rekomendacji zainicjalizowany")
            except Exception as e:
                logger.warning(f"⚠️ Nie można zainicjalizować trackera: {e}")
                self.recommendation_tracker = None
        else:
            self.recommendation_tracker = None
        
        # Inicjalizuj powiadomienia Telegram
        self.enable_notifications = enable_notifications
        if enable_notifications:
            try:
                from telegram_notifications import TelegramNotificationManager
                self.telegram_manager = TelegramNotificationManager()
                logger.info("✓ Manager powiadomień Telegram zainicjalizowany")
            except Exception as e:
                logger.warning(f"⚠️ Nie można zainicjalizować powiadomień Telegram: {e}")
                self.telegram_manager = None
        else:
            self.telegram_manager = None
            
        logger.info("✓ Intraday Recommendation Engine zainicjalizowany")
    
    def _get_default_config_path(self) -> str:
        """Zwraca domyślną ścieżkę do pliku konfiguracyjnego intraday"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "rules_config_intraday.json")
    
    def _load_rules_config(self) -> Dict:
        """Ładuje konfigurację reguł z pliku JSON"""
        if os.path.exists(self.rules_config_path):
            with open(self.rules_config_path, 'r', encoding='utf-8') as f:
                logger.info(f"✓ Wczytano reguły intraday z: {self.rules_config_path}")
                return json.load(f)
        else:
            logger.info(f"📝 Tworzę domyślny plik konfiguracyjny intraday: {self.rules_config_path}")
            default_rules = self._get_default_intraday_rules()
            self._save_rules_config(default_rules)
            return default_rules
    
    def _save_rules_config(self, rules: Dict) -> bool:
        """Zapisuje konfigurację reguł do pliku JSON"""
        try:
            with open(self.rules_config_path, 'w', encoding='utf-8') as f:
                json.dump(rules, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Zapisano reguły intraday do: {self.rules_config_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Błąd zapisu reguł: {e}")
            return False
    
    def _get_default_intraday_rules(self) -> Dict:
        """Zwraca domyślne reguły dla tradingu intraday"""
        # Wczytaj z już utworzonego pliku
        intraday_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules_config_intraday.json")
        if os.path.exists(intraday_config_path):
            with open(intraday_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Fallback - podstawowa konfiguracja
        return {
            "meta": {"version": "2.0", "trading_style": "intraday"},
            "buy_rules": {"price_drop_intraday": {"enabled": True, "threshold_percent": -2.5}},
            "sell_rules": {"quick_profit_intraday": {"enabled": True, "profit_threshold_percent": 1.5}},
            "general_settings": {"min_confidence_buy": 0.8}
        }
    
    def is_trading_hours(self) -> bool:
        """Sprawdza czy jesteśmy w godzinach notowań"""
        now = datetime.now().time()
        trading_hours = self.rules.get("general_settings", {}).get("trading_hours", {})
        start_time = time.fromisoformat(trading_hours.get("start", "09:00"))
        end_time = time.fromisoformat(trading_hours.get("end", "17:00"))
        
        return start_time <= now <= end_time
    
    def is_session_near_end(self, minutes_threshold: int = 30) -> bool:
        """Sprawdza czy sesja kończy się w ciągu threshold minut"""
        if not self.is_trading_hours():
            return True
            
        now = datetime.now().time()
        trading_hours = self.rules.get("general_settings", {}).get("trading_hours", {})
        end_time = time.fromisoformat(trading_hours.get("end", "17:00"))
        
        # Konwersja na datetime dla obliczeń
        today = datetime.now().date()
        end_datetime = datetime.combine(today, end_time)
        threshold_datetime = end_datetime - timedelta(minutes=minutes_threshold)
        
        return datetime.now() >= threshold_datetime
    
    def evaluate_intraday_buy_signals(self, ticker: str, analysis: Dict) -> Dict:
        """Ocenia sygnały kupna zoptymalizowane pod intraday"""
        buy_rules = self.rules.get("buy_rules", {})
        signals = []
        total_confidence = 0.0
        
        current_price = analysis.get("current_price", 0)
        current_volume = analysis.get("current_volume", 0)
        avg_volume = analysis.get("avg_volume_20", 1)
        
        # 1. Spadek intraday z wolumenem
        if buy_rules.get("price_drop_intraday", {}).get("enabled", False):
            rule = buy_rules["price_drop_intraday"]
            price_change = analysis.get("price_change_1d", 0)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            threshold = rule.get("threshold_percent", -2.5)
            min_volume = rule.get("min_volume_multiplier", 1.8)
            
            if price_change <= threshold and volume_ratio >= min_volume:
                confidence = rule.get("confidence_weight", 1.2)
                signals.append({
                    "rule": "price_drop_intraday",
                    "name": rule.get("name", "Spadek intraday"),
                    "value": price_change,
                    "threshold": threshold,
                    "confidence": confidence,
                    "details": f"Spadek {price_change:.1f}% z wolumenem {volume_ratio:.1f}x"
                })
                total_confidence += confidence
        
        # 2. RSI wyprzedanie (agresywny próg)
        if buy_rules.get("oversold_rsi_fast", {}).get("enabled", False):
            rule = buy_rules["oversold_rsi_fast"]
            rsi = analysis.get("rsi")
            threshold = rule.get("threshold", 35)
            
            if rsi is not None and rsi < threshold:
                confidence = rule.get("confidence_weight", 1.0)
                signals.append({
                    "rule": "oversold_rsi_fast",
                    "name": rule.get("name", "RSI wyprzedanie (szybkie)"),
                    "value": rsi,
                    "threshold": threshold,
                    "confidence": confidence,
                    "details": f"RSI {rsi:.1f} < {threshold}"
                })
                total_confidence += confidence
        
        # 3. Momentum reversal
        if buy_rules.get("momentum_reversal", {}).get("enabled", False):
            rule = buy_rules["momentum_reversal"]
            price_change = analysis.get("price_change_1d", 0)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            volume_spike = rule.get("min_volume_spike", 2.5)
            price_threshold = rule.get("price_change_threshold", -1.5)
            
            if price_change <= price_threshold and volume_ratio >= volume_spike:
                confidence = rule.get("confidence_weight", 1.1)
                signals.append({
                    "rule": "momentum_reversal",
                    "name": rule.get("name", "Odwrócenie momentum"),
                    "value": price_change,
                    "threshold": price_threshold,
                    "confidence": confidence,
                    "details": f"Reversal: {price_change:.1f}% z wolumenem {volume_ratio:.1f}x"
                })
                total_confidence += confidence
        
        # 4. Bollinger Bands bounce
        if buy_rules.get("bollinger_bounce", {}).get("enabled", False):
            rule = buy_rules["bollinger_bounce"]
            bb_lower = analysis.get("bb_lower")
            
            if bb_lower is not None and current_price > 0:
                distance_from_lower = (current_price - bb_lower) / bb_lower * 100
                threshold = rule.get("touch_threshold_percent", 2.0)
                
                if 0 <= distance_from_lower <= threshold:
                    confidence = rule.get("confidence_weight", 0.9)
                    signals.append({
                        "rule": "bollinger_bounce",
                        "name": rule.get("name", "Odbicie od Bollinger"),
                        "value": current_price,
                        "threshold": bb_lower,
                        "confidence": confidence,
                        "details": f"{distance_from_lower:.1f}% od dolnego BB"
                    })
                    total_confidence += confidence
        
        return {
            "signals": signals,
            "total_confidence": total_confidence,
            "signal_count": len(signals)
        }
    
    def evaluate_intraday_sell_signals(self, ticker: str, analysis: Dict, 
                                     entry_price: Optional[float] = None, 
                                     entry_time: Optional[datetime] = None) -> Dict:
        """Ocenia sygnały sprzedaży zoptymalizowane pod intraday"""
        sell_rules = self.rules.get("sell_rules", {})
        signals = []
        total_confidence = 0.0
        
        current_price = analysis.get("current_price", 0)
        current_time = datetime.now()
        
        # 1. Szybki zysk intraday
        if sell_rules.get("quick_profit_intraday", {}).get("enabled", False) and entry_price:
            rule = sell_rules["quick_profit_intraday"]
            profit_percent = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            threshold = rule.get("profit_threshold_percent", 1.5)
            
            if profit_percent >= threshold:
                confidence = rule.get("confidence_weight", 1.5)
                signals.append({
                    "rule": "quick_profit_intraday",
                    "name": rule.get("name", "Szybki zysk intraday"),
                    "value": profit_percent,
                    "threshold": threshold,
                    "confidence": confidence,
                    "details": f"Zysk {profit_percent:.1f}% osiągnięty"
                })
                total_confidence += confidence
        
        # 2. Wyjście przed końcem sesji
        if sell_rules.get("session_end_exit", {}).get("enabled", False):
            rule = sell_rules["session_end_exit"]
            minutes_threshold = rule.get("minutes_before_close", 30)
            
            if self.is_session_near_end(minutes_threshold):
                confidence = rule.get("confidence_weight", 1.0)
                signals.append({
                    "rule": "session_end_exit",
                    "name": rule.get("name", "Wyjście przed końcem sesji"),
                    "value": 1,
                    "threshold": 1,
                    "confidence": confidence,
                    "details": f"Koniec sesji za < {minutes_threshold}min"
                })
                total_confidence += confidence
        
        # 3. Ciasny stop loss
        if sell_rules.get("tight_stop_loss", {}).get("enabled", False) and entry_price:
            rule = sell_rules["tight_stop_loss"]
            loss_percent = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            threshold = rule.get("loss_threshold_percent", -1.5)
            
            if loss_percent <= threshold:
                confidence = rule.get("confidence_weight", 1.5)
                signals.append({
                    "rule": "tight_stop_loss",
                    "name": rule.get("name", "Ciasny Stop Loss"),
                    "value": loss_percent,
                    "threshold": threshold,
                    "confidence": confidence,
                    "details": f"Strata {loss_percent:.1f}% - stop loss"
                })
                total_confidence += confidence
        
        # 4. RSI wykupienie (agresywne)
        if sell_rules.get("overbought_rsi_aggressive", {}).get("enabled", False):
            rule = sell_rules["overbought_rsi_aggressive"]
            rsi = analysis.get("rsi")
            threshold = rule.get("threshold", 65)
            
            if rsi is not None and rsi > threshold:
                confidence = rule.get("confidence_weight", 0.9)
                signals.append({
                    "rule": "overbought_rsi_aggressive",
                    "name": rule.get("name", "RSI wykupienie (agresywne)"),
                    "value": rsi,
                    "threshold": threshold,
                    "confidence": confidence,
                    "details": f"RSI {rsi:.1f} > {threshold}"
                })
                total_confidence += confidence
        
        # 5. Opór Bollinger Bands
        if sell_rules.get("resistance_hit_intraday", {}).get("enabled", False):
            rule = sell_rules["resistance_hit_intraday"]
            bb_upper = analysis.get("bb_upper")
            
            if bb_upper is not None and current_price > 0:
                distance_from_upper = abs(current_price - bb_upper) / bb_upper * 100
                threshold = rule.get("resistance_buffer_percent", 1.0)
                
                if distance_from_upper <= threshold:
                    confidence = rule.get("confidence_weight", 1.0)
                    signals.append({
                        "rule": "resistance_hit_intraday",
                        "name": rule.get("name", "Opór intraday"),
                        "value": current_price,
                        "threshold": bb_upper,
                        "confidence": confidence,
                        "details": f"{distance_from_upper:.1f}% od górnego BB"
                    })
                    total_confidence += confidence
        
        return {
            "signals": signals,
            "total_confidence": total_confidence,
            "signal_count": len(signals)
        }
    
    def analyze_ticker_intraday(self, ticker: str, entry_price: Optional[float] = None, 
                               entry_time: Optional[datetime] = None) -> Dict:
        """
        Główna metoda analizy dla tradingu intraday
        
        Args:
            ticker: Symbol spółki
            entry_price: Cena wejścia (jeśli mamy pozycję)
            entry_time: Czas wejścia (jeśli mamy pozycję)
        """
        logger.info(f"🚀 Analiza intraday dla {ticker}")
        
        # Sprawdź godziny notowań
        if not self.is_trading_hours():
            logger.warning("⏰ Poza godzinami notowań")
            return {
                "ticker": ticker,
                "error": "Poza godzinami notowań",
                "recommendation": "WAIT",
                "timestamp": datetime.now().isoformat()
            }
        
        # Pobierz analizę techniczną (krótszy okres dla intraday)
        analysis = self.technical_analyzer.analyze_ticker(ticker, days_back=30)
        
        if not analysis:
            logger.error(f"❌ Brak danych technicznych dla {ticker}")
            return {
                "ticker": ticker,
                "error": "Brak danych technicznych",
                "recommendation": "SKIP",
                "timestamp": datetime.now().isoformat()
            }
        
        # Weryfikacja komunikatów rynkowych (jeśli włączona w konfiguracji)
        news_analysis = None
        news_impact_confidence = 0.0
        news_impact_note = ""
        
        if hasattr(self, 'current_config') and self.current_config:
            news_config = self.current_config.get('news_verification', {})
            if news_config.get('enabled', False):
                timeframe = news_config.get('timeframe_hours', 24)
                news_analysis = self.check_market_news(ticker, timeframe)
                news_impact_confidence, news_impact_note = self.evaluate_news_impact(news_analysis, news_config)
                logger.info(f"📰 Wpływ komunikatów na {ticker}: {news_impact_confidence} ({news_impact_note})")
        
        # Oceń sygnały
        buy_analysis = self.evaluate_intraday_buy_signals(ticker, analysis)
        sell_analysis = self.evaluate_intraday_sell_signals(ticker, analysis, entry_price, entry_time)
        
        # Uwzględnij wpływ komunikatów na pewność sygnałów
        if news_impact_confidence != 0.0:
            buy_analysis["total_confidence"] += news_impact_confidence
            sell_analysis["total_confidence"] += news_impact_confidence
            buy_analysis["signals"].append({
                "signal": "news_impact",
                "description": news_impact_note,
                "confidence": news_impact_confidence,
                "source": "news_verification"
            })
        
        # Określ finalną rekomendację
        final_recommendation = self._get_intraday_recommendation(buy_analysis, sell_analysis, entry_price is not None)
        
        # Przygotuj wynik analizy
        result = {
            "ticker": ticker,
            "technical_analysis": analysis,
            "buy_analysis": buy_analysis,
            "sell_analysis": sell_analysis,
            "final_recommendation": final_recommendation,
            "has_position": entry_price is not None,
            "entry_price": entry_price,
            "entry_time": entry_time.isoformat() if entry_time else None,
            "current_price": analysis.get("current_price"),
            "profit_loss": ((analysis.get("current_price", 0) - entry_price) / entry_price * 100) if entry_price else None,
            "timestamp": datetime.now().isoformat()
        }
        
        # Zapisz rekomendację do trackera (tylko jeśli to nowa rekomendacja bez pozycji)
        if (self.recommendation_tracker and 
            entry_price is None and 
            final_recommendation in ['BUY', 'SELL']):
            try:
                recommendation_id = self.recommendation_tracker.save_recommendation(
                    ticker, result, self.current_config
                )
                result['recommendation_id'] = recommendation_id
                logger.info(f"📝 Zapisano rekomendację #{recommendation_id} do trackera")
            except Exception as e:
                logger.warning(f"⚠️ Nie można zapisać rekomendacji do trackera: {e}")
        
        # Powiadomienia Telegram o nowych rekomendacjach (tylko jeśli to nowa rekomendacja bez pozycji)
        if (self.telegram_manager and 
            entry_price is None and 
            final_recommendation in ['BUY', 'SELL']):
            try:
                self.send_recommendation_notification(ticker, final_recommendation, result)
            except Exception as e:
                logger.warning(f"⚠️ Nie można wysłać powiadomienia Telegram dla {ticker}: {e}")
        
        logger.info(f"✅ Analiza intraday zakończona: {ticker} -> {final_recommendation}")
        
        return result
    
    def _get_intraday_recommendation(self, buy_signals: Dict, sell_signals: Dict, has_position: bool) -> str:
        """Określa finalną rekomendację dla tradingu intraday"""
        settings = self.rules.get("general_settings", {})
        min_buy_confidence = settings.get("min_confidence_buy", 0.8)
        min_sell_confidence = settings.get("min_confidence_sell", 0.7)
        
        buy_confidence = buy_signals.get("total_confidence", 0)
        sell_confidence = sell_signals.get("total_confidence", 0)
        
        # Jeśli mamy pozycję, priorytet ma sprzedaż
        if has_position:
            if sell_confidence >= min_sell_confidence:
                return "SELL"
            elif sell_confidence > 0:
                return "HOLD"
            else:
                return "HOLD"
        
        # Jeśli nie mamy pozycji, rozważ kupno
        else:
            if buy_confidence >= min_buy_confidence:
                return "BUY"
            elif sell_confidence >= min_sell_confidence:
                return "WAIT"  # Rynek w trendzie spadkowym
            else:
                return "WAIT"
    
    def get_session_summary(self) -> Dict:
        """Zwraca podsumowanie aktualnej sesji"""
        return {
            "session_active": self.is_trading_hours(),
            "session_near_end": self.is_session_near_end(),
            "active_positions": len(self.active_positions),
            "positions": self.active_positions,
            "timestamp": datetime.now().isoformat()
        }
    
    def scan_market_intraday(self, tickers: List[str], max_workers: int = 5) -> List[Dict]:
        """
        Skanuj cały rynek w poszukiwaniu okazji intraday - przetwarzanie równoległe
        
        Args:
            tickers: Lista symboli spółek do przeskanowania
            max_workers: Maksymalna liczba wątków do przetwarzania równoległego
            
        Returns:
            Lista rekomendacji posortowana według pewności i typu
        """
        import concurrent.futures
        import threading
        
        logger.info(f"🚀 Skanowanie intraday dla {len(tickers)} spółek (równolegle)")
        
        if not self.is_trading_hours():
            logger.warning("⏰ Skanowanie poza godzinami notowań")
            return []
        
        recommendations = []
        failed_tickers = []
        
        def analyze_single_ticker(ticker: str) -> Optional[Dict]:
            """Analizuj pojedynczą spółkę - funkcja pomocnicza dla wątków"""
            try:
                result = self.analyze_ticker_intraday(ticker)
                if "error" not in result:
                    return result
                else:
                    failed_tickers.append((ticker, result.get("error", "Unknown error")))
            except Exception as e:
                failed_tickers.append((ticker, str(e)))
                logger.error(f"❌ Błąd analizy intraday {ticker}: {e}")
            return None
        
        # Przetwarzanie równoległe z ograniczeniem wątków
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit wszystkie zadania
            future_to_ticker = {
                executor.submit(analyze_single_ticker, ticker): ticker 
                for ticker in tickers
            }
            
            # Zbierz wyniki w miarę ukończenia
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    result = future.result()
                    if result:
                        recommendations.append(result)
                        logger.info(f"✓ Przeanalizowano {ticker}: {result.get('final_recommendation', result.get('recommendation', 'N/A'))}")
                except Exception as e:
                    failed_tickers.append((ticker, str(e)))
                    logger.error(f"❌ Błąd wątku dla {ticker}: {e}")
        
        # Sortuj według strategii intraday:
        # 1. Najpierw BUY z największą pewnością
        # 2. Potem SELL z największą pewnością  
        # 3. Na końcu HOLD/WAIT
        def sort_key(x):
            recommendation = x.get('final_recommendation', x.get('recommendation', 'WAIT'))
            buy_confidence = x.get("buy_analysis", {}).get("total_confidence", 0)
            sell_confidence = x.get("sell_analysis", {}).get("total_confidence", 0)
            
            # Priorytetyzacja dla intraday
            if recommendation == 'BUY':
                return (3, buy_confidence)  # Najwyższy priorytet
            elif recommendation == 'SELL':
                return (2, sell_confidence)  # Średni priorytet
            else:
                return (1, max(buy_confidence, sell_confidence))  # Najniższy priorytet
        
        recommendations.sort(key=sort_key, reverse=True)
        
        # Logowanie podsumowania
        buy_count = sum(1 for r in recommendations if r.get('final_recommendation', r.get('recommendation')) == 'BUY')
        sell_count = sum(1 for r in recommendations if r.get('final_recommendation', r.get('recommendation')) == 'SELL')
        
        logger.info(f"✅ Skanowanie intraday zakończone:")
        logger.info(f"   📊 Przeanalizowano: {len(recommendations)}/{len(tickers)} spółek")
        logger.info(f"   🟢 Sygnały BUY: {buy_count}")
        logger.info(f"   🔴 Sygnały SELL: {sell_count}")
        logger.info(f"   ❌ Błędy: {len(failed_tickers)}")
        
        if failed_tickers:
            logger.warning(f"❌ Błędy dla: {[t[0] for t in failed_tickers[:5]]}")
        
        # Wyślij podsumowanie skanowania przez Telegram (jeśli są rekomendacje)
        if recommendations and buy_count + sell_count > 0:
            try:
                scan_config = {'max_workers': max_workers, 'total_tickers': len(tickers)}
                self.send_scan_summary_notification(recommendations, scan_config)
            except Exception as e:
                logger.warning(f"⚠️ Nie można wysłać podsumowania skanowania: {e}")
        
        return recommendations
    
    def get_top_intraday_opportunities(self, limit: int = 10) -> List[Dict]:
        """
        Pobierz top okazje intraday z bazy danych
        
        Args:
            limit: Maksymalna liczba okazji do zwrócenia
        """
        from workers.quotes_daily import get_companies
        
        # Pobierz listę spółek z bazy
        companies = get_companies()
        tickers = [company['ticker'] for company in companies]
        
        # Ogranicz do najbardziej płynnych spółek dla intraday
        priority_tickers = [
            'CDR', 'PKN', 'PZU', 'ALE', 'CCC', 'LPP', 'JSW', 'KGHM', 
            'OPL', 'PEO', 'PKO', 'MBK', 'ING', 'BNP', 'AMC'
        ]
        
        # Użyj priorytetowych jeśli dostępne, inaczej wszystkie
        scan_tickers = [t for t in priority_tickers if t in tickers] or tickers[:20]
        
        logger.info(f"🎯 Szukanie top {limit} okazji intraday z {len(scan_tickers)} spółek")
        
        # Skanuj rynek
        all_opportunities = self.scan_market_intraday(scan_tickers)
        
        # Filtruj tylko rekomendacje BUY i SELL
        opportunities = [
            opp for opp in all_opportunities 
            if opp.get('final_recommendation', opp.get('recommendation')) in ['BUY', 'SELL']
        ]
        
        return opportunities[:limit]
    
    def monitor_active_positions(self) -> Dict:
        """
        Monitoruj aktywne pozycje i generuj rekomendacje dla każdej
        """
        if not self.active_positions:
            return {"message": "Brak aktywnych pozycji", "positions": []}
        
        monitored_positions = []
        
        for ticker, position_info in self.active_positions.items():
            try:
                entry_price = position_info.get('entry_price')
                entry_time_str = position_info.get('entry_time')
                entry_time = datetime.fromisoformat(entry_time_str) if entry_time_str else None
                
                # Analizuj aktualną sytuację
                result = self.analyze_ticker_intraday(ticker, entry_price, entry_time)
                
                monitored_positions.append({
                    "ticker": ticker,
                    "position": position_info,
                    "current_analysis": result,
                    "recommendation": result.get('final_recommendation', result.get('recommendation')),
                    "profit_loss": result.get('profit_loss', 0)
                })
                
            except Exception as e:
                logger.error(f"❌ Błąd monitorowania pozycji {ticker}: {e}")
        
        return {
            "session_active": self.is_trading_hours(),
            "positions_count": len(monitored_positions),
            "positions": monitored_positions,
            "timestamp": datetime.now().isoformat()
        }
    
    def apply_config_overrides(self, config: Dict) -> None:
        """
        Aplikuje nadpisania konfiguracji z panelu użytkownika
        
        Args:
            config: Słownik z konfiguracją z panelu użytkownika
        """
        if not config:
            return
            
        # Zapisz konfigurację dla użycia w analizie
        self.current_config = config
        
        logger.info(f"🔧 Aplikuję nadpisania konfiguracji: {config.get('name', 'Unknown')}")
        
        # Aktualizuj parametry analizy spadków ceny
        if 'price_drop_analysis' in config and config['price_drop_analysis']['enabled']:
            price_drop_config = config['price_drop_analysis']
            if 'price_drop_intraday' in self.rules.get('buy_rules', {}):
                self.rules['buy_rules']['price_drop_intraday'].update({
                    'threshold_percent': -abs(price_drop_config['threshold_percent']),  # Zawsze ujemny
                    'max_duration_minutes': price_drop_config['timeframe_minutes'],
                    'min_volume_multiplier': price_drop_config['min_volume_multiplier']
                })
                logger.info(f"✓ Zaktualizowano parametry spadku ceny: {price_drop_config['threshold_percent']}% w {price_drop_config['timeframe_minutes']}min")
        
        # Aktualizuj parametry RSI
        if 'technical_indicators' in config:
            indicators = config['technical_indicators']
            
            if 'rsi' in indicators and indicators['rsi']['enabled']:
                rsi_config = indicators['rsi']
                # Aktualizuj reguły RSI
                if 'oversold_rsi_fast' in self.rules.get('buy_rules', {}):
                    self.rules['buy_rules']['oversold_rsi_fast']['threshold'] = rsi_config['oversold_threshold']
                if 'overbought_rsi_aggressive' in self.rules.get('sell_rules', {}):
                    self.rules['sell_rules']['overbought_rsi_aggressive']['threshold'] = rsi_config['overbought_threshold']
                logger.info(f"✓ Zaktualizowano progi RSI: wyprzedanie {rsi_config['oversold_threshold']}, wykupienie {rsi_config['overbought_threshold']}")
            
            if 'macd' in indicators and indicators['macd']['enabled']:
                macd_config = indicators['macd']
                if 'macd_cross_intraday' in self.rules.get('buy_rules', {}):
                    self.rules['buy_rules']['macd_cross_intraday'].update({
                        'fast_periods': macd_config['fast_periods'],
                        'slow_periods': macd_config['slow_periods'],
                        'signal_periods': macd_config['signal_periods']
                    })
                logger.info(f"✓ Zaktualizowano parametry MACD: {macd_config['fast_periods']}/{macd_config['slow_periods']}/{macd_config['signal_periods']}")
        
        # Wyłącz reguły jeśli wskaźniki są dezaktywowane
        if 'technical_indicators' in config:
            indicators = config['technical_indicators']
            
            # Wyłącz RSI jeśli dezaktywowane
            if not indicators.get('rsi', {}).get('enabled', True):
                for rule_name in ['oversold_rsi_fast']:
                    if rule_name in self.rules.get('buy_rules', {}):
                        self.rules['buy_rules'][rule_name]['enabled'] = False
                for rule_name in ['overbought_rsi_aggressive']:
                    if rule_name in self.rules.get('sell_rules', {}):
                        self.rules['sell_rules'][rule_name]['enabled'] = False
                logger.info("⚠️ Wyłączono reguły RSI")
            
            # Wyłącz Bollinger Bands jeśli dezaktywowane
            if not indicators.get('bollinger_bands', {}).get('enabled', True):
                for rule_name in ['bollinger_bounce']:
                    if rule_name in self.rules.get('buy_rules', {}):
                        self.rules['buy_rules'][rule_name]['enabled'] = False
                logger.info("⚠️ Wyłączono reguły Bollinger Bands")
            
            # Wyłącz MACD jeśli dezaktywowane
            if not indicators.get('macd', {}).get('enabled', True):
                for rule_name in ['macd_cross_intraday']:
                    if rule_name in self.rules.get('buy_rules', {}):
                        self.rules['buy_rules'][rule_name]['enabled'] = False
                logger.info("⚠️ Wyłączono reguły MACD")
        
        # Wyłącz analizę spadków ceny jeśli dezaktywowana
        if 'price_drop_analysis' in config and not config['price_drop_analysis']['enabled']:
            for rule_name in ['price_drop_intraday', 'momentum_reversal']:
                if rule_name in self.rules.get('buy_rules', {}):
                    self.rules['buy_rules'][rule_name]['enabled'] = False
            logger.info("⚠️ Wyłączono reguły analizy spadków ceny")
        
        # Aktualizuj parametry weryfikacji komunikatów
        if 'news_verification' in config and config['news_verification']['enabled']:
            news_config = config['news_verification']
            logger.info(f"✓ Aktywowano weryfikację komunikatów: przedział {news_config.get('timeframe_hours', 24)}h")
        elif 'news_verification' in config and not config['news_verification']['enabled']:
            logger.info("⚠️ Wyłączono weryfikację komunikatów rynkowych")
    
    def check_market_news(self, ticker: str, timeframe_hours: int = 24) -> Dict:
        """
        Sprawdza czy pojawiły się komunikaty/news dla danej spółki w określonym przedziale czasu
        
        Args:
            ticker: Symbol spółki
            timeframe_hours: Przedział czasu w godzinach do sprawdzenia (domyślnie 24h)
            
        Returns:
            Dict z informacjami o komunikatach
        """
        try:
            from datetime import datetime, timedelta
            import re
            
            # Symulacja sprawdzenia komunikatów (w rzeczywistej implementacji można podłączyć do API news)
            # Na razie zwrócimy przykładowe dane
            
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(hours=timeframe_hours)
            
            # Symulacja komunikatów (można zastąpić prawdziwym API)
            news_analysis = {
                'has_news': False,
                'news_count': 0,
                'latest_news_time': None,
                'sentiment_score': 0.0,  # -1.0 to 1.0 (negatywny do pozytywny)
                'news_impact': 'neutral',  # 'positive', 'negative', 'neutral'
                'news_titles': [],
                'timeframe_hours': timeframe_hours
            }
            
            # Przykładowa logika - sprawdź czy są jakieś komunikaty w symulowanej bazie
            # W rzeczywistej implementacji tutaj byłoby API do serwisu news
            
            # Symulacja dla niektórych spółek
            simulated_news = {
                'PKN': {
                    'has_news': True,
                    'news_count': 2,
                    'sentiment_score': 0.3,
                    'news_impact': 'positive',
                    'news_titles': ['PKN Orlen prezentuje wyniki finansowe', 'Nowe inwestycje w sektor petrochemiczny']
                },
                'PZU': {
                    'has_news': True,
                    'news_count': 1,
                    'sentiment_score': -0.2,
                    'news_impact': 'negative',
                    'news_titles': ['PZU obniża prognozy na 2025 rok']
                },
                'CDR': {
                    'has_news': False,
                    'news_count': 0,
                    'sentiment_score': 0.0,
                    'news_impact': 'neutral',
                    'news_titles': []
                }
            }
            
            if ticker in simulated_news:
                ticker_news = simulated_news[ticker]
                news_analysis.update(ticker_news)
                if news_analysis['has_news']:
                    news_analysis['latest_news_time'] = current_time - timedelta(hours=2)  # Symulacja - 2h temu
                    
            logger.info(f"📰 Sprawdzono komunikaty dla {ticker}: {news_analysis['news_count']} komunikatów, wpływ: {news_analysis['news_impact']}")
            return news_analysis
            
        except Exception as e:
            logger.error(f"❌ Błąd podczas sprawdzania komunikatów dla {ticker}: {e}")
            return {
                'has_news': False,
                'news_count': 0,
                'latest_news_time': None,
                'sentiment_score': 0.0,
                'news_impact': 'neutral',
                'news_titles': [],
                'timeframe_hours': timeframe_hours,
                'error': str(e)
            }
    
    def evaluate_news_impact(self, news_data: Dict, config: Dict) -> Tuple[float, str]:
        """
        Ocenia wpływ komunikatów na decyzję inwestycyjną
        
        Args:
            news_data: Dane o komunikatach z check_market_news
            config: Konfiguracja weryfikacji komunikatów
            
        Returns:
            Tuple[confidence_modifier, recommendation_note]
        """
        try:
            if not config.get('enabled', False):
                return 0.0, ""
                
            confidence_modifier = 0.0
            recommendation_note = ""
            
            # Sprawdź czy są komunikaty w wymaganym przedziale czasu
            require_news = config.get('require_news_presence', False)
            avoid_news = config.get('avoid_recent_news', False)
            
            if require_news and not news_data['has_news']:
                confidence_modifier = -1.0  # Brak komunikatów obniża pewność
                recommendation_note = "Brak komunikatów rynkowych"
                
            elif avoid_news and news_data['has_news']:
                confidence_modifier = -0.5  # Obecność komunikatów obniża pewność
                recommendation_note = f"Wykryto {news_data['news_count']} komunikatów - zwiększone ryzyko"
                
            elif news_data['has_news']:
                # Uwzględnij sentyment komunikatów
                sentiment_score = news_data.get('sentiment_score', 0.0)
                
                if sentiment_score > 0.2:
                    confidence_modifier = 0.3  # Pozytywne komunikaty
                    recommendation_note = "Pozytywne komunikaty rynkowe"
                elif sentiment_score < -0.2:
                    confidence_modifier = -0.3  # Negatywne komunikaty
                    recommendation_note = "Negatywne komunikaty rynkowe"
                else:
                    confidence_modifier = 0.1  # Neutralne komunikaty
                    recommendation_note = "Neutralne komunikaty rynkowe"
                    
            return confidence_modifier, recommendation_note
            
        except Exception as e:
            logger.error(f"❌ Błąd podczas oceny wpływu komunikatów: {e}")
            return 0.0, f"Błąd analizy komunikatów: {str(e)}"
    
    def auto_evaluate_recommendations(self) -> Dict:
        """
        Automatycznie ocenia wszystkie aktywne rekomendacje
        Używa nowego systemu wielogodzinnej oceny
        
        Returns:
            Wyniki automatycznej oceny
        """
        if not self.recommendation_tracker:
            logger.warning("⚠️ Tracker rekomendacji nie jest dostępny")
            return {'error': 'Tracker not available'}
        
        try:
            # Najpierw uruchom wielogodzinne oceny
            results = self.recommendation_tracker.auto_evaluate_active_recommendations()
            
            eval_count = results.get('evaluated_count', 0)
            multi_hour_count = results.get('multi_hour_results', {}).get('total_evaluations', 0)
            
            logger.info(f"🔄 Oceniono {eval_count} rekomendacji automatycznie")
            logger.info(f"   📊 W tym {multi_hour_count} ocen wielogodzinnych")
            
            # Dodatkowe informacje o optymalnych momentach sprzedaży
            if multi_hour_count > 0:
                try:
                    optimal_analysis = self.recommendation_tracker.get_optimal_exit_analysis(days_back=7)
                    if 'recommendations' in optimal_analysis:
                        best_hour = optimal_analysis['recommendations'].get('best_profit_hour', {})
                        if best_hour:
                            logger.info(f"💡 Optymalny czas sprzedaży: {best_hour.get('hour', 'N/A')}h (średnio {best_hour.get('avg_profit', 0):.2f}%)")
                except Exception as e:
                    logger.debug(f"Nie można pobrać analizy optymalnych wyjść: {e}")
            
            return results
        except Exception as e:
            logger.error(f"❌ Błąd automatycznej oceny rekomendacji: {e}")
            return {'error': str(e)}
    
    def get_tracking_stats(self, days_back: int = 7) -> Dict:
        """
        Pobiera statystyki skuteczności rekomendacji
        
        Args:
            days_back: Liczba dni wstecz do analizy
            
        Returns:
            Słownik ze statystykami
        """
        if not self.recommendation_tracker:
            return {'error': 'Tracker not available'}
        
        try:
            stats = self.recommendation_tracker.get_performance_stats(days_back)
            best_configs = self.recommendation_tracker.get_best_configurations(3)
            
            return {
                'daily_stats': stats,
                'best_configurations': best_configs,
                'tracking_enabled': True
            }
        except Exception as e:
            logger.error(f"❌ Błąd pobierania statystyk trackingu: {e}")
            return {'error': str(e)}

    def schedule_auto_evaluation(self, interval_minutes: int = 60) -> bool:
        """
        Ustawia automatyczną ocenę rekomendacji co określony interwał
        
        Args:
            interval_minutes: Interwał w minutach między oceną
            
        Returns:
            True jeśli harmonogram został ustawiony
        """
        try:
            import threading
            import time
            
            def auto_eval_loop():
                """Pętla automatycznej oceny"""
                while True:
                    try:
                        # Czekaj określony interwał
                        time.sleep(interval_minutes * 60)
                        
                        # Uruchom automatyczną ocenę tylko w godzinach notowań lub tuż po nich
                        current_hour = datetime.now().hour
                        if 9 <= current_hour <= 18:  # Podczas i tuż po sesji
                            logger.info(f"🔄 Automatyczna ocena rekomendacji (co {interval_minutes}min)")
                            results = self.auto_evaluate_recommendations()
                            eval_count = results.get('evaluated_count', 0)
                            if eval_count > 0:
                                logger.info(f"✅ Automatycznie oceniono {eval_count} rekomendacji")
                        else:
                            logger.debug(f"⏰ Pomijam automatyczną ocenę poza godzinami notowań ({current_hour}:00)")
                            
                    except Exception as e:
                        logger.error(f"❌ Błąd w automatycznej ocenie: {e}")
                        time.sleep(60)  # Krótka przerwa przed ponowną próbą
            
            # Uruchom w osobnym wątku
            eval_thread = threading.Thread(target=auto_eval_loop, daemon=True)
            eval_thread.start()
            
            logger.info(f"✅ Ustawiono automatyczną ocenę rekomendacji co {interval_minutes} minut")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd ustawienia automatycznej oceny: {e}")
            return False

    def run_background_evaluation(self) -> None:
        """
        Uruchamia jednorazową automatyczną ocenę w tle (np. z crona)
        Metoda przystosowana do uruchamiania z zewnątrz (cron, scheduler)
        """
        try:
            logger.info("🔄 Uruchomiono jednorazową automatyczną ocenę rekomendacji")
            
            # Sprawdź czy to odpowiedni czas (tylko w godzinach notowań lub tuż po)
            current_hour = datetime.now().hour
            if not (9 <= current_hour <= 18):
                logger.info(f"⏰ Pomijam ocenę poza godzinami notowań ({current_hour}:00)")
                return
            
            # Uruchom automatyczną ocenę
            results = self.auto_evaluate_recommendations()
            eval_count = results.get('evaluated_count', 0)
            
            if eval_count > 0:
                success_count = results.get('success_count', 0)
                success_rate = (success_count / eval_count * 100) if eval_count > 0 else 0
                
                logger.info(f"✅ Jednorazowa ocena zakończona:")
                logger.info(f"   📊 Oceniono: {eval_count} rekomendacji")
                logger.info(f"   🎯 Skuteczność: {success_rate:.1f}%")
                
                # Aktualizuj statystyki dzienne
                if self.recommendation_tracker and hasattr(self.recommendation_tracker, 'update_daily_stats'):
                    self.recommendation_tracker.update_daily_stats()
                    logger.info("📈 Zaktualizowano statystyki dzienne")
            else:
                logger.info("ℹ️ Brak rekomendacji do oceny")
                
        except Exception as e:
            logger.error(f"❌ Błąd jednorazowej automatycznej oceny: {e}")
    
    def send_recommendation_notification(self, ticker: str, recommendation: str, analysis_result: Dict) -> bool:
        """
        Wysyła powiadomienie Telegram o nowej rekomendacji intraday
        
        Args:
            ticker: Symbol spółki
            recommendation: Typ rekomendacji (BUY/SELL)
            analysis_result: Wynik analizy intraday
            
        Returns:
            True jeśli powiadomienie zostało wysłane
        """
        if not self.telegram_manager:
            return False
            
        try:
            # Przygotuj dane dla powiadomienia
            current_price = analysis_result.get('technical_analysis', {}).get('current_price', 0)
            buy_confidence = analysis_result.get('buy_analysis', {}).get('total_confidence', 0)
            sell_confidence = analysis_result.get('sell_analysis', {}).get('total_confidence', 0)
            
            # Pobierz główne sygnały
            main_signals = []
            if recommendation == 'BUY':
                signals = analysis_result.get('buy_analysis', {}).get('signals', [])
                main_signals = [s.get('name', s.get('rule', 'Sygnał')) for s in signals[:3]]
            elif recommendation == 'SELL':
                signals = analysis_result.get('sell_analysis', {}).get('signals', [])
                main_signals = [s.get('name', s.get('rule', 'Sygnał')) for s in signals[:3]]
            
            # Utwórz wiadomość
            icon = "⚡🟢" if recommendation == 'BUY' else "⚡🔴"
            confidence = buy_confidence if recommendation == 'BUY' else sell_confidence
            
            message = f"{icon} REKOMENDACJA INTRADAY\n\n"
            message += f"📈 Spółka: {ticker}\n"
            message += f"💡 Akcja: {recommendation}\n"
            message += f"💰 Cena: {current_price:.2f} PLN\n"
            message += f"🎯 Pewność: {confidence:.1f}\n"
            message += f"⏰ Czas: {datetime.now().strftime('%H:%M:%S')}\n\n"
            
            if main_signals:
                message += "📊 Główne sygnały:\n"
                for signal in main_signals:
                    message += f"  • {signal}\n"
            
            # Dodaj target i stop loss jeśli dostępne
            if analysis_result.get('target_price'):
                message += f"\n🎯 Target: {analysis_result['target_price']:.2f} PLN"
            if analysis_result.get('stop_loss'):
                message += f"\n🛑 Stop Loss: {analysis_result['stop_loss']:.2f} PLN"
            
            message += f"\n\n💡 Trading intraday - max 3h"
            
            # Wyślij powiadomienie
            chat_id = self.telegram_manager.default_chat_id
            if not chat_id:
                logger.warning("⚠️ Brak domyślnego chat_id dla powiadomień")
                return False
                
            success = self.telegram_manager.send_message(
                chat_id=chat_id,
                message=message,
                title=f'Rekomendacja Intraday - {ticker}',
                notification_type='intraday_recommendation',
                ticker=ticker,
                metadata={'confidence': confidence, 'recommendation': recommendation}
            )
            
            if success:
                logger.info(f"✅ Wysłano powiadomienie Telegram: {ticker} {recommendation}")
            else:
                logger.warning(f"⚠️ Nie udało się wysłać powiadomienia: {ticker} {recommendation}")
                
            return success
            
        except Exception as e:
            logger.error(f"❌ Błąd wysyłania powiadomienia Telegram: {e}")
            return False
    
    def send_scan_summary_notification(self, scan_results: List[Dict], scan_config: Optional[Dict] = None) -> bool:
        """
        Wysyła powiadomienie z podsumowaniem skanowania intraday
        
        Args:
            scan_results: Lista wyników skanowania
            scan_config: Konfiguracja skanowania
            
        Returns:
            True jeśli powiadomienie zostało wysłane
        """
        if not self.telegram_manager or not scan_results:
            return False
            
        try:
            # Filtruj tylko rekomendacje BUY i SELL
            recommendations = [
                r for r in scan_results 
                if r.get('final_recommendation', r.get('recommendation')) in ['BUY', 'SELL']
            ]
            
            if not recommendations:
                return False
            
            buy_count = len([r for r in recommendations if r.get('final_recommendation', r.get('recommendation')) == 'BUY'])
            sell_count = len([r for r in recommendations if r.get('final_recommendation', r.get('recommendation')) == 'SELL'])
            
            # Utwórz wiadomość podsumowania
            message = f"📊 SKANOWANIE INTRADAY - PODSUMOWANIE\n\n"
            message += f"🕐 Czas: {datetime.now().strftime('%H:%M:%S')}\n"
            message += f"📈 Znalezione okazje: {len(recommendations)}\n"
            message += f"🟢 Sygnały BUY: {buy_count}\n"
            message += f"🔴 Sygnały SELL: {sell_count}\n\n"
            
            # Top 5 najlepszych okazji
            top_recommendations = sorted(
                recommendations, 
                key=lambda x: max(
                    x.get('buy_analysis', {}).get('total_confidence', 0),
                    x.get('sell_analysis', {}).get('total_confidence', 0)
                ), 
                reverse=True
            )[:5]
            
            if top_recommendations:
                message += "🏆 TOP OKAZJE:\n"
                for i, rec in enumerate(top_recommendations, 1):
                    ticker = rec['ticker']
                    recommendation = rec.get('final_recommendation', rec.get('recommendation'))
                    price = rec.get('technical_analysis', {}).get('current_price', 0)
                    confidence = max(
                        rec.get('buy_analysis', {}).get('total_confidence', 0),
                        rec.get('sell_analysis', {}).get('total_confidence', 0)
                    )
                    
                    icon = "🟢" if recommendation == 'BUY' else "🔴"
                    message += f"{i}. {icon} {ticker} - {recommendation} @ {price:.2f} (🎯{confidence:.1f})\n"
            
            # Dodaj informacje o konfiguracji jeśli dostępne
            if scan_config:
                workers = scan_config.get('max_workers', 5)
                message += f"\n⚙️ Wątki: {workers} | Skanowane: {len(scan_results)} spółek"
            
            # Wyślij powiadomienie
            chat_id = self.telegram_manager.default_chat_id
            if not chat_id:
                logger.warning("⚠️ Brak domyślnego chat_id dla powiadomień")
                return False
                
            success = self.telegram_manager.send_message(
                chat_id=chat_id,
                message=message,
                title='Skanowanie Intraday - Podsumowanie',
                notification_type='intraday_scan_summary',
                metadata={
                    'total_recommendations': len(recommendations),
                    'buy_count': buy_count,
                    'sell_count': sell_count
                }
            )
            
            if success:
                logger.info(f"✅ Wysłano podsumowanie skanowania: {len(recommendations)} okazji")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Błąd wysyłania podsumowania skanowania: {e}")
            return False
def main():
    """Funkcja testowa"""
    engine = IntradayRecommendationEngine()
    
    # Test analizy
    result = engine.analyze_ticker_intraday("CDR")
    print("=== WYNIK ANALIZY INTRADAY ===")
    print(f"Ticker: {result['ticker']}")
    print(f"Rekomendacja: {result.get('recommendation', result.get('final_recommendation', 'N/A'))}")
    
    if 'buy_analysis' in result:
        print(f"Sygnały kupna: {result['buy_analysis']['signal_count']}")
        print(f"Sygnały sprzedaży: {result['sell_analysis']['signal_count']}")
    else:
        print(f"Status: {result.get('error', 'Brak błędu')}")
    
    # Test z pozycją (tylko jeśli w godzinach notowań)
    if result.get('recommendation') != 'WAIT':
        entry_price = 28.50
        entry_time = datetime.now() - timedelta(hours=2)
        result_with_position = engine.analyze_ticker_intraday("CDR", entry_price, entry_time)
        print("\n=== WYNIK Z POZYCJĄ ===")
        print(f"Rekomendacja: {result_with_position.get('recommendation', result_with_position.get('final_recommendation', 'N/A'))}")
        if result_with_position.get('profit_loss'):
            print(f"P&L: {result_with_position['profit_loss']:.2f}%")
    
    # Test skanowania równoległego
    print("\n=== TEST SKANOWANIA RÓWNOLEGŁEGO ===")
    test_tickers = ['CDR', 'PKN', 'ALE']
    print(f"Testowanie skanowania dla: {test_tickers}")
    
    # Symuluj godziny notowań dla testu
    original_is_trading_hours = engine.is_trading_hours
    engine.is_trading_hours = lambda: True  # Force trading hours dla testu
    
    scan_results = engine.scan_market_intraday(test_tickers, max_workers=2)
    print(f"✅ Wyniki skanowania: {len(scan_results)} spółek")
    
    for result in scan_results[:3]:
        rec = result.get('final_recommendation', result.get('recommendation', 'N/A'))
        print(f"- {result['ticker']}: {rec}")
    
    # Przywróć oryginalną funkcję
    engine.is_trading_hours = original_is_trading_hours
    
    print("\n=== TEST TOP OPPORTUNITIES ===")
    # Test funkcji top opportunities (też z wymuszonym trading hours)
    engine.is_trading_hours = lambda: True
    top_opps = engine.get_top_intraday_opportunities(limit=5)
    print(f"✅ Top opportunities: {len(top_opps)} okazji")
    
    for opp in top_opps[:3]:
        rec = opp.get('final_recommendation', opp.get('recommendation', 'N/A'))
        print(f"- {opp['ticker']}: {rec}")
    
    # Przywróć
    engine.is_trading_hours = original_is_trading_hours

if __name__ == "__main__":
    main()
