#!/bin/bash
#
# check-infra.sh - Verify IterateSwarm infrastructure is healthy
#
# Checks:
# 1. Temporal UI (localhost:8080)
# 2. Temporal gRPC (localhost:7233)
# 3. Redpanda (localhost:9644)
# 4. PostgreSQL (localhost:5432)
# 5. Qdrant (localhost:6333)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "IterateSwarm Infrastructure Health Check"
echo "=============================================="
echo ""

PASSED=0
FAILED=0

# Helper function
check_service() {
    local name=$1
    local url=$2
    local check_type=$3
    local payload=$4

    echo -n "Checking $name... "

    if [ "$check_type" == "curl" ]; then
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ HEALTHY${NC}"
            ((PASSED++))
        else
            echo -e "${RED}✗ UNHEALTHY${NC}"
            echo "  URL: $url"
            ((FAILED++))
        fi
    elif [ "$check_type" == "rpk" ]; then
        if docker exec iterateswarm-redpanda rpk cluster info > /dev/null 2>&1; then
            echo -e "${GREEN}✓ HEALTHY${NC}"
            ((PASSED++))
        else
            echo -e "${RED}✗ UNHEALTHY${NC}"
            ((FAILED++))
        fi
    elif [ "$check_type" == "postgres" ]; then
        if PGPASSWORD=${POSTGRES_PASSWORD:-iterateswarm} psql -h localhost -U ${POSTGRES_USER:-iterateswarm} -d ${POSTGRES_DB:-iterateswarm} -c "SELECT 1" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ HEALTHY${NC}"
            ((PASSED++))
        else
            echo -e "${RED}✗ UNHEALTHY${NC}"
            ((FAILED++))
        fi
    fi
}

# Check 1: Temporal UI
check_service "Temporal UI" "http://localhost:8080/api/health" "curl"

# Check 2: Temporal gRPC (via admin-tools)
echo -n "Checking Temporal gRPC (7233)... "
if docker exec iterateswarm-temporal-admin nc -z temporal 7233 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ HEALTHY${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ UNHEALTHY${NC}"
    ((FAILED++))
fi

# Check 3: Redpanda
check_service "Redpanda" "http://localhost:9644/v1/status/ready" "curl"

# Check 4: Redpanda Cluster Info
check_service "Redpanda Cluster" "" "rpk"

# Check 5: PostgreSQL
check_service "PostgreSQL" "" "postgres"

# Check 6: Qdrant
check_service "Qdrant" "http://localhost:6333/collections" "curl"

# Check 7: Elasticsearch
echo -n "Checking Elasticsearch... "
if curl -sf "http://localhost:9200/_cluster/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ HEALTHY${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ UNHEALTHY${NC}"
    ((FAILED++))
fi

echo ""
echo "=============================================="
echo "Summary: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo "=============================================="

if [ $FAILED -gt 0 ]; then
    echo -e "${YELLOW}Some services are unhealthy. Check docker-compose logs.${NC}"
    echo ""
    echo "Useful commands:"
    echo "  docker-compose ps              # Show container status"
    echo "  docker-compose logs <service>  # Check specific service logs"
    echo "  docker-compose down && docker-compose up -d  # Restart all"
    exit 1
fi

echo -e "${GREEN}All infrastructure services are healthy!${NC}"
exit 0
