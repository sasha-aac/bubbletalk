#!/bin/bash
# BubbleTalk Setup Script

echo "🗨️  BubbleTalk Setup"
echo "===================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION found"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Linux: Setup v4l2loopback
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo ""
    echo "Linux detected - checking for v4l2loopback..."
    
    if ! lsmod | grep -q "v4l2loopback"; then
        echo "⚠️  v4l2loopback kernel module not loaded"
        echo "To set up virtual camera on Linux, run:"
        echo "  sudo apt install v4l2-loopback-dkms"
        echo "  sudo modprobe v4l2loopback"
    else
        echo "✓ v4l2loopback module is loaded"
    fi
fi

echo ""
echo "✓ Setup complete!"
echo ""
echo "To run BubbleTalk:"
echo "  source venv/bin/activate"
echo "  python3 main.py"
echo ""
