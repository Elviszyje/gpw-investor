#!/bin/bash

# GPW Investor - Docker Management Scripts

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_green() {
    echo -e "${GREEN}$1${NC}"
}

print_yellow() {
    echo -e "${YELLOW}$1${NC}"
}

print_red() {
    echo -e "${RED}$1${NC}"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_red "❌ Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Build the application
build() {
    print_yellow "🔨 Building GPW Investor application..."
    docker-compose build gpw_app
    print_green "✅ Build completed successfully!"
}

# Start services
start() {
    print_yellow "🚀 Starting GPW Investor services..."
    docker-compose up -d
    print_green "✅ Services started successfully!"
    print_yellow "📊 Application will be available at: http://localhost:5001"
    print_yellow "🗄️ PostgreSQL available at: localhost:5432"
}

# Stop services
stop() {
    print_yellow "⏹️ Stopping GPW Investor services..."
    docker-compose down
    print_green "✅ Services stopped successfully!"
}

# Restart services
restart() {
    print_yellow "🔄 Restarting GPW Investor services..."
    docker-compose down
    docker-compose up -d
    print_green "✅ Services restarted successfully!"
}

# Show logs
logs() {
    if [ -z "$1" ]; then
        print_yellow "📋 Showing logs for all services..."
        docker-compose logs -f
    else
        print_yellow "📋 Showing logs for service: $1"
        docker-compose logs -f "$1"
    fi
}

# Show status
status() {
    print_yellow "📊 Checking services status..."
    docker-compose ps
    
    print_yellow "\n🔍 Health checks:"
    
    # Check app health
    if curl -f -s http://localhost:5001/api/app/health > /dev/null 2>&1; then
        print_green "✅ GPW App is healthy"
    else
        print_red "❌ GPW App is not responding"
    fi
    
    # Check database
    if docker-compose exec postgres pg_isready -U gpw_user -d gpw_investor > /dev/null 2>&1; then
        print_green "✅ PostgreSQL is healthy"
    else
        print_red "❌ PostgreSQL is not responding"
    fi
}

# Clean up
cleanup() {
    print_yellow "🧹 Cleaning up Docker resources..."
    docker-compose down -v
    docker system prune -f
    print_green "✅ Cleanup completed!"
}

# Database shell
db_shell() {
    print_yellow "🗄️ Opening PostgreSQL shell..."
    docker-compose exec postgres psql -U gpw_user -d gpw_investor
}

# Application shell
app_shell() {
    print_yellow "🐍 Opening application shell..."
    docker-compose exec gpw_app bash
}

# Show help
help() {
    echo "GPW Investor - Docker Management"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  build     - Build the application image"
    echo "  start     - Start all services"
    echo "  stop      - Stop all services"
    echo "  restart   - Restart all services"
    echo "  logs      - Show logs (optional: service name)"
    echo "  status    - Show services status and health"
    echo "  cleanup   - Stop services and clean up"
    echo "  db-shell  - Open PostgreSQL shell"
    echo "  app-shell - Open application shell"
    echo "  help      - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 logs gpw_app"
    echo "  $0 status"
}

# Main script
main() {
    check_docker
    
    case "${1:-help}" in
        build)
            build
            ;;
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        logs)
            logs "$2"
            ;;
        status)
            status
            ;;
        cleanup)
            cleanup
            ;;
        db-shell)
            db_shell
            ;;
        app-shell)
            app_shell
            ;;
        help|*)
            help
            ;;
    esac
}

main "$@"
