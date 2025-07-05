"""
Test configuration and fixtures.
"""

import pytest
import asyncio
from typing import AsyncGenerator
from fastapi.testclient import TestClient

from app.main import app
from app.config import Config, set_config
from app.services import ElasticsearchService, IndexingService


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config() -> Config:
    """Create test configuration."""
    # Create minimal test configuration
    config_data = {
        "app": {
            "name": "Document Search Test",
            "version": "1.0.0",
            "debug": True,
            "host": "localhost",
            "port": 8000
        },
        "gcs": {
            "bucket_name": "test-bucket",
            "project_id": "test-project"
        },
        "elasticsearch": {
            "host": "localhost",
            "port": 9200,
            "index_name": "test_documents"
        },
        "document_processing": {
            "max_file_size_mb": 8,
            "supported_formats": ["txt", "csv", "pdf", "png"]
        },
        "search": {
            "default_limit": 10,
            "max_limit": 100,
            "min_score": 0.1
        },
        "performance": {
            "max_concurrent_downloads": 5,
            "batch_size": 10
        },
        "logging": {
            "level": "DEBUG",
            "format": "simple",
            "file": "logs/test.log"
        },
        "security": {
            "enable_cors": True,
            "cors_origins": ["http://localhost:3000"]
        }
    }
    
    return Config(**config_data)


@pytest.fixture(scope="session")
def client(test_config: Config) -> TestClient:
    """Create test client."""
    set_config(test_config)
    return TestClient(app)


@pytest.fixture
async def elasticsearch_service(test_config: Config) -> AsyncGenerator[ElasticsearchService, None]:
    """Create Elasticsearch service for testing."""
    set_config(test_config)
    service = ElasticsearchService()
    
    # Initialize test index
    await service.initialize_index()
    
    yield service
    
    # Cleanup
    try:
        await service.client.indices.delete(index=service.index_name)
    except:
        pass
    await service.close()


@pytest.fixture
def sample_document_content() -> dict:
    """Sample document content for testing."""
    return {
        "txt": b"This is a sample text document with some content.",
        "csv": b"name,email,age\nJohn Doe,john@example.com,30\nJane Smith,jane@example.com,25",
        "pdf": b"%PDF-1.4\nSample PDF content for testing purposes."
    }


@pytest.fixture
def mock_gcs_blobs():
    """Mock GCS blob objects for testing."""
    class MockBlob:
        def __init__(self, name: str, size: int):
            self.name = name
            self.size = size
            self.time_created = "2024-01-01T00:00:00Z"
            self.updated = "2024-01-01T00:00:00Z"
            self.content_type = "application/octet-stream"
            self.etag = "mock-etag"
            self.generation = 1
            self.metageneration = 1
            self.storage_class = "STANDARD"
            self.metadata = {}
        
        def download_as_bytes(self):
            return b"Mock file content"
        
        def exists(self):
            return True
        
        def reload(self):
            pass
    
    return [
        MockBlob("document1.txt", 1024),
        MockBlob("document2.pdf", 2048),
        MockBlob("document3.csv", 512)
    ]
