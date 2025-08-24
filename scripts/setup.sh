#!/bin/bash

# Setup script for sensor-log-generator development environment

set -e

echo "🚀 Setting up sensor-log-generator development environment..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

echo "✅ Python version: $PYTHON_VERSION"

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
else
    echo "✅ uv is already installed"
fi

# Create necessary directories
echo "📁 Creating project directories..."
mkdir -p data logs config

# Install dependencies
echo "📦 Installing dependencies..."
uv sync --frozen

# Install development dependencies
echo "📦 Installing development dependencies..."
uv sync --frozen --all-extras

# Install pre-commit hooks
echo "🔧 Installing pre-commit hooks..."
uv run pre-commit install

# Create default config if it doesn't exist
if [ ! -f "config/config.yaml" ]; then
    echo "📝 Creating default configuration..."
    cp config.example.yaml config/config.yaml
fi

# Run initial checks
echo "🔍 Running initial checks..."
uv run ruff check src/ tests/ main.py --fix
uv run ruff format src/ tests/ main.py

echo "✅ Running tests..."
uv run pytest tests/ -v -x

# Build Docker image
if command -v docker &> /dev/null; then
    echo "🐳 Building Docker image..."
    docker build -t sensor-simulator:dev .
    echo "✅ Docker image built: sensor-simulator:dev"
else
    echo "⚠️  Docker not found, skipping container build"
fi

echo ""
echo "✨ Setup complete! You're ready to start developing."
echo ""
echo "Quick commands:"
echo "  make test       - Run tests"
echo "  make lint       - Run linter"
echo "  make format     - Format code"
echo "  make run        - Run the simulator"
echo "  make ci-local   - Run full CI pipeline locally"
echo ""
echo "To run the simulator:"
echo "  uv run main.py --config config/config.yaml"
echo ""
echo "To run with Docker:"
echo "  docker run -v \$(pwd)/data:/app/data sensor-simulator:dev"