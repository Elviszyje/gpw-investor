# 🚀 Publikacja GPW Investor do Repozytorium Git

Kompletny przewodnik po publikacji projektu GPW Investor do repozytorium Git (GitHub, GitLab, Bitbucket, itp.).

## 📋 Przygotowanie Projektu

### 1. Sprawdź obecny stan
```bash
# Sprawdź czy to już repozytorium Git
git status

# Jeśli nie jest, zainicjalizuj
git init
```

### 2. Przygotuj konfigurację środowiska
```bash
# Skopiuj przykładową konfigurację
cp .env .env.backup  # zachowaj obecną konfigurację
cp .env.example .env

# WAŻNE: Uzupełnij .env swoimi danymi
# Nie publikuj prawdziwych haseł!
```

### 3. Sprawdź co będzie dodane
```bash
# Zobacz jakie pliki będą w repozytorium
git add . --dry-run
git status
```

## 🗂️ Pliki Przygotowane do Publikacji

### ✅ Zawarte w repozytorium:
- 📁 **Kod aplikacji** - app.py, blueprints/, workers/, templates/, static/
- 🐳 **Docker** - Dockerfile, docker-compose.yml, docker-entrypoint.sh
- 📋 **Konfiguracja** - requirements.txt, nginx.conf, init-schema.sql
- 📚 **Dokumentacja** - README.md, instrukcje instalacji
- 🛠️ **Skrypty** - docker-manager.sh, package-for-transfer.sh/bat
- ⚙️ **Przykłady** - .env.example
- 📁 **Struktura folderów** - .gitkeep files

