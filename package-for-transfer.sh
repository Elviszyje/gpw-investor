#!/bin/bash

# GPW Investor - Package Script for Transfer
# Skrypt do przygotowania projektu do przeniesienia na inny komputer

set -e

echo "🚀 GPW Investor - Przygotowanie do transferu"
echo "============================================"

# Sprawdź czy jesteśmy w poprawnym folderze
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Błąd: Nie znaleziono docker-compose.yml"
    echo "Uruchom skrypt z głównego folderu projektu GPW Investor"
    exit 1
fi

# Nazwa pliku archiwum
ARCHIVE_NAME="gpw_investor_$(date +%Y%m%d_%H%M%S).tar.gz"
TEMP_DIR="gpw_investor_package"

echo "📦 Przygotowywanie archiwum: $ARCHIVE_NAME"

# Sprawdź czy aplikacja jest uruchomiona
if docker-compose ps | grep -q "Up"; then
    echo "⚠️  Aplikacja jest uruchomiona. Zatrzymuję na czas tworzenia archiwum..."
    docker-compose down
    RESTART_NEEDED=true
else
    RESTART_NEEDED=false
fi

# Utwórz backup bazy danych jeśli istnieje
if docker volume ls | grep -q "gpw_investor_postgres_data"; then
    echo "💾 Tworzenie backup'u bazy danych..."
    docker-compose up -d postgres
    sleep 5
    docker-compose exec -T postgres pg_dump -U gpw_user gpw_investor > db_backup.sql 2>/dev/null || echo "⚠️  Nie udało się utworzyć backup'u bazy"
    docker-compose down
fi

# Utwórz folder tymczasowy
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

echo "📋 Kopiowanie plików..."

# Skopiuj podstawowe pliki aplikacji
cp -r blueprints utils templates static workers scheduler "$TEMP_DIR/" 2>/dev/null || true
cp app.py requirements.txt docker-compose.yml Dockerfile .env "$TEMP_DIR/"
cp docker-entrypoint.sh init-db.sql init-schema.sql nginx.conf .dockerignore "$TEMP_DIR/" 2>/dev/null || true
cp docker-manager.sh "$TEMP_DIR/" 2>/dev/null || true

# Skopiuj dokumentację
cp *.md "$TEMP_DIR/" 2>/dev/null || true

# Skopiuj backup bazy danych jeśli istnieje
[ -f "db_backup.sql" ] && cp db_backup.sql "$TEMP_DIR/"

# Skopiuj ważne foldery danych (zachowaj strukturę)
for dir in data logs models storage historical_data; do
    if [ -d "$dir" ]; then
        echo "  📁 Kopiowanie $dir/..."
        cp -r "$dir" "$TEMP_DIR/"
    else
        # Utwórz pusty folder
        mkdir -p "$TEMP_DIR/$dir"
        echo "  📁 Utworzono pusty folder $dir/"
    fi
done

# Utwórz archiwum
echo "🗜️  Tworzenie archiwum..."
tar -czf "$ARCHIVE_NAME" -C "$TEMP_DIR" .

# Usuń folder tymczasowy
rm -rf "$TEMP_DIR"
rm -f db_backup.sql

# Sprawdź rozmiar archiwum
ARCHIVE_SIZE=$(du -h "$ARCHIVE_NAME" | cut -f1)

echo "✅ Archiwum utworzone pomyślnie!"
echo "📊 Nazwa pliku: $ARCHIVE_NAME"
echo "📊 Rozmiar: $ARCHIVE_SIZE"
echo ""

# Uruchom ponownie aplikację jeśli była uruchomiona
if [ "$RESTART_NEEDED" = true ]; then
    echo "🔄 Uruchamiam aplikację ponownie..."
    docker-compose up -d
fi

echo "📋 Instrukcje transferu:"
echo "======================="
echo "1. Przenieś plik '$ARCHIVE_NAME' na nowy komputer"
echo "2. Na nowym komputerze:"
echo "   mkdir gpw_investor && cd gpw_investor"
echo "   tar -xzf $ARCHIVE_NAME"
echo "   chmod +x docker-manager.sh"
echo "3. Postępuj według instrukcji w INSTALACJA_NA_NOWYM_KOMPUTERZE.md"
echo ""
echo "🎯 Gotowe! Projekt jest spakowany do transferu."

# Opcjonalne: sprawdź zawartość archiwum
echo ""
echo "📦 Zawartość archiwum:"
tar -tzf "$ARCHIVE_NAME" | head -20
if [ $(tar -tzf "$ARCHIVE_NAME" | wc -l) -gt 20 ]; then
    echo "... ($(tar -tzf "$ARCHIVE_NAME" | wc -l) plików łącznie)"
fi
