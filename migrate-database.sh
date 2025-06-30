#!/bin/bash
# Database Migration Script for GPW Investor
# Fixes missing columns in companies table

set -e

echo "🔧 GPW Investor - Database Migration"
echo "===================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if .env exists and load it
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    exit 1
fi

# Load .env file and export variables for bash
set -a  # automatically export all variables
source .env
set +a  # stop automatically exporting

# Validate database connection variables
if [ -z "$POSTGRES_DB" ] || [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_PASSWORD" ]; then
    echo -e "${RED}❌ Missing required database environment variables!${NC}"
    echo -e "${YELLOW}Required: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD${NC}"
    exit 1
fi

# Detect database port from DB_PORT or default to 5432
DB_PORT=${DB_PORT:-5432}
echo -e "${BLUE}🔍 Database configuration:${NC}"
echo -e "  Host: ${DB_HOST:-localhost}"
echo -e "  Port: $DB_PORT"
echo -e "  Database: $POSTGRES_DB"
echo -e "  User: $POSTGRES_USER"

# Auto-detect container name - prioritize GPW-specific container
POSTGRES_CONTAINER=""

# First try to find GPW-specific PostgreSQL container
if docker ps --format "{{.Names}}" | grep -q "^gpw_postgres$"; then
    POSTGRES_CONTAINER="gpw_postgres"
    echo -e "${GREEN}✅ Found GPW PostgreSQL container: $POSTGRES_CONTAINER${NC}"
elif docker ps --format "{{.Names}}" | grep -q "postgres"; then
    POSTGRES_CONTAINER=$(docker ps --format "{{.Names}}" | grep "postgres" | head -1)
    echo -e "${YELLOW}⚠️ Using generic PostgreSQL container: $POSTGRES_CONTAINER${NC}"
else
    echo -e "${RED}❌ No PostgreSQL container found!${NC}"
    echo -e "${YELLOW}💡 Make sure PostgreSQL container is running:${NC}"
    echo -e "${YELLOW}   docker-compose -f docker-compose.compatible.yml ps${NC}"
    exit 1
fi

echo -e "${BLUE}🔍 Using PostgreSQL container: $POSTGRES_CONTAINER${NC}"

# Wait for PostgreSQL to be ready with extended timeout and better error handling
echo -e "${YELLOW}⏳ Waiting for PostgreSQL to be ready...${NC}"
TIMEOUT=120  # 2 minutes timeout
COUNTER=0
until docker exec "$POSTGRES_CONTAINER" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; do
  echo "Waiting for PostgreSQL... ($COUNTER/$TIMEOUT seconds)"
  
  # Show container status for debugging
  if [ $((COUNTER % 20)) -eq 0 ] && [ $COUNTER -gt 0 ]; then
    echo -e "${BLUE}🔍 Container status:${NC}"
    docker ps --filter "name=$POSTGRES_CONTAINER" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo -e "${BLUE}🔍 Recent container logs:${NC}"
    docker logs "$POSTGRES_CONTAINER" --tail=5 2>/dev/null || echo "Could not fetch logs"
  fi
  
  sleep 5
  COUNTER=$((COUNTER + 5))
  if [ $COUNTER -ge $TIMEOUT ]; then
    echo -e "${RED}❌ Timeout waiting for PostgreSQL to be ready!${NC}"
    echo -e "${YELLOW}💡 Container status:${NC}"
    docker ps --filter "name=$POSTGRES_CONTAINER"
    echo -e "${YELLOW}💡 Container logs:${NC}"
    docker logs "$POSTGRES_CONTAINER" --tail=20
    echo -e "${YELLOW}💡 Try running manually:${NC}"
    echo -e "${YELLOW}   docker exec $POSTGRES_CONTAINER pg_isready -U $POSTGRES_USER -d $POSTGRES_DB${NC}"
    exit 1
  fi
done
echo -e "${GREEN}✅ PostgreSQL is ready!${NC}"

echo -e "${BLUE}🔧 Running database migration...${NC}"

# Create migration SQL script
MIGRATION_SQL="
-- Migration script to add missing columns to companies table
-- This script is idempotent and can be run multiple times safely

DO \$\$
BEGIN
    RAISE NOTICE 'Starting GPW Investor database migration...';
    
    -- Add data_source column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'data_source') THEN
        ALTER TABLE companies ADD COLUMN data_source VARCHAR(50) DEFAULT 'manual';
        UPDATE companies SET data_source = 'auto_registered' WHERE data_source IS NULL;
        RAISE NOTICE 'Added data_source column to companies table';
    ELSE
        RAISE NOTICE 'data_source column already exists in companies table';
    END IF;
    
    -- Add first_data_date column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'first_data_date') THEN
        ALTER TABLE companies ADD COLUMN first_data_date DATE;
        RAISE NOTICE 'Added first_data_date column to companies table';
    ELSE
        RAISE NOTICE 'first_data_date column already exists in companies table';
    END IF;
    
    -- Add last_data_date column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'last_data_date') THEN
        ALTER TABLE companies ADD COLUMN last_data_date DATE;
        RAISE NOTICE 'Added last_data_date column to companies table';
    ELSE
        RAISE NOTICE 'last_data_date column already exists in companies table';
    END IF;
    
    -- Add total_records column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'total_records') THEN
        ALTER TABLE companies ADD COLUMN total_records INTEGER DEFAULT 0;
        RAISE NOTICE 'Added total_records column to companies table';
    ELSE
        RAISE NOTICE 'total_records column already exists in companies table';
    END IF;
    
    -- Update data_source for existing records if needed
    UPDATE companies SET data_source = 'manual' WHERE data_source IS NULL OR data_source = '';
    
    RAISE NOTICE 'Database migration completed successfully!';
END \$\$;

-- Verify the schema
SELECT 
    column_name, 
    data_type, 
    is_nullable, 
    column_default
FROM information_schema.columns 
WHERE table_name = 'companies' 
ORDER BY ordinal_position;
"

# Execute migration
if docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<< "$MIGRATION_SQL"; then
    echo -e "${GREEN}✅ Database migration completed successfully!${NC}"
    
    # Show current companies table structure
    echo -e "${BLUE}📋 Current companies table structure:${NC}"
    docker exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\d companies"
    
    echo ""
    echo -e "${GREEN}🎉 Migration completed! The application should now work properly.${NC}"
    echo -e "${YELLOW}💡 You may need to restart the application containers:${NC}"
    echo -e "${YELLOW}   docker-compose -f docker-compose.compatible.yml restart gpw_app${NC}"
    
else
    echo -e "${RED}❌ Database migration failed!${NC}"
    echo -e "${YELLOW}💡 Check the PostgreSQL logs:${NC}"
    echo -e "${YELLOW}   docker-compose -f docker-compose.compatible.yml logs postgres${NC}"
    exit 1
fi
