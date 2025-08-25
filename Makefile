.PHONY: help install install-dev setup-hooks lint format typecheck test test-cov clean build run pre-commit ci-local check-all

# Default target
help:
	@echo "Available targets:"
	@echo "  install       - Install production dependencies"
	@echo "  install-dev   - Install all dependencies including dev tools"
	@echo "  setup-hooks   - Setup git pre-commit hooks (IMPORTANT: Run this first!)"
	@echo "  lint          - Run ruff linter"
	@echo "  format        - Format code with ruff"
	@echo "  typecheck     - Run mypy type checker"
	@echo "  test          - Run tests"
	@echo "  test-cov      - Run tests with coverage"
	@echo "  check-all     - Run all checks (lint, typecheck, tests)"
	@echo "  clean         - Clean up generated files"
	@echo "  build         - Build Docker container"
	@echo "  run           - Run the simulator locally"
	@echo "  pre-commit    - Run pre-commit hooks on all files"
	@echo "  ci-local      - Run full CI pipeline locally"

# Install dependencies
install:
	uv sync --frozen

install-dev: setup-hooks
	uv sync --frozen --all-extras
	uv pip install -e .

# Setup git hooks (IMPORTANT - prevents broken commits)
setup-hooks:
	@echo "🔧 Setting up pre-commit hooks..."
	@uv pip install pre-commit
	@uv run pre-commit install --install-hooks
	@uv run pre-commit install --hook-type pre-push
	@echo "✅ Pre-commit hooks installed! Tests will run before each commit."

# Code quality checks
lint:
	uv run ruff check src/ tests/ main.py

format:
	uv run ruff format src/ tests/ main.py
	uv run ruff check --fix src/ tests/ main.py

typecheck:
	uv run mypy src/ main.py --ignore-missing-imports

# Testing
test:
	uv run pytest tests/ -v

test-fast:
	uv run pytest tests/ -m "not slow and not integration" -q --tb=short --disable-warnings

test-cov:
	uv run pytest tests/ -v --cov=src --cov-report=term --cov-report=html

test-integration:
	uv run pytest tests/ -v -m integration

test-unit:
	uv run pytest tests/ -v -m "not integration"

# Run all checks (what pre-commit will do)
check-all: lint typecheck test-fast
	@echo "✅ All checks passed!"

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.db" -delete 2>/dev/null || true
	find . -type f -name "*.db-journal" -delete 2>/dev/null || true
	find . -type f -name "*.db-wal" -delete 2>/dev/null || true
	find . -type f -name "*.db-shm" -delete 2>/dev/null || true
	rm -rf htmlcov/ coverage.xml .coverage* 2>/dev/null || true
	rm -rf dist/ build/ 2>/dev/null || true

# Docker operations
build:
	python build.py --skip-push

build-push:
	python build.py

build-multi:
	python build.py --platforms linux/amd64,linux/arm64 --skip-push

run:
	uv run main.py --config config/config.yaml

run-docker:
	docker run -v $$(pwd)/data:/app/data \
		-v $$(pwd)/logs:/app/logs \
		-e LOG_LEVEL=INFO \
		sensor-simulator:latest

run-docker-monitoring:
	docker run -v $$(pwd)/data:/app/data \
		-v $$(pwd)/logs:/app/logs \
		-e MONITORING_ENABLED=true \
		-e MONITORING_PORT=8080 \
		-p 8080:8080 \
		sensor-simulator:latest

# Pre-commit hooks
pre-commit:
	pre-commit install
	pre-commit run --all-files

pre-commit-update:
	pre-commit autoupdate

# CI/CD pipeline locally
ci-local: clean install-dev lint typecheck test-cov build
	@echo "✅ All CI checks passed!"

# Quick checks before committing
check: format lint typecheck test-unit
	@echo "✅ All checks passed! Ready to commit."

# Database operations
db-clean:
	rm -f data/*.db data/*.db-* 2>/dev/null || true
	rm -f test_*.db test_*.db-* 2>/dev/null || true
	@echo "Database files cleaned"

db-query:
	@if [ -f "data/sensor_data.db" ]; then \
		sqlite3 data/sensor_data.db "SELECT COUNT(*) as total_readings FROM sensor_data;"; \
	else \
		echo "No database found at data/sensor_data.db"; \
	fi

# Development helpers
watch:
	@echo "Watching for changes..."
	@while true; do \
		inotifywait -e modify,create,delete -r src/ tests/ 2>/dev/null && \
		make test-unit; \
	done

debug:
	uv run python -m pdb main.py --config config/config.yaml

# Documentation
docs:
	uv run python src/llm_docs.py > LLM_DOCUMENTATION.md
	@echo "Documentation generated"