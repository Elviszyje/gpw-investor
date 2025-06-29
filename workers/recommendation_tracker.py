#!/usr/bin/env python3
"""
Tracker rekomendacji GPW Investor - PostgreSQL Version
Zapisuje, śledzi i ocenia skuteczność rekomendacji intraday w PostgreSQL
Autor: GPW Investor System
Data: 2025-06-27
"""

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import pandas as pd

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RecommendationTracker:
    """Klasa do śledzenia i oceny rekomendacji intraday w PostgreSQL"""
    
    def __init__(self):
        """
        Inicjalizacja trackera rekomendacji
        """
        # Konfiguracja PostgreSQL
        load_dotenv('.env')
        
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_name = os.getenv('DB_NAME')
        
        db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        self.engine = create_engine(db_uri)
        
        self._init_database()
        logger.info(f"✓ RecommendationTracker zainicjalizowany (PostgreSQL)")
    
    def _init_database(self):
        """Inicjalizuje bazę danych i tworzy tabele"""
        try:
            with self.engine.begin() as conn:
                # Tabela rekomendacji
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS recommendations (
                        id SERIAL PRIMARY KEY,
                        ticker VARCHAR(20) NOT NULL,
                        recommendation VARCHAR(20) NOT NULL,
                        entry_price DECIMAL(10,2) NOT NULL,
                        target_price DECIMAL(10,2),
                        stop_loss DECIMAL(10,2),
                        buy_confidence DECIMAL(5,2) DEFAULT 0.0,
                        sell_confidence DECIMAL(5,2) DEFAULT 0.0,
                        signal_count INTEGER DEFAULT 0,
                        signals_data JSONB,
                        config_data JSONB,
                        news_impact DECIMAL(5,2) DEFAULT 0.0,
                        news_data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        session_date DATE,
                        status VARCHAR(20) DEFAULT 'ACTIVE',
                        notes TEXT
                    )
                '''))
                
                # Tabela oceny skuteczności
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS recommendation_results (
                        id SERIAL PRIMARY KEY,
                        recommendation_id INTEGER NOT NULL,
                        ticker VARCHAR(20) NOT NULL,
                        original_recommendation VARCHAR(20) NOT NULL,
                        entry_price DECIMAL(10,2) NOT NULL,
                        exit_price DECIMAL(10,2),
                        entry_time TIMESTAMP NOT NULL,
                        exit_time TIMESTAMP,
                        duration_minutes INTEGER,
                        profit_loss_percent DECIMAL(8,4),
                        profit_loss_amount DECIMAL(10,2),
                        max_profit_percent DECIMAL(8,4) DEFAULT 0.0,
                        max_loss_percent DECIMAL(8,4) DEFAULT 0.0,
                        status VARCHAR(20) DEFAULT 'OPEN',
                        exit_reason TEXT,
                        success BOOLEAN,
                        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (recommendation_id) REFERENCES recommendations (id)
                    )
                '''))
                
                # Tabela wielokrotnych ocen w czasie
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS recommendation_time_evaluations (
                        id SERIAL PRIMARY KEY,
                        recommendation_id INTEGER NOT NULL,
                        ticker VARCHAR(20) NOT NULL,
                        evaluation_hour INTEGER NOT NULL,
                        price_at_evaluation DECIMAL(10,2) NOT NULL,
                        profit_loss_percent DECIMAL(8,4) NOT NULL,
                        profit_loss_amount DECIMAL(10,2) NOT NULL,
                        is_optimal_exit BOOLEAN DEFAULT FALSE,
                        volume_at_evaluation BIGINT DEFAULT 0,
                        rsi_at_evaluation DECIMAL(5,2),
                        evaluation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        market_conditions JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (recommendation_id) REFERENCES recommendations (id),
                        UNIQUE(recommendation_id, evaluation_hour)
                    )
                '''))
                
                # Tabela statystyk
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS performance_stats (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL,
                        total_recommendations INTEGER DEFAULT 0,
                        successful_recommendations INTEGER DEFAULT 0,
                        failed_recommendations INTEGER DEFAULT 0,
                        success_rate DECIMAL(5,2) DEFAULT 0.0,
                        avg_profit_percent DECIMAL(8,4) DEFAULT 0.0,
                        avg_loss_percent DECIMAL(8,4) DEFAULT 0.0,
                        total_profit_loss DECIMAL(10,2) DEFAULT 0.0,
                        best_recommendation_profit DECIMAL(8,4) DEFAULT 0.0,
                        worst_recommendation_loss DECIMAL(8,4) DEFAULT 0.0,
                        avg_duration_minutes INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(date)
                    )
                '''))
                
                # Indeksy dla wydajności
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_recommendations_ticker ON recommendations(ticker)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_recommendations_date ON recommendations(session_date)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_recommendations_status ON recommendations(status)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_results_recommendation_id ON recommendation_results(recommendation_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_results_status ON recommendation_results(status)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_time_evals_recommendation_id ON recommendation_time_evaluations(recommendation_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_time_evals_hour ON recommendation_time_evaluations(evaluation_hour)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_time_evals_ticker ON recommendation_time_evaluations(ticker)'))
                
                logger.info("✓ Baza danych rekomendacji zainicjalizowana (PostgreSQL)")
                
        except Exception as e:
            logger.error(f"❌ Błąd inicjalizacji bazy danych: {e}")
            raise
    
    def save_recommendation(self, ticker: str, analysis_result: Dict, config: Optional[Dict] = None) -> int:
        """
        Zapisuje nową rekomendację do bazy danych PostgreSQL
        
        Args:
            ticker: Symbol spółki
            analysis_result: Wynik analizy z silnika rekomendacji
            config: Konfiguracja użyta do analizy
            
        Returns:
            ID zapisanej rekomendacji
        """
        try:
            with self.engine.begin() as conn:
                # Przygotuj dane do zapisu
                recommendation = analysis_result.get('final_recommendation', analysis_result.get('recommendation', 'WAIT'))
                entry_price = analysis_result.get('current_price', 0.0)
                
                buy_analysis = analysis_result.get('buy_analysis', {})
                sell_analysis = analysis_result.get('sell_analysis', {})
                
                buy_confidence = buy_analysis.get('total_confidence', 0.0)
                sell_confidence = sell_analysis.get('total_confidence', 0.0)
                signal_count = buy_analysis.get('signal_count', 0) + sell_analysis.get('signal_count', 0)
                
                # Serialize complex data
                signals_data = {
                    'buy_signals': buy_analysis.get('signals', []),
                    'sell_signals': sell_analysis.get('signals', []),
                    'technical_analysis': analysis_result.get('technical_analysis', {})
                }
                
                config_data = config or {}
                
                # News impact data
                news_impact = 0.0
                news_data = {}
                for signal in buy_analysis.get('signals', []):
                    if signal.get('signal') == 'news_impact':
                        news_impact = signal.get('confidence', 0.0)
                        news_data = {
                            'description': signal.get('description', ''),
                            'source': signal.get('source', '')
                        }
                        break
                
                # Oblicz target price i stop loss na podstawie rekomendacji
                target_price = None
                stop_loss = None
                if recommendation == 'BUY':
                    target_price = round(entry_price * 1.05, 2)  # 5% zysk
                    stop_loss = round(entry_price * 0.98, 2)     # 2% strata
                elif recommendation == 'SELL':
                    target_price = round(entry_price * 0.95, 2)  # 5% profit na short
                    stop_loss = round(entry_price * 1.02, 2)     # 2% strata na short
                
                # Wstaw rekomendację
                query = text("""
                    INSERT INTO recommendations (
                        ticker, recommendation, entry_price, target_price, stop_loss,
                        buy_confidence, sell_confidence, signal_count,
                        signals_data, config_data, news_impact, news_data,
                        session_date, status
                    ) VALUES (
                        :ticker, :recommendation, :entry_price, :target_price, :stop_loss,
                        :buy_confidence, :sell_confidence, :signal_count,
                        :signals_data, :config_data, :news_impact, :news_data,
                        :session_date, :status
                    ) RETURNING id
                """)
                
                result = conn.execute(query, {
                    'ticker': ticker,
                    'recommendation': recommendation,
                    'entry_price': entry_price,
                    'target_price': target_price,
                    'stop_loss': stop_loss,
                    'buy_confidence': buy_confidence,
                    'sell_confidence': sell_confidence,
                    'signal_count': signal_count,
                    'signals_data': json.dumps(signals_data, default=json_serial),
                    'config_data': json.dumps(config_data, default=json_serial),
                    'news_impact': news_impact,
                    'news_data': json.dumps(news_data, default=json_serial),
                    'session_date': datetime.now().date(),
                    'status': 'ACTIVE'
                })
                
                row = result.fetchone()
                recommendation_id = row[0] if row else -1
                
                logger.info(f"✅ Zapisano rekomendację #{recommendation_id}: {ticker} {recommendation} @ {entry_price}")
                return recommendation_id
                
        except Exception as e:
            logger.error(f"❌ Błąd zapisu rekomendacji: {e}")
            return -1
                target_price = None
                stop_loss = None
                
                if recommendation == 'BUY':
                    target_price = entry_price * 1.015  # 1.5% zysk intraday
                    stop_loss = entry_price * 0.985    # 1.5% strata
                elif recommendation == 'SELL':
                    target_price = entry_price * 0.985  # 1.5% zysk na short
                    stop_loss = entry_price * 1.015    # 1.5% strata na short
                
                # Wstaw do bazy
                cursor.execute('''
                    INSERT INTO recommendations (
                        ticker, recommendation, entry_price, target_price, stop_loss,
                        buy_confidence, sell_confidence, signal_count, signals_data,
                        config_data, news_impact, news_data, session_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ticker, recommendation, entry_price, target_price, stop_loss,
                    buy_confidence, sell_confidence, signal_count, signals_data,
                    config_data, news_impact, news_data, datetime.now().date()
                ))
                
                recommendation_id = cursor.lastrowid or -1
                conn.commit()
                
                logger.info(f"✓ Zapisano rekomendację #{recommendation_id}: {ticker} {recommendation} @ {entry_price:.2f}")
                return recommendation_id
                
        except Exception as e:
            logger.error(f"❌ Błąd zapisywania rekomendacji dla {ticker}: {e}")
            return -1
    
    def get_active_recommendations(self, max_age_hours: int = 8) -> List[Dict]:
        """
        Pobiera aktywne rekomendacje do śledzenia
        
        Args:
            max_age_hours: Maksymalny wiek rekomendacji w godzinach
            
        Returns:
            Lista aktywnych rekomendacji
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
                
                cursor.execute('''
                    SELECT r.*, rr.status as result_status
                    FROM recommendations r
                    LEFT JOIN recommendation_results rr ON r.id = rr.recommendation_id
                    WHERE r.status = 'ACTIVE' 
                    AND r.created_at >= ?
                    AND (rr.status IS NULL OR rr.status = 'OPEN')
                    ORDER BY r.created_at DESC
                ''', (cutoff_time,))
                
                columns = [description[0] for description in cursor.description]
                recommendations = []
                
                for row in cursor.fetchall():
                    rec_dict = dict(zip(columns, row))
                    
                    # Deserialize JSON data
                    try:
                        rec_dict['signals_data'] = json.loads(rec_dict['signals_data'] or '{}')
                        rec_dict['config_data'] = json.loads(rec_dict['config_data'] or '{}')
                        rec_dict['news_data'] = json.loads(rec_dict['news_data'] or '{}')
                    except:
                        pass
                        
                    recommendations.append(rec_dict)
                
                logger.info(f"✓ Pobrano {len(recommendations)} aktywnych rekomendacji")
                return recommendations
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania aktywnych rekomendacji: {e}")
            return []
    
    def evaluate_recommendation(self, recommendation_id: int, current_price: float, 
                               exit_reason: Optional[str] = None) -> Dict:
        """
        Ocenia skuteczność rekomendacji na podstawie aktualnej ceny
        
        Args:
            recommendation_id: ID rekomendacji do oceny
            current_price: Aktualna cena spółki
            exit_reason: Powód zamknięcia pozycji (opcjonalny)
            
        Returns:
            Słownik z wynikami oceny
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Pobierz dane rekomendacji
                cursor.execute('''
                    SELECT * FROM recommendations WHERE id = ?
                ''', (recommendation_id,))
                
                rec = cursor.fetchone()
                if not rec:
                    logger.warning(f"❌ Nie znaleziono rekomendacji #{recommendation_id}")
                    return {}
                
                columns = [description[0] for description in cursor.description]
                recommendation = dict(zip(columns, rec))
                
                entry_price = recommendation['entry_price']
                entry_time = datetime.fromisoformat(recommendation['created_at'])
                current_time = datetime.now()
                
                # Oblicz wyniki
                duration_minutes = int((current_time - entry_time).total_seconds() / 60)
                
                if recommendation['recommendation'] == 'BUY':
                    profit_loss_percent = ((current_price - entry_price) / entry_price) * 100
                elif recommendation['recommendation'] == 'SELL':
                    profit_loss_percent = ((entry_price - current_price) / entry_price) * 100
                else:
                    profit_loss_percent = 0.0
                
                # Sprawdź czy to sukces (osiągnięto target lub przekroczono czas)
                success = False
                status = 'OPEN'
                
                if recommendation['recommendation'] in ['BUY', 'SELL']:
                    target_reached = (
                        (recommendation['recommendation'] == 'BUY' and current_price >= recommendation['target_price']) or
                        (recommendation['recommendation'] == 'SELL' and current_price <= recommendation['target_price'])
                    )
                    
                    stop_loss_hit = (
                        (recommendation['recommendation'] == 'BUY' and current_price <= recommendation['stop_loss']) or
                        (recommendation['recommendation'] == 'SELL' and current_price >= recommendation['stop_loss'])
                    )
                    
                    if target_reached:
                        success = True
                        status = 'CLOSED'
                        exit_reason = exit_reason or 'TARGET_REACHED'
                    elif stop_loss_hit:
                        success = False
                        status = 'CLOSED'
                        exit_reason = exit_reason or 'STOP_LOSS'
                    elif duration_minutes > 480:  # 8 godzin - koniec sesji
                        success = profit_loss_percent > 0
                        status = 'CLOSED'
                        exit_reason = exit_reason or 'SESSION_END'
                
                # Zapisz lub zaktualizuj wynik
                cursor.execute('''
                    INSERT OR REPLACE INTO recommendation_results (
                        recommendation_id, ticker, original_recommendation,
                        entry_price, exit_price, entry_time, exit_time,
                        duration_minutes, profit_loss_percent,
                        status, exit_reason, success
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    recommendation_id, recommendation['ticker'], recommendation['recommendation'],
                    entry_price, current_price, entry_time, current_time,
                    duration_minutes, profit_loss_percent,
                    status, exit_reason, success
                ))
                
                # Zaktualizuj status rekomendacji jeśli zamknięta
                if status == 'CLOSED':
                    cursor.execute('''
                        UPDATE recommendations SET status = 'CLOSED' WHERE id = ?
                    ''', (recommendation_id,))
                
                conn.commit()
                
                result = {
                    'recommendation_id': recommendation_id,
                    'ticker': recommendation['ticker'],
                    'recommendation': recommendation['recommendation'],
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'profit_loss_percent': profit_loss_percent,
                    'duration_minutes': duration_minutes,
                    'status': status,
                    'success': success,
                    'exit_reason': exit_reason
                }
                
                logger.info(f"✓ Oceniono rekomendację #{recommendation_id}: {recommendation['ticker']} "
                           f"{profit_loss_percent:+.2f}% ({status})")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Błąd oceny rekomendacji #{recommendation_id}: {e}")
            return {}
    
    def auto_evaluate_active_recommendations(self) -> Dict:
        """
        Automatycznie ocenia wszystkie aktywne rekomendacje
        Używa nowego systemu wielogodzinnej oceny
        
        Returns:
            Słownik z podsumowaniem oceny
        """
        logger.info("🔄 Rozpoczynam automatyczną ocenę aktywnych rekomendacji...")
        
        # Użyj nowego systemu wielogodzinnej oceny
        multi_hour_results = self.auto_evaluate_active_recommendations_multi_hour()
        
        if 'error' in multi_hour_results:
            logger.error(f"❌ Błąd wielogodzinnej oceny: {multi_hour_results['error']}")
            return multi_hour_results
        
        total_evaluations = multi_hour_results.get('total_evaluations', 0)
        
        if total_evaluations == 0:
            logger.info("ℹ️ Brak rekomendacji do oceny w żadnym interwale czasowym")
            
            # Sprawdź czy są stare rekomendacje do zamknięcia
            active_recommendations = self.get_active_recommendations()
            if not active_recommendations:
                return {'evaluated_count': 0, 'results': []}
        
        # Dodatkowo uruchom standardową ocenę dla zamykania pozycji po 8h
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Znajdź rekomendacje starsze niż 8h które nie zostały jeszcze zamknięte
                cutoff_time = datetime.now() - timedelta(hours=8)
                cursor.execute('''
                    SELECT id, ticker, recommendation, entry_price, created_at
                    FROM recommendations 
                    WHERE status = 'ACTIVE'
                    AND created_at <= ?
                    AND recommendation IN ('BUY', 'SELL')
                ''', (cutoff_time,))
                
                old_recommendations = cursor.fetchall()
                
                closed_count = 0
                successful_closed = 0
                results = []
                
                for rec_id, ticker, recommendation, entry_price, created_at in old_recommendations:
                    try:
                        # Pobierz aktualną cenę dla finalnego zamknięcia
                        from workers.technical_analysis import TechnicalAnalyzer
                        analyzer = TechnicalAnalyzer()
                        analysis = analyzer.analyze_ticker(ticker, days_back=5)
                        
                        if analysis and 'current_price' in analysis:
                            current_price = analysis['current_price']
                            
                            # Oceń finalnie rekomendację
                            result = self.evaluate_recommendation(rec_id, current_price, 'SESSION_END_8H')
                            
                            if result:
                                results.append(result)
                                closed_count += 1
                                if result.get('success', False):
                                    successful_closed += 1
                                    
                    except Exception as e:
                        logger.error(f"❌ Błąd zamykania rekomendacji {rec_id}: {e}")
                        continue
                
                # Zaktualizuj statystyki dzienne
                self.update_daily_stats()
                
                logger.info(f"✅ Oceniono {total_evaluations} w interwałach + zamknięto {closed_count} starych rekomendacji")
                
                return {
                    'evaluated_count': total_evaluations + closed_count,
                    'successful_count': successful_closed,
                    'failed_count': closed_count - successful_closed,
                    'success_rate': successful_closed / closed_count if closed_count > 0 else 0,
                    'closed_old_recommendations': closed_count,
                    'multi_hour_results': multi_hour_results,
                    'results': results
                }
                
        except Exception as e:
            logger.error(f"❌ Błąd automatycznej oceny: {e}")
            return {
                'evaluated_count': total_evaluations,
                'successful_count': 0,
                'failed_count': 0,
                'success_rate': 0,
                'multi_hour_results': multi_hour_results,
                'error': str(e)
            }
    
    def update_daily_stats(self, date: Optional[datetime] = None) -> bool:
        """
        Aktualizuje statystyki dzienne
        
        Args:
            date: Data dla której aktualizować statystyki (domyślnie dziś)
            
        Returns:
            True jeśli sukces
        """
        try:
            target_date = date.date() if date else datetime.now().date()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Pobierz statystyki z danego dnia
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_recommendations,
                        COUNT(CASE WHEN rr.success = 1 THEN 1 END) as successful_recommendations,
                        COUNT(CASE WHEN rr.success = 0 THEN 1 END) as failed_recommendations,
                        ROUND(AVG(CASE WHEN rr.success = 1 THEN rr.profit_loss_percent END), 2) as avg_profit_percent,
                        ROUND(AVG(CASE WHEN rr.success = 0 THEN rr.profit_loss_percent END), 2) as avg_loss_percent,
                        ROUND(SUM(rr.profit_loss_percent), 2) as total_profit_loss,
                        MAX(rr.profit_loss_percent) as best_recommendation_profit,
                        MIN(rr.profit_loss_percent) as worst_recommendation_loss,
                        ROUND(AVG(rr.duration_minutes)) as avg_duration_minutes
                    FROM recommendations r
                    LEFT JOIN recommendation_results rr ON r.id = rr.recommendation_id
                    WHERE r.session_date = ? AND rr.status = 'CLOSED'
                ''', (target_date,))
                
                stats = cursor.fetchone()
                
                if stats and stats[0] > 0:  # Jeśli są dane
                    total_recs = stats[0]
                    successful_recs = stats[1] or 0
                    success_rate = (successful_recs / total_recs * 100) if total_recs > 0 else 0
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO performance_stats (
                            date, total_recommendations, successful_recommendations,
                            failed_recommendations, success_rate, avg_profit_percent,
                            avg_loss_percent, total_profit_loss, best_recommendation_profit,
                            worst_recommendation_loss, avg_duration_minutes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        target_date, total_recs, successful_recs, stats[2] or 0,
                        round(success_rate, 2), stats[3] or 0.0, stats[4] or 0.0,
                        stats[5] or 0.0, stats[6] or 0.0, stats[7] or 0.0,
                        stats[8] or 0
                    ))
                    
                    conn.commit()
                    logger.info(f"✓ Zaktualizowano statystyki dzienne dla {target_date}: {total_recs} rekomendacji, "
                               f"{success_rate:.1f}% skuteczność")
                    
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd aktualizacji statystyk dziennych: {e}")
            return False
    
    def get_performance_stats(self, days_back: int = 7) -> List[Dict]:
        """
        Pobiera statystyki wydajności z ostatnich dni
        
        Args:
            days_back: Liczba dni wstecz
            
        Returns:
            Lista statystyk dziennych
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                start_date = datetime.now().date() - timedelta(days=days_back)
                
                cursor.execute('''
                    SELECT * FROM performance_stats 
                    WHERE date >= ? 
                    ORDER BY date DESC
                ''', (start_date,))
                
                columns = [description[0] for description in cursor.description]
                stats = []
                
                for row in cursor.fetchall():
                    stats.append(dict(zip(columns, row)))
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania statystyk wydajności: {e}")
            return []
    
    def get_best_configurations(self, limit: int = 5) -> List[Dict]:
        """
        Znajduje najlepsze konfiguracje na podstawie historycznych wyników
        
        Args:
            limit: Maksymalna liczba konfiguracji do zwrócenia
            
        Returns:
            Lista najlepszych konfiguracji
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        r.config_data,
                        COUNT(*) as total_count,
                        COUNT(CASE WHEN rr.success = 1 THEN 1 END) as success_count,
                        ROUND(AVG(rr.profit_loss_percent), 2) as avg_return,
                        ROUND(COUNT(CASE WHEN rr.success = 1 THEN 1 END) * 100.0 / COUNT(*), 2) as success_rate
                    FROM recommendations r
                    JOIN recommendation_results rr ON r.id = rr.recommendation_id
                    WHERE rr.status = 'CLOSED' AND r.config_data != '{}'
                    GROUP BY r.config_data
                    HAVING COUNT(*) >= 3
                    ORDER BY success_rate DESC, avg_return DESC
                    LIMIT ?
                ''', (limit,))
                
                results = []
                for row in cursor.fetchall():
                    try:
                        config_data = json.loads(row[0])
                        results.append({
                            'config': config_data,
                            'total_count': row[1],
                            'success_count': row[2],
                            'avg_return': row[3],
                            'success_rate': row[4]
                        })
                    except:
                        continue
                
                return results
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania najlepszych konfiguracji: {e}")
            return []
    
    def evaluate_recommendation_at_hour(self, recommendation_id: int, evaluation_hour: int, 
                                       current_price: float, market_data: Optional[Dict] = None) -> bool:
        """
        Zapisuje ocenę rekomendacji w określonej godzinie od jej utworzenia
        
        Args:
            recommendation_id: ID rekomendacji
            evaluation_hour: Godzina od utworzenia (1-8)
            current_price: Cena w tym momencie
            market_data: Dodatkowe dane rynkowe (volume, RSI, itp.)
            
        Returns:
            True jeśli ocena została zapisana
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Pobierz dane rekomendacji
                cursor.execute('''
                    SELECT ticker, recommendation, entry_price, created_at
                    FROM recommendations WHERE id = ?
                ''', (recommendation_id,))
                
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"❌ Nie znaleziono rekomendacji #{recommendation_id}")
                    return False
                
                ticker, recommendation, entry_price, created_at = result
                
                # Oblicz zysk/stratę
                if recommendation == 'BUY':
                    profit_loss_percent = ((current_price - entry_price) / entry_price) * 100
                elif recommendation == 'SELL':
                    profit_loss_percent = ((entry_price - current_price) / entry_price) * 100
                else:
                    profit_loss_percent = 0.0
                
                profit_loss_amount = current_price - entry_price
                
                # Przygotuj dodatkowe dane
                volume_at_evaluation = market_data.get('current_volume', 0) if market_data else 0
                rsi_at_evaluation = market_data.get('rsi') if market_data else None
                market_conditions = json.dumps({
                    'bb_position': market_data.get('bb_position') if market_data else None,
                    'macd_histogram': market_data.get('macd_histogram') if market_data else None,
                    'price_change_1d': market_data.get('price_change_1d') if market_data else None,
                    'volume_ratio': market_data.get('volume_ratio') if market_data else None
                }, default=json_serial) if market_data else '{}'
                
                # Zapisz ocenę czasową
                cursor.execute('''
                    INSERT OR REPLACE INTO recommendation_time_evaluations (
                        recommendation_id, ticker, evaluation_hour, price_at_evaluation,
                        profit_loss_percent, profit_loss_amount, volume_at_evaluation,
                        rsi_at_evaluation, market_conditions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    recommendation_id, ticker, evaluation_hour, current_price,
                    profit_loss_percent, profit_loss_amount, volume_at_evaluation,
                    rsi_at_evaluation, market_conditions
                ))
                
                conn.commit()
                
                logger.info(f"✓ Zapisano ocenę {evaluation_hour}h dla #{recommendation_id}: {ticker} {profit_loss_percent:+.2f}%")
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd zapisu oceny czasowej #{recommendation_id}: {e}")
            return False
    
    def mark_optimal_exit_points(self, recommendation_id: int) -> bool:
        """
        Analizuje wszystkie oceny czasowe i oznacza optymalny moment sprzedaży
        
        Args:
            recommendation_id: ID rekomendacji do analizy
            
        Returns:
            True jeśli analiza została wykonana
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Pobierz wszystkie oceny czasowe dla rekomendacji
                cursor.execute('''
                    SELECT id, evaluation_hour, profit_loss_percent
                    FROM recommendation_time_evaluations
                    WHERE recommendation_id = ?
                    ORDER BY evaluation_hour ASC
                ''', (recommendation_id,))
                
                evaluations = cursor.fetchall()
                if not evaluations:
                    return False
                
                # Znajdź optymalny moment sprzedaży (maksymalny zysk)
                best_evaluation = max(evaluations, key=lambda x: x[2])  # maksymalny profit_loss_percent
                best_eval_id = best_evaluation[0]
                
                # Resetuj wszystkie oznaczenia
                cursor.execute('''
                    UPDATE recommendation_time_evaluations 
                    SET is_optimal_exit = FALSE 
                    WHERE recommendation_id = ?
                ''', (recommendation_id,))
                
                # Oznacz optymalny moment
                cursor.execute('''
                    UPDATE recommendation_time_evaluations 
                    SET is_optimal_exit = TRUE 
                    WHERE id = ?
                ''', (best_eval_id,))
                
                conn.commit()
                
                optimal_hour = best_evaluation[1]
                optimal_profit = best_evaluation[2]
                logger.info(f"✓ Optymalny exit dla #{recommendation_id}: {optimal_hour}h ({optimal_profit:+.2f}%)")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd oznaczania optymalnego exit #{recommendation_id}: {e}")
            return False

    def auto_evaluate_active_recommendations_multi_hour(self) -> Dict:
        """
        Automatycznie ocenia rekomendacje w wielu interwałach czasowych (1-8h)
        
        Returns:
            Słownik z podsumowaniem oceny
        """
        try:
            from workers.technical_analysis import TechnicalAnalyzer
            analyzer = TechnicalAnalyzer()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                current_time = datetime.now()
                evaluations_made = []
                
                # Sprawdź rekomendacje dla każdej godziny (1-8h)
                for hour in range(1, 9):
                    cutoff_time = current_time - timedelta(hours=hour)
                    
                    # Znajdź rekomendacje które są właśnie w tej godzinie
                    # i jeszcze nie zostały ocenione w tym interwale
                    cursor.execute('''
                        SELECT r.id, r.ticker, r.recommendation, r.entry_price, r.created_at
                        FROM recommendations r
                        WHERE r.status = 'ACTIVE'
                        AND r.created_at <= ?
                        AND r.created_at > ?
                        AND r.recommendation IN ('BUY', 'SELL')
                        AND NOT EXISTS (
                            SELECT 1 FROM recommendation_time_evaluations rte
                            WHERE rte.recommendation_id = r.id 
                            AND rte.evaluation_hour = ?
                        )
                    ''', (cutoff_time, cutoff_time - timedelta(minutes=30), hour))
                    
                    recommendations_for_hour = cursor.fetchall()
                    
                    for rec_id, ticker, recommendation, entry_price, created_at in recommendations_for_hour:
                        try:
                            # Pobierz aktualną cenę i dane techniczne
                            analysis = analyzer.analyze_ticker(ticker, days_back=5)
                            if not analysis or 'current_price' not in analysis:
                                continue
                            
                            current_price = analysis['current_price']
                            
                            # Przygotuj dane rynkowe
                            market_data = {
                                'current_volume': analysis.get('current_volume', 0),
                                'rsi': analysis.get('rsi'),
                                'bb_position': analysis.get('bb_position'),
                                'macd_histogram': analysis.get('macd_histogram'),
                                'price_change_1d': analysis.get('price_change_1d'),
                                'volume_ratio': analysis.get('current_volume', 1) / analysis.get('avg_volume_20', 1) if analysis.get('avg_volume_20', 0) > 0 else 1
                            }
                            
                            # Zapisz ocenę czasową
                            success = self.evaluate_recommendation_at_hour(
                                rec_id, hour, current_price, market_data
                            )
                            
                            if success:
                                evaluations_made.append({
                                    'recommendation_id': rec_id,
                                    'ticker': ticker,
                                    'hour': hour,
                                    'price': current_price
                                })
                                
                                # Jeśli to już 8 godzin, oznacz optymalny exit
                                if hour == 8:
                                    self.mark_optimal_exit_points(rec_id)
                                    
                        except Exception as e:
                            logger.error(f"❌ Błąd oceny {hour}h dla {ticker}: {e}")
                            continue
                
                logger.info(f"🔄 Wielogodzinne oceny zakończone: {len(evaluations_made)} ocen")
                
                # Grupuj wyniki według godzin
                by_hour = {}
                for eval_data in evaluations_made:
                    hour = eval_data['hour']
                    if hour not in by_hour:
                        by_hour[hour] = []
                    by_hour[hour].append(eval_data)
                
                return {
                    'total_evaluations': len(evaluations_made),
                    'evaluations_by_hour': by_hour,
                    'hours_evaluated': list(by_hour.keys()),
                    'timestamp': current_time.isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Błąd wielogodzinnej automatycznej oceny: {e}")
            return {'error': str(e)}
    
    def get_optimal_exit_analysis(self, days_back: int = 30) -> Dict:
        """
        Analizuje optymalne momenty sprzedaży na podstawie historycznych danych
        
        Args:
            days_back: Liczba dni wstecz do analizy
            
        Returns:
            Słownik z analizą optymalnych czasów sprzedaży
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cutoff_date = datetime.now() - timedelta(days=days_back)
                
                # Pobierz statystyki dla każdej godziny
                cursor.execute('''
                    SELECT 
                        rte.evaluation_hour,
                        COUNT(*) as total_evaluations,
                        AVG(rte.profit_loss_percent) as avg_profit_loss,
                        MAX(rte.profit_loss_percent) as max_profit_loss,
                        MIN(rte.profit_loss_percent) as min_profit_loss,
                        COUNT(CASE WHEN rte.is_optimal_exit = 1 THEN 1 END) as optimal_exit_count,
                        COUNT(CASE WHEN rte.profit_loss_percent > 0 THEN 1 END) as profitable_count
                    FROM recommendation_time_evaluations rte
                    JOIN recommendations r ON rte.recommendation_id = r.id
                    WHERE r.created_at >= ?
                    GROUP BY rte.evaluation_hour
                    ORDER BY rte.evaluation_hour
                ''', (cutoff_date,))
                
                hourly_stats = cursor.fetchall()
                
                # Pobierz najlepsze momenty sprzedaży według typu rekomendacji
                cursor.execute('''
                    SELECT 
                        r.recommendation,
                        rte.evaluation_hour,
                        COUNT(*) as count,
                        AVG(rte.profit_loss_percent) as avg_profit
                    FROM recommendation_time_evaluations rte
                    JOIN recommendations r ON rte.recommendation_id = r.id
                    WHERE r.created_at >= ?
                    AND rte.is_optimal_exit = 1
                    GROUP BY r.recommendation, rte.evaluation_hour
                    ORDER BY r.recommendation, avg_profit DESC
                ''', (cutoff_date,))
                
                optimal_by_type = cursor.fetchall()
                
                # Przygotuj wyniki
                analysis = {
                    'period_days': days_back,
                    'hourly_performance': [],
                    'optimal_exit_patterns': {},
                    'recommendations': {},
                    'timestamp': datetime.now().isoformat()
                }
                
                # Statystyki godzinowe
                for hour, total, avg_profit, max_profit, min_profit, optimal_count, profitable_count in hourly_stats:
                    success_rate = profitable_count / total if total > 0 else 0
                    optimal_rate = optimal_count / total if total > 0 else 0
                    
                    analysis['hourly_performance'].append({
                        'hour': hour,
                        'total_evaluations': total,
                        'avg_profit_loss': avg_profit,
                        'max_profit': max_profit,
                        'min_loss': min_profit,
                        'success_rate': success_rate,
                        'optimal_exit_rate': optimal_rate,
                        'profitable_count': profitable_count
                    })
                
                # Wzorce optymalnych wyjść
                for rec_type, hour, count, avg_profit in optimal_by_type:
                    if rec_type not in analysis['optimal_exit_patterns']:
                        analysis['optimal_exit_patterns'][rec_type] = []
                    
                    analysis['optimal_exit_patterns'][rec_type].append({
                        'hour': hour,
                        'count': count,
                        'avg_profit': avg_profit
                    })
                
                # Rekomendacje na podstawie analizy
                if analysis['hourly_performance']:
                    best_hour = max(analysis['hourly_performance'], key=lambda x: x['avg_profit_loss'])
                    safest_hour = max(analysis['hourly_performance'], key=lambda x: x['success_rate'])
                    
                    analysis['recommendations'] = {
                        'best_profit_hour': {
                            'hour': best_hour['hour'],
                            'avg_profit': best_hour['avg_profit_loss'],
                            'reason': 'Najwyższy średni zysk'
                        },
                        'safest_hour': {
                            'hour': safest_hour['hour'],
                            'success_rate': safest_hour['success_rate'],
                            'reason': 'Najwyższa skuteczność'
                        }
                    }
                
                return analysis
                
        except Exception as e:
            logger.error(f"❌ Błąd analizy optymalnych wyjść: {e}")
            return {'error': str(e)}

def main():
    """Funkcja testowa"""
    tracker = RecommendationTracker("test_recommendations.db")
    
    # Test zapisywania rekomendacji
    test_analysis = {
        'ticker': 'TEST',
        'final_recommendation': 'BUY',
        'current_price': 100.0,
        'buy_analysis': {
            'total_confidence': 2.5,
            'signal_count': 3,
            'signals': [
                {'signal': 'rsi_oversold', 'confidence': 1.0},
                {'signal': 'price_drop', 'confidence': 1.2},
                {'signal': 'news_impact', 'confidence': 0.3, 'description': 'Pozytywne komunikaty'}
            ]
        },
        'sell_analysis': {
            'total_confidence': 0.5,
            'signal_count': 1,
            'signals': []
        }
    }
    
    test_config = {
        'name': 'Test Config',
        'max_workers': 5,
        'price_drop_analysis': {'enabled': True, 'threshold_percent': 2.5}
    }
    
    # Zapisz rekomendację
    rec_id = tracker.save_recommendation('TEST', test_analysis, test_config)
    print(f"✓ Zapisano rekomendację #{rec_id}")
    
    # Oceń rekomendację (symulacja wzrostu ceny o 2%)
    result = tracker.evaluate_recommendation(rec_id, 102.0, 'TEST_EVALUATION')
    print(f"✓ Wynik oceny: {result}")
    
    # Pobierz statystyki
    stats = tracker.get_performance_stats(1)
    print(f"✓ Statystyki: {stats}")
    
    print("✅ Test tracker zakończony pomyślnie")


if __name__ == "__main__":
    main()
