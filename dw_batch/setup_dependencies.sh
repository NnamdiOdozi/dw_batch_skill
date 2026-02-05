#!/bin/bash
# Setup script for dw_batch_request skill dependencies
# Run this once after cloning the project to avoid dependency issues

echo "Setting up dw_batch_request dependencies..."

# Check if virtual environment exists
if [ ! -d "../../.venv" ]; then
    echo "Error: Virtual environment not found at ../../.venv"
    echo "Please create a virtual environment first: python -m venv .venv"
    exit 1
fi

# Activate virtual environment
source ../../.venv/bin/activate

# Install required packages
echo "Installing Python packages..."
pip install -q python-docx python-pptx odfpy pypdf pdfplumber openai python-dotenv pandas xlrd pdf2image Pillow

# Check for system dependency (poppler)
echo "Checking for poppler-utils (required for pdf2image)..."
if ! command -v pdftoppm &> /dev/null; then
    echo "⚠ WARNING: poppler-utils not found"
    echo "  For scanned PDF support, install poppler-utils:"
    echo "    Ubuntu/Debian: apt-get install poppler-utils"
    echo "    macOS: brew install poppler"
fi

echo "✓ Dependencies installed successfully!"
echo ""
echo "Next steps:"
echo "1. Copy .env.sample to .env and add your DOUBLEWORD_AUTH_TOKEN"
echo "2. Edit prompt.txt with your task instructions"
echo "3. Run: python create_batch.py --input-dir /path/to/your/files/"
echo "4. Run: python submit_batch.py"
echo "5. Run: python poll_and_process.py"
