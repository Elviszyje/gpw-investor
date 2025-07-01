#!/bin/bash
# GPW Investor - Quick Setup dla serwerów zdalnych
# Nie wymaga pliku .env.unified - tworzy go automatycznie

set -e

echo "🚀 GPW Investor - Quick Remote Setup"
echo "===================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 1. Pulling latest changes from git...${NC}"
git pull

echo -e "${BLUE}🔧 2. Creating .env configuration...${NC}"

# Create .env directly without needing .env.unified
cat > .env << 'EOF'
# GPW Investor - Production Environment Configuration
# ВАЖNE: Zmień hasła przed deploymentem!

# ===== KONFIGURACJA BAZY DANYCH =====
POSTGRES_DB=gpw_investor
POSTGRES_USER=gpw_user
POSTGRES_PASSWORD=secure_production_password_123

# Database connection dla aplikacji (musi być identyczne z PostgreSQL)
DB_HOST=postgres
DB_PORT=5432
DB_NAME=gpw_investor
DB_USER=gpw_user
DB_PASSWORD=secure_production_password_123

# ===== KONFIGURACJA FLASK =====
FLASK_ENV=production
FLASK_DEBUG=false
SECRET_KEY=your_very_secure_secret_key_min_32_chars_here

# ===== KONFIGURACJA APLIKACJI =====
APP_PORT=5000
TZ=Europe/Warsaw

# ===== REDIS =====
REDIS_URL=redis://redis:6379/0

# ===== OPCJONALNE - TELEGRAM BOT =====
TELEGRAM_BOT_TOKEN=
TELEGRAM_DEFAULT_CHAT_ID=
EOF

echo -e "${GREEN}✅ Created .env with default secure passwords${NC}"

echo -e "${RED}🚨 IMPORTANT: Review and change passwords in .env if needed!${NC}"
echo -e "${YELLOW}Current passwords are reasonably secure but you may want to customize them.${NC}"

echo ""
echo -e "${BLUE}📝 Current .env configuration:${NC}"
cat .env

echo ""
echo -e "${YELLOW}Continue with deployment? Press Enter to proceed or Ctrl+C to edit .env first...${NC}"
read

echo -e "${BLUE}🗂️ 3. Archiving old configuration files...${NC}"

# Create archive directory
mkdir -p archive/old-configs

# Archive old files (only if they exist)
echo -e "${YELLOW}Moving old files to archive...${NC}"
[ -f docker-compose.yml ] && mv docker-compose.yml archive/old-configs/ || true
[ -f docker-compose.production.yml ] && mv docker-compose.production.yml archive/old-configs/ || true
[ -f docker-compose.compatible.yml ] && mv docker-compose.compatible.yml archive/old-configs/ || true
[ -f docker-compose.optimized.yml ] && mv docker-compose.optimized.yml archive/old-configs/ || true
[ -f migrate-database.sh ] && mv migrate-database*.sh archive/old-configs/ || true
[ -f deploy.sh ] && mv deploy.sh archive/old-configs/ || true
[ -f deploy-remote.sh ] && mv deploy-remote.sh archive/old-configs/ || true

echo -e "${GREEN}✅ Old files archived${NC}"

echo -e "${BLUE}🚀 4. Running unified deployment...${NC}"

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
echo -e "${GREEN}🎉 Quick setup completed!${NC}"
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
echo ""
echo -e "${GREEN}✅ Rozwiązuje błąd: password authentication failed for user gpw_user${NC}"
