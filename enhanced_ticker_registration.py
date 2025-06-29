#!/usr/bin/env python3
"""
Enhanced Ticker Auto-Registration System
Rozszerzony system automatycznej rejestracji tickerów podczas importu
Automatycznie tworzy tickery, analizuje dane i przygotowuje integrację ze scrapingiem
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
import requests
from ticker_manager import TickerManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedTickerAutoRegistration:
    """Rozszerzony system auto-rejestracji tickerów"""
    
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
        
        # Ticker Manager
        self.ticker_manager = TickerManager()
        
        # Cache informacji o spółkach
        self.company_info_cache = {}
        
        logger.info("✅ Enhanced Ticker Auto-Registration zainicjalizowany")
    
    def get_company_info(self, ticker: str) -> Dict[str, str]:
        """
        Próbuje uzyskać informacje o spółce (nazwa, sektor)
        Używa różnych źródeł: cache, GPW, Stooq, itp.
        """
        ticker_upper = ticker.upper()
        
        # Sprawdź cache
        if ticker_upper in self.company_info_cache:
            return self.company_info_cache[ticker_upper]
        
        # Domyślne wartości
        company_info = {
            'name': ticker_upper,
            'sector': 'Unknown',
            'market': 'GPW',
            'source': 'default'
        }
        
        # Próba 1: Sprawdź czy już mamy w bazie
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT name, sector FROM companies WHERE ticker = :ticker"),
                    {"ticker": ticker_upper}
                ).fetchone()
                
                if result and result[0] and result[0] != ticker_upper:
                    company_info.update({
                        'name': result[0],
                        'sector': result[1] or 'Unknown',
                        'source': 'database'
                    })
                    self.company_info_cache[ticker_upper] = company_info
                    return company_info
        except Exception as e:
            logger.warning(f"⚠️ Błąd sprawdzania bazy dla {ticker}: {e}")
        
        # Próba 2: GPW API/Scraping (można dodać w przyszłości)
        # company_info = self._get_from_gpw_api(ticker_upper, company_info)
        
        # Próba 3: Mapowanie znanych tickerów
        known_companies = {
            'PKN': {'name': 'PKN Orlen', 'sector': 'Paliwa'},
            'PEO': {'name': 'Polski Koncern Naftowy Orlen', 'sector': 'Paliwa'},
            'CDP': {'name': 'CD Projekt', 'sector': 'Gry komputerowe'},
            'JSW': {'name': 'Jastrzębska Spółka Węglowa', 'sector': 'Górnictwo'},
            'KGH': {'name': 'KGHM Polska Miedź', 'sector': 'Górnictwo'},
            'LPP': {'name': 'LPP', 'sector': 'Odzież'},
            'ALE': {'name': 'Allegro.eu', 'sector': 'E-commerce'},
            'CCC': {'name': 'CCC', 'sector': 'Odzież'},
            'DNP': {'name': 'Dino Polska', 'sector': 'Handel detaliczny'},
            '11B': {'name': '11 bit studios', 'sector': 'Gry komputerowe'},
            'CDR': {'name': 'CD Projekt RED', 'sector': 'Gry komputerowe'},
            'KRU': {'name': 'Kruk', 'sector': 'Usługi finansowe'},
            'MBK': {'name': 'mBank', 'sector': 'Bankowość'},
            'PKO': {'name': 'PKO Bank Polski', 'sector': 'Bankowość'},
            'PZU': {'name': 'PZU', 'sector': 'Ubezpieczenia'},
            'LTS': {'name': 'Grupa Lotos', 'sector': 'Paliwa'}
        }
        
        if ticker_upper in known_companies:
            company_info.update(known_companies[ticker_upper])
            company_info['source'] = 'known_mapping'
        
        # Cache rezultat
        self.company_info_cache[ticker_upper] = company_info
        logger.info(f"📊 Info o spółce {ticker}: {company_info['name']} ({company_info['sector']})")
        
        return company_info
    
    def auto_register_from_import(self, ticker: str, import_stats: Dict) -> Dict[str, Any]:
        """
        Rozszerzona auto-rejestracja podczas importu
        
        Args:
            ticker: Symbol spółki
            import_stats: Statystyki importu (imported, skipped, errors, etc.)
        
        Returns:
            Dict z wynikami rejestracji
        """
        result = {
            'ticker': ticker.upper(),
            'registered': False,
            'company_created': False,
            'data_source_registered': False,
            'continuity_analyzed': False,
            'company_info': {},
            'continuity_analysis': {},
            'errors': []
        }
        
        try:
            # 1. Uzyskaj informacje o spółce
            company_info = self.get_company_info(ticker)
            result['company_info'] = company_info
            
            # 2. Zarejestruj ticker z rozszerzonymi informacjami
            success = self.ticker_manager.register_ticker(
                ticker=ticker,
                name=company_info['name'],
                sector=company_info['sector'],
                source_type='historical'
            )
            
            if success:
                result['registered'] = True
                result['company_created'] = True
                logger.info(f"✅ Zarejestrowano spółkę {ticker}: {company_info['name']}")
                
                # 3. Zarejestruj źródło danych z metadanymi
                source_success = self.ticker_manager.register_data_source(
                    ticker=ticker,
                    source_type='historical_import',
                    source_name='txt_files',
                    record_count=import_stats.get('imported', 0),
                    metadata={
                        'import_date': datetime.now().isoformat(),
                        'imported_records': import_stats.get('imported', 0),
                        'skipped_records': import_stats.get('skipped', 0),
                        'error_records': import_stats.get('errors', 0),
                        'source_file': import_stats.get('source_file', 'unknown'),
                        'company_info_source': company_info['source'],
                        'auto_registered': True
                    }
                )
                
                if source_success:
                    result['data_source_registered'] = True
                    
                    # 4. Analizuj ciągłość danych
                    if import_stats.get('imported', 0) > 0:
                        continuity = self.ticker_manager.analyze_data_continuity(ticker)
                        result['continuity_analysis'] = continuity
                        result['continuity_analyzed'] = True
                        
                        # 5. Przygotuj rekomendacje dla scrapingu
                        scraping_suggestion = self.ticker_manager.suggest_scraping_schedule(ticker)
                        result['scraping_suggestion'] = scraping_suggestion
                        
                        logger.info(f"📈 Analiza {ticker}: {continuity.get('total_records', 0)} rekordów, "
                                  f"ostatnie: {continuity.get('last_date', 'N/A')}")
                        
                        if scraping_suggestion['priority'] == 'high':
                            logger.warning(f"⚠️ {ticker}: {scraping_suggestion['reason']}")
                
            else:
                result['errors'].append("Błąd rejestracji tickera")
                
        except Exception as e:
            error_msg = f"Błąd auto-rejestracji {ticker}: {e}"
            result['errors'].append(error_msg)
            logger.error(f"❌ {error_msg}")
        
        return result
    
    def analyze_import_batch(self, ticker_results: List[Dict]) -> Dict[str, Any]:
        """Analizuje wyniki importu dla całej partii tickerów"""
        analysis = {
            'total_tickers': len(ticker_results),
            'successful_registrations': 0,
            'failed_registrations': 0,
            'new_companies': 0,
            'companies_with_data': 0,
            'high_priority_for_scraping': 0,
            'sectors_summary': {},
            'data_quality_issues': [],
            'recommendations': []
        }
        
        for result in ticker_results:
            if result['registered']:
                analysis['successful_registrations'] += 1
                
                if result['company_created']:
                    analysis['new_companies'] += 1
                
                # Analiza sektorów
                sector = result['company_info'].get('sector', 'Unknown')
                if sector not in analysis['sectors_summary']:
                    analysis['sectors_summary'][sector] = 0
                analysis['sectors_summary'][sector] += 1
                
                # Sprawdź jakość danych
                if result.get('continuity_analyzed'):
                    continuity = result['continuity_analysis']
                    if continuity.get('total_records', 0) > 0:
                        analysis['companies_with_data'] += 1
                    
                    # Problemy z jakością
                    if continuity.get('gap_count', 0) > 0:
                        analysis['data_quality_issues'].append({
                            'ticker': result['ticker'],
                            'issue': 'data_gaps',
                            'gap_count': continuity.get('gap_count', 0)
                        })
                    
                    # Priority scrapingu
                    suggestion = result.get('scraping_suggestion', {})
                    if suggestion.get('priority') == 'high':
                        analysis['high_priority_for_scraping'] += 1
            else:
                analysis['failed_registrations'] += 1
        
        # Generuj rekomendacje
        if analysis['high_priority_for_scraping'] > 0:
            analysis['recommendations'].append(
                f"🔥 {analysis['high_priority_for_scraping']} tickerów wymaga natychmiastowego scrapingu"
            )
        
        if analysis['data_quality_issues']:
            analysis['recommendations'].append(
                f"⚠️ {len(analysis['data_quality_issues'])} tickerów ma luki w danych historycznych"
            )
        
        logger.info(f"📊 Analiza importu: {analysis['successful_registrations']}/{analysis['total_tickers']} "
                   f"tickerów zarejestrowanych, {analysis['new_companies']} nowych spółek")
        
        return analysis
    
    def generate_integration_readiness_report(self) -> Dict[str, Any]:
        """Generuje raport gotowości do integracji danych historycznych ze scrapingiem"""
        try:
            # Pobierz wszystkie tickery
            all_tickers = self.ticker_manager.get_all_tickers()
            
            report = {
                'generated_at': datetime.now().isoformat(),
                'total_companies': len(all_tickers),
                'data_source_analysis': {},
                'scraping_readiness': {},
                'data_quality_summary': {},
                'integration_opportunities': []
            }
            
            # Analiza źródeł danych
            by_source = {}
            with_historical = 0
            with_scraping = 0
            ready_for_integration = 0
            
            for ticker_info in all_tickers:
                source = ticker_info['data_source']
                if source not in by_source:
                    by_source[source] = []
                by_source[source].append(ticker_info['ticker'])
                
                if 'historical' in source:
                    with_historical += 1
                if 'scraping' in source:
                    with_scraping += 1
                if source == 'both':
                    ready_for_integration += 1
            
            report['data_source_analysis'] = {
                'by_source': by_source,
                'with_historical': with_historical,
                'with_scraping': with_scraping,
                'fully_integrated': ready_for_integration
            }
            
            # Analiza gotowości do scrapingu
            tickers_for_scraping = self.ticker_manager.get_tickers_for_scraping()
            high_priority = []
            medium_priority = []
            
            for ticker in tickers_for_scraping:
                suggestion = self.ticker_manager.suggest_scraping_schedule(ticker)
                if suggestion['priority'] == 'high':
                    high_priority.append(ticker)
                elif suggestion['priority'] == 'medium':
                    medium_priority.append(ticker)
            
            report['scraping_readiness'] = {
                'total_ready': len(tickers_for_scraping),
                'high_priority': high_priority,
                'medium_priority': medium_priority,
                'low_priority': len(tickers_for_scraping) - len(high_priority) - len(medium_priority)
            }
            
            # Rekomendacje integracji
            if len(high_priority) > 0:
                report['integration_opportunities'].append({
                    'type': 'immediate_scraping',
                    'tickers': high_priority[:5],  # Top 5
                    'reason': 'Tickery z danymi historycznymi ale nieaktualnymi - natychmiast rozpocznij scraping'
                })
            
            if ready_for_integration < with_historical:
                historical_only = with_historical - ready_for_integration
                report['integration_opportunities'].append({
                    'type': 'enable_scraping',
                    'count': historical_only,
                    'reason': f'{historical_only} tickerów ma tylko dane historyczne - włącz dla nich scraping'
                })
            
            logger.info(f"📋 Raport integracji: {ready_for_integration}/{len(all_tickers)} "
                       f"w pełni zintegrowanych, {len(high_priority)} wysokiej priority")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Błąd generowania raportu integracji: {e}")
            return {}

def enhanced_auto_register_ticker_from_import(ticker: str, import_stats: Dict) -> Dict[str, Any]:
    """Główna funkcja rozszerzonej auto-rejestracji - zastąpienie starej funkcji"""
    try:
        auto_registration = EnhancedTickerAutoRegistration()
        return auto_registration.auto_register_from_import(ticker, import_stats)
    except Exception as e:
        logger.error(f"❌ Błąd enhanced auto-rejestracji dla {ticker}: {e}")
        return {
            'ticker': ticker,
            'registered': False,
            'errors': [str(e)]
        }

def main():
    """Demo rozszerzonej auto-rejestracji"""
    print("🚀 ENHANCED TICKER AUTO-REGISTRATION SYSTEM")
    print("=" * 60)
    
    try:
        auto_reg = EnhancedTickerAutoRegistration()
        
        # Test rejestracji nowego tickera
        test_ticker = "NEWTEST"
        test_stats = {
            'imported': 1500,
            'skipped': 10,
            'errors': 2,
            'source_file': 'NEWTEST_5min.txt'
        }
        
        print(f"\n🔄 Testuję rejestrację: {test_ticker}")
        result = auto_reg.auto_register_from_import(test_ticker, test_stats)
        
        print(f"✅ Rezultat rejestracji:")
        print(f"   Zarejestrowany: {result['registered']}")
        print(f"   Spółka: {result['company_info'].get('name', 'N/A')}")
        print(f"   Sektor: {result['company_info'].get('sector', 'N/A')}")
        print(f"   Źródło danych: {result['data_source_registered']}")
        print(f"   Analiza ciągłości: {result['continuity_analyzed']}")
        
        if result.get('scraping_suggestion'):
            suggestion = result['scraping_suggestion']
            print(f"   Rekomendacja scrapingu: {suggestion['priority']} - {suggestion['reason']}")
        
        # Generuj raport integracji
        print(f"\n📋 RAPORT GOTOWOŚCI INTEGRACJI:")
        print("-" * 40)
        
        report = auto_reg.generate_integration_readiness_report()
        
        print(f"📊 Łączne spółki: {report['total_companies']}")
        print(f"📈 Z danymi historycznymi: {report['data_source_analysis']['with_historical']}")
        print(f"🔄 Z scrapingiem: {report['data_source_analysis']['with_scraping']}")
        print(f"🎯 W pełni zintegrowane: {report['data_source_analysis']['fully_integrated']}")
        
        scraping = report['scraping_readiness']
        print(f"\n🚀 Gotowe do scrapingu: {scraping['total_ready']}")
        print(f"   🔥 Wysokiej priority: {len(scraping['high_priority'])}")
        print(f"   ⚠️ Średniej priority: {len(scraping['medium_priority'])}")
        
        if scraping['high_priority']:
            print(f"   Top priority: {', '.join(scraping['high_priority'][:5])}")
        
        print(f"\n💡 Możliwości integracji: {len(report['integration_opportunities'])}")
        for opp in report['integration_opportunities']:
            print(f"   - {opp['type']}: {opp['reason']}")
        
    except Exception as e:
        print(f"❌ Błąd główny: {e}")

if __name__ == "__main__":
    main()
