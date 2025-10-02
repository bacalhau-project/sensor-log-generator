# Sensor Log Generator - Development Commands
# Run 'just' to see all available commands

# Default: show all available commands
default:
    @just --list

# Run quick tests (2 second timeout per test)
test-quick:
    uv run pytest tests/ -v --tb=short --timeout=2 -q

# Run fast tests (subset of tests, ~30 seconds)
test-fast:
    uv run scripts/test-fast.py

# Run all tests with standard timeout
test:
    uv run pytest tests/ -v --tb=short

# Run tests in parallel (faster but may have issues with database locks)
test-parallel:
    uv run pytest tests/ -v --tb=short -n auto

# Run tests serially (slower but avoids database lock issues)
test-serial:
    uv run run_tests_serial.py

# Run specific test file
test-file FILE:
    uv run pytest {{FILE}} -v --tb=short

# Run tests with coverage report
test-coverage:
    uv run pytest tests/ --cov=src --cov-report=term-missing --cov-report=html

# Type check with mypy
type-check:
    uv run mypy --config-file=mypy.ini src/ main.py

# Run ruff linter
lint:
    uv run ruff check .

# Run ruff linter with auto-fix
lint-fix:
    uv run ruff check --fix .

# Format code with ruff
format:
    uv run ruff format .

# Run all checks (lint, type-check, tests)
check-all:
    uv run scripts/check.py

# Run all checks with auto-fix
check-fix:
    uv run scripts/check.py --fix

# Setup development environment and pre-commit hooks
setup-dev:
    uv sync
    uv run scripts/setup.py --dev

# Run the main application
run:
    uv run main.py --config config/config.yaml --identity config/node-identity.json

# Run with custom config
run-custom CONFIG IDENTITY:
    uv run main.py --config {{CONFIG}} --identity {{IDENTITY}}

# Run stress test with default settings
stress-test:
    uv run stress_test.py

# Run production stress test
stress-test-prod:
    ./stress_test_production.sh

# Monitor database (shows live stats)
monitor-db:
    ./monitor_db.sh

# Check database integrity
check-db:
    ./check_db.sh

# Query all log files
query-logs:
    ./query_all_log_files.sh

# Build Docker image
docker-build:
    docker build -t sensor-simulator .

# Run Docker container
docker-run:
    docker run -v $(pwd)/data:/app/data sensor-simulator

# Run Docker container with DELETE mode (for Mac/Windows)
docker-run-delete:
    docker run -v $(pwd)/data:/app/data -e SENSOR_WAL=false sensor-simulator

# Test Docker container
docker-test:
    ./test_container.sh

# Build multi-platform Docker images and push to registry
docker-build-multi:
    uv run build.py --push

# Test build locally without pushing (single platform, faster)
build-test:
    @echo "🔨 Testing local build (linux/amd64 only, no push)..."
    uv run build.py --dev --platforms linux/amd64 --skip-push

# Test build and push to your personal registry (dev mode)
build-dev:
    @echo "🔨 Building and pushing dev image..."
    @echo "ℹ️  This will push to ghcr.io/{{`git config user.name | tr '[:upper:]' '[:lower:]'`}}/sensor-log-generator:dev"
    PUSH_TO_REGISTRY=true uv run build.py --dev --platforms linux/amd64

# Test full multi-platform build locally (no push)
build-test-multi:
    @echo "🔨 Testing full multi-platform build (no push)..."
    @echo "⚠️  This will take several minutes..."
    uv run build.py --platforms linux/amd64,linux/arm64 --skip-push

# Build and push production release (requires version tag)
build-release VERSION:
    @echo "🚀 Building and pushing release v{{VERSION}}..."
    @echo "⚠️  This will create git tags and push to registry"
    @read -p "Continue? (y/N) " confirm && [ "$$confirm" = "y" ] || exit 1
    PUSH_TO_REGISTRY=true uv run build.py --version-tag {{VERSION}}

# Test the build script configuration without building
build-check:
    @echo "🔍 Checking build configuration..."
    @echo ""
    @echo "Git remote:"
    @git remote get-url origin || echo "No git remote configured"
    @echo ""
    @echo "Current version:"
    @git describe --tags --abbrev=0 2>/dev/null || echo "No tags found"
    @echo ""
    @echo "Will build as:"
    @uv run -s build.py --help | head -20
    @echo ""
    @echo "Docker buildx builders:"
    @docker buildx ls || echo "Docker buildx not available"

