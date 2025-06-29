#!/usr/bin/env python3
"""
PostgreSQL Ticker Management System - Zarządzanie tickerami i integracją danych
Automatyczne dodawanie nowych tickerów i synchronizacja między danymi historycznymi a scrapingiem
Pracuje z bazą PostgreSQL
Autor: GPW Investor System
Data: 2025-06-25
"""

import logging
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import json
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TickerManager:
    """Zarządzanie tickerami i integracją danych historycznych z scrapingiem w PostgreSQL"""
    
    def __init__(self):
        load_dotenv('.env')
        
        # Konfiguracja PostgreSQL
        self.pg_config = {
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'host': os.getenv('DB_HOST'),
            'port': os.getenv('DB_PORT'),
            'database': os.getenv('DB_NAME')
        }
        
        # Sprawdź konfigurację
        missing_config = [k for k, v in self.pg_config.items() if not v]
        if missing_config:
            raise ValueError(f"Brakuje konfiguracji PostgreSQL: {missing_config}")
        
        # Połączenie PostgreSQL
        db_uri = f"postgresql://{self.pg_config['user']}:{self.pg_config['password']}@{self.pg_config['host']}:{self.pg_config['port']}/{self.pg_config['database']}"
        self.engine = create_engine(db_uri)
        
        # Sprawdź połączenie
        self._test_connection()
    
    def _test_connection(self):
        """Testuje połączenie z bazą danych"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            logger.info("✅ Połączenie z PostgreSQL nawiązane")
        except Exception as e:
            logger.error(f"❌ Błąd połączenia z PostgreSQL: {e}")
            raise
    
    def ensure_company_exists(self, ticker: str) -> Optional[int]:
        """Zapewnia że spółka istnieje i zwraca jej ID"""
        try:
            with self.engine.begin() as conn:
                # Sprawdź czy spółka istnieje
                result = conn.execute(
                    text("SELECT id FROM companies WHERE ticker = :ticker"), 
                    {"ticker": ticker.upper()}
                )
                row = result.fetchone()
                
                if row:
                    return row[0]
                
                # Dodaj nową spółkę
                result = conn.execute(
                    text("""
                        INSERT INTO companies (ticker, name, sector, is_active, data_source)
                        VALUES (:ticker, :name, :sector, :active, :source)
                        RETURNING id
                    """),
                    {
                        "ticker": ticker.upper(),
                        "name": ticker.upper(),
                        "sector": "Unknown",
                        "active": True,
                        "source": "auto_registered"
                    }
                )
                row = result.fetchone()
                company_id = row[0] if row else None
                
                if company_id:
                    logger.info(f"✅ Auto-dodano spółkę {ticker} (ID: {company_id})")
                    return company_id
                
        except Exception as e:
            logger.error(f"❌ Błąd zapewniania istnienia spółki {ticker}: {e}")
        
        return None
    
    def register_ticker(self, ticker: str, name: Optional[str] = None, 
                       sector: Optional[str] = None, source_type: str = 'historical',
                       update_stats: bool = True) -> bool:
        """
        Rejestruje nowy ticker w systemie
        
        Args:
            ticker: Symbol spółki
            name: Nazwa spółki
            sector: Sektor
            source_type: Typ źródła danych ('historical', 'scraping', 'both')
            update_stats: Czy aktualizować statystyki (może być kosztowne)
        """
        try:
            with self.engine.begin() as conn:
                # Sprawdź czy ticker już istnieje
                result = conn.execute(
                    text("SELECT id, data_source FROM companies WHERE ticker = :ticker"), 
                    {"ticker": ticker.upper()}
                )
                existing = result.fetchone()
                
                if existing:
                    # Aktualizuj istniejący ticker
                    company_id, current_source = existing
                    
                    # Zaktualizuj źródło danych jeśli potrzeba
                    new_source = self._merge_data_sources(current_source, source_type)
                    
                    conn.execute(
                        text("""
                            UPDATE companies 
                            SET name = COALESCE(:name, name),
                                sector = COALESCE(:sector, sector),
                                data_source = :source,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE ticker = :ticker
                        """), 
                        {
                            "name": name,
                            "sector": sector,
                            "source": new_source,
                            "ticker": ticker.upper()
                        }
                    )
                    
                    logger.info(f"✅ Zaktualizowano ticker {ticker} (źródło: {new_source})")
                    
                else:
                    # Dodaj nowy ticker
                    conn.execute(
                        text("""
                            INSERT INTO companies (ticker, name, sector, data_source, is_active)
                            VALUES (:ticker, :name, :sector, :source, :active)
                        """), 
                        {
                            "ticker": ticker.upper(),
                            "name": name or ticker.upper(),
                            "sector": sector or "Unknown",
                            "source": source_type,
                            "active": True
                        }
                    )
                    
                    logger.info(f"✅ Dodano nowy ticker: {ticker}")
                
                # Zaktualizuj statystyki tylko jeśli requested
                if update_stats:
                    self.update_ticker_stats(ticker)
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd rejestracji ticker {ticker}: {e}")
            return False
    
    def _merge_data_sources(self, current: str, new: str) -> str:
        """Łączy źródła danych"""
        if current == new:
            return current
        elif current == 'historical' and new == 'scraping':
            return 'both'
        elif current == 'scraping' and new == 'historical':
            return 'both'
        elif new == 'both':
            return 'both'
        else:
            return new
    
    def register_data_source(self, ticker: str, source_type: str, source_name: str,
                            record_count: int = 0, metadata: Optional[Dict] = None) -> bool:
        """Rejestruje źródło danych dla tickera"""
        try:
            with self.engine.begin() as conn:
                # Sprawdź czy źródło już istnieje
                result = conn.execute(
                    text("""
                        SELECT id FROM data_sources 
                        WHERE ticker = :ticker AND source_type = :type AND source_name = :name
                    """), 
                    {"ticker": ticker.upper(), "type": source_type, "name": source_name}
                )
                
                if result.fetchone():
                    # Aktualizuj istniejące
                    conn.execute(
                        text("""
                            UPDATE data_sources 
                            SET record_count = :count, 
                                last_updated = CURRENT_TIMESTAMP,
                                metadata = :metadata
                            WHERE ticker = :ticker AND source_type = :type AND source_name = :name
                        """), 
                        {
                            "count": record_count,
                            "metadata": json.dumps(metadata or {}),
                            "ticker": ticker.upper(),
                            "type": source_type,
                            "name": source_name
                        }
                    )
                else:
                    # Dodaj nowe
                    conn.execute(
                        text("""
                            INSERT INTO data_sources 
                            (ticker, source_type, source_name, record_count, metadata)
                            VALUES (:ticker, :type, :name, :count, :metadata)
                        """), 
                        {
                            "ticker": ticker.upper(),
                            "type": source_type,
                            "name": source_name,
                            "count": record_count,
                            "metadata": json.dumps(metadata or {})
                        }
                    )
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd rejestracji źródła {source_name} dla {ticker}: {e}")
            return False
    
    def update_ticker_stats(self, ticker: str) -> bool:
        """Aktualizuje statystyki tickera na podstawie danych w quotes_intraday"""
        try:
            with self.engine.begin() as conn:
                # Pobierz company_id dla tickera
                result = conn.execute(
                    text("SELECT id FROM companies WHERE ticker = :ticker"),
                    {"ticker": ticker.upper()}
                )
                row = result.fetchone()
                if not row:
                    logger.warning(f"⚠️ Ticker {ticker} nie znaleziony podczas aktualizacji statystyk")
                    return False
                
                company_id = row[0]
                
                # Pobierz statystyki w osobnych zapytaniach (szybsze)
                stats_result = conn.execute(
                    text("""
                        SELECT 
                            COUNT(*) as total_records,
                            MIN(datetime) as first_date,
                            MAX(datetime) as last_date
                        FROM quotes_intraday 
                        WHERE company_id = :company_id
                    """),
                    {"company_id": company_id}
                )
                
                stats_row = stats_result.fetchone()
                total_records = 0
                first_date = None
                last_date = None
                
                if stats_row:
                    total_records, first_date, last_date = stats_row
                    
                    # Aktualizuj w jednym prostym zapytaniu
                    conn.execute(
                        text("""
                            UPDATE companies 
                            SET total_records = :total,
                                first_data_date = :first_date,
                                last_data_date = :last_date,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE ticker = :ticker
                        """),
                        {
                            "total": total_records or 0,
                            "first_date": first_date,
                            "last_date": last_date,
                            "ticker": ticker.upper()
                        }
                    )
                
                logger.info(f"✅ Zaktualizowano statystyki dla {ticker} (rekordy: {total_records or 0})")
                return True
                
        except Exception as e:
            logger.error(f"❌ Błąd aktualizacji statystyk dla {ticker}: {e}")
            return False
    
    def get_all_tickers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Pobiera listę wszystkich tickerów"""
        try:
            with self.engine.connect() as conn:
                query = """
                    SELECT ticker, name, sector, data_source, first_data_date, 
                           last_data_date, total_records, is_active
                    FROM companies
                """
                params = {}
                
                if active_only:
                    query += " WHERE is_active = :active"
                    params["active"] = True
                    
                query += " ORDER BY ticker"
                
                result = conn.execute(text(query), params)
                rows = result.fetchall()
                
                tickers = []
                for row in rows:
                    tickers.append({
                        'ticker': row[0],
                        'name': row[1],
                        'sector': row[2],
                        'data_source': row[3],
                        'first_data_date': row[4].isoformat() if row[4] else None,
                        'last_data_date': row[5].isoformat() if row[5] else None,
                        'total_records': row[6] or 0,
                        'is_active': bool(row[7])
                    })
                
                return tickers
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania tickerów: {e}")
            return []
    
    def analyze_data_continuity(self, ticker: str) -> Dict[str, Any]:
        """Analizuje ciągłość danych między historycznymi a scrapingiem"""
        try:
            with self.engine.connect() as conn:
                # Pobierz dane dla tickera
                result = conn.execute(
                    text("""
                        SELECT qi.datetime
                        FROM quotes_intraday qi
                        JOIN companies c ON qi.company_id = c.id
                        WHERE c.ticker = :ticker
                        ORDER BY qi.datetime
                    """), 
                    {"ticker": ticker.upper()}
                )
                
                data_points = result.fetchall()
                
                if not data_points:
                    return {
                        'ticker': ticker,
                        'has_data': False,
                        'continuity_status': 'no_data'
                    }
                
                # Analiza ciągłości
                first_date = data_points[0][0]
                last_date = data_points[-1][0]
                
                # Sprawdź luki w danych - konwertuj na listę tupli
                data_tuples = [(row[0],) for row in data_points]
                gaps = self._find_data_gaps(data_tuples)
                
                # Określ czy dane są ciągłe do teraz
                days_since_last = (datetime.now() - last_date).days
                is_current = days_since_last <= 3
                
                analysis = {
                    'ticker': ticker,
                    'has_data': True,
                    'first_date': first_date.isoformat(),
                    'last_date': last_date.isoformat(),
                    'days_since_last': days_since_last,
                    'is_current': is_current,
                    'total_records': len(data_points),
                    'gaps': gaps,
                    'gap_count': len(gaps),
                    'continuity_status': 'continuous' if len(gaps) == 0 and is_current else 'has_gaps'
                }
                
                # Zapisz analizę
                self._save_continuity_analysis(ticker, analysis)
                
                return analysis
                
        except Exception as e:
            logger.error(f"❌ Błąd analizy ciągłości dla {ticker}: {e}")
            return {'ticker': ticker, 'error': str(e)}
    
    def _find_data_gaps(self, data_points: List[Tuple]) -> List[Dict]:
        """Znajduje luki w danych"""
        gaps = []
        
        for i in range(1, len(data_points)):
            prev_date = data_points[i-1][0]
            curr_date = data_points[i][0]
            
            # Sprawdź czy luka większa niż 1 dzień
            diff_days = (curr_date - prev_date).days
            if diff_days > 1:
                gaps.append({
                    'from_date': prev_date.isoformat(),
                    'to_date': curr_date.isoformat(),
                    'gap_days': diff_days
                })
        
        return gaps
    
    def _save_continuity_analysis(self, ticker: str, analysis: Dict):
        """Zapisuje analizę ciągłości do bazy"""
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO data_continuity 
                        (ticker, historical_end_date, gap_days, is_continuous, last_check)
                        VALUES (:ticker, :end_date, :gaps, :continuous, CURRENT_TIMESTAMP)
                        ON CONFLICT (ticker) DO UPDATE SET
                        historical_end_date = EXCLUDED.historical_end_date,
                        gap_days = EXCLUDED.gap_days,
                        is_continuous = EXCLUDED.is_continuous,
                        last_check = EXCLUDED.last_check
                    """), 
                    {
                        "ticker": ticker.upper(),
                        "end_date": analysis.get('last_date'),
                        "gaps": analysis.get('gap_count', 0),
                        "continuous": analysis.get('continuity_status') == 'continuous'
                    }
                )
                
        except Exception as e:
            logger.error(f"❌ Błąd zapisywania analizy ciągłości: {e}")
    
    def get_tickers_for_scraping(self) -> List[str]:
        """Pobiera listę tickerów, które powinny być scrapowane"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT DISTINCT ticker 
                        FROM companies 
                        WHERE is_active = true 
                        AND (data_source IN ('scraping', 'both') OR total_records > 0)
                        ORDER BY ticker
                    """)
                )
                
                return [row[0] for row in result.fetchall()]
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania tickerów do scrapingu: {e}")
            return []
    
    def save_intraday_quote(self, ticker: str, price: float, volume: int = 0, 
                           open_price: Optional[float] = None, high_price: Optional[float] = None,
                           low_price: Optional[float] = None) -> bool:
        """Zapisuje notowanie intraday do PostgreSQL"""
        try:
            # Zapewnij istnienie spółki
            company_id = self.ensure_company_exists(ticker)
            if not company_id:
                return False
            
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO quotes_intraday 
                        (company_id, datetime, price, volume, open, high, low)
                        VALUES (:company_id, :datetime, :price, :volume, :open, :high, :low)
                        ON CONFLICT (company_id, datetime) DO UPDATE SET
                        price = EXCLUDED.price,
                        volume = EXCLUDED.volume,
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low
                    """),
                    {
                        "company_id": company_id,
                        "datetime": datetime.now(),
                        "price": price,
                        "volume": volume,
                        "open": open_price,
                        "high": high_price,
                        "low": low_price
                    }
                )
            
            # Zaktualizuj statystyki
            self.update_ticker_stats(ticker)
            
            logger.info(f"💾 PostgreSQL: Zapisano {ticker} = {price} PLN")
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd zapisu {ticker} do PostgreSQL: {e}")
            return False
    
    def generate_integration_report(self) -> Dict[str, Any]:
        """Generuje raport integracji danych historycznych ze scrapingiem"""
        try:
            tickers = self.get_all_tickers()
            
            report = {
                'generated_at': datetime.now().isoformat(),
                'total_tickers': len(tickers),
                'by_data_source': {},
                'continuity_analysis': [],
                'scraping_suggestions': [],
                'summary': {}
            }
            
            # Analiza według źródeł danych
            for ticker_info in tickers:
                source = ticker_info['data_source']
                if source not in report['by_data_source']:
                    report['by_data_source'][source] = []
                report['by_data_source'][source].append(ticker_info['ticker'])
            
            # Analiza ciągłości dla każdego tickera z danymi
            for ticker_info in tickers:
                if ticker_info['total_records'] > 0:
                    ticker = ticker_info['ticker']
                    continuity = self.analyze_data_continuity(ticker)
                    suggestion = self.suggest_scraping_schedule(ticker)
                    
                    report['continuity_analysis'].append(continuity)
                    report['scraping_suggestions'].append(suggestion)
            
            # Podsumowanie
            high_priority = len([s for s in report['scraping_suggestions'] if s['priority'] == 'high'])
            medium_priority = len([s for s in report['scraping_suggestions'] if s['priority'] == 'medium'])
            
            report['summary'] = {
                'high_priority_tickers': high_priority,
                'medium_priority_tickers': medium_priority,
                'ready_for_scraping': len(self.get_tickers_for_scraping()),
                'total_records': sum(t['total_records'] for t in tickers if t['total_records'])
            }
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Błąd generowania raportu integracji: {e}")
            return {}
    
    def suggest_scraping_schedule(self, ticker: str) -> Dict[str, Any]:
        """Sugeruje harmonogram scrapingu na podstawie analizy danych"""
        analysis = self.analyze_data_continuity(ticker)
        
        if not analysis.get('has_data'):
            return {
                'ticker': ticker,
                'suggestion': 'start_scraping',
                'priority': 'high',
                'reason': 'Brak danych historycznych - rozpocznij scraping'
            }
        
        days_since_last = analysis.get('days_since_last', 999)
        
        if days_since_last > 7:
            return {
                'ticker': ticker,
                'suggestion': 'resume_scraping',
                'priority': 'high',
                'reason': f'Dane nieaktualne ({days_since_last} dni) - wznów scraping'
            }
        elif days_since_last > 3:
            return {
                'ticker': ticker,
                'suggestion': 'monitor_closely',
                'priority': 'medium',
                'reason': f'Dane lekko nieaktualne ({days_since_last} dni)'
            }
        else:
            return {
                'ticker': ticker,
                'suggestion': 'continue_normal',
                'priority': 'low',
                'reason': 'Dane aktualne - kontynuuj normalny scraping'
            }
    
    def update_all_ticker_stats(self) -> Dict[str, int]:
        """Aktualizuje statystyki dla wszystkich tickerów - do użycia po imporcie"""
        try:
            results = {'updated': 0, 'errors': 0}
            
            with self.engine.connect() as conn:
                # Pobierz wszystkie tickery
                result = conn.execute(text("SELECT ticker FROM companies WHERE is_active = true"))
                tickers = [row[0] for row in result.fetchall()]
            
            logger.info(f"🔄 Aktualizuję statystyki dla {len(tickers)} tickerów...")
            
            for ticker in tickers:
                try:
                    if self.update_ticker_stats(ticker):
                        results['updated'] += 1
                    else:
                        results['errors'] += 1
                except Exception as e:
                    logger.error(f"❌ Błąd aktualizacji {ticker}: {e}")
                    results['errors'] += 1
            
            logger.info(f"✅ Aktualizacja statystyk zakończona: {results['updated']} OK, {results['errors']} błędów")
            return results
            
        except Exception as e:
            logger.error(f"❌ Błąd masowej aktualizacji statystyk: {e}")
            return {'updated': 0, 'errors': 1}

