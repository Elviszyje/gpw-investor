# NAPRAWY BŁĘDÓW DOCKERA - INSTRUKCJA KROK PO KROK

## 🚨 PROBLEMY ZIDENTYFIKOWANE:
1. `ModuleNotFoundError: No module named 'import_historical_data'`
2. `column "service_name" of relation "health_check" does not exist`
3. `relation "ticker_mappings" does not exist`
4. `No such file or directory: '/app/scheduler/../tickers_config.json'`

## ✅ ROZWIĄZANIE - WYKONAJ TE KROKI:

### 1. Pobierz najnowsze zmiany z repozytorium
```bash
cd /path/to/gpw_investor
git pull origin main
```

### 2. Zatrzymaj i usuń obecne kontenery
```bash
docker-compose down
docker system prune -f
```

### 3. Usuń stare obrazy Docker (wymusza przebudowę)
```bash
docker rmi gpw_investor-app:latest 2>/dev/null || true
docker rmi gpw_investor_app:latest 2>/dev/null || true
```

### 4. Sprawdź czy wszystkie potrzebne pliki są obecne
```bash
echo "🔍 Sprawdzam obecność plików..."
ls -la import_historical_data.py
ls -la tickers_config.json
ls -la fix-db-schema.sql
ls -la docker-entrypoint.sh

# Jeśli któryś plik nie istnieje:
echo "❌ Brakujące pliki - sprawdź git status"
git status
```

### 5. Zbuduj obrazy od nowa (bez cache)
```bash
docker-compose build --no-cache
```

### 6. Uruchom aplikację
```bash
docker-compose up -d
```

### 7. Sprawdź logi
```bash
# Sprawdź logi aplikacji
docker-compose logs app

# Sprawdź logi bazy danych
docker-compose logs postgres

# Jeśli dalej są błędy - pełne logi:
docker-compose logs --tail=50 app
```

### 8. Test aplikacji
```bash
# Test połączenia
curl -f http://localhost:8080/api/app/health || echo "❌ Health check failed"

# Test interfejsu
curl -I http://localhost:8080 || echo "❌ Main page failed"
```

## 🔧 ROZWIĄZYWANIE KONKRETNYCH BŁĘDÓW:

### Błąd: "ModuleNotFoundError: No module named 'import_historical_data'"
**Przyczyna**: Plik nie został skopiowany do kontenera Docker
**Rozwiązanie**: 
```bash
# Sprawdź czy plik istnieje lokalnie
ls -la import_historical_data.py

# Jeśli nie ma - przywróć z git
git checkout HEAD -- import_historical_data.py

# Przebuduj obraz
docker-compose build --no-cache app
```

### Błąd: "column service_name does not exist"
**Przyczyna**: Stara struktura bazy danych
**Rozwiązanie**: Automatycznie naprawione przez `fix-db-schema.sql` w docker-entrypoint.sh

### Błąd: "relation ticker_mappings does not exist"
**Przyczyna**: Brakująca tabela
**Rozwiązanie**: Automatycznie naprawione przez migrację w docker-entrypoint.sh

### Błąd: "No such file or directory: tickers_config.json"
**Przyczyna**: Niepoprawna ścieżka w schedulerze
**Rozwiązanie**: Automatycznie naprawione - scheduler teraz sprawdza `/app/tickers_config.json` jako pierwszy

## 🔍 DIAGNOSTYKA JEŚLI NADAL NIE DZIAŁA:

### Sprawdź czy pliki są w kontenerze:
```bash
docker exec -it gpw_investor-app-1 ls -la /app/ | grep -E "(import_historical|tickers_config|fix-db)"
```

### Sprawdź logi Docker build:
```bash
docker-compose build --no-cache 2>&1 | tee build.log
grep -i "error\|failed" build.log
```

### Sprawdź zmienne środowiskowe:
```bash
docker exec -it gpw_investor-app-1 env | grep -E "(DATABASE|POSTGRES)"
```

### Sprawdź bazę danych:
```bash
# Połącz się z bazą
docker exec -it gpw_investor-postgres-1 psql -U gpw_user -d gpw_data -c "\dt"

# Sprawdź strukturę tabeli health_check
docker exec -it gpw_investor-postgres-1 psql -U gpw_user -d gpw_data -c "\d health_check"

# Sprawdź czy istnieje ticker_mappings
docker exec -it gpw_investor-postgres-1 psql -U gpw_user -d gpw_data -c "\d ticker_mappings"
```

## 📋 OSTATECZNY TEST:
Po wykonaniu wszystkich kroków sprawdź:
```bash
echo "=== FINAL TEST ==="
echo "1. Health check:"
curl -f http://localhost:8080/api/app/health && echo " ✅ OK" || echo " ❌ FAILED"

echo "2. Main page:"
curl -I http://localhost:8080 | head -1

echo "3. App logs (last 10 lines):"
docker-compose logs --tail=10 app

echo "4. No error containers:"
docker ps -a | grep -v "Up"
```

## 📞 JEŚLI NADAL NIE DZIAŁA:
1. Wyślij output z: `docker-compose logs app > app_logs.txt`
2. Wyślij output z: `docker-compose logs postgres > postgres_logs.txt`
3. Wyślij output z: `git status` i `ls -la`

Commit: `86d21dd` zawiera wszystkie naprawy.
