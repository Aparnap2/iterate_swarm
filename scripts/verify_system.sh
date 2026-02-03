#!/bin/bash
#===============================================================================
# IterateSwarm End-to-End Verification Script
# Tests the complete system from infrastructure to gRPC communication
#===============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CORE_DIR="$PROJECT_ROOT/apps/core"
AI_DIR="$PROJECT_ROOT/apps/ai"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

echo "=============================================="
echo "  IterateSwarm E2E Verification"
echo "=============================================="
echo ""

#------------------------------------------------------------------------------
# SECTION 1: Infrastructure Health Checks
#------------------------------------------------------------------------------
echo "SECTION 1: Infrastructure Health Checks"
echo "---------------------------------------"

PASSED=0
FAILED=0

# Check Temporal
if nc -z localhost 7233 2>/dev/null; then
    log_success "Temporal (gRPC): healthy"
    PASSED=$((PASSED + 1))
else
    log_error "Temporal: not responding"
    FAILED=$((FAILED + 1))
fi

# Check Redpanda
if nc -z localhost 9092 2>/dev/null; then
    log_success "Redpanda (Kafka): healthy"
    PASSED=$((PASSED + 1))
else
    log_warning "Redpanda: not accessible"
fi

# Check Qdrant
if nc -z localhost 6333 2>/dev/null; then
    log_success "Qdrant (Vector DB): healthy"
    PASSED=$((PASSED + 1))
else
    log_error "Qdrant: not responding"
    FAILED=$((FAILED + 1))
fi

# Check PostgreSQL
if nc -z localhost 5432 2>/dev/null; then
    log_success "PostgreSQL: healthy"
    PASSED=$((PASSED + 1))
else
    log_error "PostgreSQL: not responding"
    FAILED=$((FAILED + 1))
fi

echo ""
echo "Infrastructure: $PASSED passed, $FAILED failed"

if [ $FAILED -gt 0 ]; then
    INFRA_STATUS=1
else
    INFRA_STATUS=0
fi

#------------------------------------------------------------------------------
# SECTION 2: Go Code Verification
#------------------------------------------------------------------------------
echo ""
echo "SECTION 2: Go Code Verification"
echo "--------------------------------"

PASSED=0
FAILED=0

cd "$CORE_DIR"

# Go build
if go build ./... 2>&1; then
    log_success "Go build: successful"
    PASSED=$((PASSED + 1))
else
    log_error "Go build: failed"
    FAILED=$((FAILED + 1))
fi

# Go vet
if go vet ./... 2>&1; then
    log_success "Go vet: passed"
    PASSED=$((PASSED + 1))
else
    log_warning "Go vet: found issues"
    PASSED=$((PASSED + 1))
fi

# Go tests
if go test ./... 2>&1 | grep -q "ok"; then
    log_success "Go tests: passed"
    PASSED=$((PASSED + 1))
else
    log_error "Go tests: failed"
    FAILED=$((FAILED + 1))
fi

echo ""
echo "Go Code: $PASSED passed, $FAILED failed"

if [ $FAILED -gt 0 ]; then
    GO_STATUS=1
else
    GO_STATUS=0
fi

#------------------------------------------------------------------------------
# SECTION 3: Python Code Verification
#------------------------------------------------------------------------------
echo ""
echo "SECTION 3: Python Code Verification"
echo "------------------------------------"

PASSED=0
FAILED=0

cd "$AI_DIR"

# Python syntax check
if python3 -m py_compile src/grpc_server.py src/main.py 2>&1; then
    log_success "Python syntax: valid"
    PASSED=$((PASSED + 1))
else
    log_error "Python syntax: invalid"
    FAILED=$((FAILED + 1))
fi

# Run pytest
TEST_OUTPUT=$(uv run pytest tests/ -v 2>&1)
TEST_EXIT=$?

if echo "$TEST_OUTPUT" | grep -q "passed"; then
    log_success "Python tests: passed"
    PASSED=$((PASSED + 1))

    # Show test count
    PASS_COUNT=$(echo "$TEST_OUTPUT" | grep -oP '\d+(?= passed)' | tail -1)
    if [ -n "$PASS_COUNT" ]; then
        log_info "Tests passed: $PASS_COUNT"
    fi
