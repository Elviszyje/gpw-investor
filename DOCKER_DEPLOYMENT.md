# GPW Investor - Docker Deployment Guide

## 🚀 Szybki Start

### Wymagania wstępne
- Docker Desktop >= 4.0
- Docker Compose >= 2.0
- 4 GB wolnej przestrzeni dyskowej
- 2 GB dostępnej pamięci RAM

### Uruchomienie aplikacji

1. **Sklonuj/pobierz projekt**
```bash
# Jeśli masz git
git clone <repository-url>
cd gpw_investor
```

2. **Konfiguracja środowiska**
```bash
# Edytuj plik .env zgodnie z potrzebami
cp .env.example .env  # jeśli potrzebne
nano .env
```

3. **Uruchom aplikację**
```bash
# Użyj skryptu zarządzania
./docker-manager.sh start

# LUB bezpośrednio docker-compose
docker-compose up -d
```

4. **Sprawdź status**
```bash
./docker-manager.sh status
```

5. **Otwórz aplikację**
- Aplikacja: http://localhost:5001
- API Health: http://localhost:5001/api/app/health
- PostgreSQL: localhost:5432

## 🔧 Zarządzanie Kontenerami

### Skrypt zarządzania
```bash
# Wszystkie komendy
./docker-manager.sh help

# Najważniejsze komendy
./docker-manager.sh start      # Uruchom wszystko
./docker-manager.sh stop       # Zatrzymaj wszystko
./docker-manager.sh restart    # Restart
./docker-manager.sh logs       # Pokaż logi
./docker-manager.sh status     # Status usług
./docker-manager.sh cleanup    # Wyczyść wszystko
```

### Bezpośrednie komendy Docker Compose
```bash
# Uruchomienie
docker-compose up -d

# Zatrzymanie
docker-compose down

# Logi
docker-compose logs -f gpw_app
docker-compose logs -f postgres

# Status
docker-compose ps

# Rebuild
docker-compose build gpw_app
```

## 🗄️ Zarządzanie Bazą Danych

### Dostęp do bazy danych
```bash
# Shell PostgreSQL
./docker-manager.sh db-shell

# LUB bezpośrednio
docker-compose exec postgres psql -U gpw_user -d gpw_investor
```

### Backup i Restore
```bash
# Backup
docker-compose exec postgres pg_dump -U gpw_user gpw_investor > backup.sql

# Restore
docker-compose exec -T postgres psql -U gpw_user -d gpw_investor < backup.sql
```

## 🛠️ Rozwój i Debugowanie

### Dostęp do kontenerów
```bash
# Shell aplikacji
./docker-manager.sh app-shell

# Shell bazy danych
./docker-manager.sh db-shell

# Bezpośrednio
docker-compose exec gpw_app bash
docker-compose exec postgres bash
```

### Rebuilding po zmianach
```bash
# Rebuild aplikacji
./docker-manager.sh stop
./docker-manager.sh build
./docker-manager.sh start

# LUB
docker-compose down
docker-compose build gpw_app
docker-compose up -d
```

### Monitorowanie
```bash
# Logi w czasie rzeczywistym
./docker-manager.sh logs

# Logi konkretnej usługi
./docker-manager.sh logs gpw_app
./docker-manager.sh logs postgres

# Metryki systemu
docker stats
```

## 🔧 Konfiguracja

### Zmienne środowiskowe (.env)
```env
# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=gpw_investor
DB_USER=gpw_user
DB_PASSWORD=zmien-haslo-produkcyjne

# Flask
SECRET_KEY=zmien-klucz-produkcyjny
FLASK_ENV=production

# Telegram (opcjonalne)
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_DEFAULT_CHAT_ID=your-chat-id
```

### Wolumeny Docker
- `postgres_data` - dane PostgreSQL
- `redis_data` - dane Redis (cache)
- `./logs` - logi aplikacji
- `./data` - dane aplikacji
- `./storage` - przechowywanie plików
- `./models` - modele ML

## 🌐 Profile Wdrożenia

### Development (domyślny)
```bash
docker-compose up -d
```
Usługi: app, postgres, redis

### Production (z Nginx)
```bash
docker-compose --profile production up -d
```
Usługi: app, postgres, redis, nginx

### Tylko baza danych
```bash
docker-compose up -d postgres
```

## 🔍 Diagnostyka

### Health Checks
```bash
# Status wszystkich usług
curl http://localhost:5001/api/app/health

# Statystyki aplikacji
curl http://localhost:5001/api/app/stats

# PostgreSQL health
docker-compose exec postgres pg_isready -U gpw_user
```

### Problemy i rozwiązania

#### Aplikacja nie startuje
```bash
# Sprawdź logi
./docker-manager.sh logs gpw_app

# Sprawdź konfigurację
docker-compose config

# Restart
./docker-manager.sh restart
```

#### Baza danych nie odpowiada
```bash
# Sprawdź status
./docker-manager.sh status

# Sprawdź logi bazy
./docker-manager.sh logs postgres

# Restart bazy
docker-compose restart postgres
```

#### Port zajęty
```bash
# Sprawdź co używa portu
lsof -i :5001
lsof -i :5432

# Zmień port w docker-compose.yml
ports:
  - "5002:5000"  # zmiana portu aplikacji
```

## 🧹 Konserwacja

### Regularne zadania
```bash
# Czyszczenie logów
docker-compose exec gpw_app find /app/logs -name "*.log" -mtime +7 -delete

# Backup bazy danych
./backup-database.sh  # jeśli stworzony

# Update obrazów
docker-compose pull
docker-compose up -d
```

### Pełne czyszczenie
```bash
./docker-manager.sh cleanup

# LUB bardziej agresywnie
docker-compose down -v
docker system prune -a -f
```

## 📊 Monitorowanie Produkcyjne

### Metryki
- Aplikacja: http://localhost:5001/api/app/stats
- Health check: http://localhost:5001/api/app/health
- Nginx status: http://localhost:80/nginx_status (jeśli skonfigurowane)

### Alerty
- Dostępność aplikacji
- Wykorzystanie dysku
- Wykorzystanie pamięci
- Status bazy danych

## 🔐 Bezpieczeństwo

### Produkcja - ważne zmiany
1. Zmień domyślne hasła w `.env`
2. Użyj HTTPS (skonfiguruj SSL w nginx.conf)
3. Ograniczaj dostęp do portów
4. Regularne backupy
5. Monitoring logów bezpieczeństwa

### Firewall
```bash
# Przykład dla Ubuntu/Debian
ufw allow 80/tcp
ufw allow 443/tcp
ufw deny 5432/tcp  # PostgreSQL tylko lokalnie
```

## 📞 Wsparcie

W przypadku problemów:
1. Sprawdź logi: `./docker-manager.sh logs`
2. Sprawdź status: `./docker-manager.sh status`
3. Sprawdź konfigurację: `docker-compose config`
4. Restart: `./docker-manager.sh restart`
