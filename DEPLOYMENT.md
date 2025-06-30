# GPW Investor - Remote Deployment Guide

This guide covers deployment on remote servers, especially those with older Docker Compose versions.

## Quick Remote Deployment

For quick deployment on remote servers:

```bash
# 1. Upload files to remote server
# 2. Configure environment
cp .env.example .env
# Edit .env with your actual values

# 3. Run deployment script
./deploy-remote.sh
```

## Manual Remote Deployment

If you prefer manual steps:

```bash
# 1. Build image
docker build -f Dockerfile.optimized -t gpw-investor:latest .

# 2. Start services (using compatible compose file)
docker-compose -f docker-compose.compatible.yml up -d

# 3. Check status
docker-compose -f docker-compose.compatible.yml ps
```

## Troubleshooting Remote Issues

### Docker Compose Version Issues

If you see errors like:
- `deploy sub-keys are not supported`
- `'ContainerConfig' KeyError`

Use the compatible compose file:
```bash
# Instead of docker-compose.optimized.yml, use:
docker-compose -f docker-compose.compatible.yml up -d
```

### Build Script with Compatibility

```bash
# Use compatibility mode
./build-optimized.sh --compatible
```

## Differences Between Compose Files

| Feature | Optimized | Compatible |
|---------|-----------|------------|
| Resource limits | `deploy.resources` | `mem_limit` |
| CPU limits | `deploy.resources.cpus` | Removed (not supported) |
| Health checks | Advanced with conditions | Simple health checks |
| Depends on | With conditions | Simple dependencies |

## Environment Configuration

Ensure these variables are set in `.env`:

```bash
# Database
DB_HOST=postgres
DB_PORT=5432
DB_USER=gpw_user
DB_PASSWORD=your-secure-password

# Flask
SECRET_KEY=your-secret-key-min-32-chars

# PostgreSQL Container
POSTGRES_DB=gpw_investor
POSTGRES_USER=gpw_user  
POSTGRES_PASSWORD=your-secure-password
```

## Monitoring

```bash
# View logs
docker-compose -f docker-compose.compatible.yml logs -f

# Check service health
docker-compose -f docker-compose.compatible.yml ps

# Restart services
docker-compose -f docker-compose.compatible.yml restart
```

## Stopping Services

```bash
# Stop all services
docker-compose -f docker-compose.compatible.yml down

# Stop and remove volumes (data loss!)
docker-compose -f docker-compose.compatible.yml down -v
```
