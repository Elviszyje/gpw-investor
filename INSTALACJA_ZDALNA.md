# INSTALACJA NA ZDALNYM KOMPUTERZE - GPW INVESTOR

## 🚀 SZYBKA INSTALACJA

### 1. Sklonuj repozytorium
```bash
git clone https://github.com/Elviszyje/gpw-investor.git
cd gpw_investor
```

### 2. Utwórz plik konfiguracyjny
```bash
cp .env.example .env
```

### 3. Edytuj konfigurację (WAŻNE!)
```bash
nano .env
```

**Zmień w .env:**
```bash
# OBOWIĄZKOWE - Zmień hasła!
DB_PASSWORD=TWOJE_BEZPIECZNE_HASLO_DB
POSTGRES_PASSWORD=TWOJE_BEZPIECZNE_HASLO_DB
SECRET_KEY=TWOJ_SUPER_BEZPIECZNY_KLUCZ_MIN_32_ZNAKI

# OPCJONALNE - Telegram (jeśli chcesz powiadomienia)
TELEGRAM_BOT_TOKEN=twoj-telegram-bot-token
TELEGRAM_DEFAULT_CHAT_ID=twoj-telegram-chat-id
```

### 4. Uruchom Docker
```bash
# Zbuduj i uruchom
docker-compose up -d --build

# LUB użyj skryptu zarządzającego
chmod +x docker-manager.sh
./docker-manager.sh rebuild
```

### 5. Sprawdź status
```bash
# Status kontenerów
docker-compose ps

# Logi aplikacji
docker-compose logs gpw_app

# Health check
curl http://localhost:5001/api/app/health
```

## 🔧 ROZWIĄZYWANIE PROBLEMÓW

### Problem: "ModuleNotFoundError: No module named 'import_historical_data'"
**Rozwiązanie:**
```bash
# Przebuduj obraz bez cache
docker-compose build --no-cache gpw_app
docker-compose up -d
```

### Problem: "password authentication failed for user gpw_user"
**Rozwiązanie:**
```bash
# 1. Sprawdź plik .env
cat .env | grep PASSWORD

# 2. Upewnij się, że hasła się zgadzają:
# DB_PASSWORD=twoje_haslo
# POSTGRES_PASSWORD=twoje_haslo

# 3. Zrestartuj kontenery
docker-compose down
docker-compose up -d
```

### Problem: "No such file or directory: tickers_config.json"
**Rozwiązanie:**
```bash
# Sprawdź czy plik istnieje
ls -la tickers_config.json

# Jeśli nie istnieje, utwórz go:
cp tickers_config.json.example tickers_config.json  # jeśli istnieje przykład
# LUB
git checkout HEAD -- tickers_config.json  # przywróć z repo
```

### Problem: Kontenery nie startują
**Rozwiązanie:**
```bash
# Sprawdź logi
docker-compose logs

# Wyczyść i zrestartuj
docker-compose down --volumes
docker-compose up -d --build
```

## 📋 WYMAGANIA SYSTEMOWE

- **Docker**: 20.0+
- **Docker Compose**: 2.0+
- **RAM**: 4GB minimum, 8GB zalecane
- **Dysk**: 10GB wolnego miejsca
- **Porty**: 5001, 5432, 6379 (muszą być wolne)

## 🌐 DOSTĘP DO APLIKACJI

Po uruchomieniu:
- **Aplikacja**: http://localhost:5001
- **Health Check**: http://localhost:5001/api/app/health
- **API Status**: http://localhost:5001/api/app/stats

## 🔐 BEZPIECZEŃSTWO

**WAŻNE** - W środowisku produkcyjnym:
1. ✅ Zmień wszystkie hasła w `.env`
2. ✅ Używaj silnych haseł (min. 32 znaki)
3. ✅ Ogranicz dostęp do portów (firewall)
4. ✅ Regularnie aktualizuj system

## 📞 WSPARCIE

Jeśli masz problemy:
1. Sprawdź logi: `docker-compose logs gpw_app`
2. Sprawdź dokumentację: `docs/`
3. Zgłoś issue na GitHub

## 🔄 AKTUALIZACJA

```bash
# Pobierz najnowsze zmiany
git pull origin main

# Przebuduj i uruchom
docker-compose up -d --build
```
