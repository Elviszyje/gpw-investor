# 🚀 GPW Investor - Zunifikowany Production Deployment

## 🔴 Problem na serwerze zdalnym
```
❌ Błąd pobierania listy tickerów: (psycopg2.OperationalError) 
connection to server at "postgres" (172.56.0.3), port 5432 failed: 
FATAL: password authentication failed for user "gpw_user"
```

## ✅ Rozwiązanie - Zunifikowana Konfiguracja

### 📁 Nowe pliki (UŻYJ TYLKO TYCH):
```
✅ docker-compose.unified.yml    - Główna konfiguracja Docker
✅ .env.unified                  - Template zmiennych środowiskowych
✅ deploy-unified.sh             - Skrypt deployment i zarządzania
✅ database-schema-clean.sql     - Clean schema (bez RAISE NOTICE)
✅ clean-setup.sh               - Automatyczny setup i migracja
```

### 🗂️ Stare pliki (DO ARCHIWIZACJI):
```
🗑️ docker-compose.yml
🗑️ docker-compose.production.yml  
🗑️ docker-compose.compatible.yml
🗑️ docker-compose.optimized.yml
🗑️ migrate-database*.sh (wszystkie)
🗑️ deploy.sh, deploy-remote.sh
```

## 🚀 Instrukcja Deployment

### Option 1: Automatyczny Clean Setup (ZALECANE)
```bash
# 1. Uruchom automatyczny setup
./clean-setup.sh

# Skrypt automatycznie:
# - Archiwizuje stare pliki
# - Kopiuje .env.unified do .env
# - Poprosi o ustawienie bezpiecznych haseł
# - Uruchomi deployment
```

### Option 2: Manual Setup
```bash
# 1. Archiwizuj stare pliki
mkdir -p archive/old-configs
mv docker-compose*.yml archive/old-configs/ (oprócz unified)
mv migrate-database*.sh archive/old-configs/
mv deploy*.sh archive/old-configs/ (oprócz unified)

# 2. Setup environment
cp .env.unified .env

# 3. WAŻNE: Edytuj .env i ustaw bezpieczne hasła!
nano .env
# Zmień:
# POSTGRES_PASSWORD=TWOJE_BEZPIECZNE_HASLO
# SECRET_KEY=TWOJ_BEZPIECZNY_KLUCZ_MIN_32_ZNAKI

# 4. Deploy
./deploy-unified.sh deploy
```

## 🔧 Zarządzanie aplikacją

```bash
# Status i health check
./deploy-unified.sh status

# Logi aplikacji
./deploy-unified.sh logs

# Start/Stop/Restart
./deploy-unified.sh start
./deploy-unified.sh stop  
./deploy-unified.sh restart

# Migracja bazy danych
./deploy-unified.sh migrate

# Backup bazy danych
./deploy-unified.sh backup

# Shell w kontenerze
./deploy-unified.sh shell

# Naprawa problemów
./deploy-unified.sh fix

# Czyszczenie kontenerów
./deploy-unified.sh clean
```

## 🔍 Weryfikacja po deployment

### 1. Sprawdź status kontenerów
```bash
./deploy-unified.sh status
```

### 2. Testuj API
```bash
# Health check
curl http://localhost:5000/api/app/health

# Lista tickerów (to wcześniej nie działało!)
curl http://localhost:5000/api/tickers/list

# Główna strona
curl http://localhost:5000/
```

### 3. Sprawdź aplikację w przeglądarce
```
http://localhost:5000
```

## 🔧 Kluczowe zmiany w zunifikowanej konfiguracji

### 1. **Spójne zmienne środowiskowe**
- Wszystkie `DB_*` i `POSTGRES_*` zmienne są identyczne
- Eliminuje problemy z uwierzytelnianiem PostgreSQL
- Jedna konsystentna konfiguracja we wszystkich komponentach

### 2. **Clean Database Schema**
- `database-schema-clean.sql` - usunięto `RAISE NOTICE`
- Kompatybilny z PostgreSQL (brak błędów exception handling)
- Idempotentny - można uruchamiać wielokrotnie

### 3. **Zunifikowany Docker Compose**
- `docker-compose.unified.yml` - jedna konfiguracja
- Subnet `172.56.0.0/16` (dopasowany do błędu)
- Spójne nazwy kontenerów i volumów
- Health checks dla wszystkich serwisów

### 4. **Automatyczny deployment i zarządzanie**
- `deploy-unified.sh` - wszystko w jednym skrypcie
- Automatyczna walidacja środowiska
- Funkcje naprawy problemów
- Backup i monitoring

### 5. **Error handling**
- Graceful degradation przy problemach z bazą
- Lepsze logowanie błędów
- Automatyczne retry dla połączeń

## 🚨 Troubleshooting

### Problem z uwierzytelnianiem PostgreSQL
```bash
# 1. Sprawdź czy hasła są ustawione w .env
grep POSTGRES_PASSWORD .env

# 2. Wyczyść i restart
./deploy-unified.sh fix
./deploy-unified.sh deploy

# 3. Sprawdź bezpośrednio PostgreSQL
docker exec -it gpw_postgres psql -U gpw_user -d gpw_investor -c "SELECT 1;"
```

### Problem z siecią Docker
```bash
# Sprawdź sieci
docker network ls
docker network inspect gpw_docker_gpw_network

# Restart Docker (macOS/Windows)
docker system prune -f
```

### Problem z kontenerami
```bash
# Debug kontenerów
./deploy-unified.sh logs
docker-compose -f docker-compose.unified.yml ps

# Sprawdź health checks
docker inspect gpw_postgres | grep Health -A 10
```

### Aplikacja nie odpowiada
```bash
# Sprawdź port i proces
netstat -tulpn | grep :5000
docker logs gpw_app

# Restart aplikacji
./deploy-unified.sh restart
```

## 📊 Monitoring po deployment

### 1. **Health Checks**
```bash
# API health
curl -s http://localhost:5000/api/app/health | jq .

# Database health  
curl -s http://localhost:5000/api/tickers/list | jq .
```

### 2. **Resource monitoring**
```bash
# Container stats
docker stats gpw_postgres gpw_redis gpw_app

# Disk usage
docker system df
```

### 3. **Logs**
```bash
# Real-time logs
./deploy-unified.sh logs

# PostgreSQL logs
docker logs gpw_postgres

# Application logs
docker logs gpw_app
```

## 🎯 Po sukcesie deployment

Po potwierdzeniu, że zunifikowana konfiguracja działa stabilnie:

1. **Usuń stare pliki** z `archive/old-configs/`
2. **Skonfiguruj backup** używając `./deploy-unified.sh backup`
3. **Monitoruj logi** regularnie
4. **Testuj funkcjonalności** importu danych i ML

---

## 📞 Support

Jeśli nadal wystąpią problemy:

1. Uruchom: `./deploy-unified.sh fix`
2. Sprawdź logi: `./deploy-unified.sh logs`
3. Zweryfikuj zmienne środowiskowe w `.env`
4. Sprawdź dokumentację `DEPLOYMENT-UNIFIED.md`

Zunifikowana konfiguracja rozwiązuje wszystkie zidentyfikowane problemy i zapewnia stabilne, produkcyjne środowisko dla GPW Investor.
