# GPW Investor - Deployment Production (Zunifikowany)

## Problem na serwerze zdalnym
❌ **Błąd:** `connection to server at "postgres" (172.56.0.3), port 5432 failed: FATAL: password authentication failed for user "gpw_user"`

## Rozwiązanie - Zunifikowana Konfiguracja

### 1. Pliki do użycia:
```
✅ docker-compose.unified.yml    - główna konfiguracja
✅ .env.unified                  - template zmiennych środowiskowych 
✅ deploy-unified.sh             - skrypt deployment
✅ database-schema-clean.sql     - clean schema bez RAISE NOTICE
```

### 2. Archiwizuj stare pliki:
```bash
mkdir -p archive/old-configs
mv docker-compose.yml archive/old-configs/
mv docker-compose.production.yml archive/old-configs/
mv docker-compose.compatible.yml archive/old-configs/
mv docker-compose.optimized.yml archive/old-configs/
mv migrate-database*.sh archive/old-configs/
mv deploy.sh archive/old-configs/
mv deploy-remote.sh archive/old-configs/
```

### 3. Setup Environment:
```bash
# Skopiuj template do .env
cp .env.unified .env

# Edytuj .env i ustaw bezpieczne hasła:
nano .env
```

**WAŻNE:** Zmień wszystkie hasła w `.env`:
```bash
POSTGRES_PASSWORD=TWOJE_BEZPIECZNE_HASLO
SECRET_KEY=TWOJ_BEZPIECZNY_KLUCZ_MIN_32_ZNAKI
```

### 4. Deployment:
```bash
# Pełny deployment
./deploy-unified.sh deploy

# Sprawdź status
./deploy-unified.sh status

# Zobacz logi w przypadku problemów
./deploy-unified.sh logs
```

### 5. Inne komendy:
```bash
./deploy-unified.sh start      # Start kontenerów
./deploy-unified.sh stop       # Stop kontenerów
./deploy-unified.sh restart    # Restart
./deploy-unified.sh migrate    # Migracja bazy danych
./deploy-unified.sh backup     # Backup bazy
./deploy-unified.sh shell      # Shell w kontenerze
./deploy-unified.sh fix        # Napraw problemy
./deploy-unified.sh clean      # Wyczyść kontenery
```

## Kluczowe zmiany w zunifikowanej konfiguracji:

1. **Spójne zmienne środowiskowe:** 
   - DB_* i POSTGRES_* zmienne są identyczne
   - Eliminuje problemy z uwierzytelnianiem

2. **Clean Database Schema:**
   - Usunięto `RAISE NOTICE` (powodowały błędy PostgreSQL)
   - Używa `database-schema-clean.sql`

3. **Sieć Dockera:**
   - Subnet: `172.56.0.0/16` (dopasowany do błędu)
   - Spójne nazwy kontenerów

4. **Health Checks:**
   - Automatyczne sprawdzanie stanu serwisów
   - Timeout i retry logic

5. **Jednolity skrypt deployment:**
   - Wszystko w jednym pliku
   - Automatyczna walidacja
   - Fix funkcje dla problemów

## Troubleshooting:

### Problem z uwierzytelnianiem:
```bash
# Wyczyść wszystko i zacznij od nowa
./deploy-unified.sh fix
./deploy-unified.sh deploy
```

### Problem z siecią:
```bash
# Sprawdź sieci Docker
docker network ls
docker network inspect <network_name>
```

### Problem z kontenerami:
```bash
# Debug kontenerów
./deploy-unified.sh logs
docker-compose -f docker-compose.unified.yml ps
```

### Problem z bazą danych:
```bash
# Sprawdź PostgreSQL bezpośrednio
docker exec -it gpw_postgres psql -U gpw_user -d gpw_investor -c "SELECT 1;"
```

## Po deployment sprawdź:

1. **Status kontenerów:**
   ```bash
   ./deploy-unified.sh status
   ```

2. **Aplikacja działa:**
   ```bash
   curl http://localhost:5000/api/app/health
   ```

3. **Baza danych działa:**
   ```bash
   curl http://localhost:5000/api/tickers/list
   ```

4. **Import danych:**
   ```bash
   curl http://localhost:5000/api/import/historical-data
   ```

## Pliki do usunięcia po sukcesie:
Po potwierdzeniu, że zunifikowana konfiguracja działa, usuń:
- Wszystkie stare `docker-compose*.yml` (oprócz `unified`)
- Wszystkie stare `migrate-database*.sh`  
- Stare `deploy*.sh` (oprócz `unified`)
- Stare `.env.*` (oprócz `unified` jako template)

Ta konfiguracja rozwiązuje wszystkie zidentyfikowane problemy i zapewnia spójne, działające środowisko production.
