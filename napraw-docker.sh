#!/bin/bash
# SKRYPT NAPRAWCZY - ZDALNA NAPRAWA DOCKER
# Wykonaj ten skrypt na zdalnym serwerze aby naprawić problemy

echo "🔧 NAPRAWA DOCKER - GPW INVESTOR"
echo "================================"
echo ""

# Sprawdź czy jesteśmy w odpowiednim katalogu
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Nie znaleziono docker-compose.yml"
    echo "💡 Przejdź do katalogu z projektem GPW Investor"
    exit 1
fi

echo "📁 Katalog: $(pwd)"
echo ""

# Krok 1: Pobierz najnowszy kod
echo "1️⃣ POBIERANIE NAJNOWSZEGO KODU..."
echo "---------------------------------"
git fetch origin
BEFORE_COMMIT=$(git rev-parse HEAD)
git pull origin main
AFTER_COMMIT=$(git rev-parse HEAD)

if [ "$BEFORE_COMMIT" != "$AFTER_COMMIT" ]; then
    echo "✅ Zaktualizowano kod (${BEFORE_COMMIT:0:7} → ${AFTER_COMMIT:0:7})"
else
    echo "ℹ️ Kod już aktualny (commit: ${AFTER_COMMIT:0:7})"
fi
echo ""

# Krok 2: Sprawdź kluczowe pliki
echo "2️⃣ SPRAWDZANIE KLUCZOWYCH PLIKÓW..."
echo "-----------------------------------"
MISSING_FILES=()

check_file() {
    if [ -f "$1" ]; then
        echo "✅ $1"
    else
        echo "❌ BRAK: $1"
        MISSING_FILES+=("$1")
    fi
}

check_file "import_historical_data.py"
check_file "tickers_config.json"
check_file "fix-db-schema.sql"
check_file "docker-entrypoint.sh"

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo ""
    echo "❌ Brakuje ${#MISSING_FILES[@]} plików. Próbuję przywrócić..."
    for file in "${MISSING_FILES[@]}"; do
        git checkout HEAD -- "$file" 2>/dev/null && echo "✅ Przywrócono $file" || echo "❌ Nie udało się przywrócić $file"
    done
fi
echo ""

# Krok 3: Zatrzymaj stare kontenery
echo "3️⃣ ZATRZYMYWANIE STARYCH KONTENERÓW..."
echo "-------------------------------------"
docker-compose down
echo "✅ Kontenery zatrzymane"
echo ""

# Krok 4: Usuń stare obrazy (opcjonalnie - zachowaj dane)
echo "4️⃣ CZYSZCZENIE STARYCH OBRAZÓW..."
echo "--------------------------------"
echo "Usuwam stare obrazy aplikacji..."
docker rmi $(docker images | grep gpw | awk '{print $3}') 2>/dev/null || echo "ℹ️ Brak starych obrazów do usunięcia"

# Krok 5: Opcjonalnie usuń wolumeny bazy (TO USUWA DANE!)
read -p "❓ Czy usunąć dane bazy danych? To naprawi błędy struktury ale usunie wszystkie dane [y/N]: " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️ Usuwam wolumeny bazy danych..."
    docker volume rm $(docker volume ls | grep gpw | awk '{print $2}') 2>/dev/null || echo "ℹ️ Brak wolumenów do usunięcia"
    echo "✅ Wolumeny usunięte - baza zostanie zainicjowana od nowa"
else
    echo "ℹ️ Zachowuję istniejące dane bazy"
fi
echo ""

# Krok 6: Zbuduj od nowa
echo "5️⃣ BUDOWANIE NOWYCH OBRAZÓW..."
echo "------------------------------"
echo "To może potrwać kilka minut..."
docker-compose build --no-cache --progress=plain

if [ $? -eq 0 ]; then
    echo "✅ Budowanie zakończone sukcesem"
else
    echo "❌ Błąd podczas budowania"
    echo "💡 Sprawdź logi powyżej i upewnij się że wszystkie pliki są dostępne"
    exit 1
fi
echo ""

# Krok 7: Uruchom aplikację
echo "6️⃣ URUCHAMIANIE APLIKACJI..."
echo "----------------------------"
docker-compose up -d

if [ $? -eq 0 ]; then
    echo "✅ Aplikacja uruchomiona"
else
    echo "❌ Błąd podczas uruchamiania"
    exit 1
fi
echo ""

# Krok 8: Sprawdź status
echo "7️⃣ SPRAWDZANIE STATUSU..."
echo "-------------------------"
echo "Czekam 30 sekund na uruchomienie..."
sleep 30

echo "Status kontenerów:"
docker-compose ps

echo ""
echo "Test połączenia:"
curl -f http://localhost:8080/api/app/health && echo " ✅ Health check OK" || echo " ❌ Health check FAILED"

echo ""
echo "Ostatnie logi aplikacji:"
docker-compose logs --tail=10 app

echo ""
echo "🎉 NAPRAWA ZAKOŃCZONA!"
echo "====================="
echo ""
echo "📋 NASTĘPNE KROKI:"
echo "• Sprawdź czy aplikacja działa: http://localhost:8080"
echo "• Jeśli nadal błędy, wykonaj: docker-compose logs app"
echo "• Pełna diagnostyka: ./diagnoza-docker.sh"
