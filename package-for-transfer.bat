@echo off
REM GPW Investor - Package Script for Transfer (Windows)
REM Skrypt do przygotowania projektu do przeniesienia na inny komputer (Windows)

setlocal enabledelayedexpansion

echo 🚀 GPW Investor - Przygotowanie do transferu (Windows)
echo ====================================================

REM Sprawdź czy jesteśmy w poprawnym folderze
if not exist "docker-compose.yml" (
    echo ❌ Błąd: Nie znaleziono docker-compose.yml
    echo Uruchom skrypt z głównego folderu projektu GPW Investor
    pause
    exit /b 1
)

REM Utwórz nazwę archiwum z datą
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "ARCHIVE_NAME=gpw_investor_%YYYY%%MM%%DD%_%HH%%Min%%Sec%.zip"

echo 📦 Przygotowywanie archiwum: %ARCHIVE_NAME%

REM Sprawdź czy aplikacja jest uruchomiona
docker-compose ps > nul 2>&1
if !errorlevel! == 0 (
    echo ⚠️  Zatrzymuję aplikację na czas tworzenia archiwum...
    docker-compose down
    set RESTART_NEEDED=true
) else (
    set RESTART_NEEDED=false
)

echo 📋 Przygotowywanie plików...

REM Utwórz folder tymczasowy
set TEMP_DIR=gpw_investor_package
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

REM Skopiuj podstawowe pliki
echo   📄 Kopiowanie plików aplikacji...
xcopy /s blueprints "%TEMP_DIR%\blueprints\" > nul 2>&1
xcopy /s utils "%TEMP_DIR%\utils\" > nul 2>&1
xcopy /s templates "%TEMP_DIR%\templates\" > nul 2>&1
xcopy /s static "%TEMP_DIR%\static\" > nul 2>&1
xcopy /s workers "%TEMP_DIR%\workers\" > nul 2>&1
xcopy /s scheduler "%TEMP_DIR%\scheduler\" > nul 2>&1

copy app.py "%TEMP_DIR%\" > nul 2>&1
copy requirements.txt "%TEMP_DIR%\" > nul 2>&1
copy docker-compose.yml "%TEMP_DIR%\" > nul 2>&1
copy Dockerfile "%TEMP_DIR%\" > nul 2>&1
copy .env "%TEMP_DIR%\" > nul 2>&1
copy docker-entrypoint.sh "%TEMP_DIR%\" > nul 2>&1
copy init-db.sql "%TEMP_DIR%\" > nul 2>&1
copy init-schema.sql "%TEMP_DIR%\" > nul 2>&1
copy nginx.conf "%TEMP_DIR%\" > nul 2>&1
copy .dockerignore "%TEMP_DIR%\" > nul 2>&1
copy docker-manager.sh "%TEMP_DIR%\" > nul 2>&1
copy *.md "%TEMP_DIR%\" > nul 2>&1

REM Skopiuj foldery danych
echo   📁 Kopiowanie folderów danych...
for %%d in (data logs models storage historical_data) do (
    if exist "%%d" (
        echo     Kopiowanie %%d\...
        xcopy /s "%%d" "%TEMP_DIR%\%%d\" > nul 2>&1
    ) else (
        echo     Tworzenie pustego folderu %%d\...
        mkdir "%TEMP_DIR%\%%d" > nul 2>&1
    )
)

REM Utwórz archiwum ZIP (wymaga PowerShell)
echo 🗜️  Tworzenie archiwum ZIP...
powershell -command "Compress-Archive -Path '%TEMP_DIR%\*' -DestinationPath '%ARCHIVE_NAME%' -Force"

REM Usuń folder tymczasowy
rmdir /s /q "%TEMP_DIR%"

REM Sprawdź rozmiar archiwum
for %%A in ("%ARCHIVE_NAME%") do set "ARCHIVE_SIZE=%%~zA"
set /a "ARCHIVE_SIZE_MB=%ARCHIVE_SIZE% / 1024 / 1024"

echo ✅ Archiwum utworzone pomyślnie!
echo 📊 Nazwa pliku: %ARCHIVE_NAME%
echo 📊 Rozmiar: %ARCHIVE_SIZE_MB% MB
echo.

REM Uruchom ponownie aplikację jeśli była uruchomiona
if "%RESTART_NEEDED%"=="true" (
    echo 🔄 Uruchamiam aplikację ponownie...
    docker-compose up -d
)

echo 📋 Instrukcje transferu:
echo =======================
echo 1. Przenieś plik '%ARCHIVE_NAME%' na nowy komputer
echo 2. Na nowym komputerze:
echo    - Utwórz folder: mkdir gpw_investor
echo    - Rozpakuj archiwum do tego folderu
echo    - Otwórz PowerShell/CMD w folderze projektu
echo 3. Postępuj według instrukcji w INSTALACJA_NA_NOWYM_KOMPUTERZE.md
echo.
echo 🎯 Gotowe! Projekt jest spakowany do transferu.
echo.

pause
