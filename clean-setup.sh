#!/bin/bash
# GPW Investor - CLEAN SETUP dla production
# Rozwiązuje wszystkie problemy z uwierzytelnianiem PostgreSQL

set -e

echo "🧹 GPW Investor - Clean Setup Production"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🗂️ 1. Archiving old configuration files...${NC}"

# Create archive directory
mkdir -p archive/old-configs

# Archive old files
echo -e "${YELLOW}Moving old files to archive...${NC}"
mv docker-compose.yml archive/old-configs/ 2>/dev/null || true
mv docker-compose.production.yml archive/old-configs/ 2>/dev/null || true
mv docker-compose.compatible.yml archive/old-configs/ 2>/dev/null || true
mv docker-compose.optimized.yml archive/old-configs/ 2>/dev/null || true
mv migrate-database*.sh archive/old-configs/ 2>/dev/null || true
mv deploy.sh archive/old-configs/ 2>/dev/null || true
mv deploy-remote.sh archive/old-configs/ 2>/dev/null || true

echo -e "${GREEN}✅ Old files archived${NC}"

echo -e "${BLUE}🔧 2. Setting up unified environment...${NC}"

# Check if .env.unified exists, if not create it
if [ ! -f ".env.unified" ]; then
    echo -e "${YELLOW}⚠️ .env.unified not found, creating from scratch...${NC}"
    cat > .env.unified << 'EOF'
# GPW Investor - Zunifikowana konfiguracja środowiska production
# Skopiuj ten plik do .env i ustaw bezpieczne hasła

# ===== KONFIGURACJA BAZY DANYCH =====
POSTGRES_DB=gpw_investor
POSTGRES_USER=gpw_user
POSTGRES_PASSWORD=ZMIEN_NA_BEZPIECZNE_HASLO_PRODUCTION

# Database connection dla aplikacji (musi być identyczne z PostgreSQL)
DB_HOST=postgres
DB_PORT=5432
DB_NAME=gpw_investor
DB_USER=gpw_user
DB_PASSWORD=ZMIEN_NA_BEZPIECZNE_HASLO_PRODUCTION

# ===== KONFIGURACJA FLASK =====
FLASK_ENV=production
FLASK_DEBUG=false
SECRET_KEY=ZMIEN_NA_BEZPIECZNY_KLUCZ_MIN_32_ZNAKI_PRODUCTION

# ===== KONFIGURACJA APLIKACJI =====
APP_PORT=5000
TZ=Europe/Warsaw

# ===== REDIS =====
REDIS_URL=redis://redis:6379/0

# ===== OPCJONALNE - TELEGRAM BOT =====
TELEGRAM_BOT_TOKEN=
TELEGRAM_DEFAULT_CHAT_ID=

# ===== UWAGI =====
# 1. ZMIEŃ wszystkie hasła i klucze przed deploymentem!
# 2. Użyj: ./deploy-unified.sh deploy
# 3. Sprawdź status: ./deploy-unified.sh status
EOF
fi

# Copy unified template to .env
cp .env.unified .env

echo -e "${RED}🚨 IMPORTANT: Set secure passwords in .env file!${NC}"
echo -e "${YELLOW}Edit the following variables in .env:${NC}"
echo -e "${YELLOW}  - POSTGRES_PASSWORD${NC}"
echo -e "${YELLOW}  - SECRET_KEY${NC}"

echo ""
echo -e "${BLUE}📝 Current .env template:${NC}"
cat .env

echo ""
echo -e "${YELLOW}Please edit .env file now. Press Enter when ready to continue...${NC}"
read

echo -e "${BLUE}🚀 3. Running deployment...${NC}"

# Stop any existing containers
echo -e "${YELLOW}Stopping existing containers...${NC}"
docker-compose -f docker-compose.unified.yml down --volumes --remove-orphans 2>/dev/null || true

# Clean Docker system
echo -e "${YELLOW}Cleaning Docker system...${NC}"
docker system prune -f

# Remove old GPW containers and images
echo -e "${YELLOW}Removing old GPW containers and images...${NC}"
docker rm -f gpw_postgres gpw_redis gpw_app 2>/dev/null || true
docker rmi -f gpw-investor:latest 2>/dev/null || true

# Deploy using unified script
echo -e "${BLUE}🚀 Starting unified deployment...${NC}"
./deploy-unified.sh deploy

echo ""
echo -e "${GREEN}🎉 Clean setup completed!${NC}"
echo ""
echo -e "${BLUE}📋 Next steps:${NC}"
echo -e "${YELLOW}1. Check application status: ./deploy-unified.sh status${NC}"
echo -e "${YELLOW}2. View logs: ./deploy-unified.sh logs${NC}"
echo -e "${YELLOW}3. Test application: curl http://localhost:5000/api/app/health${NC}"
echo -e "${YELLOW}4. Test ticker list: curl http://localhost:5000/api/tickers/list${NC}"
echo ""
echo -e "${GREEN}🌐 Application URLs:${NC}"
echo -e "${YELLOW}  Main Application: http://localhost:5000${NC}"
echo -e "${YELLOW}  Health Check:    http://localhost:5000/api/app/health${NC}"
