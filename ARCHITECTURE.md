# Document Search Application Architecture

## Current Implementation Overview

This document describes the **as-implemented** architecture of the Document Search Application, focusing on the components that are actually deployed and working.

## High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DOCUMENT SEARCH APPLICATION                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐                                                            │
│  │   Client Apps   │                                                            │
│  │                 │                                                            │
│  │ • Web Browser   │────────────────────────────────────────────────────────┐   │
│  │ • curl/scripts  │                                                        │   │
│  │ • API clients   │                                                        │   │
│  └─────────────────┘                                                        │   │
│                                                                             │   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                         FASTAPI APPLICATION LAYER                          │ │
│  │                                                                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐ │ │
│  │  │   REST API      │  │   Middleware    │  │     Background Tasks       │ │ │
│  │  │                 │  │                 │  │                             │ │ │
│  │  │ • /search       │  │ • CORS          │  │ • Document Indexing         │ │ │
│  │  │ • /health       │  │ • Error Handler │  │ • Reindexing Jobs          │ │ │
│  │  │ • /admin/*      │  │ • Request/Resp  │  │ • Status Monitoring        │ │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                     │                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                           SERVICE LAYER                                    │ │
│  │                                                                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐ │ │
│  │  │  Indexing       │  │   Document      │  │   Elasticsearch Service    │ │ │
│  │  │  Service        │  │   Processor     │  │                             │ │ │
│  │  │                 │  │                 │  │ • Query Processing          │ │ │
│  │  │ • GCS Discovery │  │                 │  │ • Result Ranking           │ │ │
│  │  │ • Batch Proc.   │  │ • Text Extract. │  │ • Filtering                │ │ │
│  │  │ • Index Clear   │  │ • OCR(Tesseract)│  │ • Highlighting             │ │ │
│  │  │ • Error Handle  │  │ • PDF Parse     │  │ • Health Checks            │ │ │
│  │  └─────────────────┘  │ • CSV Parse     │  └─────────────────────────────┘ │ │
│  │                       └─────────────────┘                                  │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                     │                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                           DATA LAYER                                       │ │
│  │                                                                             │ │
│  │  ┌─────────────────┐              ┌─────────────────────────────────────────┐ │ │
│  │  │ Google Cloud    │              │           Elasticsearch                 │ │ │
│  │  │ Storage (GCS)   │              │                                         │ │ │
│  │  │                 │              │  ┌─────────────┐ ┌─────────────────────┐│ │ │
│  │  │ • Documents     │──────────────│  │   Index     │ │     Search          ││ │ │
│  │  │ • .txt, .csv    │    Reads     │  │             │ │     Engine          ││ │ │
│  │  │ • .pdf, .png    │   Documents  │  │ • Content   │ │                     ││ │ │
│  │  │ • Metadata      │              │  │ • Metadata  │ │ • Full-text Search  ││ │ │
│  │  │                 │              │  │ • Mappings  │ │ • Aggregations      ││ │ │
│  │  └─────────────────┘              │  └─────────────┘ │ • Relevance Scoring ││ │ │
│  │                                   │                  └─────────────────────┘│ │ │
│  │                                   └─────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Document Indexing Pipeline
```
GCS Bucket → Document Discovery → Content Extraction → Elasticsearch Index
     ↓              ↓                      ↓                    ↓
• Files listed  • Download docs    • Text extraction     • Bulk index
• Filter by     • Parallel proc.   • OCR for images      • Duplicate check
  format        • Error handling   • Metadata extract    • Index mapping
```

### 2. Search Request Flow
```
Client Request → API Validation → Elasticsearch Query → Result Processing → JSON Response
     ↓              ↓                      ↓                    ↓               ↓
• Query params  • Parameter       • Build ES query      • Score filtering  • Format results
• Auth check      validation      • Execute search      • Highlight text   • Add metadata
• Rate limit    • File type       • Aggregate results   • Sort by score    • Return JSON
               filtering
```

### 3. Administrative Operations
```
Admin Request → Service Call → Database Operation → Status Response
     ↓              ↓                ↓                    ↓
• Reindex      • Clear index    • Bulk operations   • Stats summary
• Stats        • Health check   • Document count    • Error reporting
• Document     • Document list  • Status queries    • Success confirmation
  management
```

## Technology Stack (Current Implementation)

### Core Technologies
- **Python 3.9+**: Main programming language
- **FastAPI**: High-performance web framework for APIs
- **Elasticsearch 8.11.0**: Search engine and document store
- **Google Cloud Storage**: Document storage and management

### Document Processing
- **pdfplumber/pypdf**: PDF text extraction (pdfplumber primary, pypdf fallback)
- **Tesseract OCR**: Image text recognition
- **Pandas**: CSV file processing
- **Pillow (PIL)**: Image processing

### Infrastructure & Deployment
- **Docker**: Containerization
- **Docker Compose**: Multi-service orchestration
- **Uvicorn**: ASGI (Asynchronous Server Gateway Interface) server
- **Pydantic**: Data validation and settings management

### Monitoring & Observability
- **Structured Logging**: JSON-formatted logs with rotation
- **Health Checks**: Elasticsearch and GCS connectivity monitoring
- **API Documentation**: FastAPI auto-generated docs

## Current API Endpoints

### Search Endpoints
- **GET** `/api/v1/search` - Simple search returning file paths
- **GET** `/api/v1/search_detailed` - Detailed search with metadata and highlights

### Administrative Endpoints
- **POST** `/api/v1/admin/reindex` - Trigger full reindexing
- **GET** `/api/v1/admin/stats` - Get indexing statistics
- **GET** `/api/v1/admin/status` - Get service status and health
- **GET** `/api/v1/admin/documents` - List all indexed documents
- **DELETE** `/api/v1/admin/documents/{document_id}` - Delete specific document

### Health Check
- **GET** `/api/v1/health` - Application health status

## File Format Support (Implemented)

| Format | Processing Method | Metadata Extracted | Status |
|--------|-------------------|-------------------|---------|
| .txt   | Direct read with encoding detection | File size, creation date | ✅ Working |
| .csv   | Pandas parsing with data analysis | Columns, rows, file size | ✅ Working |
| .pdf   | pdfplumber (primary) + pypdf (fallback) | Page count, file size | ✅ Working |
| .png   | Tesseract OCR text recognition | Dimensions, file size | ✅ Working |

## Current Deployment Configuration

### Docker Compose Services
```yaml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    ports: ["9200:9200", "9300:9300"]
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    healthcheck: curl -f http://localhost:9200/_cluster/health
  
  document-search-app:
    build: .
    ports: ["8000:8000"]
    depends_on:
      elasticsearch: { condition: service_healthy }
    environment:
      - CONFIG_PATH=/app/config/config.docker.yml
      - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
```

### Configuration Files
- **config.docker.yml**: Docker Compose configuration (uses `elasticsearch` hostname)
- **config.yml**: Local development configuration (uses `localhost`)
- **config.example.yml**: Template configuration file

## Performance & Scalability (Current State)

### Current Performance Metrics
- **Document Count**: 9 documents indexed successfully
- **Search Response Time**: < 100ms for typical queries
- **Supported File Size**: Up to 2MB per document (configurable)
- **Concurrent Processing**: 10 concurrent downloads (configurable)

### Implemented Optimizations
- **Bulk Indexing**: Elasticsearch bulk operations for efficiency
- **Async Processing**: Non-blocking I/O for document processing
- **Connection Pooling**: Elasticsearch client optimization
- **Index Clearing**: Prevents duplicate documents during reindexing
- **Error Handling**: Comprehensive error handling and logging

### Configuration Management
- **Environment-based Config**: Separate configs for local vs Docker
- **Pydantic Validation**: Type-safe configuration management
- **Environment Variables**: Secure credential management

## Known Limitations & Future Enhancements

### Current Limitations
- **Single-node Elasticsearch**: Not clustered for high availability
- **No Authentication**: Open API endpoints (development setup)
- **Limited File Types**: Only txt, csv, pdf, png supported
- **No Caching**: No Redis or query result caching
- **No Rate Limiting**: No built-in rate limiting (configured but not enforced)

### Features Not Implemented
- **Kibana**: Not being used currently
- **Load Balancer**: Single instance deployment
- **API Gateway**: Direct API access
- **Prometheus Metrics**: Structured logging only
- **JWT Authentication**: No user authentication
- **Distributed Task Queue**: Synchronous processing only

## Security Implementation (Current State)

### Implemented Security Features
- **GCS IAM**: Service account with limited permissions
- **Input Validation**: Pydantic models for request validation
- **CORS**: Cross-origin resource sharing configured
- **Container Security**: Docker containerization with non-root user
- **Structured Logging**: Security event tracking capability

### Security Gaps (Development Setup)
- **No Authentication**: Open API endpoints
- **No Rate Limiting**: Not enforced (configured but inactive)
- **No HTTPS**: HTTP only in development
- **No Network Security**: No VPC or firewall rules
- **No Audit Logging**: Basic logging only

## Deployment Architecture (Current State)

### Current Deployment
```
Docker Compose → Local Development Environment
     ↓
   Services:
   • Elasticsearch (single node)
   • Document Search App
   • Shared Docker network
   • Volume mounts for config/logs
```

### Production Readiness Status
- **✅ Containerized**: Docker images ready
- **✅ Health Checks**: Elasticsearch and app health monitoring
- **✅ Configuration Management**: Environment-based configuration
- **✅ Logging**: Structured logging with file rotation
- **⚠️ Single Point of Failure**: Single Elasticsearch node
- **❌ No Load Balancing**: Single application instance
- **❌ No Monitoring**: No metrics collection
- **❌ No Backup Strategy**: No data backup implementation

## Testing & Validation

### Verified Functionality
- **Document Indexing**: Documents successfully indexed
- **Search Operations**: Simple and detailed search working
- **Admin Operations**: Reindexing, stats, document management
- **Health Checks**: Elasticsearch and GCS connectivity
- **Error Handling**: Duplicate prevention and error recovery
- **File Processing**: All supported formats (txt, csv, pdf, png)

### Performance Validation
- **Zero Duplicates**: Index clearing prevents duplicate documents
- **Consistent Results**: Same document count across deployments
- **Fast Response**: Sub-second search responses
- **Proper URLs**: GCS URLs correctly formatted and accessible

## Conclusion

This architecture represents a **working MVP** suitable for development and small-scale deployments. The application successfully demonstrates:

1. **Document Processing Pipeline**: From GCS to Elasticsearch
2. **Search Functionality**: Fast, relevant search results
3. **Admin Interface**: Complete administrative control
4. **Docker Deployment**: Containerized, reproducible deployment
5. **Clean Architecture**: Proper separation of concerns

For production use, additional components would be needed (load balancing, authentication, monitoring, backup, etc.), but the core functionality is solid and extensible.