# Login to GitHub Container Registry for local testing
ghcr-login:
    @echo "🔐 Logging into GitHub Container Registry..."
    @echo "ℹ️  You need a GitHub Personal Access Token with write:packages scope"
    @echo "ℹ️  Create one at: https://github.com/settings/tokens/new"
    @echo ""
    @read -p "Enter your GitHub username: " username && \
    echo "$$GITHUB_TOKEN" | docker login ghcr.io -u "$$username" --password-stdin

# Test docker login status
ghcr-test-login:
    @echo "🔍 Testing GitHub Container Registry access..."
    @docker pull ghcr.io/bacalhau-project/sensor-log-generator:latest 2>&1 | \
        grep -q "denied" && echo "❌ Not logged in or no access" || echo "✅ Access confirmed"

# Simulate full release workflow locally (requires GITHUB_TOKEN)
test-release-local VERSION:
    @echo "🧪 Simulating release workflow for v{{VERSION}}..."
    @echo ""
    @if [ -z "$$GITHUB_TOKEN" ]; then \
        echo "❌ GITHUB_TOKEN not set!"; \
        echo "   Export your PAT: export GITHUB_TOKEN=ghp_xxxxx"; \
        exit 1; \
    fi
    @echo "✓ GITHUB_TOKEN is set"
    @echo ""
    @echo "Step 1: Running tests..."
    uv run pytest tests/ -v --tb=short || exit 1
    @echo ""
    @echo "✓ Tests passed"
    @echo ""
    @echo "Step 2: Logging into GHCR..."
    echo "$$GITHUB_TOKEN" | docker login ghcr.io -u $$(git config user.name) --password-stdin
    @echo ""
    @echo "Step 3: Building and pushing..."
    PUSH_TO_REGISTRY=true uv run build.py --version-tag {{VERSION}}
    @echo ""
    @echo "✅ Local release test complete!"
    @echo ""
    @echo "To trigger actual CI release:"
    @echo "  git tag v{{VERSION}}"
    @echo "  git push origin v{{VERSION}}"

# Clean up generated files and caches
clean:
    rm -rf .pytest_cache
    rm -rf .ruff_cache
    rm -rf .mypy_cache
    rm -rf htmlcov
    rm -rf data/*.db
    rm -rf data/*.log
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Clean everything including virtual environment
clean-all: clean
    rm -rf .venv

# Install/reinstall all dependencies
install:
    uv sync --dev

# Update dependencies
update:
    uv sync --upgrade

# Show current Python and package versions
versions:
    @echo "Python version:"
    @uv run python --version
    @echo ""
    @echo "Key package versions:"
    @uv run pip list | grep -E "pytest|ruff|mypy|pydantic" || true

# Run pre-commit hooks on all files
pre-commit:
    uv run pre-commit run --all-files

# Run pre-commit hooks on staged files only
pre-commit-staged:
    uv run pre-commit run

# Generate identity file template
generate-identity:
    uv run main.py --generate-identity

# Watch tests (requires entr)
watch-tests:
    ls tests/*.py src/*.py | entr -c just test-quick

# Watch for changes and run checks (requires entr)
watch-check:
    ls src/*.py tests/*.py | entr -c just check-quick

# Quick check: lint and type-check only (no tests)
check-quick:
    @echo "🔍 Running quick checks..."
    @echo "Linting..."
    @uv run ruff check .
    @echo "Type checking..."
    @uv run mypy --config-file=mypy.ini src/ main.py
    @echo "✅ Quick checks complete!"

# Run database in read-only mode for debugging
db-read:
    sqlite3 "file:data/sensor_data.db?mode=ro"

# Show database stats
db-stats:
    @echo "SELECT COUNT(*) as total_readings FROM sensor_readings;" | sqlite3 data/sensor_data.db

# Tail application logs
tail-logs:
    tail -f logs/*.log

# Show recent errors from logs
show-errors:
    grep -i error logs/*.log | tail -20

# Run with debug mode
debug:
    SENSOR_DEBUG=true uv run main.py --config config/config.yaml --identity config/node-identity.json

# Profile the application (requires py-spy)
profile:
    py-spy record -o profile.svg -- uv run main.py --config config/config.yaml --identity config/node-identity.json

# Create a new git commit with pre-commit hooks
commit MESSAGE:
    git add -A && git commit -m "{{MESSAGE}}"

# Create a commit bypassing hooks (use sparingly!)
commit-no-verify MESSAGE:
    git add -A && git commit --no-verify -m "{{MESSAGE}}"