# Funkcje pomocnicze dla integracji
def auto_register_ticker_from_import(ticker: str, import_stats: Dict) -> bool:
    """Automatycznie rejestruje ticker podczas importu danych historycznych"""
    try:
        manager = TickerManager()
        
        # Rejestruj ticker jako pochodzący z danych historycznych
        # Wyłącz update_stats podczas importu (zbyt kosztowne)
        success = manager.register_ticker(
            ticker=ticker,
            name=ticker,
            sector='Unknown',
            source_type='historical',
            update_stats=False  # Nie aktualizuj statystyk podczas importu
        )
        
        if success:
            # Rejestruj źródło danych
            manager.register_data_source(
                ticker=ticker,
                source_type='historical_import',
                source_name='txt_files',
                record_count=import_stats.get('imported', 0),
                metadata={
                    'import_date': datetime.now().isoformat(),
                    'skipped_records': import_stats.get('skipped', 0),
                    'errors': import_stats.get('errors', 0)
                }
            )
            
            logger.info(f"✅ Auto-zarejestrowano ticker {ticker} z importu historycznego (bez aktualizacji statystyk)")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Błąd auto-rejestracji ticker {ticker} z importu: {e}")
        return False

def auto_register_ticker_from_scraping(ticker: str, source_name: str = 'bankier.pl') -> bool:
    """Automatycznie rejestruje ticker podczas scrapingu"""
    try:
        manager = TickerManager()
        
        success = manager.register_ticker(
            ticker=ticker,
            name=ticker,
            sector='Unknown',
            source_type='scraping'
        )
        
        if success:
            manager.register_data_source(
                ticker=ticker,
                source_type='scraping_intraday',
                source_name=source_name,
                metadata={
                    'scraping_start': datetime.now().isoformat(),
                    'auto_registered': True
                }
            )
            
            logger.info(f"✅ Auto-zarejestrowano ticker {ticker} z scrapingu {source_name}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Błąd auto-rejestracji ticker {ticker} z scrapingu: {e}")
        return False

