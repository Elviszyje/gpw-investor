#!/bin/bash
# GPW Investor - Simple Remote Deployment Script
# For older Docker Compose versions and remote servers

set -e

echo "🚀 GPW Investor - Remote Deployment"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo -e "${YELLOW}💡 Copy .env.example to .env and configure it:${NC}"
    echo -e "${YELLOW}   cp .env.example .env${NC}"
    exit 1
fi

# Load .env file and export variables for bash
set -a  # automatically export all variables
source .env
set +a  # stop automatically exporting

# Validate environment variables
echo -e "${YELLOW}🔍 Validating environment variables...${NC}"
if [ -z "$DB_HOST" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}❌ Missing required database environment variables in .env file!${NC}"
    echo -e "${YELLOW}Required: DB_HOST, DB_USER, DB_PASSWORD${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment variables validated${NC}"

# Build the Docker image
echo -e "${BLUE}🔨 Building Docker image...${NC}"
if docker build -f Dockerfile.optimized -t gpw-investor:latest .; then
    echo -e "${GREEN}✅ Docker image built successfully${NC}"
else
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

# Stop existing containers
echo -e "${YELLOW}🛑 Stopping existing containers...${NC}"
docker-compose -f docker-compose.compatible.yml down --remove-orphans || true

# Start services
echo -e "${BLUE}🚀 Starting services...${NC}"
if docker-compose -f docker-compose.compatible.yml up -d; then
    echo -e "${GREEN}✅ Services started successfully${NC}"
    
    # Show service status
    echo -e "${BLUE}📋 Service status:${NC}"
    docker-compose -f docker-compose.compatible.yml ps
    
    # Wait a moment for services to initialize
    sleep 10
    
    # Show logs
    echo -e "${BLUE}📋 Recent logs:${NC}"
    docker-compose -f docker-compose.compatible.yml logs --tail=20
    
    echo ""
    echo -e "${GREEN}🎉 GPW Investor is running!${NC}"
    echo -e "${YELLOW}📱 Access the application at: http://localhost:5000${NC}"
    echo -e "${YELLOW}🔍 Check logs: docker-compose -f docker-compose.compatible.yml logs -f${NC}"
    echo -e "${YELLOW}🛑 Stop services: docker-compose -f docker-compose.compatible.yml down${NC}"
    
else
    echo -e "${RED}❌ Failed to start services${NC}"
    echo -e "${YELLOW}💡 Check logs: docker-compose -f docker-compose.compatible.yml logs${NC}"
    exit 1
fi
