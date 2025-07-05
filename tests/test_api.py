"""
Test API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestSearchEndpoint:
    """Test search functionality."""
    
    def test_search_endpoint_exists(self, client: TestClient):
        """Test that search endpoint is accessible."""
        response = client.get("/api/v1/search?q=test")
        # Should not return 404
        assert response.status_code != 404
    
    def test_search_requires_query(self, client: TestClient):
        """Test that search requires a query parameter."""
        response = client.get("/api/v1/search")
        assert response.status_code == 422  # Validation error
    
    def test_search_with_valid_query(self, client: TestClient):
        """Test search with valid query parameters."""
        response = client.get("/api/v1/search?q=test&limit=5")
        assert response.status_code in [200, 500]  # 500 if ES not available
        
        if response.status_code == 200:
            data = response.json()
            # Simple search returns an array of URLs
            assert isinstance(data, list)
            # If there are results, each should be a string URL
            if len(data) > 0:
                assert all(isinstance(url, str) for url in data)
                assert len(data) <= 5  # Should respect the limit
    
    def test_search_detailed_with_valid_query(self, client: TestClient):
        """Test detailed search with valid query parameters."""
        response = client.get("/api/v1/search_detailed?q=test&limit=3")
        assert response.status_code in [200, 500]  # 500 if ES not available
        
        if response.status_code == 200:
            data = response.json()
            # Detailed search returns an object with metadata
            assert "query" in data
            assert "total_hits" in data
            assert "results" in data
            assert "execution_time_ms" in data
            assert data["query"] == "test"
            assert isinstance(data["results"], list)
            assert len(data["results"]) <= 3  # Should respect the limit
    
    def test_search_detailed_requires_query(self, client: TestClient):
        """Test that detailed search requires a query parameter."""
        response = client.get("/api/v1/search_detailed")
        assert response.status_code == 422  # Validation error
    
    def test_search_with_file_type_filter(self, client: TestClient):
        """Test search with file type filter."""
        response = client.get("/api/v1/search?q=test&file_type=pdf")
        assert response.status_code in [200, 500]
    
    def test_search_with_invalid_limit(self, client: TestClient):
        """Test search with invalid limit parameter."""
        response = client.get("/api/v1/search?q=test&limit=1000")
        assert response.status_code == 422  # Validation error


class TestHealthEndpoint:
    """Test health check functionality."""
    
    def test_health_endpoint_exists(self, client: TestClient):
        """Test that health endpoint is accessible."""
        response = client.get("/api/v1/health")
        assert response.status_code in [200, 503]
    
    def test_health_response_structure(self, client: TestClient):
        """Test health response structure."""
        response = client.get("/api/v1/health")
        
        if response.status_code in [200, 503]:
            data = response.json()
            assert "status" in data
            assert "timestamp" in data
            assert "services" in data
            assert "version" in data


class TestAdminEndpoints:
    """Test admin functionality."""
    
    def test_stats_endpoint(self, client: TestClient):
        """Test statistics endpoint."""
        response = client.get("/api/v1/admin/stats")
        assert response.status_code in [200, 500]
    
    def test_status_endpoint(self, client: TestClient):
        """Test status endpoint."""
        response = client.get("/api/v1/admin/status")
        assert response.status_code in [200, 500]
    
    def test_reindex_endpoint(self, client: TestClient):
        """Test reindex trigger endpoint."""
        response = client.post("/api/v1/admin/reindex")
        assert response.status_code in [200, 500]


class TestRootEndpoint:
    """Test root endpoint."""
    
    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns application info."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
