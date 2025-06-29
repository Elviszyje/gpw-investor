# 🚀 Instalacja GPW Investor na Nowym Komputerze

## Wymagania Systemowe

### Minimalne wymagania:
- **System operacyjny**: Windows 10/11, macOS 10.15+, Ubuntu 18.04+ lub inne dystrybucje Linux
- **RAM**: minimum 4 GB (zalecane 8 GB)
- **Dysk**: 10 GB wolnej przestrzeni
- **Połączenie internetowe**: wymagane do pobierania obrazów Docker

### Wymagane oprogramowanie:
1. **Docker Desktop** (Windows/Mac) lub **Docker Engine** (Linux)
2. **Docker Compose** (zwykle instalowany z Docker Desktop)

## 📦 Krok 1: Instalacja Docker

### Windows:
1. Pobierz Docker Desktop z: https://www.docker.com/products/docker-desktop/
2. Uruchom installer i postępuj zgodnie z instrukcjami
3. Restart komputera po instalacji
4. Uruchom Docker Desktop i poczekaj na inicjalizację

### macOS:
1. Pobierz Docker Desktop z: https://www.docker.com/products/docker-desktop/
2. Przeciągnij Docker.app do folderu Applications
3. Uruchom Docker Desktop z Launchpad
4. Zaakceptuj uprawnienia systemowe

### Linux (Ubuntu/Debian):
```bash
# Aktualizuj system
sudo apt update && sudo apt upgrade -y

# Zainstaluj Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Dodaj użytkownika do grupy docker
sudo usermod -aG docker $USER

# Zainstaluj Docker Compose
sudo apt install docker-compose-plugin

# Logout i login ponownie lub:
newgrp docker
```

### Linux (CentOS/RHEL/Fedora):
```bash
# Fedora
sudo dnf install docker docker-compose
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# CentOS/RHEL
sudo yum install docker docker-compose
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

## 📁 Krok 2: Pobierz Projekt

### Opcja A: Git (jeśli masz dostęp do repozytorium)
```bash
git clone <URL_REPOZYTORIUM>
cd gpw_investor
```

### Opcja B: ZIP Archive
1. Pobierz archiwum ZIP z projektem
2. Rozpakuj do wybranego folderu
3. Otwórz terminal/CMD w folderze projektu

### Opcja C: Transfer plików
```bash
# Na komputerze źródłowym spakuj projekt
tar -czf gpw_investor.tar.gz gpw_investor/

# Przenieś na nowy komputer (USB, scp, itp.)
# Na nowym komputerze rozpakuj
tar -xzf gpw_investor.tar.gz
cd gpw_investor
```

## ⚙️ Krok 3: Konfiguracja

### Sprawdź plik .env
Otwórz plik `.env` i sprawdź konfigurację:

```bash
# Windows
notepad .env

# macOS
open -e .env

# Linux
nano .env
```

**Ważne hasła do zmiany dla produkcji:**
```env
POSTGRES_PASSWORD=twoje-bezpieczne-haslo-db
SECRET_KEY=twoj-unikalny-klucz-flaska-min-32-znaki
```

### Sprawdź porty (opcjonalne)
Jeśli porty 5001, 5432 lub 6379 są zajęte na Twoim systemie:

```bash
# Sprawdź zajęte porty
# Windows
netstat -an | findstr :5001
netstat -an | findstr :5432

# macOS/Linux
lsof -i :5001
lsof -i :5432
```

Jeśli porty są zajęte, zmień je w `docker-compose.yml`:
```yaml
ports:
  - "5002:5000"  # zmień 5001 na 5002
```

## 🚀 Krok 4: Uruchomienie

### Sprawdź Docker
```bash
# Sprawdź czy Docker działa
docker --version
docker-compose --version

# Uruchom Docker Desktop (Windows/Mac) jeśli nie jest uruchomiony
```

### Uruchom aplikację
```bash
# Opcja 1: Użyj skryptu zarządzania (Unix/Linux/Mac)
chmod +x docker-manager.sh
./docker-manager.sh start

# Opcja 2: Bezpośrednio docker-compose (wszystkie systemy)
docker-compose up -d

# Sprawdź status
docker-compose ps
```

### Monitoruj uruchamianie
```bash
# Obserwuj logi podczas startu
docker-compose logs -f

# Aby wyjść z logów, naciśnij Ctrl+C
```

## ✅ Krok 5: Weryfikacja

### Sprawdź status aplikacji
```bash
# Status kontenerów
docker-compose ps

