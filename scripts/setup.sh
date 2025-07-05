#!/bin/bash

# Document Search Application Setup Script

set -e  # Exit on any error

echo "=== Document Search Application Setup ==="
echo

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "Error: Conda is not installed. Please install conda first."
    echo "Visit: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Environment name
ENV_NAME="document-search"

echo "1. Creating conda environment: $ENV_NAME"
if conda env list | grep -q "^$ENV_NAME "; then
    echo "   Environment $ENV_NAME already exists. Removing it..."
    conda env remove -n $ENV_NAME -y
fi

# Create environment from file
if [ -f "environment.yml" ]; then
    echo "   Creating environment from environment.yml..."
    conda env create -f environment.yml
else
    echo "   Creating environment with Python 3.9..."
    conda create -n $ENV_NAME python=3.9 -y
fi

echo "2. Activating environment..."
eval "$(conda shell.bash hook)"
conda activate $ENV_NAME

echo "3. Installing Python dependencies..."
pip install -r requirements.txt

echo "4. Setting up configuration..."
if [ ! -f "config/config.yml" ]; then
    echo "   Copying example configuration..."
    cp config/config.example.yml config/config.yml
    echo "   ⚠️  Please edit config/config.yml with your settings!"
fi

echo "5. Creating necessary directories..."
mkdir -p logs
mkdir -p data
mkdir -p temp

echo "6. Checking system dependencies..."

# Check Tesseract
if ! command -v tesseract &> /dev/null; then
    echo "   ⚠️  Tesseract OCR not found. Install with:"
    echo "      Ubuntu/Debian: sudo apt-get install tesseract-ocr"
    echo "      macOS: brew install tesseract"
    echo "      RHEL/CentOS: sudo yum install tesseract"
fi

# Check Poppler
if ! command -v pdfinfo &> /dev/null; then
    echo "   ⚠️  Poppler utilities not found. Install with:"
    echo "      Ubuntu/Debian: sudo apt-get install poppler-utils"
    echo "      macOS: brew install poppler"
    echo "      RHEL/CentOS: sudo yum install poppler-utils"
fi

echo "7. Verifying Elasticsearch connection..."
if curl -s http://localhost:9200 > /dev/null; then
    echo "   ✓ Elasticsearch is running"
else
    echo "   ⚠️  Elasticsearch not found at localhost:9200"
    echo "      To start with Docker:"
    echo "      docker run -d -p 9200:9200 -e \"discovery.type=single-node\" -e \"xpack.security.enabled=false\" docker.elastic.co/elasticsearch/elasticsearch:8.11.0"
fi

echo
echo "=== Setup Complete! ==="
echo
echo "Next steps:"
echo "1. Edit config/config.yml with your settings:"
echo "   - Google Cloud Storage bucket name and project ID"
echo "   - Set GOOGLE_APPLICATION_CREDENTIALS environment variable"
echo "   - Elasticsearch connection details if different"
echo
echo "2. Start Elasticsearch if not already running:"
echo "   docker-compose up elasticsearch -d"
echo
echo "3. Run the application:"
echo "   conda activate $ENV_NAME"
echo "   python -m uvicorn app.main:app --reload"
echo
echo "4. Access the API documentation:"
echo "   http://localhost:8000/docs"
echo
echo "5. Test the health endpoint:"
echo "   curl http://localhost:8000/api/v1/health"
echo
