"""
Elasticsearch service for document indexing and search.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk

from ..config import get_config
from ..models import Document, SearchQuery, SearchResult, SearchResponse, IndexingStats

logger = logging.getLogger(__name__)


class ElasticsearchService:
    """
    Elasticsearch service for document indexing and search operations.
    """
    
    def __init__(self):
        self.config = get_config()
        self._client = None
        self.index_name = self.config.elasticsearch.index_name
    
    @property
    def client(self) -> AsyncElasticsearch:
        """Get Elasticsearch client instance."""
        if self._client is None:
            es_config = self.config.elasticsearch
            
            # Build connection parameters
            hosts = [{"host": es_config.host, "port": es_config.port, "scheme": "http"}]
            
            # Add authentication if configured
            http_auth = None
            if es_config.username and es_config.password:
                http_auth = (es_config.username, es_config.password)
            
            self._client = AsyncElasticsearch(
                hosts=hosts,
                http_auth=http_auth,
                timeout=es_config.timeout,
                max_retries=es_config.max_retries,
                retry_on_timeout=True
            )
        
        return self._client
    
    async def initialize_index(self) -> bool:
        """
        Initialize the Elasticsearch index with proper mappings.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Check if index exists
            exists_response = await self.client.indices.exists(index=self.index_name)
            exists = exists_response.body if hasattr(exists_response, 'body') else bool(exists_response)
            
            if not exists:
                # Create index with mappings
                mapping = self._get_index_mapping()
                settings = self._get_index_settings()
                
                await self.client.indices.create(
                    index=self.index_name,
                    mappings=mapping,
                    settings=settings
                )
                
                logger.info(f"Created Elasticsearch index: {self.index_name}")
            else:
                logger.info(f"Elasticsearch index already exists: {self.index_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Elasticsearch index: {str(e)}")
            return False
    
    def _get_index_mapping(self) -> Dict[str, Any]:
        """Get Elasticsearch index mapping configuration."""
        return {
            "properties": {
                "content": {
                    "type": "text",
                    "analyzer": "standard",
                    "search_analyzer": "standard"
                },
                "metadata": {
                    "properties": {
                        "file_name": {
                            "type": "keyword",
                            "fields": {
                                "text": {
                                    "type": "text",
                                    "analyzer": "standard"
                                }
                            }
                        },
                        "file_type": {
                            "type": "keyword"
                        },
                        "file_size": {
                            "type": "long"
                        },
                        "created_at": {
                            "type": "date"
                        },
                        "modified_at": {
                            "type": "date"
                        },
                        "gcs_path": {
                            "type": "keyword"
                        },
                        "content_hash": {
                            "type": "keyword"
                        },
                        "page_count": {
                            "type": "integer"
                        },
                        "image_dimensions": {
                            "properties": {
                                "width": {"type": "integer"},
                                "height": {"type": "integer"}
                            }
                        },
                        "csv_columns": {
                            "type": "keyword"
                        },
                        "csv_rows": {
                            "type": "integer"
                        }
                    }
                },
                "indexed_at": {
                    "type": "date"
                }
            }
        }
    
    def _get_index_settings(self) -> Dict[str, Any]:
        """Get Elasticsearch index settings."""
        return {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": self.config.performance.index_refresh_interval,
            "analysis": {
                "analyzer": {
                    "custom_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "stop",
                            "snowball"
                        ]
                    }
                }
            }
        }
    
    async def index_document(self, document: Document) -> bool:
        """
        Index a single document.
        
        Args:
            document: Document to index
            
        Returns:
            True if indexing successful, False otherwise
        """
        try:
            doc_body = {
                "content": document.content,
                "metadata": document.metadata.model_dump(),
                "indexed_at": document.indexed_at.isoformat()
            }
            
            await self.client.index(
                index=self.index_name,
                id=document.id,
                document=doc_body
            )
            
            logger.debug(f"Indexed document: {document.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing document {document.id}: {str(e)}")
            return False
    
    async def bulk_index_documents(self, documents: List[Document]) -> Tuple[int, int]:
        """
        Bulk index multiple documents.
        
        Args:
            documents: List of documents to index
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        if not documents:
            return 0, 0
        
        try:
            # Prepare bulk operations
            operations = []
            for doc in documents:
                operation = {
                    "_index": self.index_name,
                    "_id": doc.id,
                    "_source": {
                        "content": doc.content,
                        "metadata": doc.metadata.model_dump(),
                        "indexed_at": doc.indexed_at.isoformat()
                    }
                }
                operations.append(operation)
            
            # Execute bulk operation
            success_count, failed_operations = await async_bulk(
                self.client,
                operations,
                chunk_size=self.config.performance.batch_size,
                max_chunk_bytes=10 * 1024 * 1024,  # 10MB chunks
                timeout=f"{self.config.performance.request_timeout}s"
            )
            
            failed_count = len(failed_operations)
            
            logger.info(f"Bulk indexed {success_count} documents, {failed_count} failed")
            
            if failed_operations:
                for failed_op in failed_operations:
                    logger.error(f"Failed to index document: {failed_op}")
            
            return success_count, failed_count
            
        except Exception as e:
            logger.error(f"Error in bulk indexing: {str(e)}")
            return 0, len(documents)
    
    async def search_documents(self, query: SearchQuery) -> SearchResponse:
        """
        Search for documents based on query.
        
        Args:
            query: Search query parameters
            
        Returns:
            Search response with results
        """
        start_time = datetime.utcnow()
        
        try:
            # Build Elasticsearch query
            es_query = self._build_search_query(query)
            
            # Execute search
            response = await self.client.search(
                index=self.index_name,
                **es_query
            )
            
            # Process results
            results = self._process_search_results(response, query)
            
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return SearchResponse(
                query=query.q,
                total_hits=response["hits"]["total"]["value"],
                results=results,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return SearchResponse(
                query=query.q,
                total_hits=0,
                results=[],
                execution_time_ms=execution_time
            )
    
    def _build_search_query(self, query: SearchQuery) -> Dict[str, Any]:
        """Build Elasticsearch query from search parameters."""
        # Base query structure
        es_query = {
            "size": query.limit,
            "min_score": query.min_score or self.config.search.min_score,
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query.q,
                                "fields": [
                                    "content^2",  # Boost content matches
                                    "metadata.file_name.text^1.5",
                                    "metadata.csv_columns^1.2"
                                ],
                                "type": "best_fields",
                                "fuzziness": "AUTO"
                            }
                        }
                    ],
                    "filter": []
                }
            },
            "highlight": {
                "fields": {
                    "content": {
                        "fragment_size": self.config.search.highlight_fragment_size,
                        "number_of_fragments": self.config.search.highlight_fragments,
                        "max_analyzed_offset": self.config.search.max_analyzed_offset
                    }
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
                "max_analyzed_offset": self.config.search.max_analyzed_offset
            },
            "sort": [
                "_score",
                {"metadata.modified_at": {"order": "desc"}}
            ]
        }
        
        # Add file type filter if specified
        if query.file_type:
            es_query["query"]["bool"]["filter"].append({
                "term": {"metadata.file_type": query.file_type.value}
            })
        
        return es_query
    
    def _process_search_results(self, response: Dict[str, Any], query: SearchQuery) -> List[SearchResult]:
        """Process Elasticsearch response into SearchResult objects."""
        results = []
        
        for hit in response["hits"]["hits"]:
            metadata = hit["_source"]["metadata"]
            
            # Extract highlights
            highlights = []
            if "highlight" in hit and "content" in hit["highlight"]:
                highlights = hit["highlight"]["content"]
            
            # Create search result
            result = SearchResult(
                document_id=hit["_id"],
                file_name=metadata["file_name"],
                file_type=metadata["file_type"],
                gcs_url=f"https://storage.googleapis.com/{self.config.gcs.bucket_name}/{metadata['gcs_path']}",
                score=hit["_score"],
                highlights=highlights,
                metadata={
                    "file_size": metadata.get("file_size"),
                    "created_at": metadata.get("created_at"),
                    "page_count": metadata.get("page_count"),
                    "csv_rows": metadata.get("csv_rows")
                }
            )
            
            results.append(result)
        
        return results
    
    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the index.
        
        Args:
            document_id: ID of the document to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            await self.client.delete(
                index=self.index_name,
                id=document_id
            )
            
            logger.info(f"Deleted document from index: {document_id}")
            return True
            
        except NotFoundError:
            logger.warning(f"Document not found for deletion: {document_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            return False
    
    async def get_indexing_stats(self) -> IndexingStats:
        """
        Get statistics about the indexed documents.
        
        Returns:
            IndexingStats object with current statistics
        """
        try:
            # Get total document count
            count_response = await self.client.count(index=self.index_name)
            total_documents = count_response["count"]
            
            # Get aggregations for file types and sizes
            aggs_query = {
                "size": 0,
                "aggs": {
                    "file_types": {
                        "terms": {
                            "field": "metadata.file_type"
                        }
                    },
                    "total_size": {
                        "sum": {
                            "field": "metadata.file_size"
                        }
                    },
                    "last_indexed": {
                        "max": {
                            "field": "indexed_at"
                        }
                    }
                }
            }
            
            aggs_response = await self.client.search(
                index=self.index_name,
                **aggs_query
            )
            
            # Process aggregation results
            file_type_buckets = aggs_response["aggregations"]["file_types"]["buckets"]
            documents_by_type = {bucket["key"]: bucket["doc_count"] for bucket in file_type_buckets}
            
            total_size_bytes = aggs_response["aggregations"]["total_size"]["value"]
            total_size_mb = total_size_bytes / (1024 * 1024) if total_size_bytes else 0
            
            # Handle last_indexed safely
            last_indexed_agg = aggs_response["aggregations"]["last_indexed"]
            last_indexed = None
            if last_indexed_agg["value"] is not None:
                last_indexed_str = last_indexed_agg.get("value_as_string")
                if last_indexed_str:
                    last_indexed = datetime.fromisoformat(last_indexed_str.replace('Z', '+00:00'))
                else:
                    # Fallback to value if value_as_string is not available
                    last_indexed = datetime.fromtimestamp(last_indexed_agg["value"] / 1000)
            
            return IndexingStats(
                total_documents=total_documents,
                documents_by_type=documents_by_type,
                total_size_mb=round(total_size_mb, 2),
                last_indexed=last_indexed,
                indexing_errors=0  # This could be tracked separately
            )
            
        except Exception as e:
            logger.error(f"Error getting indexing stats: {str(e)}")
            return IndexingStats(
                total_documents=0,
                documents_by_type={},
                total_size_mb=0.0,
                last_indexed=None,
                indexing_errors=1
            )
    
    async def refresh_index(self) -> bool:
        """
        Manually refresh the index to make recent changes searchable.
        
        Returns:
            True if refresh successful, False otherwise
        """
        try:
            await self.client.indices.refresh(index=self.index_name)
            logger.info(f"Refreshed index: {self.index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing index: {str(e)}")
            return False
    
    async def health_check(self) -> bool:
        """
        Check if Elasticsearch service is healthy.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Check cluster health
            health = await self.client.cluster.health()
            status = health["status"]
            
            # Check if index exists
            index_exists_response = await self.client.indices.exists(index=self.index_name)
            index_exists = index_exists_response.body if hasattr(index_exists_response, 'body') else bool(index_exists_response)
            
            return status in ["green", "yellow"] and index_exists
            
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {str(e)}")
            return False
    
    async def close(self) -> None:
        """Close the Elasticsearch client."""
        if self._client:
            await self._client.close()
    
    async def clear_index(self) -> bool:
        """
        Clear all documents from the index.
        
        Returns:
            True if clearing successful, False otherwise
        """
        try:
            # Delete all documents in the index
            await self.client.delete_by_query(
                index=self.index_name,
                body={
                    "query": {
                        "match_all": {}
                    }
                }
            )
            
            # Refresh the index to ensure changes are visible
            await self.refresh_index()
            
            logger.info(f"Cleared all documents from index: {self.index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing index: {str(e)}")
            return False
