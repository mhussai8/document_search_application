#!/bin/bash

# Start the Document Search Application with Docker

set -e

echo "=== Starting Document Search Application ==="
echo

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed."
    exit 1
fi

# Check if Google Cloud credentials are set
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "Error: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set."
    echo "Please set it to the path of your service account JSON file."
    exit 1
fi

if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "Error: Google Cloud credentials file not found: $GOOGLE_APPLICATION_CREDENTIALS"
    exit 1
fi

echo "1. Building application image..."
docker-compose build document-search-app

echo "2. Starting Elasticsearch..."
docker-compose up -d elasticsearch

echo "3. Waiting for Elasticsearch to be ready..."
timeout=60
counter=0
until curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green\|yellow"'; do
    if [ $counter -ge $timeout ]; then
        echo "Error: Elasticsearch failed to start within $timeout seconds"
        exit 1
    fi
    echo "   Waiting for Elasticsearch... ($counter/$timeout)"
    sleep 2
    counter=$((counter + 2))
done

echo "4. Starting Document Search application..."
docker-compose up -d document-search-app

echo "5. Waiting for application to be ready..."
timeout=30
counter=0
until curl -s http://localhost:8000/api/v1/health > /dev/null; do
    if [ $counter -ge $timeout ]; then
        echo "Error: Application failed to start within $timeout seconds"
        echo "Check logs with: docker-compose logs document-search-app"
        exit 1
    fi
    echo "   Waiting for application... ($counter/$timeout)"
    sleep 2
    counter=$((counter + 2))
done

echo
echo "=== Application Started Successfully! ==="
echo
echo "Services running:"
echo "• Document Search API: http://localhost:8000"
echo "• API Documentation: http://localhost:8000/docs"
echo "• Elasticsearch: http://localhost:9200"
echo
echo "Test the application:"
echo "curl \"http://localhost:8000/api/v1/search?q=test\""
echo
echo "View logs:"
echo "docker-compose logs -f document-search-app"
echo
echo "Stop services:"
echo "docker-compose down"
