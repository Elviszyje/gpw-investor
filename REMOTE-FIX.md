# GPW Investor - Remote Server Fix Guide

This guide will fix the database schema and import issues you're experiencing on the remote server.

## 🔍 Issues Identified

1. **Database Schema Issue**: Missing columns in `companies` table
   - Error: `column "data_source" does not exist`
   - Missing columns: `data_source`, `first_data_date`, `last_data_date`, `total_records`

2. **Import Method Issue**: Missing method in HistoricalDataImporter
   - Error: `'HistoricalDataImporter' object has no attribute 'import_single_file'`

3. **Environment File Syntax**: Invalid character in Telegram bot token

## 🚀 Quick Fix (Recommended)

Run these commands on your remote server:

```bash
# 1. Pull the latest fixes
git pull origin main

# 2. Fix the environment file (remove the '>' character from Telegram token)
# Edit .env and fix this line:
# TELEGRAM_BOT_TOKEN=7865747632:AAG5pY6yzx0YupiVXXjkCQjTeco  (remove the '>' at the end)

# 3. Run the database migration script
./migrate-database.sh

# 4. Rebuild and restart the application
./deploy-remote.sh
```

## 🔧 Manual Fix (Alternative)

If you prefer to do it step by step:

### Step 1: Update Code
```bash
git pull origin main
```

### Step 2: Fix Environment File
Edit `.env` and fix the Telegram token line:
```bash
# Change this:
TELEGRAM_BOT_TOKEN=7865747632:AAG5pY6yzx0YupiVXXjkCQjTeco>

# To this:
TELEGRAM_BOT_TOKEN=7865747632:AAG5pY6yzx0YupiVXXjkCQjTeco
```

### Step 3: Run Database Migration
```bash
./migrate-database.sh
```

### Step 4: Restart Application
```bash
docker-compose -f docker-compose.compatible.yml down
docker build -f Dockerfile.optimized -t gpw-investor:latest .
docker-compose -f docker-compose.compatible.yml up -d
```

## 📋 What the Migration Does

The migration script will:
- ✅ Add missing `data_source` column to companies table
- ✅ Add missing `first_data_date` column
- ✅ Add missing `last_data_date` column  
- ✅ Add missing `total_records` column
- ✅ Set default values for existing records
- ✅ Verify the changes were applied correctly

## 🔍 Verification

After running the fixes, you should see:

1. **No more database errors** in the logs:
   ```bash
   docker-compose -f docker-compose.compatible.yml logs gpw_app
   ```

2. **Successful ticker management**: You should be able to add tickers without errors

3. **Working file uploads**: Historical data import should work properly

## 📱 Testing

Test these features after the fix:

1. **Add a new ticker**:
   - Go to `/manage/tickers`
   - Add a new ticker
   - Should succeed without database errors

2. **Upload historical data**:
   - Go to `/import`
   - Upload a CSV file
   - Should import records successfully

3. **Check logs**:
   ```bash
   docker-compose -f docker-compose.compatible.yml logs --tail=50 gpw_app
   ```
   - Should see no more "column does not exist" errors
   - Should see no more "import_single_file" errors

## 🆘 If Issues Persist

If you still see errors after the migration:

1. **Check database connection**:
   ```bash
   docker exec gpw_postgres psql -U gpw_user -d gpw_investor -c "\d companies"
   ```

2. **Verify columns exist**:
   ```bash
   docker exec gpw_postgres psql -U gpw_user -d gpw_investor -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'companies';"
   ```

3. **Check application logs**:
   ```bash
   docker-compose -f docker-compose.compatible.yml logs --tail=100 gpw_app
   ```

4. **Restart everything**:
   ```bash
   docker-compose -f docker-compose.compatible.yml down
   docker-compose -f docker-compose.compatible.yml up -d
   ```

## 📞 Support

If you need help, check the logs and share:
- Output of `migrate-database.sh`
- Application logs: `docker-compose -f docker-compose.compatible.yml logs gpw_app`
- Database structure: `docker exec gpw_postgres psql -U gpw_user -d gpw_investor -c "\d companies"`
