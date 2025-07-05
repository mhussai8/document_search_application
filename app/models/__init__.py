"""
Data models for the document search application.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class FileType(str, Enum):
    """Supported file types."""
    TXT = "txt"
    CSV = "csv"
    PDF = "pdf"
    PNG = "png"


class DocumentMetadata(BaseModel):
    """Document metadata model."""
    
    file_name: str = Field(..., description="Original file name")
    file_type: FileType = Field(..., description="File type/extension")
    file_size: int = Field(..., description="File size in bytes")
    created_at: datetime = Field(..., description="File creation timestamp")
    modified_at: datetime = Field(..., description="Last modified timestamp")
    gcs_path: str = Field(..., description="Google Cloud Storage path")
    content_hash: str = Field(..., description="Content hash for deduplication")
    
    # Format-specific metadata
    page_count: Optional[int] = Field(None, description="Number of pages (PDF)")
    image_dimensions: Optional[Dict[str, int]] = Field(None, description="Image dimensions (PNG)")
    csv_columns: Optional[List[str]] = Field(None, description="CSV column names")
    csv_rows: Optional[int] = Field(None, description="Number of CSV rows")


class Document(BaseModel):
    """Main document model."""
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    id: str = Field(..., description="Unique document identifier")
    metadata: DocumentMetadata = Field(..., description="Document metadata")
    content: str = Field(..., description="Extracted text content")
    indexed_at: datetime = Field(default_factory=datetime.utcnow, description="Indexing timestamp")


class SearchQuery(BaseModel):
    """Search query model."""
    
    q: str = Field(..., description="Search query string", min_length=1)
    limit: int = Field(default=10, description="Maximum number of results", ge=1, le=100)
    file_type: Optional[FileType] = Field(None, description="Filter by file type")
    min_score: Optional[float] = Field(None, description="Minimum relevance score", ge=0.0, le=1.0)


class SearchResult(BaseModel):
    """Individual search result model."""
    
    document_id: str = Field(..., description="Document identifier")
    file_name: str = Field(..., description="Original file name")
    file_type: FileType = Field(..., description="File type")
    gcs_url: HttpUrl = Field(..., description="Google Cloud Storage HTTP URL")
    score: float = Field(..., description="Relevance score")
    highlights: List[str] = Field(default_factory=list, description="Text highlights")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SearchResponse(BaseModel):
    """Search response model."""
    
    query: str = Field(..., description="Original search query")
    total_hits: int = Field(..., description="Total number of matching documents")
    results: List[SearchResult] = Field(..., description="Search results")
    execution_time_ms: int = Field(..., description="Query execution time in milliseconds")


class IndexingStats(BaseModel):
    """Indexing statistics model."""
    
    total_documents: int = Field(..., description="Total indexed documents")
    documents_by_type: Dict[FileType, int] = Field(..., description="Documents grouped by type")
    total_size_mb: float = Field(..., description="Total size of indexed documents in MB")
    last_indexed: Optional[datetime] = Field(None, description="Last indexing timestamp")
    indexing_errors: int = Field(default=0, description="Number of indexing errors")


class HealthStatus(BaseModel):
    """Application health status model."""
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    services: Dict[str, str] = Field(..., description="Individual service statuses")
    version: str = Field(..., description="Application version")


class ProcessingStatus(BaseModel):
    """Document processing status model."""
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    document_id: str = Field(..., description="Document identifier")
    status: str = Field(..., description="Processing status")
    progress: float = Field(..., description="Processing progress (0-100)", ge=0.0, le=100.0)
    message: Optional[str] = Field(None, description="Status message")
    started_at: datetime = Field(..., description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Processing completion time")
