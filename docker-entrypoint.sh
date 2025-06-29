#!/bin/bash
set -e

echo "🚀 Starting GPW Investor Application..."

# Validate required environment variables
echo "🔍 Validating environment variables..."
if [ -z "$DB_HOST" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo "❌ Missing required database environment variables!"
    echo "Required: DB_HOST, DB_USER, DB_PASSWORD"
    echo "Check your .env file exists and has correct values."
    exit 1
fi

if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "your-super-secret-key-change-in-production" ]; then
    echo "⚠️ WARNING: Using default SECRET_KEY! Change it in .env for production!"
fi

echo "✅ Environment variables validated"

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
until pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done
echo "✅ PostgreSQL is ready!"

# Wait a bit more to ensure database is fully ready
sleep 5

# Create necessary directories
mkdir -p storage/articles models logs data
chmod -R 755 storage models logs data

# Initialize database if needed
echo "🔧 Checking database initialization..."
python3 -c "
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Check if main tables exist
    cursor.execute(\"\"\"
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('companies', 'ticker_mappings', 'quotes_daily')
    \"\"\")
    
    table_count = cursor.fetchone()[0]
    print(f'✅ Found {table_count} main tables in database')
    
    if table_count < 3:
        print('🔧 Initializing database schema...')
        # Read and execute schema file
        with open('/app/init-schema.sql', 'r') as f:
            schema_sql = f.read()
        
        # Execute schema initialization
        cursor.execute(schema_sql)
        print('✅ Database schema initialized successfully')
    else:
        print('✅ Database is already initialized')
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f'⚠️ Database initialization failed: {e}')
    print('Application will start but may have limited functionality')
"

echo "🔧 Running database migration fixes..."
# Check if migration is needed and apply fixes
python3 -c "
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

try:
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print('⚠️ No DATABASE_URL, skipping migration')
        exit(0)
    
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Check if fix is needed
    cursor.execute(\"\"\"
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'health_check' 
        AND column_name = 'service_name'
    \"\"\")
    
    has_service_name = cursor.fetchone() is not None
    
    if not has_service_name:
        print('🔧 Applying database schema fixes...')
        # Read and execute fix file
        if os.path.exists('/app/fix-db-schema.sql'):
            with open('/app/fix-db-schema.sql', 'r') as f:
                fix_sql = f.read()
            cursor.execute(fix_sql)
            print('✅ Database schema fixes applied')
        else:
            print('⚠️ Fix file not found, applying basic fixes...')
            # Basic fixes
            cursor.execute(\"\"\"
                ALTER TABLE health_check ADD COLUMN IF NOT EXISTS service_name VARCHAR(50) DEFAULT 'database';
                CREATE TABLE IF NOT EXISTS ticker_mappings (
                    id SERIAL PRIMARY KEY,
                    ticker VARCHAR(10) NOT NULL UNIQUE,
                    bankier_symbol VARCHAR(50),
                    stooq_symbol VARCHAR(50),
                    source VARCHAR(20) DEFAULT 'manual',
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            \"\"\")
            print('✅ Basic schema fixes applied')
    else:
        print('✅ Database schema is up to date')
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f'⚠️ Database migration failed: {e}')
    print('Application will start but may have limited functionality')
"

echo "🔧 Running any necessary database migrations..."
# You can add database migration scripts here if needed

echo "🌐 Starting Flask application..."

# Execute the command passed to the container
if [ $# -eq 0 ]; then
    # Default command
    exec python app.py
else
    # Execute custom command
    exec "$@"
fi
