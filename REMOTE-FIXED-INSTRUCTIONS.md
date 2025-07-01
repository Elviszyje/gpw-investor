# 🚀 GPW Investor - Instrukcje dla Serwera Zdalnego (Aktualizowane)

## 🔴 Rozwiązanie problemów na serwerze zdalnym

### Problem 1: `cannot stat '.env.unified': no such file or directory`
### Problem 2: `syntaxerror at or near "\", Line 2: DO \$\$`

## ✅ Rozwiązanie - Aktualizowane instrukcje

### 1. Na serwerze zdalnym pobierz najnowsze zmiany:
```bash
cd /path/to/gpw_investor
git pull
```

### 2. Sprawdź dostępne pliki:
```bash
ls -la *.sh *.yml .env*
```

### 3. Opcja A: Użyj nowego prostego skryptu migracji (ZALECANE)
```bash
# Sprawdź czy masz .env file
cat .env

# Jeśli nie ma .env, skopiuj z przykładu i edytuj
cp .env.example .env
nano .env

# Uruchom prostą migrację (automatycznie znajdzie PostgreSQL)
./migrate-simple.sh
```

### 4. Opcja B: Użyj naprawionego skryptu remote
```bash
# Naprawiony skrypt bez błędów składni SQL
./migrate-database-remote.sh
```

### 5. Opcja C: Jeśli masz dostęp do zunifikowanych plików
```bash
# Jeśli .env.unified istnieje
cp .env.unified .env
nano .env  # Ustaw bezpieczne hasła!

# Używaj zunifikowanych skryptów
./deploy-unified.sh deploy
```

## 🔧 Najlepszy workflow dla serwera zdalnego:

### Krok 1: Setup środowiska
```bash
# Sprawdź obecną konfigurację
ls -la .env*
cat .env 2>/dev/null || echo "Brak .env"

# Jeśli brak .env, utwórz z template
if [ ! -f ".env" ]; then
    if [ -f ".env.unified" ]; then
        cp .env.unified .env
    elif [ -f ".env.example" ]; then
        cp .env.example .env
    else
        echo "Utwórz .env ręcznie"
        exit 1
    fi
fi

# WAŻNE: Edytuj .env i ustaw prawdziwe hasła!
nano .env
```

### Krok 2: Migracja bazy danych
```bash
# Użyj nowego, prostego skryptu
./migrate-simple.sh

# Skrypt automatycznie:
# - Znajdzie PostgreSQL (Docker lub bezpośrednio)
# - Przetestuje różne porty (5432, 15432)
# - Użyje heredoc dla clean SQL
# - Pokaże szczegóły błędów
```

### Krok 3: Deployment aplikacji
```bash
# Jeśli masz zunifikowane pliki
if [ -f "deploy-unified.sh" ]; then
    ./deploy-unified.sh deploy
else
    # Fallback do starych metod
    docker-compose up -d --build
fi
```

### Krok 4: Weryfikacja
```bash
# Sprawdź kontenery
docker ps | grep -E "(postgres|gpw)"

# Sprawdź logi
docker logs gpw_postgres
docker logs gpw_app

# Testuj aplikację
curl http://localhost:5000/api/app/health
curl http://localhost:5000/api/tickers/list
```

## 🚨 Troubleshooting błędów SQL

### Błąd: `syntaxerror at or near "\"`
**Przyczyna:** Nieprawidłowe escapowanie znaków `$` w SQL  
**Rozwiązanie:** Użyj `migrate-simple.sh` (używa heredoc)

### Błąd: `password authentication failed`
**Przyczyna:** Niepoprawne hasła w `.env`  
**Rozwiązanie:** 
```bash
# Sprawdź hasła w .env
grep -E "(POSTGRES_PASSWORD|DB_PASSWORD)" .env

# Upewnij się, że są identyczne:
POSTGRES_PASSWORD=TWOJE_HASLO
DB_PASSWORD=TWOJE_HASLO  # musi być identyczne!
```

### Błąd: `connection refused`
**Przyczyna:** PostgreSQL nie działa lub zły port  
**Rozwiązanie:**
```bash
# Sprawdź PostgreSQL
docker ps | grep postgres
docker logs postgres_container_name

# Sprawdź porty
netstat -tulpn | grep :5432
netstat -tulpn | grep :15432

# Restart PostgreSQL
docker-compose restart postgres
```

## 📋 Checklist przed deployment:

- [ ] `git pull` - pobrane najnowsze zmiany
- [ ] `.env` istnieje i ma poprawne hasła
- [ ] `POSTGRES_PASSWORD` = `DB_PASSWORD` w `.env`
- [ ] PostgreSQL jest dostępny (Docker lub bezpośrednio)
- [ ] `./migrate-simple.sh` działa bez błędów
- [ ] Aplikacja startuje i odpowiada

## 🎯 Po sukcesie:

1. **Przetestuj funkcjonalności:**
   ```bash
   curl http://localhost:5000/api/tickers/list
   curl http://localhost:5000/api/import/historical-data
   ```

2. **Skonfiguruj monitoring:**
   ```bash
   # Regularnie sprawdzaj logi
   docker logs --tail=50 gpw_app
   
   # Monitor zasobów
   docker stats
   ```

3. **Backup bazy danych:**
   ```bash
   # Jeśli masz deploy-unified.sh
   ./deploy-unified.sh backup
   
   # Lub ręcznie
   docker exec postgres_container pg_dump -U gpw_user gpw_investor > backup.sql
   ```

---

## 📞 Support

Jeśli nadal występują problemy:

1. **Sprawdź logi:** `docker logs postgres_container` i `docker logs gpw_app`
2. **Testuj połączenie:** `./migrate-simple.sh` (pokaże szczegółowe błędy)
3. **Weryfikuj .env:** Upewnij się, że hasła są identyczne
4. **Restart:** `docker-compose down && docker-compose up -d`

Nowe skrypty rozwiązują problemy ze składnią SQL i automatycznie znajdą działający PostgreSQL.
