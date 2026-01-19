#!/bin/bash
# Setup script for free-threading Python environment

set -e

echo "🔧 Sunwell Free-Threading Setup"
echo "================================="
echo ""

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed"
    echo ""
    echo "Please install uv first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    exit 1
fi

echo "✅ uv found"

# Check for Python 3.14t
if command -v python3.14t &> /dev/null; then
    echo "✅ Python 3.14t found (free-threaded)"
    PYTHON_CMD="python3.14t"
else
    echo "⚠️  Python 3.14t not found"
    echo ""
    echo "Installing Python 3.14t..."
    echo ""
    
    # Try to install via Homebrew on macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            echo "Attempting to install via Homebrew..."
            brew install python@3.14t || {
                echo ""
                echo "❌ Could not install Python 3.14t automatically"
                echo ""
                echo "Please install manually:"
                echo "  1. Build from source: https://github.com/python/cpython"
                echo "  2. Or use pyenv: pyenv install 3.14t"
                echo ""
                echo "Continuing with standard Python (GIL enabled)..."
                PYTHON_CMD="python3"
            }
        else
            echo "⚠️  Homebrew not found. Please install Python 3.14t manually."
            PYTHON_CMD="python3"
        fi
    else
        echo "⚠️  Please install Python 3.14t manually for your platform"
        PYTHON_CMD="python3"
    fi
fi

echo ""
echo "📦 Creating virtual environment..."

if [ "$PYTHON_CMD" = "python3.14t" ]; then
    uv venv --python python3.14t .venv
    echo "✅ Created venv with Python 3.14t (free-threaded)"
else
    uv venv .venv
    echo "⚠️  Created venv with standard Python (GIL enabled)"
fi

echo ""
echo "📥 Installing dependencies..."
uv pip install -e ".[dev]"

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the environment:"
echo "  source .venv/bin/activate"
echo ""
echo "To verify free-threading:"
echo "  python -c \"import sys; print('Free-threaded:', hasattr(sys, '_is_gil_enabled'))\""
echo ""
