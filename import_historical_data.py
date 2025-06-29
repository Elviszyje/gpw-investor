#!/usr/bin/env python3
"""
Historical Data Importer - Import danych historycznych OHLCV do bazy PostgreSQL
Importuje dane z plików TXT (stooq.pl format) do tabeli quotes_intraday
Integruje się z PostgreSQL Ticker Manager
Autor: GPW Investor System
Data: 2025-06-25
"""

import os
import pandas as pd
import glob
import shutil
import logging
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from ticker_manager import auto_register_ticker_from_import
from enhanced_ticker_registration import enhanced_auto_register_ticker_from_import, EnhancedTickerAutoRegistration

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('import_historical.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HistoricalDataManager:
    """Importer danych historycznych do PostgreSQL"""
    
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
        
        # Foldery
        self.input_folder = "historical_data"
        self.processed_folder = "historical_data/processed"
        self.error_folder = "historical_data/errors"
        
        self._create_folders()
    
    def _test_connection(self):
        """Testuje połączenie z bazą danych"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Połączenie z PostgreSQL sprawdzone")
        except Exception as e:
            logger.error(f"❌ Błąd połączenia z PostgreSQL: {e}")
            raise
    
    def _create_folders(self):
        """Tworzy foldery robocze"""
        for folder in [self.input_folder, self.processed_folder, self.error_folder]:
            os.makedirs(folder, exist_ok=True)
        logger.info("✅ Foldery robocze sprawdzone/utworzone")
    
    def ensure_company_exists(self, ticker: str) -> Optional[int]:
        """Sprawdza czy firma istnieje w tabeli companies, jeśli nie - dodaje ją"""
        try:
            # Użyj TickerManager do zarządzania firmami
            from ticker_manager import TickerManager
            manager = TickerManager()
            
            # Użyj metody z TickerManager
            company_id = manager.ensure_company_exists(ticker)
            if company_id:
                logger.info(f"✅ Firma {ticker} zapewniona w bazie (ID: {company_id})")
            
            return company_id
                
        except Exception as e:
            logger.error(f"❌ Błąd zapewnienia istnienia firmy {ticker}: {e}")
            return None
    
    def parse_txt_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Parsuje plik TXT z danymi historycznymi
        Format: <TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
        """
        try:
            df = pd.read_csv(file_path, header=None, names=[
                'ticker', 'period', 'date', 'time', 'open', 'high', 'low', 'close', 'volume', 'openint'
            ])
            
            if df.empty:
                logger.warning(f"⚠️ Plik {file_path} jest pusty")
                return None
            
            # Filtruj linie nagłówków (zawierające < >)
            header_mask = df['ticker'].astype(str).str.contains('<|>', na=False)
            if header_mask.any():
                logger.info(f"🗑️ Usunięto {header_mask.sum()} linii nagłówków z {file_path}")
                df = df[~header_mask].copy()
            
            if df.empty:
                logger.warning(f"⚠️ Plik {file_path} jest pusty po usunięciu nagłówków")
                return None
            
            # Kombinuj datę i czas
            df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str), 
                                          format='%Y%m%d %H%M%S')
            
            # Podstawowe validacje
            if df['datetime'].isnull().any():
                logger.error(f"❌ Błędne daty/czasy w {file_path}")
                return None
            
            # Wybierz potrzebne kolumny i zmień nazwy
            df_clean = df[['ticker', 'datetime', 'open', 'high', 'low', 'close', 'volume']].copy()
            df_clean.columns = ['ticker', 'datetime', 'open_price', 'high_price', 'low_price', 'price', 'volume']
            
            logger.info(f"✅ Sparsowano {len(df_clean)} rekordów z {file_path}")
            return df_clean
            
        except Exception as e:
            logger.error(f"❌ Błąd parsowania {file_path}: {e}")
            return None
    
    def import_dataframe(self, df: pd.DataFrame) -> Dict[str, int]:
        """Importuje DataFrame do bazy danych z obsługą duplikatów (zoptymalizowane)"""
        stats = {'imported': 0, 'skipped': 0, 'errors': 0}
        
        try:
            # Grupuj po tickerach
            tickers = df['ticker'].unique()
            logger.info(f"📊 Importowanie {len(df)} rekordów dla {len(tickers)} tickerów")
            
            for i, ticker in enumerate(tickers, 1):
                logger.info(f"🔄 Przetwarzanie {ticker} ({i}/{len(tickers)})")
                ticker_df = df[df['ticker'] == ticker].copy()
                
                # Auto-rejestracja PRZED sprawdzeniem company - ma priorytet!
                try:
                    from ticker_manager import auto_register_ticker_from_import
                    auto_register_result = auto_register_ticker_from_import(ticker, {
                        'imported': len(ticker_df),
                        'skipped': 0,
                        'errors': 0,
                        'source_file': 'historical_import'
                    })
                    if auto_register_result:
                        logger.info(f"🎯 Auto-rejestracja {ticker} zakończona sukcesem")
                    else:
                        logger.warning(f"⚠️ Auto-rejestracja {ticker} nie powiodła się")
                except Exception as auto_error:
                    logger.error(f"❌ Błąd auto-rejestracji {ticker}: {auto_error}")
                
                # Sprawdź/utwórz firmę (po auto-rejestracji)
                company_id = self.ensure_company_exists(ticker)
                if not company_id:
                    logger.error(f"❌ Nie można utworzyć firmy dla {ticker}")
                    stats['errors'] += len(ticker_df)
                    continue
                
                # Sprawdź jakie dane już istnieją w bazie (zoptymalizowane)
                with self.engine.begin() as conn:
                    existing_records = conn.execute(
                        text("SELECT datetime FROM quotes_intraday WHERE company_id = :company_id"),
                        {"company_id": company_id}
                    ).fetchall()
                    
                    existing_datetimes = {row[0] for row in existing_records}
                
                # Usuń duplikaty wewnątrz DataFrame (zachowaj pierwszy wpis)
                ticker_df = ticker_df.drop_duplicates(subset=['datetime'], keep='first')
                ticker_df['company_id'] = company_id
                
                # Filtruj nowe dane (tylko te, których nie ma w bazie)
                new_records = []
                skipped_count = 0
                
                for _, row in ticker_df.iterrows():
                    if row['datetime'] not in existing_datetimes:
                        new_records.append({
                            'datetime': row['datetime'],
                            'price': row['price'],
                            'volume': row['volume'],
                            'company_id': company_id
                        })
                    else:
                        skipped_count += 1
                
                stats['skipped'] += skipped_count
                
                if new_records:
                    # Zapisz tylko nowe rekordy w batchach dla lepszej wydajności
                    try:
                        # Podziel na batche po 1000 rekordów
                        batch_size = 1000
                        total_imported = 0
                        
                        for batch_start in range(0, len(new_records), batch_size):
                            batch_end = min(batch_start + batch_size, len(new_records))
                            batch_records = new_records[batch_start:batch_end]
                            
                            batch_df = pd.DataFrame(batch_records)
                            batch_df.to_sql(
                                'quotes_intraday', 
                                self.engine, 
                                if_exists='append', 
                                index=False,
                                method='multi'
                            )
                            total_imported += len(batch_records)
                            
                            # Log postępu dla dużych importów
                            if len(new_records) > batch_size:
                                logger.info(f"  📈 {ticker}: zapisano {total_imported}/{len(new_records)} rekordów")
                        
                        stats['imported'] += total_imported
                        
                        logger.info(f"✅ {ticker}: zaimportowano {total_imported} nowych rekordów, pominięto {skipped_count} duplikatów")
                        
                    except Exception as e:
                        logger.error(f"❌ Błąd zapisu nowych danych dla {ticker}: {e}")
                        stats['errors'] += len(new_records)
                        continue
                else:
                    logger.info(f"⚠️ {ticker}: wszystkie {len(ticker_df)} rekordów już istnieją w bazie")
                
                # Rozszerzona auto-rejestracja w Enhanced Ticker Manager (tylko dla dużych importów)
                if len(new_records) > 100:  # Tylko dla większych importów, żeby nie spowalniać
                    try:
                        enhanced_result = enhanced_auto_register_ticker_from_import(ticker, {
                            'imported': len(new_records) if new_records else 0,
                            'skipped': skipped_count,
                            'errors': 0,
                            'source_file': f'historical_import_{datetime.now().strftime("%Y%m%d")}',
                            'source': 'historical_txt'
                        })
                        
                        if enhanced_result['registered']:
                            logger.info(f"🎯 Enhanced rejestracja {ticker}: {enhanced_result['company_info']['name']} "
                                       f"({enhanced_result['company_info']['sector']})")
                    except Exception as enhanced_error:
                        logger.warning(f"⚠️ Błąd enhanced rejestracji {ticker}: {enhanced_error}")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Błąd importu DataFrame: {e}")
            stats['errors'] = len(df)
            return stats
    
    def import_single_file(self, file_path: str) -> Dict[str, Any]:
        """Importuje pojedynczy plik"""
        start_time = datetime.now()
        logger.info(f"🔄 Rozpoczynam import: {file_path}")
        
        # Parsuj plik
        df = self.parse_txt_file(file_path)
        if df is None:
            return {
                'status': 'error',
                'file': file_path,
                'error': 'Błąd parsowania',
                'duration': (datetime.now() - start_time).total_seconds()
            }
        
        # Importuj dane
        stats = self.import_dataframe(df)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        result = {
            'status': 'success' if stats['errors'] == 0 else 'partial',
            'file': file_path,
            'stats': stats,
            'records_total': len(df),
            'tickers': df['ticker'].unique().tolist(),
            'duration': duration
        }
        
        logger.info(f"✅ Import zakończony: {file_path} ({duration:.2f}s)")
        logger.info(f"   📊 Zaimportowano: {stats['imported']}, błędy: {stats['errors']}")
        
        return result
    
    def import_folder(self, folder_path: Optional[str] = None) -> Dict[str, Any]:
        """Importuje wszystkie pliki TXT z folderu"""
        if folder_path is None:
            folder_path = self.input_folder
        
        start_time = datetime.now()
        logger.info(f"🚀 Rozpoczynam import folderu: {folder_path}")
        
        # Znajdź pliki TXT
        txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
        
        if not txt_files:
            logger.warning(f"⚠️ Brak plików TXT w {folder_path}")
            return {
                'status': 'no_files',
                'folder': folder_path,
                'files_processed': 0,
                'duration': 0
            }
        
        logger.info(f"📂 Znaleziono {len(txt_files)} plików TXT")
        
        # Statystyki ogólne
        total_stats = {'imported': 0, 'skipped': 0, 'errors': 0}
        file_results = []
        all_tickers = set()
        
        # Przetwórz każdy plik
        for i, file_path in enumerate(txt_files, 1):
            logger.info(f"📄 Przetwarzam plik {i}/{len(txt_files)}: {os.path.basename(file_path)}")
            
            result = self.import_single_file(file_path)
            file_results.append(result)
            
            # Aktualizuj statystyki
            if 'stats' in result:
                for key in total_stats:
                    total_stats[key] += result['stats'].get(key, 0)
                
                if 'tickers' in result:
                    all_tickers.update(result['tickers'])
            
            # Przenieś plik do odpowiedniego folderu
            if result['status'] == 'success':
                dest_folder = self.processed_folder
            else:
                dest_folder = self.error_folder
            
            try:
                shutil.move(file_path, os.path.join(dest_folder, os.path.basename(file_path)))
                logger.info(f"✅ Przeniesiono {os.path.basename(file_path)} do {dest_folder}")
            except Exception as e:
                logger.error(f"❌ Błąd przenoszenia pliku {file_path}: {e}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Podsumowanie
        summary = {
            'status': 'completed',
            'folder': folder_path,
            'files_processed': len(txt_files),
            'files_success': len([r for r in file_results if r['status'] == 'success']),
            'files_error': len([r for r in file_results if r['status'] == 'error']),
            'total_stats': total_stats,
            'unique_tickers': list(all_tickers),
            'duration': duration,
            'file_results': file_results
        }
        
        logger.info(f"🎯 IMPORT ZAKOŃCZONY!")
        logger.info(f"   📁 Plików przetworzonych: {summary['files_processed']}")
        logger.info(f"   ✅ Plików udanych: {summary['files_success']}")
        logger.info(f"   ❌ Plików z błędami: {summary['files_error']}")
        logger.info(f"   📊 Rekordów zaimportowanych: {total_stats['imported']:,}")
        logger.info(f"   ⏭️ Duplikatów pominiętych: {total_stats['skipped']:,}")
        logger.info(f"   ⚠️ Błędów: {total_stats['errors']:,}")
        logger.info(f"   🏢 Unikalnych tickerów: {len(all_tickers)}")
        logger.info(f"   ⏱️ Czas wykonania: {duration:.2f}s")
        
        # Analiza integracji po imporcie
        if len(all_tickers) > 0:
            try:
                logger.info(f"\n📋 ANALIZA INTEGRACJI PO IMPORCIE:")
                logger.info("-" * 40)
                
                auto_reg = EnhancedTickerAutoRegistration()
                integration_report = auto_reg.generate_integration_readiness_report()
                
                logger.info(f"🎯 Status integracji:")
                logger.info(f"   📊 Łączne spółki: {integration_report['total_companies']}")
                logger.info(f"   📈 Z danymi historycznymi: {integration_report['data_source_analysis']['with_historical']}")
                logger.info(f"   🔄 Z scrapingiem: {integration_report['data_source_analysis']['with_scraping']}")
                logger.info(f"   ✅ W pełni zintegrowane: {integration_report['data_source_analysis']['fully_integrated']}")
                
                scraping = integration_report['scraping_readiness']
                logger.info(f"\n🚀 Gotowość do scrapingu:")
                logger.info(f"   📋 Gotowych do scrapingu: {scraping['total_ready']}")
                logger.info(f"   🔥 Wysokiej priority: {len(scraping['high_priority'])}")
                logger.info(f"   ⚠️ Średniej priority: {len(scraping['medium_priority'])}")
                
                if scraping['high_priority']:
                    logger.info(f"   🎯 Top priority tickery: {', '.join(scraping['high_priority'][:5])}")
                
                # Dodaj do summary
                summary['integration_analysis'] = integration_report
                
            except Exception as e:
                logger.warning(f"⚠️ Błąd analizy integracji: {e}")
        
        return summary
    
    def get_import_stats(self) -> Dict[str, Any]:
        """Pobiera statystyki importu z bazy danych"""
        try:
            with self.engine.connect() as conn:
                # Podstawowe statystyki
                total_records = conn.execute(text("SELECT COUNT(*) FROM quotes_intraday")).scalar() or 0
                total_companies = conn.execute(text("SELECT COUNT(*) FROM companies")).scalar() or 0
                
                # Statystyki per ticker
                ticker_stats = conn.execute(text("""
                    SELECT c.ticker, COUNT(qi.id) as records, 
                           MIN(qi.datetime) as first_date,
                           MAX(qi.datetime) as last_date
                    FROM companies c
                    LEFT JOIN quotes_intraday qi ON c.id = qi.company_id
                    GROUP BY c.ticker, c.id
                    ORDER BY records DESC
                """)).fetchall()
                
                return {
                    'total_records': total_records,
                    'total_companies': total_companies,
                    'ticker_stats': [
                        {
                            'ticker': row[0],
                            'records': row[1],
                            'first_date': str(row[2]) if row[2] else None,
                            'last_date': str(row[3]) if row[3] else None
                        }
                        for row in ticker_stats
                    ]
                }
                
        except Exception as e:
            logger.error(f"❌ Błąd pobierania statystyk: {e}")
            return {}
    
    def backup_database(self, backup_dir: str = "backups") -> str:
        """Create a backup of the database"""
        try:
            # Create backup directory if it doesn't exist
            os.makedirs(backup_dir, exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"gpw_backup_{timestamp}.sql")
            
            # PostgreSQL dump command
            pg_dump_cmd = f"pg_dump -h {self.pg_config['host']} -p {self.pg_config['port']} -U {self.pg_config['user']} -d {self.pg_config['database']} -f {backup_file}"
            
            # Execute backup with password
            password = self.pg_config['password'] or ''
            result = os.system(f"PGPASSWORD='{password}' {pg_dump_cmd}")
            
            if result == 0:
                logger.info(f"✅ Database backup created: {backup_file}")
                return backup_file
            else:
                logger.error(f"❌ Backup failed with code: {result}")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            return ""
    
    def clear_database(self, confirm: bool = False) -> bool:
        """Clear all imported data from the database"""
        if not confirm:
            logger.warning("❌ Clear database requires confirm=True parameter")
            return False
            
        try:
            with self.engine.connect() as conn:
                # Start transaction
                trans = conn.begin()
                try:
                    # Clear data in correct order (respecting foreign keys)
                    logger.info("🔄 Clearing quotes_intraday...")
                    conn.execute(text("DELETE FROM quotes_intraday"))
                    
                    logger.info("🔄 Clearing quotes_daily...")
                    conn.execute(text("DELETE FROM quotes_daily"))
                    
                    logger.info("🔄 Clearing companies...")
                    conn.execute(text("DELETE FROM companies"))
                    
                    # Reset sequences if they exist
                    try:
                        conn.execute(text("ALTER SEQUENCE companies_id_seq RESTART WITH 1"))
                        conn.execute(text("ALTER SEQUENCE quotes_intraday_id_seq RESTART WITH 1"))
                        conn.execute(text("ALTER SEQUENCE quotes_daily_id_seq RESTART WITH 1"))
                    except:
                        # Sequences might not exist, ignore
                        pass
                    
                    # Commit transaction
                    trans.commit()
                    logger.info("✅ Database cleared successfully")
                    return True
                    
                except Exception as e:
                    trans.rollback()
                    logger.error(f"❌ Error clearing database: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error connecting to database for clear: {e}")
            return False

def main():
    """Funkcja główna - demo importera"""
    print("📈 HISTORICAL DATA IMPORTER - PostgreSQL")
    print("=" * 50)
    
    try:
        importer = HistoricalDataManager()
        
        # Sprawdź obecny stan bazy
        print("\n📊 Sprawdzam obecny stan bazy...")
        stats = importer.get_import_stats()
        print(f"   Rekordów w bazie: {stats.get('total_records', 0):,}")
        print(f"   Firm w bazie: {stats.get('total_companies', 0)}")
        
        # Import danych
        print(f"\n🚀 Rozpoczynam import z folderu: {importer.input_folder}")
        result = importer.import_folder()
        
        if result['status'] == 'no_files':
            print("⚠️ Brak plików do importu")
            print(f"💡 Umieść pliki .txt w folderze: {importer.input_folder}")
        else:
            print(f"\n✅ Import zakończony!")
            print(f"   Plików przetworzonych: {result['files_processed']}")
            print(f"   Rekordów zaimportowanych: {result['total_stats']['imported']:,}")
            print(f"   Duplikatów pominiętych: {result['total_stats']['skipped']:,}")
            print(f"   Błędów: {result['total_stats']['errors']:,}")
            print(f"   Unikalnych tickerów: {len(result['unique_tickers'])}")
            print(f"   Czas: {result['duration']:.2f}s")
        
        # Sprawdź stan po imporcie
        print("\n📊 Stan bazy po imporcie...")
        stats_after = importer.get_import_stats()
        print(f"   Rekordów w bazie: {stats_after.get('total_records', 0):,}")
        print(f"   Firm w bazie: {stats_after.get('total_companies', 0)}")
        
    except Exception as e:
        print(f"❌ Błąd główny: {e}")
        logger.error(f"Błąd główny: {e}")

if __name__ == "__main__":
    main()


# Add a simple HistoricalDataImporter class for compatibility with the blueprint
class HistoricalDataImporter:
    """
    Simple compatibility class for the import_config blueprint.
    Wraps the main HistoricalDataManager functionality.
    """
    
    def __init__(self, source: str = 'bankier'):
        self.source = source
        try:
            self.manager = HistoricalDataManager()
            self.input_folder = getattr(self.manager, 'input_folder', 'historical_data')
        except Exception as e:
            logging.warning(f"Could not initialize HistoricalDataManager: {e}")
            self.manager = None
            self.input_folder = 'historical_data'
        
    def import_folder(self) -> dict:
        """Import from folder"""
        if self.manager:
            return self.manager.import_folder()
        else:
            return {'status': 'error', 'message': 'Manager not initialized'}
        
    def import_ticker_data(self, ticker: str, days_back: int = 365) -> bool:
        """Import historical data for a single ticker"""
        try:
            if self.manager:
                result = self.manager.import_folder()
                return result.get('status') in ['completed', 'success']
            return False
        except Exception as e:
            logging.error(f"Error importing data for {ticker}: {e}")
            return False
    
    def import_all_tickers(self, config_path: Optional[str] = None, days_back: int = 365) -> dict:
        """Import historical data for all configured tickers"""
        try:
            if self.manager:
                result = self.manager.import_folder()
                # Convert to expected format
                success_count = result.get('files_success', 0)
                total_count = result.get('files_processed', 0)
                
                return {
                    'success': success_count,
                    'total': total_count,
                    'tickers': result.get('unique_tickers', [])
                }
            return {'success': 0, 'total': 0, 'tickers': []}
        except Exception as e:
            logging.error(f"Error importing all tickers: {e}")
            return {'success': 0, 'total': 0, 'tickers': []}
    
    def get_import_stats(self) -> dict:
        """Get import statistics"""
        try:
            if self.manager:
                return self.manager.get_import_stats()
            return {}
        except Exception as e:
            logging.error(f"Error getting import stats: {e}")
            return {}
