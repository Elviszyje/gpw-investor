#!/bin/bash
# GPW Investor - Optimized Docker Build Script

set -e

echo "🚀 GPW Investor - Optimized Docker Build"
echo "======================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="gpw-investor"
DOCKERFILE="Dockerfile.optimized"
COMPOSE_FILE="docker-compose.optimized.yml"
BUILD_ARGS=""

# Parse command line arguments
PROFILE="development"
CLEAN_BUILD=false
NO_CACHE=false
PARALLEL_JOBS=4

while [[ $# -gt 0 ]]; do
  case $1 in
    --production)
      PROFILE="production"
      shift
      ;;
    --clean)
      CLEAN_BUILD=true
      shift
      ;;
    --no-cache)
      NO_CACHE=true
      BUILD_ARGS="$BUILD_ARGS --no-cache"
      shift
      ;;
    --parallel)
      PARALLEL_JOBS="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  --production    Build for production"
      echo "  --clean         Clean build (remove volumes and images)"
      echo "  --no-cache      Build without Docker cache"
      echo "  --parallel N    Set number of parallel jobs (default: 4)"
      echo "  -h, --help      Show this help"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

echo -e "${BLUE}📋 Build Configuration:${NC}"
echo -e "${BLUE}  - Profile: ${YELLOW}$PROFILE${NC}"
echo -e "${BLUE}  - Dockerfile: ${YELLOW}$DOCKERFILE${NC}"
echo -e "${BLUE}  - Compose file: ${YELLOW}$COMPOSE_FILE${NC}"
echo -e "${BLUE}  - Clean build: ${YELLOW}$CLEAN_BUILD${NC}"
echo -e "${BLUE}  - No cache: ${YELLOW}$NO_CACHE${NC}"
echo -e "${BLUE}  - Parallel jobs: ${YELLOW}$PARALLEL_JOBS${NC}"
echo ""

# Clean build if requested
if [ "$CLEAN_BUILD" = true ]; then
    echo -e "${YELLOW}🧹 Cleaning up existing containers and images...${NC}"
    
    # Stop and remove containers
    docker-compose -f $COMPOSE_FILE down --volumes --remove-orphans || true
    
    # Remove images
    docker rmi $IMAGE_NAME:latest || true
    docker rmi $(docker images -f "dangling=true" -q) 2>/dev/null || true
    
    # Prune system
    docker system prune -f
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
fi

# Enable BuildKit for faster builds
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Create necessary directories
echo -e "${BLUE}📁 Creating data directories...${NC}"
mkdir -p data/postgres data/redis logs storage/articles models
chmod -R 755 data logs storage models

# Build with optimizations
echo -e "${BLUE}🔨 Building Docker image with optimizations...${NC}"

# Set CPU cores for builds
export DOCKER_CLI_EXPERIMENTAL=enabled

# Build command with optimizations
BUILD_CMD="docker build \
    --file $DOCKERFILE \
    --tag $IMAGE_NAME:latest \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --progress=auto \
    $BUILD_ARGS \
    ."

echo -e "${YELLOW}Running: $BUILD_CMD${NC}"

# Execute build
if eval $BUILD_CMD; then
    echo -e "${GREEN}✅ Docker image built successfully${NC}"
else
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

# Validate image
echo -e "${BLUE}🔍 Validating built image...${NC}"
if docker run --rm $IMAGE_NAME:latest python -c "import app; print('✅ App imports successfully')"; then
    echo -e "${GREEN}✅ Image validation passed${NC}"
else
    echo -e "${RED}❌ Image validation failed${NC}"
    exit 1
fi

# Start services
echo -e "${BLUE}🚀 Starting services with compose...${NC}"

COMPOSE_CMD="docker-compose -f $COMPOSE_FILE"

if [ "$PROFILE" = "production" ]; then
    COMPOSE_CMD="$COMPOSE_CMD --profile production"
fi

if $COMPOSE_CMD up -d; then
    echo -e "${GREEN}✅ Services started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start services${NC}"
    exit 1
fi

# Wait for health checks
echo -e "${BLUE}⏳ Waiting for services to be healthy...${NC}"
timeout=120
counter=0

while [ $counter -lt $timeout ]; do
    if docker-compose -f $COMPOSE_FILE ps | grep -q "healthy"; then
        echo -e "${GREEN}✅ Services are healthy${NC}"
        break
    fi
    
    echo -n "."
    sleep 2
    counter=$((counter + 2))
done

if [ $counter -ge $timeout ]; then
    echo -e "${RED}❌ Services health check timeout${NC}"
    echo -e "${YELLOW}📋 Service status:${NC}"
    docker-compose -f $COMPOSE_FILE ps
    exit 1
fi

# Show final status
echo ""
echo -e "${GREEN}🎉 GPW Investor deployment completed successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Services status:${NC}"
docker-compose -f $COMPOSE_FILE ps

echo ""
echo -e "${BLUE}🌐 Application URLs:${NC}"
echo -e "${BLUE}  - Main app: ${YELLOW}http://localhost:5000${NC}"
echo -e "${BLUE}  - Health check: ${YELLOW}http://localhost:5000/api/app/health${NC}"
echo -e "${BLUE}  - Database: ${YELLOW}localhost:5432${NC}"
echo -e "${BLUE}  - Redis: ${YELLOW}localhost:6379${NC}"

if [ "$PROFILE" = "production" ]; then
    echo -e "${BLUE}  - Nginx: ${YELLOW}http://localhost${NC}"
fi

echo ""
echo -e "${YELLOW}💡 Useful commands:${NC}"
echo -e "${YELLOW}  - View logs: ${NC}docker-compose -f $COMPOSE_FILE logs -f"
echo -e "${YELLOW}  - Stop services: ${NC}docker-compose -f $COMPOSE_FILE down"
echo -e "${YELLOW}  - Restart app: ${NC}docker-compose -f $COMPOSE_FILE restart gpw_app"

echo ""
echo -e "${GREEN}✨ Ready to trade! 📈${NC}"
