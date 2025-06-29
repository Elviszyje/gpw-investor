#!/bin/bash
# DIAGNOSTYKA DOCKER - ZDALNE WYKONANIE
# Skrypt do sprawdzenia co się dzieje z kontenerem Docker na zdalnym serwerze

echo "🔍 DIAGNOSTYKA DOCKER - GPW INVESTOR"
echo "===================================="
echo ""

# 1. Sprawdź obecny stan kontenerów
echo "1️⃣ STAN KONTENERÓW:"
echo "--------------------"
docker ps -a
echo ""

# 2. Sprawdź czy najnowszy kod został pobrany
echo "2️⃣ SPRAWDZENIE REPOZYTORIUM:"
echo "-----------------------------"
echo "Obecny commit:"
git log --oneline -1
echo ""
echo "Status repo:"
git status --porcelain
echo ""
echo "Obecność kluczowych plików:"
ls -la import_historical_data.py 2>/dev/null && echo "✅ import_historical_data.py" || echo "❌ BRAK import_historical_data.py"
ls -la tickers_config.json 2>/dev/null && echo "✅ tickers_config.json" || echo "❌ BRAK tickers_config.json"
ls -la fix-db-schema.sql 2>/dev/null && echo "✅ fix-db-schema.sql" || echo "❌ BRAK fix-db-schema.sql"
echo ""

# 3. Sprawdź czy kontenery używają najnowszego obrazu
echo "3️⃣ OBRAZY DOCKER:"
echo "------------------"
docker images | grep gpw
echo ""

# 4. Sprawdź czy pliki są w kontenerze
echo "4️⃣ PLIKI W KONTENERZE:"
echo "----------------------"
echo "Sprawdzam pliki w kontenerze app..."
CONTAINER_NAME=$(docker ps --format "table {{.Names}}" | grep app | head -1)
if [ ! -z "$CONTAINER_NAME" ]; then
    echo "Kontener: $CONTAINER_NAME"
    echo "Pliki w /app/:"
    docker exec $CONTAINER_NAME ls -la /app/ | grep -E "(import_historical|tickers_config|fix-db)"
    echo ""
    echo "Struktura /app/:"
    docker exec $CONTAINER_NAME find /app -name "*.py" | head -10
else
    echo "❌ Nie znaleziono działającego kontenera app"
fi
echo ""

# 5. Sprawdź logi budowania
echo "5️⃣ OSTATNIE LOGI BUDOWANIA:"
echo "----------------------------"
echo "Sprawdzam czy build się udał..."
docker-compose logs --tail=20 app | grep -E "(COPY|ADD|RUN|ERROR|Failed)"
echo ""

# 6. Sprawdź bazę danych
echo "6️⃣ BAZA DANYCH:"
echo "---------------"
DB_CONTAINER=$(docker ps --format "table {{.Names}}" | grep postgres | head -1)
if [ ! -z "$DB_CONTAINER" ]; then
    echo "Kontener DB: $DB_CONTAINER"
    echo "Tabele w bazie:"
    docker exec $DB_CONTAINER psql -U gpw_user -d gpw_data -c "\dt" 2>/dev/null || echo "❌ Błąd połączenia z bazą"
    echo ""
    echo "Struktura health_check:"
    docker exec $DB_CONTAINER psql -U gpw_user -d gpw_data -c "\d health_check" 2>/dev/null || echo "❌ Tabela health_check nie istnieje"
else
    echo "❌ Nie znaleziono działającego kontenera postgres"
fi
echo ""

# 7. Sprawdź zmienne środowiskowe
echo "7️⃣ ZMIENNE ŚRODOWISKOWE:"
echo "------------------------"
if [ ! -z "$CONTAINER_NAME" ]; then
    echo "DATABASE_URL:"
    docker exec $CONTAINER_NAME env | grep DATABASE_URL || echo "❌ BRAK DATABASE_URL"
    echo "POSTGRES zmienne:"
    docker exec $CONTAINER_NAME env | grep POSTGRES
else
    echo "❌ Nie można sprawdzić - brak kontenera"
fi
echo ""

# 8. Sprawdź wolumeny
echo "8️⃣ WOLUMENY DOCKER:"
echo "-------------------"
docker volume ls | grep gpw
echo ""

# 9. Sprawdź ostatnie błędy z logów
echo "9️⃣ OSTATNIE BŁĘDY:"
echo "------------------"
echo "Błędy z app:"
docker-compose logs app 2>&1 | tail -30 | grep -E "(ERROR|Error|TRACEBACK|Failed|ModuleNotFoundError)"
echo ""

# 10. Test połączenia
echo "🔟 TEST POŁĄCZENIA:"
echo "------------------"
echo "Health check:"
curl -f http://localhost:8080/api/app/health 2>/dev/null && echo "✅ Health check OK" || echo "❌ Health check FAILED"
echo "Main page:"
curl -I http://localhost:8080 2>/dev/null | head -1 || echo "❌ Main page FAILED"
echo ""

echo "🏁 DIAGNOSTYKA ZAKOŃCZONA"
echo "========================="
echo ""
echo "NASTĘPNE KROKI:"
echo "1. Jeśli brak plików w repo - wykonaj: git pull origin main"
echo "2. Jeśli pliki są ale nie w kontenerze - wykonaj: docker-compose build --no-cache"
echo "3. Jeśli problemy z bazą - usuń wolumen: docker-compose down -v"
echo "4. Przebuduj wszystko: docker-compose up --build -d"
