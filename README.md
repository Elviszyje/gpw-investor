# 🚀 GPW Investor - Szybki Start

![GPW Investor](https://img.shields.io/badge/GPW-Investor-blue?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker)
![Flask](https://img.shields.io/badge/Flask-Web%20App-000000?style=for-the-badge&logo=flask)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?style=for-the-badge&logo=postgresql)

**Nowoczesna aplikacja do analizy GPW z Machine Learning, web scrapingiem i rekomendacjami inwestycyjnymi.**

## ⚡ Błyskawiczny Start (3 kroki)

```bash
# 1. Pobierz/rozpakuj projekt
git clone https://github.com/Elviszyje/gpw-investor.git && cd gpw-investor
# LUB rozpakuj archiwum ZIP/TAR.GZ

# 2. Uruchom z Docker (automatyczny wybór wersji)
./build-docker.sh && docker-compose up -d

# 3. Otwórz aplikację
open http://localhost:5001
```

### 🚨 Problem z budowaniem?
```bash
# Szybka wersja bez Chrome (zalecana dla testów)
docker build -f Dockerfile.simple -t gpw_investor . && docker-compose up -d
```

## 📋 Wymagania

- **Docker Desktop** (Windows/Mac) lub **Docker Engine** (Linux)
- **4 GB RAM** minimum
- **10 GB** miejsca na dysku

## 🎯 Po Uruchomieniu

| Usługa | URL | Opis |
|--------|-----|------|
| **Aplikacja główna** | http://localhost:5001 | Panel główny GPW Investor |
| **Health Check** | http://localhost:5001/api/app/health | Status systemu |
| **Dane dzienne** | http://localhost:5001/dane | Analiza danych giełdowych |
| **Rekomendacje** | http://localhost:5001/recommendations_tracking | ML rekomendacje z trackingiem |
| **Intraday** | http://localhost:5001/intraday | Dane w czasie rzeczywistym |
| **Wiadomości** | http://localhost:5001/news | Scraper wiadomości giełdowych |

## 🚀 Funkcje

### 🤖 Machine Learning
- **Analiza wzorców rynkowych** - wykrywanie trendów
- **Rekomendacje inwestycyjne** - ML predictions
- **Feature engineering** - automatyczne wskaźniki techniczne
- **Model tracking** - performance rekomendacji

### 📊 Analiza Danych
- **Quotes daily/intraday** - import danych GPW
- **Technical analysis** - wskaźniki techniczne
- **Backtesting** - testowanie strategii
- **Performance tracking** - monitorowanie wyników

### 🌐 Web Scraping
- **Bankier.pl** - wiadomości i analizy
- **ESPI** - komunikaty spółek
- **News portals** - agregacja newsów
- **Real-time data** - aktualne kursy

### 📱 Web Interface
- **Responsive design** - działa na mobile
- **Interactive charts** - Chart.js wizualizacje
- **Real-time updates** - live data
- **Modern UI** - Bootstrap 5

## 🛠️ Architektura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Flask App     │────│   PostgreSQL    │    │     Redis       │
│  (Port 5001)    │    │  (Port 5432)    │    │  (Port 6379)    │
│                 │    │                 │    │                 │
│ • Blueprints    │    │ • Market Data   │    │ • Cache         │
│ • ML Models     │    │ • ML Features   │    │ • Sessions      │
│ • Web Scrapers  │    │ • Tracking      │    │ • Tasks         │
│ • API/Web UI    │    │ • History       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 Zarządzanie

### Podstawowe komendy
```bash
# Status aplikacji
docker-compose ps

# Logi w czasie rzeczywistym
docker-compose logs -f

# Restart
docker-compose restart

# Zatrzymaj
docker-compose down

# Restart z rebuild
docker-compose down && docker-compose build && docker-compose up -d
```

### Dostęp do bazy danych
```bash
# Shell PostgreSQL
docker-compose exec postgres psql -U gpw_user -d gpw_investor

# Backup bazy
docker-compose exec postgres pg_dump -U gpw_user gpw_investor > backup.sql
```

### Development
```bash
# Shell aplikacji
docker-compose exec gpw_app bash

# Uruchom worker
docker-compose exec gpw_app python workers/quotes_daily.py

# Test endpoint
curl http://localhost:5001/api/app/health
```

## 📁 Struktura Projektu

```
gpw_investor/
├── 🐍 app.py                 # Flask application
├── 🔧 docker-compose.yml     # Services configuration
├── 🐳 Dockerfile            # Application container
├── ⚙️ .env                  # Environment variables
├── 📋 requirements.txt      # Python dependencies
├── 
├── 🎯 blueprints/           # Feature modules
│   ├── data_ops.py         # Data operations
│   ├── recommendations.py  # ML recommendations
│   ├── ml.py              # Machine Learning
│   ├── scrapers.py        # Web scrapers
│   └── notifications.py   # Alerts & notifications
├── 
├── 🤖 workers/             # Background jobs
│   ├── quotes_daily.py    # Daily quotes import
│   ├── market_pattern_ml.py # ML pattern analysis
│   ├── news_scraper.py    # News scraping
│   └── recommendation_*.py # Recommendation engines
├── 
├── 🎨 templates/           # Jinja2 templates
├── 📊 static/             # CSS/JS/images
├── 🗄️ data/               # Application data
├── 📝 logs/               # Application logs
├── 🧠 models/             # ML models
└── 💾 storage/            # File storage
```

## 🔒 Bezpieczeństwo

### Produkcja - ważne zmiany w `.env`:
```env
# Zmień domyślne hasła!
POSTGRES_PASSWORD=twoje-bezpieczne-haslo-db
SECRET_KEY=twoj-unikalny-klucz-flaska-min-32-znaki

# Produkcja
FLASK_ENV=production
FLASK_DEBUG=false
```

## 📊 Monitoring

### Health Check
```bash
curl http://localhost:5001/api/app/health
```

### Metryki aplikacji
```bash
curl http://localhost:5001/api/app/stats
```

### Przykładowa odpowiedź:
```json
{
  "status": "healthy",
  "services": {
    "database": "healthy",
    "ml_models": "trained",
    "schedulers": "running"
  },
  "app": {
    "blueprints": 6,
    "endpoint_count": 82,
    "debug_mode": false
  },
  "system": {
    "memory_mb": 256.5,
    "cpu_percent": 15.2,
    "uptime": "2h 15m"
  }
}
```

## 🆘 Rozwiązywanie Problemów

| Problem | Rozwiązanie |
|---------|-------------|
| 🚫 Port zajęty | `lsof -i :5001` → zmień port w docker-compose.yml |
| 🗄️ Baza nie działa | `docker-compose logs postgres` → restart postgres |
| 🤖 Brak modeli ML | Aplikacja automatycznie tworzy/trenuje modele |
| 📊 Brak danych | `docker exec gpw_app python workers/quotes_daily.py` |
| 🔄 Błędy aplikacji | `docker-compose logs gpw_app` → sprawdź logi |

## 📚 Dokumentacja

- **[INSTALACJA_NA_NOWYM_KOMPUTERZE.md](INSTALACJA_NA_NOWYM_KOMPUTERZE.md)** - Szczegółowa instalacja
- **[DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)** - Deployment guide
- **[package-for-transfer.sh](package-for-transfer.sh)** - Skrypt do transferu

## 🎯 Quick Commands

```bash
# Automatyczne budowanie (wybór wersji)
./build-docker.sh

# Szybkie budowanie (bez Chrome)
docker build -f Dockerfile.simple -t gpw_investor:simple . && docker-compose up -d

# Budowanie pełnej wersji (z Chrome)
docker build -f Dockerfile -t gpw_investor:full . && docker-compose up -d

# Kompletna reinstalacja
docker-compose down -v && docker system prune -f && docker-compose up -d

# Package dla transferu
./package-for-transfer.sh

# Import danych GPW
docker-compose exec gpw_app python workers/quotes_daily.py

# Test wszystkich endpointów
for endpoint in / /dane /recommendations_tracking /intraday /news /api/app/health; do
  echo "Testing $endpoint..."
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5001$endpoint
done
```

---

## 🎉 Gotowe!

Po uruchomieniu masz pełną platformę do analizy GPW z:

✅ **Machine Learning** - automatyczne rekomendacje  
✅ **Web Scraping** - aktualne dane rynkowe  
✅ **Real-time Analytics** - live dashboard  
✅ **API Integration** - RESTful endpoints  
✅ **Modern UI** - responsive web interface  

**Powodzenia z inwestowaniem! 📈🚀**
