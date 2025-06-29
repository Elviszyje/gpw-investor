# 🗄️ SCHEMAT BAZY DANYCH GPW INVESTOR

## 📄 Nowy, skonsolidowany schemat

**Plik główny:** `database-schema.sql`

### ✅ **Zalety nowego rozwiązania:**

1. **Jeden plik zamiast trzech** - `database-schema.sql` zastępuje:
   - `init-db.sql` (podstawowa inicjalizacja)
   - `init-schema.sql` (kompletny schemat)
   - `fix-db-schema.sql` (naprawki)

2. **Idempotentny** - można uruchomić wielokrotnie bez błędów
3. **Kompletny** - zawiera wszystkie tabele, indeksy, dane początkowe
4. **Odporny na błędy** - używa `IF NOT EXISTS`, `ON CONFLICT DO NOTHING`
5. **Transakcyjny** - wszystkie operacje w jednej transakcji
6. **Zoptymalizowany** - dodane indeksy dla wydajności

### 📊 **Struktura bazy danych:**

#### **Główne tabele:**
- `companies` - spółki giełdowe
- `ticker_mappings` - mapowania symbolów dla różnych źródeł
- `quotes_daily` - notowania dzienne
- `quotes_intraday` - notowania intraday

#### **ML i rekomendacje:**
- `recommendations` - rekomendacje z ML (ujednolicona struktura)
- `recommendation_tracking` - śledzenie zmian rekomendacji
- `recommendation_results` - wyniki wykonanych rekomendacji
- `ml_predictions` - predykcje modeli ML

#### **Wiadomości:**
- `articles` - artykuły i wiadomości
- `espi_reports` - komunikaty ESPI

#### **System:**
- `health_check` - monitoring zdrowia aplikacji
- `operation_logs` - logi operacji systemowych
- `app_config` - konfiguracja aplikacji
- `price_rules` - reguły alertów cenowych

### 🔧 **Optymalizacje:**

1. **28+ indeksów wydajnościowych** na kluczowych kolumnach
2. **Composite indeksy** dla złożonych zapytań i joinów
3. **Partial indeksy** z WHERE dla filtrowanych danych
4. **Triggery** do automatycznej aktualizacji `updated_at`
5. **Constrainty** i klucze obce dla integralności danych
6. **JSONB** dla elastycznego przechowywania metadanych
7. **Ustawienia timezone** na Europe/Warsaw
8. **PostgreSQL optimizations** (shared_buffers, work_mem, etc.)
9. **Automatyczne VACUUM** z zoptymalizowanymi parametrami
10. **Full-text search indeksy** dla artykułów (GIN)
11. **VACUUM ANALYZE** na końcu inicjalizacji

### 🚀 **Użycie:**

Schema jest automatycznie wykonywany przez `docker-entrypoint.sh` podczas pierwszego uruchomienia kontenera.

**Ręczne wykonanie:**
```bash
psql -U gpw_user -d gpw_investor -f database-schema.sql
```

### 📁 **Archiwum:**

Stare pliki SQL zostały przeniesione do `archive/old-sql-files/` i są ignorowane przez git.

### 🔄 **Migracje:**

Nowy schemat zawiera wszystkie kolumny wymagane przez aplikację, w tym:
- Kolumny legacy dla kompatybilności wstecznej
- Nowe kolumny wymagane przez aktualny kod
- Poprawne typy danych i constrainty

**Nie są już potrzebne osobne skrypty migracyjne** - wszystko jest zawarte w jednym pliku.
