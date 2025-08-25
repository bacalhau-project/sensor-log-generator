#!/bin/bash
#
# Setup pre-commit hooks for the project
#

set -e

echo "🔧 Setting up pre-commit hooks..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install pre-commit if not already installed
echo "📦 Installing pre-commit..."
uv pip install pre-commit

# Install the git hooks
echo "🪝 Installing git hooks..."
uv run pre-commit install --install-hooks

# Install hooks for different stages
uv run pre-commit install --hook-type pre-push

echo "✅ Pre-commit hooks installed successfully!"
echo ""
echo "📋 Available commands:"
echo "   • Run on all files:     pre-commit run --all-files"
echo "   • Run on staged files:  pre-commit run"
echo "   • Update hooks:         pre-commit autoupdate"
echo "   • Skip hooks (emergency): git commit --no-verify"
echo ""
echo "⚡ Quick checks before commit:"
echo "   • Syntax and linting (fast)"
echo "   • Type checking"
echo "   • Fast unit tests"
echo ""
echo "🚀 Full checks before push:"
echo "   • Security scanning"
echo "   • Full test suite with coverage"
echo ""
echo "💡 Tip: To temporarily disable hooks, use: git commit --no-verify"
echo "        But please fix issues before pushing!"