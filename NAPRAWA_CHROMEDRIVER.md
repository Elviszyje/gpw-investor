# 🔧 Szybka Naprawa - Problem z ChromeDriver na Intel

## Problem
Jeśli podczas budowania Docker otrzymujesz błąd:
```
failed to solve: process "/bin/sh -c ARCH=$(dpkg --print-architecture) ... exit code: 8
```

## ⚡ Szybkie Rozwiązanie (2 minuty)

### Opcja 1: Automatyczny skrypt (zalecana)
```bash
# Uruchom skrypt automatycznego budowania
./build-docker.sh

# Wybierz opcję 2 (uproszczona wersja) lub 3 (automatyczna)
# Następnie:
docker-compose up -d
```

### Opcja 2: Ręczne budowanie uproszczonej wersji
```bash
# 1. Zbuduj uproszczoną wersję (bez Chrome)
docker build -f Dockerfile.simple -t gpw_investor .

# 2. Zaktualizuj docker-compose.yml
sed -i 's/dockerfile: Dockerfile/dockerfile: Dockerfile.simple/' docker-compose.yml

# 3. Uruchom
docker-compose up -d
```

### Opcja 3: Jedną komendą
```bash
# Wszystko w jednej linii
docker build -f Dockerfile.simple -t gpw_investor . && sed -i 's/dockerfile: Dockerfile/dockerfile: Dockerfile.simple/' docker-compose.yml && docker-compose up -d
```

## ✅ Co będzie działać

### Z uproszczoną wersją (Dockerfile.simple):
- ✅ **Wszystkie funkcje ML** - rekomendacje, analiza wzorców
- ✅ **API i Web UI** - pełny interfejs użytkownika  
- ✅ **Import danych** - quotes daily/intraday
- ✅ **Podstawowy web scraping** - RSS, prostsze scrapers
- ✅ **Baza danych** - PostgreSQL + Redis
- ✅ **Wszystkie endpointy** - /dane, /recommendations_tracking, itp.

### Nie będzie działać:
- ❌ **Chrome/Selenium scrapers** - bankier_scraper.py, scrape_selenium.py
- ❌ **Zaawansowany web scraping** - wymagający przeglądarki

## 🎯 Zalecenia

### Dla większości użytkowników:
👉 **Używaj Dockerfile.simple** - szybsze, mniejsze, wystarczające do większości zadań

### Jeśli potrzebujesz pełny web scraping:
1. Spróbuj zaktualizowanego Dockerfile (naprawiliśmy ChromeDriver)
2. Użyj alternatywnych scrapers bez Chrome
3. Uruchom Chrome w osobnym kontenerze

## 📊 Porównanie wersji

| Funkcja | Dockerfile | Dockerfile.simple |
|---------|------------|-------------------|
| Rozmiar obrazu | ~1.5GB | ~500MB |
| Czas budowania | 10-15 min | 3-5 min |
| Chrome/Selenium | ✅ | ❌ |
| ML & API | ✅ | ✅ |
| Podstawowy scraping | ✅ | ✅ |
| Stabilność budowania | ⚠️ (Chrome issues) | ✅ |

## 🆘 Nadal nie działa?

1. **Wyczyść Docker cache:**
   ```bash
   docker system prune -f
   ```

2. **Sprawdź zasoby:**
   ```bash
   # Minimum 4GB RAM, 10GB disk space
   docker system df
   ```

3. **Użyj najnowszej wersji:**
   ```bash
   git pull origin main
   ```

4. **Sprawdź logi:**
   ```bash
   docker-compose logs gpw_app
   ```

## ✨ Po uruchomieniu

Aplikacja będzie dostępna na:
- **🌐 Web UI**: http://localhost:5001  
- **🔍 Health Check**: http://localhost:5001/api/app/health
- **📊 Dane**: http://localhost:5001/dane
- **🤖 ML Rekomendacje**: http://localhost:5001/recommendations_tracking

**Problem rozwiązany! 🎉**
