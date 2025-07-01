#!/bin/bash
# GPW Investor - Production Deployment Script
# Single script to deploy and manage the application

set -e

echo "🚀 GPW Investor - Production Deployment"
echo "======================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.production.yml"
ENV_FILE=".env"

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠️ No .env file found. Creating from template...${NC}"
    if [ -f ".env.production" ]; then
        cp .env.production .env
        echo -e "${GREEN}✅ Created .env from .env.production template${NC}"
        echo -e "${YELLOW}💡 Please edit .env file and set secure passwords before continuing${NC}"
        echo -e "${YELLOW}💡 Press Enter to continue or Ctrl+C to abort${NC}"
        read
    else
        echo -e "${RED}❌ No .env template found! Please create .env file manually.${NC}"
        exit 1
    fi
fi

# Load environment variables
echo -e "${BLUE}🔍 Loading environment configuration...${NC}"
set -a
source "$ENV_FILE"
set +a

# Validate required environment variables
echo -e "${YELLOW}🔍 Validating environment variables...${NC}"
REQUIRED_VARS=("POSTGRES_DB" "POSTGRES_USER" "POSTGRES_PASSWORD" "SECRET_KEY")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo -e "${RED}❌ Missing required environment variables:${NC}"
    printf '%s\n' "${MISSING_VARS[@]}"
    exit 1
fi

echo -e "${GREEN}✅ Environment variables validated${NC}"

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy    - Deploy the application (build and start)"
    echo "  start     - Start existing containers"
    echo "  stop      - Stop containers"
    echo "  restart   - Restart containers"
    echo "  logs      - Show application logs"
    echo "  status    - Show container status"
    echo "  migrate   - Run database migration"
    echo "  backup    - Backup database"
    echo "  clean     - Clean up containers and images"
    echo "  shell     - Open shell in app container"
    echo ""
}

# Function to deploy application
deploy() {
    echo -e "${BLUE}🔨 Building application...${NC}"
    docker-compose -f "$COMPOSE_FILE" build --no-cache

    echo -e "${BLUE}🛑 Stopping existing containers...${NC}"
    docker-compose -f "$COMPOSE_FILE" down --remove-orphans

    echo -e "${BLUE}🚀 Starting services...${NC}"
    docker-compose -f "$COMPOSE_FILE" up -d

    echo -e "${BLUE}⏳ Waiting for services to be ready...${NC}"
    sleep 15

    # Check service health
    check_health
    
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    show_status
}

# Function to check service health
check_health() {
    echo -e "${BLUE}🔍 Checking service health...${NC}"
    
    # Check PostgreSQL
    if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL is healthy${NC}"
    else
        echo -e "${RED}❌ PostgreSQL is not ready${NC}"
    fi
    
    # Check Redis
    if docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis is healthy${NC}"
    else
        echo -e "${RED}❌ Redis is not ready${NC}"
    fi
    
    # Check Application
    if curl -f http://localhost:${APP_PORT:-5000}/api/app/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Application is healthy${NC}"
    else
        echo -e "${YELLOW}⚠️ Application health check failed (might still be starting)${NC}"
    fi
}

# Function to show status
show_status() {
    echo -e "${BLUE}📋 Container Status:${NC}"
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo ""
    echo -e "${BLUE}📊 Resource Usage:${NC}"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
        gpw_postgres gpw_redis gpw_app 2>/dev/null || echo "Some containers may not be running"
    
    echo ""
    echo -e "${GREEN}🌐 Application URLs:${NC}"
    echo -e "${YELLOW}  Main Application: http://localhost:${APP_PORT:-5000}${NC}"
    echo -e "${YELLOW}  Health Check:    http://localhost:${APP_PORT:-5000}/api/app/health${NC}"
}

# Function to migrate database
migrate_database() {
    echo -e "${BLUE}🔧 Running database migration...${NC}"
    
    # Wait for PostgreSQL to be ready
    echo -e "${YELLOW}⏳ Waiting for PostgreSQL...${NC}"
    until docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; do
        echo "Waiting for PostgreSQL..."
        sleep 2
    done
    
    # Run migration
    MIGRATION_SQL="
DO \$\$ 
BEGIN
    -- Add data_source column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'data_source') THEN
        ALTER TABLE companies ADD COLUMN data_source VARCHAR(50) DEFAULT 'manual';
        UPDATE companies SET data_source = 'auto_registered' WHERE data_source IS NULL;
    END IF;
    
    -- Add first_data_date column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'first_data_date') THEN
        ALTER TABLE companies ADD COLUMN first_data_date DATE;
    END IF;
    
    -- Add last_data_date column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'last_data_date') THEN
        ALTER TABLE companies ADD COLUMN last_data_date DATE;
    END IF;
    
    -- Add total_records column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'total_records') THEN
        ALTER TABLE companies ADD COLUMN total_records INTEGER DEFAULT 0;
    END IF;
    
    -- Update data_source for existing records
    UPDATE companies SET data_source = 'manual' WHERE data_source IS NULL OR data_source = '';
END \$\$;"

    if docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$MIGRATION_SQL"; then
        echo -e "${GREEN}✅ Database migration completed successfully!${NC}"
        
        # Show current companies table structure
        echo -e "${BLUE}📋 Current companies table structure:${NC}"
        docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\d companies"
    else
        echo -e "${RED}❌ Database migration failed!${NC}"
        exit 1
    fi
}

# Function to backup database
backup_database() {
    echo -e "${BLUE}💾 Creating database backup...${NC}"
    
    BACKUP_DIR="./backups"
    BACKUP_FILE="$BACKUP_DIR/gpw_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    mkdir -p "$BACKUP_DIR"
    
    if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_FILE"; then
        echo -e "${GREEN}✅ Database backup created: $BACKUP_FILE${NC}"
    else
        echo -e "${RED}❌ Database backup failed!${NC}"
        exit 1
    fi
}

# Main command handling
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    start)
        echo -e "${BLUE}🚀 Starting services...${NC}"
        docker-compose -f "$COMPOSE_FILE" up -d
        sleep 10
        show_status
        ;;
    stop)
        echo -e "${BLUE}🛑 Stopping services...${NC}"
        docker-compose -f "$COMPOSE_FILE" down
        ;;
    restart)
        echo -e "${BLUE}🔄 Restarting services...${NC}"
        docker-compose -f "$COMPOSE_FILE" restart
        sleep 10
        show_status
        ;;
    logs)
        echo -e "${BLUE}📋 Application logs:${NC}"
        docker-compose -f "$COMPOSE_FILE" logs -f --tail=100
        ;;
    status)
        show_status
        ;;
    migrate)
        migrate_database
        ;;
    backup)
        backup_database
        ;;
    clean)
        echo -e "${YELLOW}⚠️ This will remove all containers and images. Continue? (y/N)${NC}"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            docker-compose -f "$COMPOSE_FILE" down --volumes --remove-orphans
            docker system prune -f
            echo -e "${GREEN}✅ Cleanup completed${NC}"
        fi
        ;;
    shell)
        echo -e "${BLUE}🐚 Opening shell in app container...${NC}"
        docker-compose -f "$COMPOSE_FILE" exec app /bin/bash
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
