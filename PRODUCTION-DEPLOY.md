# GPW Investor - Production Deployment Guide

## 🚀 Quick Start

To deploy GPW Investor application on a remote server, use the consolidated production setup:

### 1. Prerequisites
- Docker and Docker Compose installed
- Git repository cloned
- Minimum 4GB RAM, 20GB disk space

### 2. Setup Environment
```bash
# Copy environment template
cp .env.production .env

# Edit configuration (REQUIRED!)
nano .env

# Update these values:
# - POSTGRES_PASSWORD (set secure password)
# - SECRET_KEY (set secure random key)
# - DB_PASSWORD (must match POSTGRES_PASSWORD)
```

### 3. Deploy Application
```bash
# Make deployment script executable
chmod +x deploy.sh

# Deploy everything (build, migrate, start)
./deploy.sh deploy
```

### 4. Verify Deployment
```bash
# Check status
./deploy.sh status

# View logs
./deploy.sh logs
```

## 📋 Management Commands

```bash
./deploy.sh start      # Start services
./deploy.sh stop       # Stop services  
./deploy.sh restart    # Restart services
./deploy.sh status     # Show status
./deploy.sh logs       # Show logs
./deploy.sh migrate    # Run database migration
./deploy.sh backup     # Backup database
./deploy.sh shell      # Open app shell
./deploy.sh clean      # Clean up (WARNING: removes data)
```

## 🔧 Configuration Files

### Production Files (Use These):
- `docker-compose.production.yml` - Main Docker Compose configuration
- `.env.production` - Environment template (copy to `.env`)
- `deploy.sh` - All-in-one deployment script
- `database-schema.sql` - Complete database schema

### Legacy Files (Archive/Remove):
- `docker-compose.yml` - Original version
- `docker-compose.optimized.yml` - Development optimized version  
- `docker-compose.compatible.yml` - Compatibility version
- `migrate-database*.sh` - Old migration scripts
- `build-*.sh` - Old build scripts

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL logs
docker logs gpw_postgres

# Test database connection
docker exec gpw_postgres pg_isready -U gpw_user -d gpw_investor

# Run migration manually
./deploy.sh migrate
```

### Application Issues
```bash
# Check app logs
docker logs gpw_app

# Restart app only
docker restart gpw_app

# Open shell for debugging
./deploy.sh shell
```

### Password Authentication Failed
1. Ensure `.env` file has matching passwords:
   - `POSTGRES_PASSWORD=your_secure_password`
   - `DB_PASSWORD=your_secure_password`
2. Clean deploy:
   ```bash
   docker-compose -f docker-compose.production.yml down -v
   ./deploy.sh deploy
   ```

## 🔒 Security Notes

1. **Change default passwords** in `.env`
2. **Set secure SECRET_KEY** (32+ characters)
3. **Limit port exposure** if needed
4. **Regular backups**: `./deploy.sh backup`
5. **Monitor logs**: `./deploy.sh logs`

## 📊 Default Access

- **Application**: http://localhost:5000
- **Health Check**: http://localhost:5000/api/app/health
- **Database**: localhost:5432 (internal only)
- **Redis**: localhost:6379 (internal only)

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GPW App       │    │   PostgreSQL    │    │     Redis       │
│   (Flask)       │◄──►│   (Database)    │    │    (Cache)      │
│   Port: 5000    │    │   Port: 5432    │    │   Port: 6379    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Data Persistence

All important data is stored in Docker volumes:
- `postgres_data` - Database files
- `redis_data` - Cache data  
- `app_data` - Application data
- `app_logs` - Application logs
- `app_storage` - File storage
- `app_models` - ML models

## 🔄 Updates

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
./deploy.sh deploy
```

## 💾 Backup Strategy

```bash
# Create backup
./deploy.sh backup

# Backups stored in: ./backups/
# Format: gpw_backup_YYYYMMDD_HHMMSS.sql
```

## 🎯 Production Checklist

- [ ] Environment variables configured
- [ ] Secure passwords set
- [ ] Application accessible
- [ ] Database migration completed
- [ ] Health checks passing
- [ ] Logs monitoring setup
- [ ] Backup schedule configured
- [ ] Firewall rules configured (if needed)

## 📞 Support

For issues:
1. Check logs: `./deploy.sh logs`
2. Verify status: `./deploy.sh status`
3. Check database: `./deploy.sh migrate`
4. Review configuration in `.env`
