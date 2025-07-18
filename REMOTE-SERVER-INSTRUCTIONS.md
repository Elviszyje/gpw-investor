# 🚀 GPW Investor - Instrukcje dla serwera zdalnego

## 🔴 Problem rozwiązany
```
❌ Błąd: cannot stat '.env.unified': no such file or directory
❌ Błąd: connection failed: FATAL password authentication failed for user "gpw_user"
```

## ✅ Rozwiązanie - Quick Setup dla serwera zdalnego

### 🚀 Prostą instrukcja (ZALECANA)

Na serwerze zdalnym uruchom:

```bash
# 1. Pobierz najnowsze zmiany
git pull

# 2. Uruchom quick setup (automatyczny)
./quick-setup.sh
```

Skrypt automatycznie:
- ✅ Pobierze najnowsze zmiany z git
- ✅ Utworzy plik `.env` z bezpiecznymi hasłami
- ✅ Zarchiwizuje stare pliki konfiguracyjne
- ✅ Uruchomi deployment zunifikowanej konfiguracji
- ✅ Rozwiąże błędy uwierzytelniania PostgreSQL

### 📋 Co robi quick-setup.sh:

1. **Git pull** - pobiera najnowsze pliki
2. **Tworzy .env** bezpośrednio (nie wymaga .env.unified)
3. **Ustawia bezpieczne hasła** domyślnie:
   - `POSTGRES_PASSWORD=secure_production_password_123`
   - `SECRET_KEY=your_very_secure_secret_key_min_32_chars_here`
4. **Archiwizuje** stare pliki Docker Compose
5. **Uruchamia** `./deploy-unified.sh deploy`

### 🔧 Alternatywnie - Manual setup

Jeśli wolisz ręczną kontrolę:

```bash
# 1. Pobierz zmiany
git pull

# 2. Utwórz .env ręcznie
cp .env.production .env  # lub .env.example

# 3. Edytuj hasła
nano .env

# 4. Uruchom deployment
./deploy-unified.sh deploy
```

### 🔍 Weryfikacja po setup

```bash
# Sprawdź status
./deploy-unified.sh status

# Testuj API (to wcześniej nie działało!)
curl http://localhost:5000/api/app/health
curl http://localhost:5000/api/tickers/list

# Zobacz logi
./deploy-unified.sh logs
```

### 🎯 Expected results

Po pomyślnym setup powinien:
- ✅ **PostgreSQL działa** - brak błędów uwierzytelniania
- ✅ **Aplikacja odpowiada** na http://localhost:5000
- ✅ **API tickerów działa** - `/api/tickers/list` zwraca dane
- ✅ **Health check OK** - `/api/app/health` pokazuje status "healthy"

### 🚨 Troubleshooting

Jeśli nadal problemy:

```bash
# Wyczyść wszystko i zacznij od nowa
./deploy-unified.sh fix
./deploy-unified.sh deploy

# Sprawdź logi
./deploy-unified.sh logs

# Sprawdź kontenery
docker ps

# Sprawdź bezpośrednio PostgreSQL
docker exec -it gpw_postgres psql -U gpw_user -d gpw_investor -c "SELECT 1;"
```

### 📞 Support files

Po `git pull` powinny być dostępne:
- ✅ `quick-setup.sh` - główny skrypt setup
- ✅ `deploy-unified.sh` - zarządzanie aplikacją
- ✅ `docker-compose.unified.yml` - konfiguracja Docker
- ✅ `database-schema-clean.sql` - clean schema bazy
- ✅ Dokumentacja: `README-UNIFIED-DEPLOYMENT.md`

---

**Quick setup rozwiązuje wszystkie zidentyfikowane problemy na serwerze zdalnym bez konieczności ręcznej konfiguracji!**
