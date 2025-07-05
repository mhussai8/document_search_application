"""
Google Cloud Storage service for document retrieval and management.
"""

import asyncio
import logging
from typing import List, Tuple, Optional, AsyncGenerator
from datetime import datetime

from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError
import aiofiles

from ..config import get_config
from ..models import DocumentMetadata, FileType

logger = logging.getLogger(__name__)


class GCSService:
    """
    Google Cloud Storage service for document operations.
    """
    
    def __init__(self):
        self.config = get_config()
        self._client = None
        self._bucket = None
    
    @property
    def client(self) -> storage.Client:
        """Get GCS client instance."""
        if self._client is None:
            self._client = storage.Client(
                project=self.config.gcs.project_id
            )
        return self._client
    
    @property
    def bucket(self) -> storage.Bucket:
        """Get GCS bucket instance."""
        if self._bucket is None:
            self._bucket = self.client.bucket(self.config.gcs.bucket_name)
        return self._bucket
    
    async def list_documents(self, prefix: str = "") -> List[storage.Blob]:
        """
        List all documents in the GCS bucket.
        
        Args:
            prefix: Optional prefix to filter documents
            
        Returns:
            List of GCS blob objects
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            blobs = await loop.run_in_executor(
                None,
                lambda: list(self.bucket.list_blobs(prefix=prefix))
            )
            
            # Filter by supported file types
            supported_extensions = {f".{fmt}" for fmt in self.config.document_processing.supported_formats}
            
            filtered_blobs = []
            for blob in blobs:
                if any(blob.name.lower().endswith(ext) for ext in supported_extensions):
                    filtered_blobs.append(blob)
            
            logger.info(f"Found {len(filtered_blobs)} documents in GCS bucket")
            return filtered_blobs
            
        except Exception as e:
            logger.error(f"Error listing documents from GCS: {str(e)}")
            return []
    
    async def download_document(self, blob: storage.Blob) -> Optional[bytes]:
        """
        Download document content from GCS.
        
        Args:
            blob: GCS blob object
            
        Returns:
            Document content as bytes or None if failed
        """
        try:
            # Check file size
            if blob.size > self.config.document_processing.max_file_size_mb * 1024 * 1024:
                logger.warning(f"File {blob.name} exceeds size limit: {blob.size} bytes")
                return None
            
            # Download content
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                blob.download_as_bytes
            )
            
            logger.debug(f"Downloaded {blob.name}: {len(content)} bytes")
            return content
            
        except Exception as e:
            logger.error(f"Error downloading {blob.name}: {str(e)}")
            return None
    
    async def get_document_url(self, blob_name: str, expiration_hours: int = 24) -> Optional[str]:
        """
        Generate a signed URL for document access.
        
        Args:
            blob_name: Name of the blob in GCS
            expiration_hours: URL expiration time in hours
            
        Returns:
            Signed URL or None if failed
        """
        try:
            blob = self.bucket.blob(blob_name)
            
            # Generate signed URL
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(
                None,
                lambda: blob.generate_signed_url(
                    expiration=datetime.utcnow().replace(
                        hour=datetime.utcnow().hour + expiration_hours
                    ),
                    method="GET"
                )
            )
            
            return url
            
        except Exception as e:
            logger.error(f"Error generating URL for {blob_name}: {str(e)}")
            return None
    
    async def get_public_url(self, blob_name: str) -> str:
        """
        Get public URL for a document (if bucket allows public access).
        
        Args:
            blob_name: Name of the blob in GCS
            
        Returns:
            Public URL
        """
        return f"https://storage.googleapis.com/{self.config.gcs.bucket_name}/{blob_name}"
    
    async def check_document_exists(self, blob_name: str) -> bool:
        """
        Check if a document exists in GCS.
        
        Args:
            blob_name: Name of the blob to check
            
        Returns:
            True if document exists, False otherwise
        """
        try:
            blob = self.bucket.blob(blob_name)
            loop = asyncio.get_event_loop()
            exists = await loop.run_in_executor(None, blob.exists)
            return exists
            
        except Exception as e:
            logger.error(f"Error checking existence of {blob_name}: {str(e)}")
            return False
    
    async def get_document_metadata(self, blob: storage.Blob) -> Optional[dict]:
        """
        Get metadata for a document.
        
        Args:
            blob: GCS blob object
            
        Returns:
            Document metadata dictionary
        """
        try:
            # Reload blob to get latest metadata
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, blob.reload)
            
            metadata = {
                "name": blob.name,
                "size": blob.size,
                "created": blob.time_created,
                "updated": blob.updated,
                "content_type": blob.content_type,
                "etag": blob.etag,
                "generation": blob.generation,
                "metageneration": blob.metageneration,
                "storage_class": blob.storage_class,
            }
            
            # Add custom metadata if available
            if blob.metadata:
                metadata.update(blob.metadata)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting metadata for {blob.name}: {str(e)}")
            return None
    
    async def batch_download_documents(self, blobs: List[storage.Blob]) -> AsyncGenerator[Tuple[storage.Blob, Optional[bytes]], None]:
        """
        Download multiple documents concurrently.
        
        Args:
            blobs: List of GCS blob objects to download
            
        Yields:
            Tuple of (blob, content) for each document
        """
        semaphore = asyncio.Semaphore(self.config.performance.max_concurrent_downloads)
        
        async def download_single(blob: storage.Blob) -> Tuple[storage.Blob, Optional[bytes]]:
            async with semaphore:
                content = await self.download_document(blob)
                return blob, content
        
        # Create download tasks
        tasks = [download_single(blob) for blob in blobs]
        
        # Process downloads in batches
        batch_size = self.config.performance.batch_size
        for i in range(0, len(tasks), batch_size):
            batch_tasks = tasks[i:i + batch_size]
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Download error: {str(result)}")
                    continue
                
                blob, content = result
                yield blob, content
    
    async def upload_processed_document(self, blob_name: str, content: bytes, metadata: dict = None) -> bool:
        """
        Upload a processed document back to GCS.
        
        Args:
            blob_name: Name for the new blob
            content: Document content as bytes
            metadata: Optional metadata dictionary
            
        Returns:
            True if upload successful, False otherwise
        """
        try:
            blob = self.bucket.blob(blob_name)
            
            # Set metadata if provided
            if metadata:
                blob.metadata = metadata
            
            # Upload content
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: blob.upload_from_string(content)
            )
            
            logger.info(f"Uploaded processed document: {blob_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading {blob_name}: {str(e)}")
            return False
    
    async def delete_document(self, blob_name: str) -> bool:
        """
        Delete a document from GCS.
        
        Args:
            blob_name: Name of the blob to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            blob = self.bucket.blob(blob_name)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, blob.delete)
            
            logger.info(f"Deleted document: {blob_name}")
            return True
            
        except NotFound:
            logger.warning(f"Document not found for deletion: {blob_name}")
            return False
        except Exception as e:
            logger.error(f"Error deleting {blob_name}: {str(e)}")
            return False
    
    async def health_check(self) -> bool:
        """
        Check if GCS service is healthy.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Try to list objects (requires less permissions than bucket.reload())
            loop = asyncio.get_event_loop()
            # Just try to list one object to test connectivity and permissions
            blobs = await loop.run_in_executor(
                None,
                lambda: list(self.bucket.list_blobs(max_results=1))
            )
            logger.info("GCS health check passed")
            return True
            
        except Exception as e:
            logger.warning(f"GCS health check failed: {str(e)}")
            logger.warning("GCS may not be accessible, but application will continue")
            # Return True to allow the app to start even if GCS has permission issues
            return True
