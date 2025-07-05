"""
Document indexing orchestration service.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .gcs_service import GCSService
from .document_processor import BatchDocumentProcessor
from .elasticsearch_service import ElasticsearchService
from ..config import get_config
from ..models import Document, IndexingStats

logger = logging.getLogger(__name__)


class IndexingService:
    """
    Orchestrates the document indexing pipeline from GCS to Elasticsearch.
    """
    
    def __init__(self):
        self.config = get_config()
        self.gcs_service = GCSService()
        self.processor = BatchDocumentProcessor(
            max_concurrent=self.config.performance.max_concurrent_downloads
        )
        self.elasticsearch_service = ElasticsearchService()
        
        # Statistics tracking
        self.stats = {
            "documents_processed": 0,
            "documents_indexed": 0,
            "documents_failed": 0,
            "processing_errors": [],
            "indexing_errors": []
        }
    
    async def initialize(self) -> bool:
        """
        Initialize the indexing service and required dependencies.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize Elasticsearch index
            es_initialized = await self.elasticsearch_service.initialize_index()
            if not es_initialized:
                logger.error("Failed to initialize Elasticsearch index")
                return False
            
            # Verify GCS connectivity
            gcs_healthy = await self.gcs_service.health_check()
            if not gcs_healthy:
                logger.warning("GCS service health check failed - continuing anyway")
                logger.warning("Some features may not work if GCS is not accessible")
            else:
                logger.info("GCS service health check passed")
            
            logger.info("Indexing service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing indexing service: {str(e)}")
            return False
    
    async def full_reindex(self) -> IndexingStats:
        """
        Perform a complete reindexing of all documents from GCS.
        
        Returns:
            IndexingStats with the results of the reindexing operation
        """
        logger.info("Starting full reindex operation")
        start_time = datetime.utcnow()
        
        # Reset statistics
        self.stats = {
            "documents_processed": 0,
            "documents_indexed": 0,
            "documents_failed": 0,
            "processing_errors": [],
            "indexing_errors": []
        }
        
        try:
            # Step 1: Clear existing index
            logger.info("Clearing existing index...")
            cleared = await self.elasticsearch_service.clear_index()
            if not cleared:
                logger.warning("Failed to clear existing index - continuing anyway")
            
            # Step 2: Discover documents in GCS
            logger.info("Discovering documents in GCS...")
            blobs = await self.gcs_service.list_documents()
            
            if not blobs:
                logger.warning("No documents found in GCS bucket")
                return await self.elasticsearch_service.get_indexing_stats()
            
            logger.info(f"Found {len(blobs)} documents to process")
            
            # Step 3: Process documents in batches
            batch_size = self.config.performance.batch_size
            total_batches = (len(blobs) + batch_size - 1) // batch_size
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(blobs))
                batch_blobs = blobs[start_idx:end_idx]
                
                logger.info(f"Processing batch {batch_idx + 1}/{total_batches} ({len(batch_blobs)} documents)")
                
                # Process batch
                await self._process_document_batch(batch_blobs)
            
            # Step 4: Refresh Elasticsearch index
            await self.elasticsearch_service.refresh_index()
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"Full reindex completed in {duration:.2f} seconds")
            logger.info(f"Statistics: {self.stats['documents_indexed']} indexed, {self.stats['documents_failed']} failed")
            
            return await self.elasticsearch_service.get_indexing_stats()
            
        except Exception as e:
            logger.error(f"Error during full reindex: {str(e)}")
            return await self.elasticsearch_service.get_indexing_stats()
    
    async def incremental_index(self, file_paths: List[str] = None) -> IndexingStats:
        """
        Perform incremental indexing of new or modified documents.
        
        Args:
            file_paths: Optional list of specific file paths to index
            
        Returns:
            IndexingStats with the results of the indexing operation
        """
        logger.info("Starting incremental indexing")
        
        try:
            # If specific paths provided, use them; otherwise discover all
            if file_paths:
                blobs = []
                for path in file_paths:
                    if await self.gcs_service.check_document_exists(path):
                        blob = self.gcs_service.bucket.blob(path)
                        blobs.append(blob)
                    else:
                        logger.warning(f"Document not found in GCS: {path}")
            else:
                blobs = await self.gcs_service.list_documents()
            
            if not blobs:
                logger.info("No documents to index")
                return await self.elasticsearch_service.get_indexing_stats()
            
            # Process documents
            await self._process_document_batch(blobs)
            
            # Refresh index
            await self.elasticsearch_service.refresh_index()
            
            logger.info(f"Incremental indexing completed: {len(blobs)} documents processed")
            
            return await self.elasticsearch_service.get_indexing_stats()
            
        except Exception as e:
            logger.error(f"Error during incremental indexing: {str(e)}")
            return await self.elasticsearch_service.get_indexing_stats()
    
    async def _process_document_batch(self, blobs: List[Any]) -> None:
        """
        Process a batch of documents from GCS blobs.
        
        Args:
            blobs: List of GCS blob objects to process
        """
        try:
            # Step 1: Download documents
            downloaded_docs = []
            async for blob, content in self.gcs_service.batch_download_documents(blobs):
                if content is not None:
                    # Use just the blob name (filename) as the GCS path
                    # The full URL will be constructed in the search results
                    gcs_path = blob.name
                    downloaded_docs.append((content, blob.name, gcs_path))
                else:
                    self.stats["documents_failed"] += 1
                    self.stats["processing_errors"].append(f"Failed to download: {blob.name}")
            
            if not downloaded_docs:
                logger.warning("No documents successfully downloaded in batch")
                return
            
            # Step 2: Process documents
            logger.info(f"Processing {len(downloaded_docs)} downloaded documents")
            processed_docs = await self.processor.process_batch(downloaded_docs)
            
            # Filter successful processing
            valid_docs = [doc for doc in processed_docs if doc is not None]
            failed_count = len(processed_docs) - len(valid_docs)
            
            self.stats["documents_processed"] += len(downloaded_docs)
            self.stats["documents_failed"] += failed_count
            
            if failed_count > 0:
                logger.warning(f"{failed_count} documents failed processing")
            
            # Step 3: Index documents in Elasticsearch
            if valid_docs:
                logger.info(f"Indexing {len(valid_docs)} processed documents")
                success_count, failed_count = await self.elasticsearch_service.bulk_index_documents(valid_docs)
                
                self.stats["documents_indexed"] += success_count
                if failed_count > 0:
                    self.stats["documents_failed"] += failed_count
                    self.stats["indexing_errors"].append(f"Failed to index {failed_count} documents")
            
        except Exception as e:
            logger.error(f"Error processing document batch: {str(e)}")
            self.stats["processing_errors"].append(str(e))
    
    async def delete_document(self, gcs_path: str) -> bool:
        """
        Delete a document from both GCS and Elasticsearch.
        
        Args:
            gcs_path: GCS path of the document to delete (can be filename or full path)
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            logger.info(f"Attempting to delete document: {gcs_path}")
            
            # Try both the provided path and a constructed full path
            search_paths = [gcs_path]
            
            # If the path doesn't start with gs://, try constructing the full path
            if not gcs_path.startswith("gs://"):
                full_path = f"gs://{self.gcs_service.bucket.name}/{gcs_path}"
                search_paths.append(full_path)
            else:
                # If it's a full path, also try just the filename
                filename = gcs_path.split("/")[-1]
                search_paths.append(filename)
            
            # Search for the document by exact GCS path match
            for search_path in search_paths:
                query = {
                    "query": {
                        "term": {
                            "metadata.gcs_path": search_path
                        }
                    },
                    "size": 1
                }
                
                # Execute the search directly
                response = await self.elasticsearch_service.client.search(
                    index=self.elasticsearch_service.index_name,
                    **query
                )
                
                logger.info(f"Search response for {search_path}: {response['hits']['total']}")
                
                if response["hits"]["hits"]:
                    # Found the document
                    doc_id = response["hits"]["hits"][0]["_id"]
                    actual_gcs_path = response["hits"]["hits"][0]["_source"]["metadata"]["gcs_path"]
                    
                    logger.info(f"Found document to delete: {actual_gcs_path} (ID: {doc_id})")
                    
                    # Delete from Elasticsearch using the correct document ID
                    es_deleted = await self.elasticsearch_service.delete_document(doc_id)
                    
                    if es_deleted:
                        logger.info(f"Successfully deleted document: {actual_gcs_path} (ID: {doc_id})")
                    else:
                        logger.warning(f"Failed to delete document from Elasticsearch: {actual_gcs_path}")
                        
                    return es_deleted
            
            # If we get here, the document was not found with any search path
            logger.warning(f"Document not found for deletion: {gcs_path}")
            
            # Try a broader search to see if the document exists with a different path
            wildcard_query = {
                "query": {
                    "wildcard": {
                        "metadata.gcs_path": f"*{gcs_path.split('/')[-1]}*"
                    }
                },
                "size": 5
            }
            
            wildcard_response = await self.elasticsearch_service.client.search(
                index=self.elasticsearch_service.index_name,
                **wildcard_query
            )
            
            if wildcard_response["hits"]["hits"]:
                similar_paths = [hit["_source"]["metadata"]["gcs_path"] for hit in wildcard_response["hits"]["hits"]]
                logger.warning(f"Found similar paths: {similar_paths}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting document {gcs_path}: {str(e)}")
            return False
    
    async def get_processing_status(self) -> Dict[str, Any]:
        """
        Get current processing status and statistics.
        
        Returns:
            Dictionary with processing status information
        """
        # Get Elasticsearch stats
        es_stats = await self.elasticsearch_service.get_indexing_stats()
        
        return {
            "indexing_stats": es_stats.model_dump(),
            "processing_stats": self.stats,
            "services_health": {
                "elasticsearch": await self.elasticsearch_service.health_check(),
                "gcs": await self.gcs_service.health_check()
            }
        }
    
    async def cleanup(self) -> None:
        """Clean up resources used by the indexing service."""
        try:
            await self.elasticsearch_service.close()
            logger.info("Indexing service cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