def main():
    """Demo funkcji zarządzania tickerami"""
    print("🎯 POSTGRESQL TICKER MANAGEMENT SYSTEM")
    print("=" * 50)
    
    try:
        manager = TickerManager()
        
        # Przykładowe dane
        tickers = manager.get_all_tickers()
        print(f"📊 Znaleziono {len(tickers)} tickerów:")
        
        for ticker in tickers[:10]:  # Pokaż tylko pierwsze 10
            print(f"  {ticker['ticker']}: {ticker['total_records']:,} rekordów, źródło: {ticker['data_source']}")
        
        # Raport integracji
        print("\n📋 RAPORT INTEGRACJI:")
        print("-" * 30)
        report = manager.generate_integration_report()
        
        print(f"Łącznie tickerów: {report['total_tickers']}")
        print(f"Wysokiej priority: {report['summary']['high_priority_tickers']}")
        print(f"Gotowych do scrapingu: {report['summary']['ready_for_scraping']}")
        print(f"Łączne rekordy: {report['summary']['total_records']:,}")
        
        # Pokaż według źródeł
        print("\n📂 Według źródeł danych:")
        for source, tickers_list in report['by_data_source'].items():
            print(f"  {source}: {len(tickers_list)} tickerów")
        
    except Exception as e:
        print(f"❌ Błąd: {e}")

if __name__ == "__main__":
    main()