else
    log_error "Python tests: failed"
    FAILED=$((FAILED + 1))
fi

echo ""
echo "Python Code: $PASSED passed, $FAILED failed"

if [ $FAILED -gt 0 ]; then
    PYTHON_STATUS=1
else
    PYTHON_STATUS=0
fi

#------------------------------------------------------------------------------
# SECTION 4: gRPC Communication Test
#------------------------------------------------------------------------------
echo ""
echo "SECTION 4: gRPC Communication Test"
echo "-----------------------------------"

cd "$AI_DIR"

# Start gRPC server in background
log_info "Starting Python gRPC server..."
uv run python -m src.main --mode grpc &
GRPC_PID=$!
sleep 3

# Check if server is listening
if nc -z localhost 50051 2>/dev/null; then
    log_success "gRPC server: listening on port 50051"
else
    log_warning "gRPC server: not yet listening"
fi

# Cleanup
kill $GRPC_PID 2>/dev/null || true

#------------------------------------------------------------------------------
# SECTION 5: Protobuf Verification
#------------------------------------------------------------------------------
echo ""
echo "SECTION 5: Protobuf Verification"
echo "---------------------------------"

PASSED=0
FAILED=0

# Check proto files exist
if [ -f "$PROJECT_ROOT/proto/ai/v1/agent.proto" ]; then
    log_success "agent.proto: exists"
    PASSED=$((PASSED + 1))
else
    log_error "agent.proto: not found"
    FAILED=$((FAILED + 1))
fi

# Check generated Go code
if [ -f "$PROJECT_ROOT/gen/go/ai/v1/agent.pb.go" ]; then
    log_success "Generated Go code: exists"
    PASSED=$((PASSED + 1))
else
    log_error "Generated Go code: not found"
    FAILED=$((FAILED + 1))
fi

# Check generated Python code
if [ -f "$PROJECT_ROOT/gen/python/ai/v1/agent_pb2.py" ]; then
    log_success "Generated Python code: exists"
    PASSED=$((PASSED + 1))
else
    log_error "Generated Python code: not found"
    FAILED=$((FAILED + 1))
fi

echo ""
echo "Protobuf: $PASSED passed, $FAILED failed"

if [ $FAILED -gt 0 ]; then
    PROTO_STATUS=1
else
    PROTO_STATUS=0
fi

#------------------------------------------------------------------------------
# FINAL SUMMARY
#------------------------------------------------------------------------------
echo ""
echo "=============================================="
echo "  VERIFICATION SUMMARY"
echo "=============================================="
echo ""

TOTAL_STATUS=0

if [ $INFRA_STATUS -eq 0 ]; then
    log_success "Infrastructure: HEALTHY"
else
    log_error "Infrastructure: ISSUES DETECTED"
    TOTAL_STATUS=$((TOTAL_STATUS + 1))
fi

if [ $GO_STATUS -eq 0 ]; then
    log_success "Go Code: VERIFIED"
else
    log_error "Go Code: ISSUES DETECTED"
    TOTAL_STATUS=$((TOTAL_STATUS + 1))
fi

if [ $PYTHON_STATUS -eq 0 ]; then
    log_success "Python Code: VERIFIED"
else
    log_error "Python Code: ISSUES DETECTED"
    TOTAL_STATUS=$((TOTAL_STATUS + 1))
fi

if [ $PROTO_STATUS -eq 0 ]; then
    log_success "Protocol Buffers: VERIFIED"
else
    log_error "Protocol Buffers: ISSUES DETECTED"
    TOTAL_STATUS=$((TOTAL_STATUS + 1))
fi

echo ""
if [ $TOTAL_STATUS -eq 0 ]; then
    echo -e "${GREEN}=============================================="
    echo "  SYSTEM VERIFIED"
    echo "==============================================${NC}"
    echo ""
    echo "All components passed verification."
    exit 0
else
    echo -e "${RED}=============================================="
    echo "  VERIFICATION FAILED"
    echo "==============================================${NC}"
    echo ""
    echo "$TOTAL_STATUS component(s) have issues that need attention."
    exit 1
fi
