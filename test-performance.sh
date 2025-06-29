#!/bin/bash
# GPW Investor - Performance Testing Script

set -e

echo "🎯 GPW Investor - Performance Testing"
echo "====================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
APP_URL="http://localhost:5000"
DB_CONTAINER="gpw_postgres"
APP_CONTAINER="gpw_app"
REDIS_CONTAINER="gpw_redis"

# Test configuration
CONCURRENT_REQUESTS=10
TEST_DURATION=30
ENDPOINTS=(
    "/api/app/health"
    "/api/app/stats"
    "/"
    "/quotes"
    "/recommendations"
)

echo -e "${BLUE}📊 Performance Testing Configuration:${NC}"
echo -e "${BLUE}  - App URL: ${YELLOW}$APP_URL${NC}"
echo -e "${BLUE}  - Concurrent requests: ${YELLOW}$CONCURRENT_REQUESTS${NC}"
echo -e "${BLUE}  - Test duration: ${YELLOW}${TEST_DURATION}s${NC}"
echo -e "${BLUE}  - Endpoints: ${YELLOW}${#ENDPOINTS[@]}${NC}"
echo ""

# Check if containers are running
echo -e "${BLUE}🔍 Checking container status...${NC}"
for container in $DB_CONTAINER $APP_CONTAINER $REDIS_CONTAINER; do
    if docker ps | grep -q $container; then
        echo -e "${GREEN}✅ $container is running${NC}"
    else
        echo -e "${RED}❌ $container is not running${NC}"
        exit 1
    fi
done

# Wait for application to be ready
echo -e "${BLUE}⏳ Waiting for application to be ready...${NC}"
timeout=60
counter=0

while [ $counter -lt $timeout ]; do
    if curl -s -f "$APP_URL/api/app/health" > /dev/null; then
        echo -e "${GREEN}✅ Application is ready${NC}"
        break
    fi
    
    echo -n "."
    sleep 2
    counter=$((counter + 2))
done

if [ $counter -ge $timeout ]; then
    echo -e "${RED}❌ Application readiness timeout${NC}"
    exit 1
fi

echo ""

# Database performance test
echo -e "${BLUE}🗄️ Database Performance Test${NC}"
echo "=============================="

echo -e "${YELLOW}📊 Testing database connection and basic queries...${NC}"

