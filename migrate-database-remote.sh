#!/bin/bash
# Database Migration Script for GPW Investor (Remote Version)
# For remote servers with custom port configurations
# Uses direct connection through exposed port

set -e

echo "🔧 GPW Investor - Database Migration (Remote)"
echo "=============================================="

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

# Use custom external port if specified, otherwise try to detect
EXTERNAL_DB_PORT=${EXTERNAL_DB_PORT:-15432}
DB_HOST=${DB_HOST:-localhost}

echo -e "${BLUE}🔍 Remote database configuration:${NC}"
echo -e "  Host: $DB_HOST"
echo -e "  External Port: $EXTERNAL_DB_PORT"
echo -e "  Database: $POSTGRES_DB"
echo -e "  User: $POSTGRES_USER"

# Check if PostgreSQL is accessible through external port
echo -e "${YELLOW}⏳ Checking PostgreSQL connection through external port...${NC}"
TIMEOUT=60
COUNTER=0

# Install psql if not available (for direct connection testing)
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}💡 psql not found, will use docker container for connection${NC}"
    # Try to use PostgreSQL from container
    POSTGRES_CONTAINER=""
    if docker ps --format "{{.Names}}" | grep -q "postgres"; then
        POSTGRES_CONTAINER=$(docker ps --format "{{.Names}}" | grep "postgres" | head -1)
        echo -e "${GREEN}✅ Using PostgreSQL container for migration: $POSTGRES_CONTAINER${NC}"
        
        # Test connection through container
        until docker exec "$POSTGRES_CONTAINER" psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" > /dev/null 2>&1; do
            echo "Waiting for PostgreSQL... ($COUNTER/$TIMEOUT seconds)"
            sleep 5
            COUNTER=$((COUNTER + 5))
            if [ $COUNTER -ge $TIMEOUT ]; then
                echo -e "${RED}❌ Cannot connect to PostgreSQL!${NC}"
                exit 1
            fi
        done
        
        # Run migration using container
        echo -e "${BLUE}🔧 Running database migration through container...${NC}"
        
        MIGRATION_SQL='
DO $$ 
BEGIN
    RAISE NOTICE ''GPW Investor database migration started'';
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = ''companies'' AND column_name = ''data_source'') THEN
        ALTER TABLE companies ADD COLUMN data_source VARCHAR(50) DEFAULT ''manual'';
        UPDATE companies SET data_source = ''auto_registered'' WHERE data_source IS NULL;
        RAISE NOTICE ''Added data_source column'';
    ELSE
        RAISE NOTICE ''data_source column exists'';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = ''companies'' AND column_name = ''first_data_date'') THEN
        ALTER TABLE companies ADD COLUMN first_data_date DATE;
        RAISE NOTICE ''Added first_data_date column'';
    ELSE
        RAISE NOTICE ''first_data_date column exists'';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = ''companies'' AND column_name = ''last_data_date'') THEN
        ALTER TABLE companies ADD COLUMN last_data_date DATE;
        RAISE NOTICE ''Added last_data_date column'';
    ELSE
        RAISE NOTICE ''last_data_date column exists'';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = ''companies'' AND column_name = ''total_records'') THEN
        ALTER TABLE companies ADD COLUMN total_records INTEGER DEFAULT 0;
        RAISE NOTICE ''Added total_records column'';
    ELSE
        RAISE NOTICE ''total_records column exists'';
    END IF;
    
    UPDATE companies SET data_source = ''manual'' WHERE data_source IS NULL OR data_source = '''';
    RAISE NOTICE ''Migration completed'';
END $$;'

        if docker exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$MIGRATION_SQL"; then
            echo -e "${GREEN}✅ Database migration completed successfully!${NC}"
        else
            echo -e "${RED}❌ Database migration failed!${NC}"
            exit 1
        fi
        
    else
        echo -e "${RED}❌ No PostgreSQL container found and psql not available!${NC}"
        echo -e "${YELLOW}💡 Install postgresql-client or run the container-based migration${NC}"
        exit 1
    fi
else
    # Direct connection method using psql
    echo -e "${BLUE}🔧 Testing direct connection to PostgreSQL...${NC}"
    
    until PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$EXTERNAL_DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" > /dev/null 2>&1; do
        echo "Waiting for PostgreSQL connection... ($COUNTER/$TIMEOUT seconds)"
        sleep 5
        COUNTER=$((COUNTER + 5))
        if [ $COUNTER -ge $TIMEOUT ]; then
            echo -e "${RED}❌ Cannot connect to PostgreSQL on port $EXTERNAL_DB_PORT!${NC}"
            echo -e "${YELLOW}💡 Check if PostgreSQL is running and port is correct${NC}"
            exit 1
        fi
    done
    
    echo -e "${GREEN}✅ PostgreSQL connection successful!${NC}"
    echo -e "${BLUE}🔧 Running database migration...${NC}"
    
    # Run migration using direct connection
    MIGRATION_SQL="
DO \$\$ 
BEGIN
    RAISE NOTICE 'GPW Investor database migration started';
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'companies' AND column_name = 'data_source') THEN
        ALTER TABLE companies ADD COLUMN data_source VARCHAR(50) DEFAULT 'manual';
        UPDATE companies SET data_source = 'auto_registered' WHERE data_source IS NULL;
        RAISE NOTICE 'Added data_source column';
    ELSE
        RAISE NOTICE 'data_source column exists';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'companies' AND column_name = 'first_data_date') THEN
        ALTER TABLE companies ADD COLUMN first_data_date DATE;
        RAISE NOTICE 'Added first_data_date column';
    ELSE
        RAISE NOTICE 'first_data_date column exists';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'companies' AND column_name = 'last_data_date') THEN
        ALTER TABLE companies ADD COLUMN last_data_date DATE;
        RAISE NOTICE 'Added last_data_date column';
    ELSE
        RAISE NOTICE 'last_data_date column exists';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'companies' AND column_name = 'total_records') THEN
        ALTER TABLE companies ADD COLUMN total_records INTEGER DEFAULT 0;
        RAISE NOTICE 'Added total_records column';
    ELSE
        RAISE NOTICE 'total_records column exists';
    END IF;
    
    UPDATE companies SET data_source = 'manual' WHERE data_source IS NULL OR data_source = '';
    RAISE NOTICE 'Migration completed';
END \$\$;"

    if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$EXTERNAL_DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$MIGRATION_SQL"; then
        echo -e "${GREEN}✅ Database migration completed successfully!${NC}"
        
        # Show table structure
        echo -e "${BLUE}📋 Updated companies table structure:${NC}"
        PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$EXTERNAL_DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\d companies"
        
    else
        echo -e "${RED}❌ Database migration failed!${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}🎉 Migration completed successfully!${NC}"
echo -e "${YELLOW}💡 You may need to restart the application:${NC}"
echo -e "${YELLOW}   docker-compose -f docker-compose.compatible.yml restart gpw_app${NC}"
