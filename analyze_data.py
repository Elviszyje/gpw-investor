#!/usr/bin/env python3
"""
Data Analyzer - Analiza jakości i statystyk danych w bazie PostgreSQL
Narzędzie do analizy danych historycznych i bieżących
Autor: GPW Investor System
Data: 2025-06-25
"""

import logging
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataAnalyzer:
    """Analyzer jakości danych w PostgreSQL"""
    
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
                conn.execute(text("SELECT 1"))
            logger.info("✅ Połączenie z PostgreSQL sprawdzone")
        except Exception as e:
            logger.error(f"❌ Błąd połączenia z PostgreSQL: {e}")
            raise
    
    def get_basic_stats(self) -> Dict[str, Any]:
        """Pobiera podstawowe statystyki z bazy danych"""
        try:
            with self.engine.connect() as conn:
                # Statystyki tabel
                stats = {}
                
                # Companies
                companies_count = conn.execute(text("SELECT COUNT(*) FROM companies")).scalar() or 0
                stats['companies'] = {
                    'total_count': companies_count
                }
                
                # Quotes intraday
                intraday_count = conn.execute(text("SELECT COUNT(*) FROM quotes_intraday")).scalar() or 0
                intraday_date_range = conn.execute(text("""
                    SELECT MIN(datetime), MAX(datetime) FROM quotes_intraday
                """)).fetchone()
                
                stats['quotes_intraday'] = {
                    'total_records': intraday_count,
                    'first_date': str(intraday_date_range[0]) if intraday_date_range and intraday_date_range[0] else None,
                    'last_date': str(intraday_date_range[1]) if intraday_date_range and intraday_date_range[1] else None
                }
                
                # Quotes daily
                daily_count = conn.execute(text("SELECT COUNT(*) FROM quotes_daily")).scalar() or 0
                daily_date_range = conn.execute(text("""
                    SELECT MIN(date), MAX(date) FROM quotes_daily
                """)).fetchone()
                
                stats['quotes_daily'] = {
                    'total_records': daily_count,
                    'first_date': str(daily_date_range[0]) if daily_date_range and daily_date_range[0] else None,
                    'last_date': str(daily_date_range[1]) if daily_date_range and daily_date_range[1] else None
                }
                
                # Data sources (jeśli istnieje)
                try:
                    sources_count = conn.execute(text("SELECT COUNT(*) FROM data_sources")).scalar() or 0
                    stats['data_sources'] = {'total_count': sources_count}
                except:
                    stats['data_sources'] = {'total_count': 0}
                
                logger.info("✅ Pobrano podstawowe statystyki")
                return stats
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania statystyk: {e}")
            return {}
    
    def analyze_ticker_data(self, ticker: str) -> Dict[str, Any]:
        """Analizuje dane dla konkretnego tickera"""
        try:
            with self.engine.connect() as conn:
                # Podstawowe info o firmie
                company_info = conn.execute(text("""
                    SELECT id, ticker, name, sector FROM companies WHERE ticker = :ticker
                """), {"ticker": ticker.upper()}).fetchone()
                
                if not company_info:
                    return {'error': f'Ticker {ticker} nie istnieje w bazie'}
                
                company_id, ticker_name, company_name, sector = company_info
                
                # Statystyki intraday
                intraday_stats = conn.execute(text("""
                    SELECT COUNT(*), MIN(datetime), MAX(datetime), 
                           AVG(price), MIN(price), MAX(price),
                           SUM(volume)
                    FROM quotes_intraday WHERE company_id = :company_id
                """), {"company_id": company_id}).fetchone()
                
                # Statystyki daily
                daily_stats = conn.execute(text("""
                    SELECT COUNT(*), MIN(date), MAX(date),
                           AVG(close), MIN(close), MAX(close),
                           SUM(volume)
                    FROM quotes_daily WHERE company_id = :company_id
                """), {"company_id": company_id}).fetchone()
                
                # Analiza ciągłości danych intraday
                continuity_analysis = self._analyze_data_continuity(company_id, ticker_name)
                
                analysis = {
                    'ticker': ticker_name,
                    'company_name': company_name or ticker_name,
                    'sector': sector or 'Unknown',
                    'company_id': company_id,
                    'intraday': {
                        'records_count': intraday_stats[0] if intraday_stats else 0,
                        'first_date': str(intraday_stats[1]) if intraday_stats and intraday_stats[1] else None,
                        'last_date': str(intraday_stats[2]) if intraday_stats and intraday_stats[2] else None,
                        'avg_price': float(intraday_stats[3]) if intraday_stats and intraday_stats[3] else 0,
                        'min_price': float(intraday_stats[4]) if intraday_stats and intraday_stats[4] else 0,
                        'max_price': float(intraday_stats[5]) if intraday_stats and intraday_stats[5] else 0,
                        'total_volume': int(intraday_stats[6]) if intraday_stats and intraday_stats[6] else 0
                    },
                    'daily': {
                        'records_count': daily_stats[0] if daily_stats else 0,
                        'first_date': str(daily_stats[1]) if daily_stats and daily_stats[1] else None,
                        'last_date': str(daily_stats[2]) if daily_stats and daily_stats[2] else None,
                        'avg_price': float(daily_stats[3]) if daily_stats and daily_stats[3] else 0,
                        'min_price': float(daily_stats[4]) if daily_stats and daily_stats[4] else 0,
                        'max_price': float(daily_stats[5]) if daily_stats and daily_stats[5] else 0,
                        'total_volume': int(daily_stats[6]) if daily_stats and daily_stats[6] else 0
                    },
                    'continuity': continuity_analysis
                }
                
                logger.info(f"✅ Przeanalizowano dane dla {ticker}")
                return analysis
                
        except Exception as e:
            logger.error(f"❌ Błąd analizy dla {ticker}: {e}")
            return {'error': str(e)}
    
    def _analyze_data_continuity(self, company_id: int, ticker: str) -> Dict[str, Any]:
        """Analizuje ciągłość danych"""
        try:
            with self.engine.connect() as conn:
                # Pobierz dane chronologicznie
                data_points = conn.execute(text("""
                    SELECT datetime FROM quotes_intraday 
                    WHERE company_id = :company_id 
                    ORDER BY datetime
                """), {"company_id": company_id}).fetchall()
                
                if not data_points:
                    return {'status': 'no_data', 'gaps': []}
                
                # Znajdź luki
                gaps = []
                for i in range(1, len(data_points)):
                    prev_time = data_points[i-1][0]
                    curr_time = data_points[i][0]
                    
                    # Sprawdź czy luka większa niż 1 dzień
                    diff = curr_time - prev_time
                    if diff.days > 1:
                        gaps.append({
                            'from': str(prev_time),
                            'to': str(curr_time),
                            'gap_days': diff.days
                        })
                
                # Sprawdź aktualność
                last_date = data_points[-1][0]
                days_since_last = (datetime.now() - last_date.replace(tzinfo=None)).days
                
                return {
                    'status': 'continuous' if len(gaps) == 0 else 'has_gaps',
                    'gaps': gaps,
                    'gap_count': len(gaps),
                    'last_update': str(last_date),
                    'days_since_last': days_since_last,
                    'is_current': days_since_last <= 3
                }
                
        except Exception as e:
            logger.error(f"❌ Błąd analizy ciągłości: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_all_tickers_analysis(self) -> List[Dict[str, Any]]:
        """Analizuje wszystkie tickery w bazie"""
        try:
            with self.engine.connect() as conn:
                tickers = conn.execute(text("SELECT ticker FROM companies ORDER BY ticker")).fetchall()
                
                analyses = []
                for ticker_row in tickers:
                    ticker = ticker_row[0]
                    analysis = self.analyze_ticker_data(ticker)
                    if 'error' not in analysis:
                        analyses.append(analysis)
                
                logger.info(f"✅ Przeanalizowano {len(analyses)} tickerów")
                return analyses
                
        except Exception as e:
            logger.error(f"❌ Błąd analizy wszystkich tickerów: {e}")
            return []
    
    def generate_quality_report(self) -> Dict[str, Any]:
        """Generuje raport jakości danych"""
        logger.info("🔄 Generuję raport jakości danych...")
        
        # Podstawowe statystyki
        basic_stats = self.get_basic_stats()
        
        # Analiza wszystkich tickerów
        all_analyses = self.get_all_tickers_analysis()
        
        # Podsumowanie jakości
        quality_summary = {
            'total_tickers': len(all_analyses),
            'tickers_with_intraday': len([a for a in all_analyses if a['intraday']['records_count'] > 0]),
            'tickers_with_daily': len([a for a in all_analyses if a['daily']['records_count'] > 0]),
            'tickers_current': len([a for a in all_analyses if a['continuity'].get('is_current', False)]),
            'tickers_with_gaps': len([a for a in all_analyses if a['continuity'].get('gap_count', 0) > 0]),
            'total_intraday_records': sum([a['intraday']['records_count'] for a in all_analyses]),
            'total_daily_records': sum([a['daily']['records_count'] for a in all_analyses])
        }
        
        # Top tickery
        top_by_records = sorted(all_analyses, key=lambda x: x['intraday']['records_count'], reverse=True)[:10]
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'basic_stats': basic_stats,
            'quality_summary': quality_summary,
            'top_tickers_by_records': [
                {
                    'ticker': t['ticker'],
                    'intraday_records': t['intraday']['records_count'],
                    'daily_records': t['daily']['records_count']
                }
                for t in top_by_records
            ],
            'data_issues': [
                {
                    'ticker': a['ticker'],
                    'issue': 'no_intraday_data' if a['intraday']['records_count'] == 0 else 'data_gaps',
                    'gap_count': a['continuity'].get('gap_count', 0),
                    'days_since_last': a['continuity'].get('days_since_last', 999)
                }
                for a in all_analyses
                if a['intraday']['records_count'] == 0 or a['continuity'].get('gap_count', 0) > 0 or not a['continuity'].get('is_current', False)
            ]
        }
        
        logger.info("✅ Raport jakości wygenerowany")
        return report
    
    def save_report_to_file(self, report: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Zapisuje raport do pliku JSON"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data_quality_report_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"✅ Raport zapisany do: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ Błąd zapisu raportu: {e}")
            return ""
    
    def print_summary(self, report: Dict[str, Any]):
        """Wyświetla podsumowanie raportu"""
        print("\n📊 RAPORT JAKOŚCI DANYCH")
        print("=" * 50)
        
        basic = report.get('basic_stats', {})
        quality = report.get('quality_summary', {})
        
        print(f"📈 Podstawowe statystyki:")
        print(f"   Firmy w bazie: {basic.get('companies', {}).get('total_count', 0)}")
        print(f"   Rekordy intraday: {basic.get('quotes_intraday', {}).get('total_records', 0):,}")
        print(f"   Rekordy daily: {basic.get('quotes_daily', {}).get('total_records', 0):,}")
        
        print(f"\n📊 Jakość danych:")
        print(f"   Tickery z danymi intraday: {quality.get('tickers_with_intraday', 0)}/{quality.get('total_tickers', 0)}")
        print(f"   Tickery z danymi daily: {quality.get('tickers_with_daily', 0)}/{quality.get('total_tickers', 0)}")
        print(f"   Tickery aktualne: {quality.get('tickers_current', 0)}/{quality.get('total_tickers', 0)}")
        print(f"   Tickery z lukami: {quality.get('tickers_with_gaps', 0)}")
        
        print(f"\n🏆 Top tickery (według liczby rekordów):")
        for ticker_info in report.get('top_tickers_by_records', [])[:5]:
            print(f"   {ticker_info['ticker']}: {ticker_info['intraday_records']:,} intraday, {ticker_info['daily_records']:,} daily")
        
        issues = report.get('data_issues', [])
        if issues:
            print(f"\n⚠️ Problemy z danymi ({len(issues)} tickerów):")
            for issue in issues[:10]:  # Pokaż pierwsze 10
                if issue['issue'] == 'no_intraday_data':
                    print(f"   {issue['ticker']}: Brak danych intraday")
                else:
                    print(f"   {issue['ticker']}: {issue['gap_count']} luk, {issue['days_since_last']} dni od ostatniego")
    
    def analyze_data_quality(self) -> Dict[str, Any]:
        """Analyze data quality - wrapper around generate_quality_report"""
        return self.generate_quality_report()
    
    def analyze_completeness(self) -> Dict[str, Any]:
        """Analyze data completeness"""
        try:
            with self.engine.connect() as conn:
                # Check for missing data points in time series
                query = text("""
                    SELECT 
                        c.ticker,
                        COUNT(qi.id) as total_records,
                        DATE_PART('day', MAX(qi.datetime) - MIN(qi.datetime)) as date_span_days,
                        COUNT(qi.id) / GREATEST(DATE_PART('day', MAX(qi.datetime) - MIN(qi.datetime)) * 288, 1) as completeness_ratio
                    FROM companies c
                    LEFT JOIN quotes_intraday qi ON c.id = qi.company_id
                    WHERE qi.id IS NOT NULL
                    GROUP BY c.id, c.ticker
                    ORDER BY completeness_ratio DESC
                """)
                
                result = conn.execute(query)
                completeness_data = []
                
                for row in result:
                    completeness_data.append({
                        'ticker': row.ticker,
                        'total_records': row.total_records,
                        'date_span_days': float(row.date_span_days) if row.date_span_days else 0,
                        'completeness_ratio': float(row.completeness_ratio) if row.completeness_ratio else 0
                    })
                
                # Calculate overall statistics
                total_tickers = len(completeness_data)
                avg_completeness = sum(item['completeness_ratio'] for item in completeness_data) / max(total_tickers, 1)
                
                return {
                    'success': True,
                    'overall_completeness': avg_completeness,
                    'total_tickers': total_tickers,
                    'ticker_completeness': completeness_data,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error analyzing completeness: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def generate_ml_readiness_report(self) -> Dict[str, Any]:
        """Generate ML readiness report"""
        try:
            basic_stats = self.get_basic_stats()
            completeness = self.analyze_completeness()
            
            # Calculate ML readiness score
            ml_score = 0
            factors = []
            
            # Factor 1: Data volume (30%)
            total_records = basic_stats.get('quotes_intraday', {}).get('total_records', 0)
            if total_records > 100000:
                volume_score = 30
                factors.append("✅ Sufficient data volume (>100k records)")
            elif total_records > 10000:
                volume_score = 20
                factors.append("⚠️ Moderate data volume (>10k records)")
            else:
                volume_score = 10
                factors.append("❌ Low data volume (<10k records)")
            ml_score += volume_score
            
            # Factor 2: Data completeness (25%)
            avg_completeness = completeness.get('overall_completeness', 0)
            if avg_completeness > 0.8:
                completeness_score = 25
                factors.append("✅ High data completeness (>80%)")
            elif avg_completeness > 0.5:
                completeness_score = 15
                factors.append("⚠️ Moderate data completeness (>50%)")
            else:
                completeness_score = 5
                factors.append("❌ Low data completeness (<50%)")
            ml_score += completeness_score
            
            # Factor 3: Number of tickers (20%)
            total_tickers = basic_stats.get('companies', {}).get('total_count', 0)
            if total_tickers > 20:
                ticker_score = 20
                factors.append("✅ Good ticker diversity (>20 tickers)")
            elif total_tickers > 10:
                ticker_score = 15
                factors.append("⚠️ Moderate ticker diversity (>10 tickers)")
            else:
                ticker_score = 5
                factors.append("❌ Low ticker diversity (<10 tickers)")
            ml_score += ticker_score
            
            # Factor 4: Data recency (15%)
            # Check if we have recent data (last 30 days)
            try:
                with self.engine.connect() as conn:
                    recent_query = text("""
                        SELECT COUNT(*) as recent_count
                        FROM quotes_intraday
                        WHERE datetime > NOW() - INTERVAL '30 days'
                    """)
                    recent_result = conn.execute(recent_query).scalar()
                    recent_count = recent_result if recent_result is not None else 0
                    
                    if recent_count > 1000:
                        recency_score = 15
                        factors.append("✅ Recent data available (last 30 days)")
                    elif recent_count > 100:
                        recency_score = 10
                        factors.append("⚠️ Some recent data (last 30 days)")
                    else:
                        recency_score = 0
                        factors.append("❌ No recent data (last 30 days)")
            except:
                recency_score = 0
                factors.append("❌ Could not check data recency")
            ml_score += recency_score
            
            # Factor 5: Data consistency (10%)
            # Simple consistency check - no negative prices, volume > 0, etc.
            try:
                with self.engine.connect() as conn:
                    consistency_query = text("""
                        SELECT 
                            COUNT(*) as total,
                            COUNT(CASE WHEN price <= 0 THEN 1 END) as negative_prices,
                            COUNT(CASE WHEN volume < 0 THEN 1 END) as negative_volume,
                            COUNT(CASE WHEN high_price < low_price THEN 1 END) as invalid_highs
                        FROM quotes_intraday
                    """)
                    consistency_result = conn.execute(consistency_query).fetchone()
                    
                    if consistency_result:
                        total_inconsistent = (consistency_result.negative_prices + 
                                            consistency_result.negative_volume + 
                                            consistency_result.invalid_highs)
                        consistency_ratio = 1 - (total_inconsistent / max(consistency_result.total, 1))
                        
                        if consistency_ratio > 0.95:
                            consistency_score = 10
                            factors.append("✅ High data consistency (>95%)")
                        elif consistency_ratio > 0.9:
                            consistency_score = 7
                            factors.append("⚠️ Good data consistency (>90%)")
                        else:
                            consistency_score = 3
                            factors.append("❌ Poor data consistency (<90%)")
                    else:
                        consistency_score = 0
                        factors.append("❌ Could not check data consistency")
            except:
                consistency_score = 0
                factors.append("❌ Could not check data consistency")
            ml_score += consistency_score
            
            # Determine readiness level
            if ml_score >= 80:
                readiness_level = "HIGH"
                readiness_color = "success"
                recommendation = "Data is ready for ML model training"
            elif ml_score >= 60:
                readiness_level = "MEDIUM"
                readiness_color = "warning"
                recommendation = "Data is acceptable for ML, but improvements recommended"
            else:
                readiness_level = "LOW"
                readiness_color = "danger"
                recommendation = "Data needs significant improvement before ML training"
            
            return {
                'success': True,
                'ml_readiness_score': ml_score,
                'readiness_level': readiness_level,
                'readiness_color': readiness_color,
                'recommendation': recommendation,
                'factors': factors,
                'detailed_scores': {
                    'data_volume': volume_score,
                    'completeness': completeness_score,
                    'ticker_diversity': ticker_score,
                    'data_recency': recency_score,
                    'data_consistency': consistency_score
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating ML readiness report: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

def main():
    """Funkcja główna - demo analizatora"""
    print("🔍 DATA ANALYZER - PostgreSQL")
    print("=" * 50)
    
    try:
        analyzer = DataAnalyzer()
        
        # Generuj raport
        print("\n🔄 Generuję raport jakości danych...")
        report = analyzer.generate_quality_report()
        
        # Wyświetl podsumowanie
        analyzer.print_summary(report)
        
        # Zapisz raport
        filename = analyzer.save_report_to_file(report)
        if filename:
            print(f"\n💾 Raport zapisany do: {filename}")
        
    except Exception as e:
        print(f"❌ Błąd główny: {e}")
        logger.error(f"Błąd główny: {e}")

if __name__ == "__main__":
    main()