DB_STATS=$(docker exec $DB_CONTAINER psql -U gpw_user -d gpw_investor -t -c "
SELECT 
    COUNT(*) as total_tables,
    (SELECT COUNT(*) FROM companies) as companies_count,
    (SELECT COUNT(*) FROM quotes_daily) as quotes_count,
    (SELECT COUNT(*) FROM recommendations) as recommendations_count;
")

echo -e "${GREEN}Database stats:${NC}"
echo "$DB_STATS"

# Test query performance
echo -e "${YELLOW}⚡ Testing query performance...${NC}"

QUERY_TIME=$(docker exec $DB_CONTAINER psql -U gpw_user -d gpw_investor -t -c "
\\timing on
SELECT c.ticker, q.close_price, q.date 
FROM companies c 
JOIN quotes_daily q ON c.id = q.company_id 
WHERE q.date >= CURRENT_DATE - INTERVAL '30 days' 
ORDER BY q.date DESC 
LIMIT 100;
" 2>&1 | grep "Time:" | head -1)

echo -e "${GREEN}Sample query time: $QUERY_TIME${NC}"

# Index usage check
echo -e "${YELLOW}🔍 Checking index usage...${NC}"

INDEX_COUNT=$(docker exec $DB_CONTAINER psql -U gpw_user -d gpw_investor -t -c "
SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public';
")

echo -e "${GREEN}Total indexes: $INDEX_COUNT${NC}"

echo ""

# Application performance test
echo -e "${BLUE}🌐 Application Performance Test${NC}"
echo "==============================="

# Test each endpoint
for endpoint in "${ENDPOINTS[@]}"; do
    echo -e "${YELLOW}🎯 Testing endpoint: $endpoint${NC}"
    
    # Single request test
    RESPONSE_TIME=$(curl -s -w "%{time_total}" -o /dev/null "$APP_URL$endpoint")
    HTTP_CODE=$(curl -s -w "%{http_code}" -o /dev/null "$APP_URL$endpoint")
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}  ✅ HTTP $HTTP_CODE - Response time: ${RESPONSE_TIME}s${NC}"
    else
        echo -e "${RED}  ❌ HTTP $HTTP_CODE - Failed${NC}"
        continue
    fi
    
    # Load test with Apache Bench (if available)
    if command -v ab > /dev/null; then
        echo -e "${YELLOW}  🔥 Load testing (${CONCURRENT_REQUESTS} concurrent, ${TEST_DURATION}s)...${NC}"
        
        AB_RESULT=$(ab -n $((CONCURRENT_REQUESTS * 10)) -c $CONCURRENT_REQUESTS -t $TEST_DURATION -q "$APP_URL$endpoint" 2>/dev/null | grep -E "(Requests per second|Time per request|Transfer rate)")
        
        echo -e "${GREEN}  📊 Load test results:${NC}"
        echo "$AB_RESULT" | while read line; do
            echo -e "${GREEN}    $line${NC}"
        done
    else
        echo -e "${YELLOW}  ⚠️ Apache Bench not available, skipping load test${NC}"
    fi
    
    echo ""
done

# Memory and CPU usage
echo -e "${BLUE}💾 Resource Usage${NC}"
echo "================="

echo -e "${YELLOW}📊 Container resource usage:${NC}"

docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" $DB_CONTAINER $APP_CONTAINER $REDIS_CONTAINER

echo ""

# Database connection stats
echo -e "${BLUE}🔗 Database Connections${NC}"
echo "======================"

DB_CONNECTIONS=$(docker exec $DB_CONTAINER psql -U gpw_user -d gpw_investor -t -c "
SELECT 
    COUNT(*) as active_connections,
    MAX(EXTRACT(EPOCH FROM (now() - query_start))) as longest_query_seconds
FROM pg_stat_activity 
WHERE state = 'active';
")

echo -e "${GREEN}Database connections:${NC}"
echo "$DB_CONNECTIONS"

# Redis performance
echo -e "${BLUE}🔴 Redis Performance${NC}"
echo "==================="

if docker exec $REDIS_CONTAINER redis-cli ping > /dev/null 2>&1; then
    REDIS_INFO=$(docker exec $REDIS_CONTAINER redis-cli info memory | grep -E "(used_memory_human|used_memory_peak_human|maxmemory_human)")
    echo -e "${GREEN}Redis memory usage:${NC}"
    echo "$REDIS_INFO"
    
    # Redis performance test
    REDIS_PERF=$(docker exec $REDIS_CONTAINER redis-cli --latency-history -i 1 ping | head -5)
    echo -e "${GREEN}Redis latency test:${NC}"
    echo "$REDIS_PERF"
else
    echo -e "${RED}❌ Redis is not responding${NC}"
fi

echo ""

# Application logs check
echo -e "${BLUE}📋 Recent Application Logs${NC}"
echo "=========================="

echo -e "${YELLOW}🔍 Checking for errors in logs (last 50 lines):${NC}"

ERROR_COUNT=$(docker logs $APP_CONTAINER --tail 50 2>&1 | grep -i error | wc -l)
WARNING_COUNT=$(docker logs $APP_CONTAINER --tail 50 2>&1 | grep -i warning | wc -l)

echo -e "${GREEN}Error count: $ERROR_COUNT${NC}"
echo -e "${GREEN}Warning count: $WARNING_COUNT${NC}"

if [ $ERROR_COUNT -gt 0 ]; then
    echo -e "${RED}⚠️ Recent errors found:${NC}"
    docker logs $APP_CONTAINER --tail 50 2>&1 | grep -i error | tail -3
fi

echo ""

# Summary
echo -e "${GREEN}🎉 Performance Test Completed!${NC}"
echo "=============================="

echo -e "${BLUE}📊 Quick Summary:${NC}"
echo -e "${BLUE}  - Database indexes: ${YELLOW}$INDEX_COUNT${NC}"
echo -e "${BLUE}  - Application errors: ${YELLOW}$ERROR_COUNT${NC}"
echo -e "${BLUE}  - Application warnings: ${YELLOW}$WARNING_COUNT${NC}"

if [ $ERROR_COUNT -eq 0 ] && [ $WARNING_COUNT -le 5 ]; then
    echo -e "${GREEN}✅ Overall health: GOOD${NC}"
else
    echo -e "${YELLOW}⚠️ Overall health: NEEDS ATTENTION${NC}"
fi

echo ""
echo -e "${YELLOW}💡 Recommendations:${NC}"

if [ $ERROR_COUNT -gt 0 ]; then
    echo -e "${YELLOW}  - Review application logs for errors${NC}"
fi

if [ "$INDEX_COUNT" -lt 20 ]; then
    echo -e "${YELLOW}  - Consider using database-schema.sql with optimized indexes${NC}"
fi

echo -e "${YELLOW}  - Monitor resource usage during peak hours${NC}"
echo -e "${YELLOW}  - Set up proper monitoring (Prometheus/Grafana)${NC}"
echo -e "${YELLOW}  - Consider using Redis for caching if not already implemented${NC}"

echo ""
echo -e "${GREEN}📈 For detailed monitoring, visit: ${YELLOW}$APP_URL/api/app/stats${NC}"
