"""
FastAPI routes for the document search application.
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from ..models import SearchQuery, SearchResponse, HealthStatus, IndexingStats, FileType
from ..services import ElasticsearchService, IndexingService
from ..config import get_config

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Global services (will be injected via dependency injection in production)
elasticsearch_service = ElasticsearchService()
indexing_service = IndexingService()
config = get_config()


@router.get("/search_detailed", response_model=SearchResponse)
async def search_documents_detailed(
    q: str = Query(..., description="Search query", min_length=1, max_length=1000),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=100),
    file_type: Optional[FileType] = Query(None, description="Filter by file type"),
    min_score: Optional[float] = Query(None, description="Minimum relevance score", ge=0.0, le=1.0)
) -> SearchResponse:
    """
    Search for documents containing the specified query with detailed results.
    
    This endpoint provides full-text search capabilities across all indexed documents
    with support for filtering by file type and minimum relevance score.
    Returns detailed information including highlights, metadata, and scores.
    """
    try:
        # Create search query
        search_query = SearchQuery(
            q=q,
            limit=limit,
            file_type=file_type,
            min_score=min_score
        )
        
        # Perform search
        results = await elasticsearch_service.search_documents(search_query)
        
        logger.info(f"Search completed: '{q}' -> {len(results.results)} results in {results.execution_time_ms}ms")
        
        return results
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/search")
async def search_documents(
    q: str = Query(..., description="Search query", min_length=1, max_length=1000),
    limit: int = Query(50, description="Maximum number of results", ge=1, le=500),
    file_type: Optional[FileType] = Query(None, description="Filter by file type")
) -> List[str]:
    """
    Simple search that returns only file paths containing the search term.
    
    This endpoint provides a lightweight search that returns just the GCS paths
    of documents that match the query. Returns an empty list if no matches found.
    """
    try:
        # Create search query with higher limit for simple search
        search_query = SearchQuery(
            q=q,
            limit=limit,
            file_type=file_type,
            min_score=0.0  # Accept any relevance score
        )
        
        # Perform search
        results = await elasticsearch_service.search_documents(search_query)
        
        # Extract just the GCS URLs from search results
        file_paths = []
        for result in results.results:
            # Convert the gcs_url (HttpUrl) to string for JSON serialization
            file_paths.append(str(result.gcs_url))
        
        logger.info(f"Simple search completed: '{q}' -> {len(file_paths)} files found")
        
        return file_paths
        
    except Exception as e:
        logger.error(f"Simple search error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """
    Check the health status of the application and its dependencies.
    
    Returns information about the status of Elasticsearch, GCS, and other services.
    """
    try:
        # Check service health
        es_healthy = await elasticsearch_service.health_check()
        
        # Determine overall status
        overall_status = "healthy" if es_healthy else "unhealthy"
        
        # Build response using Pydantic model
        health_status = HealthStatus(
            status=overall_status,
            timestamp=datetime.utcnow(),
            services={
                "elasticsearch": "healthy" if es_healthy else "unhealthy",
                "api": "healthy"
            },
            version=config.app.version
        )
        
        # Return the Pydantic model directly - FastAPI will handle serialization
        return health_status
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        
        # Return unhealthy status
        return HealthStatus(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            services={
                "elasticsearch": "unknown",
                "api": "healthy"
            },
            version=config.app.version
        )


@router.post("/admin/reindex")
async def trigger_reindex(background_tasks: BackgroundTasks) -> dict:
    """
    Trigger a full reindexing of all documents.
    
    This operation runs in the background and can take several minutes
    depending on the number of documents.
    """
    try:
        # Add reindexing task to background
        background_tasks.add_task(perform_reindex)
        
        return {
            "message": "Reindexing started",
            "status": "accepted",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Reindex trigger error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start reindexing: {str(e)}"
        )


@router.get("/admin/stats", response_model=IndexingStats)
async def get_indexing_stats() -> IndexingStats:
    """
    Get statistics about indexed documents.
    
    Returns information about document counts, file types, sizes, and indexing status.
    """
    try:
        stats = await elasticsearch_service.get_indexing_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Stats retrieval error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.get("/admin/status")
async def get_processing_status() -> dict:
    """
    Get detailed processing and service status information.
    
    Returns comprehensive status information for monitoring and debugging.
    """
    try:
        status = await indexing_service.get_processing_status()
        return status
        
    except Exception as e:
        logger.error(f"Status retrieval error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve status: {str(e)}"
        )


@router.post("/admin/documents/{document_id}/reindex")
async def reindex_document(document_id: str, background_tasks: BackgroundTasks) -> dict:
    """
    Reindex a specific document by its GCS path.
    
    Args:
        document_id: GCS path of the document to reindex
    """
    try:
        # Add single document reindexing task
        background_tasks.add_task(perform_incremental_index, [document_id])
        
        return {
            "message": f"Document reindexing started: {document_id}",
            "status": "accepted",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Document reindex error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reindex document: {str(e)}"
        )


@router.get("/admin/documents")
async def list_documents(
    limit: int = Query(default=100, description="Maximum number of documents to return"),
    offset: int = Query(default=0, description="Number of documents to skip")
) -> dict:
    """
    List all indexed documents with their metadata.
    Useful for administration and debugging.
    """
    try:
        # Search for all documents
        query = {
            "query": {
                "match_all": {}
            },
            "size": limit,
            "from": offset,
            "_source": ["metadata.gcs_path", "metadata.file_name", "metadata.file_type", "metadata.file_size", "indexed_at"]
        }
        
        response = await elasticsearch_service.client.search(
            index=elasticsearch_service.index_name,
            **query
        )
        
        documents = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            documents.append({
                "document_id": hit["_id"],
                "gcs_path": source["metadata"]["gcs_path"],
                "file_name": source["metadata"]["file_name"],
                "file_type": source["metadata"]["file_type"],
                "file_size": source["metadata"]["file_size"],
                "indexed_at": source.get("indexed_at", "unknown")
            })
        
        return {
            "total_documents": response["hits"]["total"]["value"],
            "documents": documents,
            "limit": limit,
            "offset": offset,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"List documents error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list documents: {str(e)}"
        )


@router.delete("/admin/documents/{document_id:path}")
async def delete_document(document_id: str) -> dict:
    """
    Delete a document from the search index.
    
    Args:
        document_id: GCS path of the document to delete (URL encoded)
    """
    try:
        # URL decode the document_id to get the actual GCS path
        import urllib.parse
        gcs_path = urllib.parse.unquote(document_id)
        
        success = await indexing_service.delete_document(gcs_path)
        
        if success:
            return {
                "message": f"Document deleted: {gcs_path}",
                "status": "success",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Document not found: {gcs_path}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document deletion error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )


# Background task functions
async def perform_reindex():
    """Background task for full reindexing."""
    try:
        logger.info("Starting background reindexing task")
        await indexing_service.initialize()
        stats = await indexing_service.full_reindex()
        logger.info(f"Background reindexing completed: {stats.total_documents} documents indexed")
        
    except Exception as e:
        logger.error(f"Background reindexing failed: {str(e)}")


async def perform_incremental_index(file_paths: List[str]):
    """Background task for incremental indexing."""
    try:
        logger.info(f"Starting incremental indexing for {len(file_paths)} documents")
        await indexing_service.initialize()
        stats = await indexing_service.incremental_index(file_paths)
        logger.info(f"Incremental indexing completed: {stats.total_documents} total documents")
        
    except Exception as e:
        logger.error(f"Incremental indexing failed: {str(e)}")
