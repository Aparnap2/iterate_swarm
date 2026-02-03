# IterateSwarm Makefile
# Quick commands for development and operations

.PHONY: help up down status test build clean proto verify deps logs

# Default target
help:
	@echo "IterateSwarm - Polyglot AI ChatOps Platform"
	@echo ""
	@echo "Commands:"
	@echo "  up          Start all services (Docker + apps)"
	@echo "  down        Stop all Docker services"
	@echo "  status      Check service status"
	@echo "  test        Run all tests (Go + Python)"
	@echo "  build       Build all applications"
	@echo "  clean       Clean build artifacts"
	@echo "  proto       Generate protobuf code"
	@echo "  verify      Run E2E verification script"
	@echo "  deps        Install dependencies"
	@echo "  logs        Tail logs from all services"

# Start all infrastructure and applications
up:
	@echo "Starting IterateSwarm..."
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	sleep 10
	@echo "Infrastructure started"

# Stop all Docker services
down:
	@echo "Stopping all services..."
	docker-compose down
	@echo "All services stopped"

# Check service status
status:
	@echo "Service Status:"
	docker-compose ps

# Run all tests
test:
	@echo "Running tests..."
	@echo "Go tests:"
	cd apps/core && go test ./...
	@echo "Python tests:"
	cd apps/ai && uv run pytest tests/ -v

# Build all applications
build:
	@echo "Building applications..."
	cd apps/core && go build -o bin/server ./cmd/server && go build -o bin/worker ./cmd/worker

# Clean build artifacts
clean:
	@echo "Cleaning..."
	cd apps/core && rm -rf bin/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Generate protobuf code
proto:
	@echo "Generating protobuf code..."
	docker run --rm -v $$(pwd):/workspace -w /workspace bufbuild/buf:latest generate
	@echo "Protobuf code generated"

# Run E2E verification
verify:
	@echo "Running E2E verification..."
	./scripts/verify_system.sh

# Install dependencies
deps:
	@echo "Installing dependencies..."
	cd apps/core && go mod download
	cd apps/ai && uv sync

# Tail logs from all services
logs:
	@echo "Showing logs (Ctrl+C to exit)..."
	docker-compose logs -f

# Full restart
restart: down up
	@echo "Full restart complete"
