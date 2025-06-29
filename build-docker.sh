#!/bin/bash

# GPW Investor - Build Script with Dockerfile Selection
# Wybierz wersję Dockerfile odpowiednią dla Twojego przypadku użycia

set -e

echo "🚀 GPW Investor - Docker Build Script"
echo "====================================="
echo ""

# Sprawdź czy Docker działa
if ! command -v docker &> /dev/null; then
    echo "❌ Docker nie jest zainstalowany lub nie działa"
    exit 1
fi

# Menu wyboru
echo "Wybierz wersję do zbudowania:"
echo "1) Pełna wersja (z Chrome/Selenium) - zalecana dla web scrapingu"
echo "2) Uproszczona wersja (bez Chrome) - szybsza, mniejsza, do podstawowych funkcji"
echo "3) Automatyczny wybór na podstawie architektury"
echo ""
read -p "Twój wybór (1-3): " choice

case $choice in
    1)
        echo "🔧 Budowanie pełnej wersji z Chrome/Selenium..."
        DOCKERFILE="Dockerfile"
        IMAGE_TAG="gpw_investor:full"
        ;;
    2)
        echo "🔧 Budowanie uproszczonej wersji bez Chrome..."
        DOCKERFILE="Dockerfile.simple"
        IMAGE_TAG="gpw_investor:simple"
        ;;
    3)
        ARCH=$(uname -m)
        echo "🔍 Wykryto architekturę: $ARCH"
        if [[ "$ARCH" == "x86_64" ]]; then
            echo "🔧 Budowanie pełnej wersji dla x86_64..."
            DOCKERFILE="Dockerfile"
            IMAGE_TAG="gpw_investor:full"
        else
            echo "🔧 Budowanie uproszczonej wersji dla $ARCH..."
            DOCKERFILE="Dockerfile.simple"
            IMAGE_TAG="gpw_investor:simple"
        fi
        ;;
    *)
        echo "❌ Nieprawidłowy wybór"
        exit 1
        ;;
esac

echo ""
echo "📋 Szczegóły budowania:"
echo "Dockerfile: $DOCKERFILE"
echo "Image tag: $IMAGE_TAG"
echo ""

# Sprawdź czy Dockerfile istnieje
if [ ! -f "$DOCKERFILE" ]; then
    echo "❌ Plik $DOCKERFILE nie istnieje!"
    exit 1
fi

# Budowanie
echo "🔨 Rozpoczynam budowanie obrazu Docker..."
echo "To może potrwać kilka minut..."
echo ""

if docker build -f "$DOCKERFILE" -t "$IMAGE_TAG" .; then
    echo ""
    echo "✅ Obraz zbudowany pomyślnie!"
    echo "🏷️  Tag: $IMAGE_TAG"
    echo ""
    
    # Sprawdź rozmiar obrazu
    SIZE=$(docker images "$IMAGE_TAG" --format "table {{.Size}}" | tail -n 1)
    echo "📊 Rozmiar obrazu: $SIZE"
    echo ""
    
    # Aktualizuj docker-compose.yml jeśli używamy uproszczonej wersji
    if [[ "$DOCKERFILE" == "Dockerfile.simple" ]]; then
        echo "⚠️  UWAGA: Używasz uproszczonej wersji bez Chrome."
        echo "   Web scrapers z Selenium mogą nie działać."
        echo "   Jeśli potrzebujesz web scrapingu, użyj opcji 1."
        echo ""
        
        # Opcjonalnie zaktualizuj docker-compose.yml
        read -p "Czy zaktualizować docker-compose.yml dla uproszczonej wersji? (y/n): " update_compose
        if [[ "$update_compose" == "y" || "$update_compose" == "Y" ]]; then
            sed -i.bak 's/dockerfile: Dockerfile/dockerfile: Dockerfile.simple/' docker-compose.yml
            echo "✅ docker-compose.yml zaktualizowany"
        fi
    fi
    
    echo "🚀 Następne kroki:"
    echo "1. Uruchom: docker-compose up -d"
    echo "2. Sprawdź: curl http://localhost:5001/api/app/health"
    echo "3. Otwórz: http://localhost:5001"
    
else
    echo ""
    echo "❌ Błąd podczas budowania obrazu!"
    echo ""
    echo "🔧 Możliwe rozwiązania:"
    echo "1. Spróbuj uproszczonej wersji (opcja 2)"
    echo "2. Sprawdź połączenie internetowe"
    echo "3. Wyczyść cache Docker: docker system prune"
    echo "4. Sprawdź logi powyżej dla szczegółów błędu"
    exit 1
fi