# Powinna pokazać:
# ✓ gpw_app - Up (healthy)
# ✓ gpw_postgres - Up (healthy)  
# ✓ gpw_redis - Up (healthy)
```

### Sprawdź aplikację w przeglądarce
1. Otwórz przeglądarkę
2. Przejdź do: **http://localhost:5001**
3. Powinieneś zobaczyć stronę główną GPW Investor

### Test API
```bash
# Health check (zwróci JSON z statusem)
curl http://localhost:5001/api/app/health

# Statystyki aplikacji
curl http://localhost:5001/api/app/stats
```

## 🛠️ Krok 6: Zarządzanie

### Podstawowe komendy
```bash
# Zatrzymaj aplikację
docker-compose down

# Uruchom ponownie
docker-compose up -d

# Restart pojedynczego serwisu
docker-compose restart gpw_app

# Sprawdź logi
docker-compose logs gpw_app
docker-compose logs postgres
```

### Backup danych (zalecane)
```bash
# Backup bazy danych
docker-compose exec postgres pg_dump -U gpw_user gpw_investor > backup-$(date +%Y%m%d).sql

# Backup pełnego stanu (zatrzymaj najpierw aplikację)
docker-compose down
tar -czf gpw_backup-$(date +%Y%m%d).tar.gz data/ logs/ models/ storage/
docker-compose up -d
```

## 🔧 Rozwiązywanie Problemów

### Problem: Kontenery nie startują
```bash
# Sprawdź szczegółowe logi
docker-compose logs

# Sprawdź zasoby systemowe
docker system df
docker system prune  # wyczyść niepotrzebne zasoby
```

### Problem: Port zajęty
```bash
# Windows
netstat -ano | findstr :5001
taskkill /PID <PID> /F

# Linux/Mac
sudo lsof -i :5001
sudo kill <PID>

# LUB zmień port w docker-compose.yml
```

### Problem: Brak pamięci
```bash
# Sprawdź wykorzystanie
docker stats

# Zwiększ limity w Docker Desktop (Windows/Mac):
# Settings > Resources > Memory (ustaw min 4GB)
```

### Problem: Baza danych nie działa
```bash
# Sprawdź logi bazy
docker-compose logs postgres

# Restart bazy danych
docker-compose restart postgres

# Sprawdź czy baza jest dostępna
docker-compose exec postgres pg_isready -U gpw_user
```

### Problem: Aplikacja zwraca błędy
```bash
# Sprawdź logi aplikacji
docker-compose logs gpw_app

# Wejdź do kontenera aplikacji
docker-compose exec gpw_app bash
# Sprawdź pliki i konfigurację
```

## 🔧 Rozwiązywanie Problemów z Budowaniem

### Problem: Błąd ChromeDriver na procesorach Intel
Jeśli otrzymujesz błąd podczas instalacji ChromeDriver:
```
failed to solve: process "/bin/sh -c ARCH=$(dpkg --print-architecture) ... exit code: 8
```

**Rozwiązanie 1: Użyj skryptu budowania**
```bash
# Automatyczny wybór wersji
./build-docker.sh

# Wybierz opcję 2 (uproszczona wersja) lub 3 (automatyczna)
```

**Rozwiązanie 2: Użyj uproszczonej wersji**
```bash
# Buduj bez Chrome/Selenium
docker-compose build --build-arg DOCKERFILE=Dockerfile.simple

# LUB bezpośrednio
docker build -f Dockerfile.simple -t gpw_investor .
```

**Rozwiązanie 3: Ręczne dostosowanie**
```bash
# Edytuj docker-compose.yml
nano docker-compose.yml

# Zmień linię:
# dockerfile: Dockerfile
# na:
# dockerfile: Dockerfile.simple
```

### Problem: Długie budowanie na starszych komputerach
```bash
# Użyj cache Docker
docker build --cache-from gpw_investor .

# LUB wyczyść i rozpocznij od nowa
docker system prune -f
docker-compose build --no-cache
```

### Problem: Brak pamięci podczas budowania
```bash
# Zwiększ limity Docker Desktop (Windows/Mac)
# Settings > Resources > Memory (min 4GB)

# Linux - sprawdź dostępną pamięć
free -h
df -h
```

## 📋 Wersje Dockerfile

### Dockerfile (pełna wersja)
- ✅ Pełna funkcjonalność z Chrome/Selenium
- ✅ Web scraping z wszystkich portali
- ❌ Większy rozmiar (~1.5GB)
- ❌ Dłuższe budowanie
- 🎯 **Zalecana dla produkcji**

### Dockerfile.simple (uproszczona)
- ✅ Szybkie budowanie (~500MB)
- ✅ Wszystkie funkcje ML i API
- ✅ Podstawowy web scraping
- ❌ Brak Chrome/Selenium scrapers
- 🎯 **Zalecana do testów i development**
