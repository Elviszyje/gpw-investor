#!/bin/bash
# GPW Investor - Simple Remote Migration Script
# Works with both Docker containers and direct PostgreSQL connections
# Fixed SQL syntax errors

set -e

echo "🔧 GPW Investor - Simple Remote Migration"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if .env exists and load it
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo -e "${YELLOW}💡 Create .env file with database configuration${NC}"
    exit 1
fi

# Load .env file
set -a
source .env
set +a

# Validate required variables
if [ -z "$POSTGRES_DB" ] || [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_PASSWORD" ]; then
    echo -e "${RED}❌ Missing required database environment variables!${NC}"
    echo -e "${YELLOW}Required: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD${NC}"
    exit 1
fi

echo -e "${BLUE}🔍 Database configuration:${NC}"
echo -e "  Database: $POSTGRES_DB"
echo -e "  User: $POSTGRES_USER"

# Try to find PostgreSQL container
POSTGRES_CONTAINER=""
if docker ps --format "{{.Names}}" | grep -q "postgres"; then
    POSTGRES_CONTAINER=$(docker ps --format "{{.Names}}" | grep "postgres" | head -1)
    echo -e "${GREEN}✅ Found PostgreSQL container: $POSTGRES_CONTAINER${NC}"
else
    echo -e "${YELLOW}⚠️ No PostgreSQL container found${NC}"
fi

# Migration SQL (using heredoc to avoid quoting issues)
run_migration() {
    local connection_method="$1"
    
    echo -e "${BLUE}🔧 Running database migration via $connection_method...${NC}"
    
    # Use heredoc for clean SQL
    cat << 'EOF' | $connection_method
DO $$ 
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
    
    -- Update existing records
    UPDATE companies SET data_source = 'manual' WHERE data_source IS NULL OR data_source = '';
END $$;
EOF
}

# Wait for PostgreSQL to be ready
wait_for_postgres() {
    local test_command="$1"
    local timeout=60
    local counter=0
    
    echo -e "${YELLOW}⏳ Waiting for PostgreSQL to be ready...${NC}"
    
    until eval "$test_command" > /dev/null 2>&1; do
        echo "Waiting for PostgreSQL... ($counter/$timeout seconds)"
        sleep 5
        counter=$((counter + 5))
        if [ $counter -ge $timeout ]; then
            echo -e "${RED}❌ Timeout waiting for PostgreSQL!${NC}"
            return 1
        fi
    done
    
    echo -e "${GREEN}✅ PostgreSQL is ready!${NC}"
    return 0
}

# Method 1: Try Docker container
if [ -n "$POSTGRES_CONTAINER" ]; then
    echo -e "${BLUE}📦 Attempting migration via Docker container...${NC}"
    
    # Test connection
    test_cmd="docker exec $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB -c 'SELECT 1'"
    
    if wait_for_postgres "$test_cmd"; then
        # Run migration
        migration_cmd="docker exec -i $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB"
        
        if run_migration "$migration_cmd"; then
            echo -e "${GREEN}✅ Database migration completed successfully via Docker!${NC}"
            exit 0
        else
            echo -e "${RED}❌ Migration failed via Docker${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ Docker method failed, trying direct connection...${NC}"
    fi
fi

# Method 2: Try direct connection (with different ports)
for port in 5432 15432 ${EXTERNAL_DB_PORT:-5432} ${DB_PORT:-5432}; do
    echo -e "${BLUE}🔌 Attempting direct connection on port $port...${NC}"
    
    # Test connection
    test_cmd="PGPASSWORD=$POSTGRES_PASSWORD psql -h ${DB_HOST:-localhost} -p $port -U $POSTGRES_USER -d $POSTGRES_DB -c 'SELECT 1'"
    
    if wait_for_postgres "$test_cmd"; then
        # Run migration
        migration_cmd="PGPASSWORD=$POSTGRES_PASSWORD psql -h ${DB_HOST:-localhost} -p $port -U $POSTGRES_USER -d $POSTGRES_DB"
        
        if run_migration "$migration_cmd"; then
            echo -e "${GREEN}✅ Database migration completed successfully via direct connection (port $port)!${NC}"
            
            # Show table structure
            echo -e "${BLUE}📋 Updated companies table structure:${NC}"
            PGPASSWORD="$POSTGRES_PASSWORD" psql -h "${DB_HOST:-localhost}" -p "$port" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\d companies"
            
            exit 0
        else
            echo -e "${RED}❌ Migration failed via direct connection on port $port${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ Could not connect on port $port${NC}"
    fi
done

# If we get here, all methods failed
echo -e "${RED}❌ All migration methods failed!${NC}"
echo -e "${YELLOW}💡 Please check:${NC}"
echo -e "${YELLOW}  1. PostgreSQL is running${NC}"
echo -e "${YELLOW}  2. Database credentials in .env are correct${NC}"
echo -e "${YELLOW}  3. Database is accessible${NC}"
echo -e "${YELLOW}  4. Try: docker-compose logs postgres${NC}"
exit 1
