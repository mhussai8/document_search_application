# Document Search Application

A high-performance document search application that indexes and searches documents from Google Cloud Storage using Elasticsearch, LangChain, and FastAPI.

## Features

- **Multi-format Support**: .csv, .txt, .pdf, .png files
- **Cloud Integration**: Google Cloud Storage integration
- **Fast Search**: Elasticsearch-powered full-text search
- **Scalable**: Handles 2000+ documents with <1s response time
- **RESTful API**: FastAPI-based REST endpoints
- **Intelligent Processing**: LangChain framework for document processing
- **OCR Support**: Text extraction from images using OCR

## Requirements

- Python 3.9+
- Conda (package manager)
- Elasticsearch 8.x
- Google Cloud Storage account with service account credentials

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# 1. Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"

# 2. Build and start all services
docker-compose up -d --build

# 3. Check status
curl http://localhost:8000/api/v1/health
```

**Note**: The `--build` flag ensures that any code changes are incorporated into the Docker image. For subsequent runs without code changes, you can use `docker-compose up -d`.

### Option 2: Local Development

```bash
# 1. Setup environment
conda create -n document-search python=3.9
conda activate document-search
conda install -c conda-forge tesseract poppler
pip install -r requirements.txt

# 2. Start Elasticsearch
docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 \
  -e "discovery.type=single-node" -e "xpack.security.enabled=false" \
  docker.elastic.co/elasticsearch/elasticsearch:8.11.0

# 3. Configure for local
cp config/config.example.yml config/config.yml
# Edit config.yml with your GCS settings

# 4. Start application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Configuration

### Google Cloud Setup

1. Create a Google Cloud project
2. Enable Cloud Storage API
3. Create a service account and download credentials JSON
4. Set environment variable:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"
   ```

### Config Files

- **config.example.yml**: For local development (uses `localhost`)
- **config.docker.yml**: For Docker Compose (uses `elasticsearch`)
- **config.yml**: Your actual configuration (copy from one of the above)

## Usage

### API Documentation
Visit `http://localhost:8000/docs` for interactive API documentation.

### Search Examples
```bash
# Simple search - returns file paths
curl "http://localhost:8000/api/v1/search?q=contract"

# Detailed search with metadata and highlights
curl "http://localhost:8000/api/v1/search_detailed?q=contract&limit=10&file_type=pdf"

# Manual indexing
curl -X POST "http://localhost:8000/api/v1/admin/reindex"
```

## API Endpoints

### Search
- **GET** `/api/v1/search?q=<query>&limit=<limit>&file_type=<type>`
  - Returns: Array of GCS file paths
- **GET** `/api/v1/search_detailed?q=<query>&limit=<limit>&file_type=<type>&min_score=<score>`
  - Returns: SearchResponse with metadata, highlights, and relevance scores

### Admin
- **POST** `/api/v1/admin/reindex` - Manually trigger document reindexing
- **GET** `/api/v1/admin/stats` - Get indexing statistics
- **GET** `/api/v1/admin/documents` - List all indexed documents with pagination
- **DELETE** `/api/v1/admin/documents/{document_path}` - Delete a document by GCS path

### Health Check
- **GET** `/api/v1/health` - Application health status

## File Format Support

| Format | Text Extraction | Metadata Extracted |
|--------|----------------|-------------------|
| .txt   | Direct read with encoding detection | File info only |
| .csv   | Pandas parsing with column/row analysis | `csv_columns`, `csv_rows` |
| .pdf   | PyPDF2/pdfplumber text extraction | `page_count` |
| .png   | OCR (Tesseract) text recognition | `image_dimensions` |

## Development

### Running Tests
```bash
pytest tests/
```

### Logs
- Console output (development)
- `logs/app.log` (production)

## Troubleshooting

### Common Issues

1. **Elasticsearch Connection Error**
   - Verify Elasticsearch is running: `curl http://localhost:9200`
   - **For Docker Compose**: Use `elasticsearch` as host instead of `localhost`

2. **Google Cloud Authentication Error**
   - Verify credentials file path and service account permissions

3. **Files Not Being Indexed**
   - Check file size limit in config.yml (default: 2MB)
   - Verify file format is supported and GCS permissions

4. **Code Changes Not Reflected in Docker**
   - Rebuild the Docker image: `docker-compose up -d --build`
   - Or rebuild just the app: `docker-compose build document-search-app && docker-compose up -d`

## License

MIT License - see LICENSE file for details.