### ❌ Zignorowane (.gitignore):
- 🔐 **Hasła i klucze** - .env (prawdziwy plik konfiguracyjny)
- 📊 **Dane aplikacji** - data/, logs/, storage/ (tylko struktura)
- 🤖 **Modele ML** - models/*.pkl (za duże do repozytorium)
- 🐍 **Python cache** - __pycache__/, *.pyc
- 🗄️ **Dane bazy** - postgres_data/, redis_data/
- 💾 **Archiwa** - *.tar.gz, *.zip, backup*.sql

## 🔧 Krok po Kroku - Publikacja

### GitHub (zalecane)

#### 1. Utwórz repozytorium na GitHub
1. Idź na https://github.com/new
2. Nazwa: `gpw-investor` (lub inna)
3. Opis: `🚀 GPW Investor - ML-powered stock analysis platform with Docker`
4. Publiczne/Prywatne: według preferencji
5. **NIE** zaznaczaj: Add README, .gitignore, license (mamy już swoje)
6. Kliknij **Create repository**

#### 2. Lokalnie - dodaj pliki
```bash
# Zainicjalizuj repozytorium (jeśli jeszcze nie)
git init

# Dodaj wszystkie pliki
git add .

# Sprawdź co zostanie dodane
git status

# Pierwszy commit
git commit -m "feat: initial GPW Investor release with Docker containerization

✨ Features:
- Flask app with modular blueprints architecture
- ML models for stock recommendations and pattern analysis
- Web scrapers for real-time market data (Bankier, ESPI, news)
- PostgreSQL + Redis containerized setup
- Docker deployment with health checks
- Comprehensive documentation and transfer scripts
- Modern responsive UI with Chart.js visualizations

🐳 Docker:
- Multi-service setup (Flask + PostgreSQL + Redis)
- Auto-initialization with sample data
- Production-ready configuration
- Health monitoring and logging

📚 Documentation:
- Quick start guide (3 commands)
- Detailed installation instructions
- Transfer/deployment scripts
- Troubleshooting guide

🚀 Ready to run: docker-compose up -d"
```

#### 3. Połącz z GitHub
```bash
# Dodaj remote (gotowe dla tego repozytorium)
git remote add origin https://github.com/Elviszyje/gpw-investor.git

# Sprawdź połączenie
git remote -v

# Wypchnij na GitHub
git branch -M main
git push -u origin main
```

### GitLab

#### 1. Utwórz projekt na GitLab
1. Idź na https://gitlab.com/projects/new
2. Wybierz "Create blank project"
3. Project name: `gpw-investor`
4. Ustaw widoczność
5. **NIE** zaznaczaj initialize options
6. **Create project**

#### 2. Wypchnij kod
```bash
git init
git add .
git commit -m "feat: initial GPW Investor release"
git remote add origin https://gitlab.com/USERNAME/gpw-investor.git
git branch -M main
git push -u origin main
```

### Bitbucket

#### 1. Utwórz repozytorium
1. https://bitbucket.org/repo/create
2. Repository name: `gpw-investor`
3. **NIE** zaznaczaj include options

#### 2. Wypchnij kod
```bash
git init
git add .
git commit -m "feat: initial GPW Investor release"
git remote add origin https://bitbucket.org/USERNAME/gpw-investor.git
git push -u origin main
```

## 🔒 Bezpieczeństwo - WAŻNE!

### ❌ NIGDY nie publikuj:
```bash
# Sprawdź czy .env jest zignorowany
cat .gitignore | grep .env

# Sprawdź czy nie ma .env w staging
git status
```

### ✅ Bezpieczne praktyki:
- 🔐 Użyj .env.example z placeholder'ami
- 🔑 Prawdziwe hasła tylko w lokalnym .env
- 📝 Dokumentuj wymagane zmienne środowiskowe
- 🚫 Nie commituj kluczy API, tokenów, haseł

## 📊 Po Publikacji

### 1. Sprawdź repozytorium
```bash
# Clone test w nowym folderze
cd /tmp
git clone https://github.com/Elviszyje/gpw-investor.git
cd REPO_NAME

# Test uruchomienia
cp .env.example .env
# Edytuj .env z własnymi danymi
docker-compose up -d
```

### 2. Aktualizuj README.md
```bash
# Zastąp placeholder URL w README.md
sed -i 's/<repo>/https:\/\/github.com\/Elviszyje\/gpw-investor.git/g' README.md
git add README.md
git commit -m "docs: update repository URL in README"
git push
```

### 3. Dodaj dodatkowe pliki (opcjonalne)
```bash
# License
# CONTRIBUTING.md
# CHANGELOG.md
# .github/workflows/ (dla GitHub Actions)
```

## 🚀 Dalsze Zarządzanie

### Aktualizacje
```bash
# Nowe zmiany
git add .
git commit -m "feat: add new feature XYZ"
git push

# Tagi wersji
git tag -a v1.0.0 -m "Release version 1.0.0"
git push --tags
```

### Branching Strategy
```bash
# Development branch
git checkout -b develop
git push -u origin develop

# Feature branches
git checkout -b feature/new-scraper
# ... zmiany ...
git push -u origin feature/new-scraper
# Potem Pull Request/Merge Request
```

### Issue tracking
- Używaj Issues na GitHub/GitLab/Bitbucket
- Labels: bug, enhancement, documentation, etc.
- Milestones dla wersji

## 🎯 Quick Commands

```bash
# Kompletna publikacja (pierwsze uruchomienie)
git init
git add .
git commit -m "feat: initial GPW Investor release"
git remote add origin https://github.com/Elviszyje/gpw-investor.git
git branch -M main
git push -u origin main

# Update README z prawdziwym URL
sed -i 's/<repo>/https:\/\/github.com\/Elviszyje\/gpw-investor.git/g' README.md
git add README.md
git commit -m "docs: update repository URL"
git push

# Tag pierwszej wersji
git tag -a v1.0.0 -m "Initial release"
git push --tags
```

## 📞 Wsparcie

Po publikacji repozytorium:
1. **README.md** będzie zawierał instrukcje quick start
2. **Issues** - dla bug reportów i feature requests
3. **Wiki/Docs** - dla rozszerzonej dokumentacji
4. **Releases** - dla packaged versions

**Gotowe! Twój projekt GPW Investor jest teraz dostępny publicznie! 🎉**
