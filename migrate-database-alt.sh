#!/bin/bash
# Alternative Database Migration Script for GPW Investor
# For cases where PostgreSQL is on a different port or external server

set -e

echo "🔧 GPW Investor - Alternative Database Migration"
echo "==============================================="

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

# Get database connection parameters
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}

echo -e "${BLUE}🔍 Database configuration:${NC}"
echo -e "  Host: $DB_HOST"
echo -e "  Port: $DB_PORT"
echo -e "  Database: $POSTGRES_DB"
echo -e "  User: $POSTGRES_USER"

# Method 1: Try using docker exec first
echo -e "${YELLOW}🔍 Method 1: Trying to find PostgreSQL container...${NC}"
POSTGRES_CONTAINER=$(docker ps --format "table {{.Names}}" | grep -E "(postgres|gpw_postgres)" | head -1)

if [ -n "$POSTGRES_CONTAINER" ]; then
    echo -e "${GREEN}✅ Found PostgreSQL container: $POSTGRES_CONTAINER${NC}"
    
    # Wait for PostgreSQL to be ready
    echo -e "${YELLOW}⏳ Waiting for PostgreSQL to be ready...${NC}"
    until docker exec "$POSTGRES_CONTAINER" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; do
        echo "Waiting for PostgreSQL..."
        sleep 2
    done
    echo -e "${GREEN}✅ PostgreSQL is ready!${NC}"
    
    EXEC_METHOD="docker exec -i $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB"
    
else
    # Method 2: Try direct connection using psql
    echo -e "${YELLOW}🔍 Method 2: Trying direct psql connection...${NC}"
    
    # Check if psql is available
    if ! command -v psql &> /dev/null; then
        echo -e "${RED}❌ Neither PostgreSQL container found nor psql command available!${NC}"
        echo -e "${YELLOW}💡 Options:${NC}"
        echo -e "${YELLOW}   1. Make sure PostgreSQL container is running${NC}"
        echo -e "${YELLOW}   2. Install postgresql-client: apt-get install postgresql-client${NC}"
        echo -e "${YELLOW}   3. Run migration from inside a PostgreSQL container${NC}"
        exit 1
    fi
    
    # Test connection
    if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" > /dev/null 2>&1; then
        echo -e "${RED}❌ Cannot connect to PostgreSQL!${NC}"
        echo -e "${YELLOW}💡 Check:${NC}"
        echo -e "${YELLOW}   - Host: $DB_HOST${NC}"
        echo -e "${YELLOW}   - Port: $DB_PORT${NC}"
        echo -e "${YELLOW}   - Database: $POSTGRES_DB${NC}"
        echo -e "${YELLOW}   - User: $POSTGRES_USER${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Direct PostgreSQL connection successful!${NC}"
    EXEC_METHOD="PGPASSWORD=$POSTGRES_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $POSTGRES_USER -d $POSTGRES_DB"
fi

echo -e "${BLUE}🔧 Running database migration...${NC}"

# Create migration SQL script
MIGRATION_SQL="
-- Migration script to add missing columns to companies table
-- This script is idempotent and can be run multiple times safely

DO \$\$
BEGIN
    RAISE NOTICE 'GPW Investor database migration started';
    
    -- Add data_source column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'data_source') THEN
        ALTER TABLE companies ADD COLUMN data_source VARCHAR(50) DEFAULT 'manual';
        UPDATE companies SET data_source = 'auto_registered' WHERE data_source IS NULL;
        RAISE NOTICE 'Added data_source column';
    ELSE
        RAISE NOTICE 'data_source column exists';
    END IF;
    
    -- Add first_data_date column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'first_data_date') THEN
        ALTER TABLE companies ADD COLUMN first_data_date DATE;
        RAISE NOTICE 'Added first_data_date column';
    ELSE
        RAISE NOTICE 'first_data_date column exists';
    END IF;
    
    -- Add last_data_date column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'last_data_date') THEN
        ALTER TABLE companies ADD COLUMN last_data_date DATE;
        RAISE NOTICE 'Added last_data_date column';
    ELSE
        RAISE NOTICE 'last_data_date column exists';
    END IF;
    
    -- Add total_records column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'companies' AND column_name = 'total_records') THEN
        ALTER TABLE companies ADD COLUMN total_records INTEGER DEFAULT 0;
        RAISE NOTICE 'Added total_records column';
    ELSE
        RAISE NOTICE 'total_records column exists';
    END IF;
    
    -- Update data_source for existing records if needed
    UPDATE companies SET data_source = 'manual' WHERE data_source IS NULL OR data_source = '';
    
    RAISE NOTICE 'Migration completed';
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
if echo "$MIGRATION_SQL" | eval "$EXEC_METHOD"; then
    echo -e "${GREEN}✅ Database migration completed successfully!${NC}"
    
    # Show current companies table structure
    echo -e "${BLUE}📋 Current companies table structure:${NC}"
    echo "\d companies" | eval "$EXEC_METHOD"
    
    echo ""
    echo -e "${GREEN}🎉 Migration completed! The application should now work properly.${NC}"
    echo -e "${YELLOW}💡 You may need to restart the application containers:${NC}"
    echo -e "${YELLOW}   docker-compose -f docker-compose.compatible.yml restart gpw_app${NC}"
    
else
    echo -e "${RED}❌ Database migration failed!${NC}"
    echo -e "${YELLOW}💡 Check the PostgreSQL connection and logs${NC}"
    exit 1
fi
