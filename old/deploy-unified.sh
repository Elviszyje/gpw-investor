#!/bin/bash
# GPW Investor - Zunifikowany skrypt deployment dla production
# Single point deployment i zarządzania aplikacją

set -e

echo "🚀 GPW Investor - Zunifikowany Deployment Production"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.unified.yml"
ENV_FILE=".env"
ENV_TEMPLATE=".env.unified"

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy    - Full deployment (build + migrate + start)"
    echo "  start     - Start containers"
    echo "  stop      - Stop containers"  
    echo "  restart   - Restart containers"
    echo "  status    - Show status and health"
    echo "  logs      - Show application logs"
    echo "  migrate   - Run database migration"
    echo "  backup    - Backup database"
    echo "  clean     - Clean containers and images"
    echo "  shell     - Open shell in app container"
    echo "  fix       - Fix common deployment issues"
    echo ""
}

# Function to setup environment
setup_environment() {
    echo -e "${BLUE}🔧 Setting up environment...${NC}"
    
    # Check if .env exists
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}⚠️ No .env file found. Creating from template...${NC}"
        if [ -f "$ENV_TEMPLATE" ]; then
            cp "$ENV_TEMPLATE" "$ENV_FILE"
            echo -e "${GREEN}✅ Created .env from template${NC}"
            echo -e "${RED}🚨 IMPORTANT: Edit .env file and set secure passwords!${NC}"
            echo -e "${YELLOW}Press Enter to continue or Ctrl+C to edit .env first${NC}"
            read
        else
            echo -e "${RED}❌ No .env template found!${NC}"
            exit 1
        fi
    fi

    # Load environment variables
    echo -e "${BLUE}🔍 Loading environment configuration...${NC}"
    set -a
    source "$ENV_FILE"
    set +a

    # Validate critical variables
    echo -e "${YELLOW}🔍 Validating environment variables...${NC}"
    REQUIRED_VARS=("POSTGRES_DB" "POSTGRES_USER" "POSTGRES_PASSWORD" "SECRET_KEY")
    MISSING_VARS=()

    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ] || [[ "${!var}" == *"ZMIEN"* ]]; then
            MISSING_VARS+=("$var")
        fi
    done

    if [ ${#MISSING_VARS[@]} -ne 0 ]; then
        echo -e "${RED}❌ Missing or default values in environment variables:${NC}"
        printf '%s\n' "${MISSING_VARS[@]}"
        echo -e "${YELLOW}Please edit .env file and set secure values${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Environment validated${NC}"
}

# Function to check system requirements
check_requirements() {
    echo -e "${BLUE}🔍 Checking system requirements...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found!${NC}"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}❌ Docker Compose not found!${NC}"
        exit 1
    fi
    
    # Check compose file
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo -e "${RED}❌ Docker Compose file not found: $COMPOSE_FILE${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ System requirements OK${NC}"
}

# Function to deploy application
deploy() {
    echo -e "${BLUE}🚀 Starting full deployment...${NC}"
    
    setup_environment
    check_requirements
    
    # Build application
    echo -e "${BLUE}🔨 Building application...${NC}"
    docker-compose -f "$COMPOSE_FILE" build --no-cache
    
    # Stop existing containers
    echo -e "${BLUE}🛑 Stopping existing containers...${NC}"
    docker-compose -f "$COMPOSE_FILE" down --remove-orphans --volumes
    
    # Start services
    echo -e "${BLUE}🚀 Starting services...${NC}"
    docker-compose -f "$COMPOSE_FILE" up -d
    
    # Wait for services
    echo -e "${BLUE}⏳ Waiting for services to start...${NC}"
    sleep 20
    
    # Run migration
    echo -e "${BLUE}🔧 Running database migration...${NC}"
    migrate_database
    
    # Check health
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
        return 1
    fi
    
    # Check Redis
    if docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis is healthy${NC}"
    else
        echo -e "${RED}❌ Redis is not ready${NC}"
        return 1
    fi
    
    # Check Application
    sleep 5
    if curl -f -s http://localhost:5000/api/app/health > /dev/null 2>&1; then
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
    docker stats --no-stream --format "table {{.Container}}\\t{{.CPUPerc}}\\t{{.MemUsage}}" \\
        gpw_postgres gpw_redis gpw_app 2>/dev/null || echo "Some containers may not be running"
    
    echo ""
    echo -e "${GREEN}🌐 Application URLs:${NC}"
    echo -e "${YELLOW}  Main Application: http://localhost:5000${NC}"
    echo -e "${YELLOW}  Health Check:    http://localhost:5000/api/app/health${NC}"
    
    echo ""
    echo -e "${BLUE}🔧 Management Commands:${NC}"
    echo -e "${YELLOW}  Check logs:    $0 logs${NC}"
    echo -e "${YELLOW}  Open shell:    $0 shell${NC}"
    echo -e "${YELLOW}  Restart:       $0 restart${NC}"
}

# Function to migrate database
migrate_database() {
    echo -e "${BLUE}🔧 Running database migration...${NC}"
    
    # Wait for PostgreSQL
    echo -e "${YELLOW}⏳ Waiting for PostgreSQL...${NC}"
    timeout=60
    counter=0
    until docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; do
        echo "Waiting for PostgreSQL... ($counter/$timeout seconds)"
        sleep 2
        counter=$((counter + 2))
        if [ $counter -ge $timeout ]; then
            echo -e "${RED}❌ PostgreSQL timeout!${NC}"
            return 1
        fi
    done
    
    echo -e "${GREEN}✅ PostgreSQL ready, running migration...${NC}"
    
    # Migration SQL (idempotent)
    MIGRATION_SQL="
DO \\$\\$ 
BEGIN
    -- Add data_source column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'data_source') THEN
        ALTER TABLE companies ADD COLUMN data_source VARCHAR(50) DEFAULT 'manual';
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
END \\$\\$;"

    if docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$MIGRATION_SQL"; then
        echo -e "${GREEN}✅ Database migration completed!${NC}"
    else
        echo -e "${RED}❌ Database migration failed!${NC}"
        return 1
    fi
}

# Function to backup database
backup_database() {
    echo -e "${BLUE}💾 Creating database backup...${NC}"
    
    setup_environment
    
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

# Function to fix common issues
fix_issues() {
    echo -e "${BLUE}🔧 Fixing common deployment issues...${NC}"
    
    # Stop all containers
    echo -e "${YELLOW}🛑 Stopping all containers...${NC}"
    docker-compose -f "$COMPOSE_FILE" down --volumes --remove-orphans
    
    # Remove old images
    echo -e "${YELLOW}🗑️ Removing old images...${NC}"
    docker image prune -f
    docker volume prune -f
    
    # Remove gpw-related containers and images
    echo -e "${YELLOW}🗑️ Cleaning GPW containers...${NC}"
    docker rm -f gpw_postgres gpw_redis gpw_app 2>/dev/null || true
    docker rmi -f gpw-investor:latest 2>/dev/null || true
    
    echo -e "${GREEN}✅ Cleanup completed. Try deployment again.${NC}"
}

# Main command handling
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    start)
        setup_environment
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
        setup_environment
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
        setup_environment
        migrate_database
        ;;
    backup)
        backup_database
        ;;
    clean)
        echo -e "${YELLOW}⚠️ This will remove all containers and volumes. Continue? (y/N)${NC}"
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
    fix)
        fix_issues
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
