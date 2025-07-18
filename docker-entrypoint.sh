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
        # Read and execute NEW consolidated schema file
        with open('/app/database-schema.sql', 'r') as f:
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

echo "🔧 Running any necessary database migrations..."
# Note: The new database-schema.sql is idempotent and handles all migrations automatically

echo "🌐 Starting Flask application..."
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
