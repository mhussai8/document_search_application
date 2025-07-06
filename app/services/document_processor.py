"""
Document processing services for extracting text from various file formats.
"""

import asyncio
import hashlib
import io
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import pandas as pd
import pytesseract
from PIL import Image
from pypdf import PdfReader
import pdfplumber

from ..models import Document, DocumentMetadata, FileType
from ..config import get_config

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Document processing service for extracting text from various file formats.
    """
    
    def __init__(self):
        self.config = get_config()
        
    async def process_document(self, file_content: bytes, file_name: str, gcs_path: str) -> Optional[Document]:
        """
        Process a document and extract its content.
        
        Args:
            file_content: Raw file content as bytes
            file_name: Original file name
            gcs_path: Google Cloud Storage path
            
        Returns:
            Processed Document object or None if processing failed
        """
        try:
            # Validate file size
            file_size = len(file_content)
            max_size = self.config.document_processing.max_file_size_mb * 1024 * 1024
            
            if file_size > max_size:
                logger.warning(f"File {file_name} exceeds size limit: {file_size} bytes")
                return None
            
            # Determine file type
            file_type = self._get_file_type(file_name)
            if not file_type:
                logger.warning(f"Unsupported file type for {file_name}")
                return None
            
            # Extract content based on file type
            content, metadata_extra = await self._extract_content(file_content, file_type, file_name)
            
            if not content:
                logger.warning(f"No content extracted from {file_name}")
                return None
            
            # Create document metadata
            metadata = DocumentMetadata(
                file_name=file_name,
                file_type=file_type,
                file_size=file_size,
                created_at=datetime.utcnow(),
                modified_at=datetime.utcnow(),
                gcs_path=gcs_path,
                content_hash=self._calculate_hash(file_content),
                **metadata_extra
            )
            
            # Generate document ID
            doc_id = self._generate_document_id(gcs_path, metadata.content_hash)
            
            # Create document
            document = Document(
                id=doc_id,
                metadata=metadata,
                content=content
            )
            
            logger.info(f"Successfully processed document: {file_name}")
            return document
            
        except Exception as e:
            logger.error(f"Error processing document {file_name}: {str(e)}")
            return None
    
    def _get_file_type(self, file_name: str) -> Optional[FileType]:
        """Determine file type from file name."""
        extension = Path(file_name).suffix.lower().lstrip('.')
        
        if extension in self.config.document_processing.supported_formats:
            return FileType(extension)
        return None
    
    async def _extract_content(self, file_content: bytes, file_type: FileType, file_name: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract content from file based on its type.
        
        Returns:
            Tuple of (extracted_text, additional_metadata)
        """
        if file_type == FileType.TXT:
            return await self._extract_text_content(file_content)
        elif file_type == FileType.CSV:
            return await self._extract_csv_content(file_content)
        elif file_type == FileType.PDF:
            return await self._extract_pdf_content(file_content)
        elif file_type == FileType.PNG:
            return await self._extract_image_content(file_content)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    async def _extract_text_content(self, file_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """Extract content from text files."""
        try:
            # Try UTF-8 first, fallback to other encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    content = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # If all encodings fail, use UTF-8 with error replacement
                content = file_content.decode('utf-8', errors='replace')
            
            return content.strip(), {}
            
        except Exception as e:
            logger.error(f"Error extracting text content: {str(e)}")
            return "", {}
    
    async def _extract_csv_content(self, file_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """Extract content from CSV files."""
        try:
            # Read CSV into pandas DataFrame
            csv_file = io.StringIO(file_content.decode('utf-8'))
            df = pd.read_csv(csv_file, nrows=self.config.document_processing.csv.max_rows)
            
            # Extract meaningful content
            content_parts = []
            
            # Add column information
            columns = df.columns.tolist()
            content_parts.append(f"Columns: {', '.join(columns)}")
            
            # Add sample data (first few rows as text)
            sample_rows = min(5, len(df))
            for i in range(sample_rows):
                row_data = []
                for col in columns:
                    value = str(df.iloc[i][col])
                    row_data.append(f"{col}: {value}")
                content_parts.append(" | ".join(row_data))
            
            # Add all data as searchable text
            for col in columns:
                if df[col].dtype == 'object':  # Text columns
                    text_values = df[col].dropna().astype(str).tolist()
                    content_parts.extend(text_values)
            
            content = "\n".join(content_parts)
            
            metadata = {
                "csv_columns": columns,
                "csv_rows": len(df)
            }
            
            return content, metadata
            
        except Exception as e:
            logger.error(f"Error extracting CSV content: {str(e)}")
            return "", {}
    
    async def _extract_pdf_content(self, file_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """Extract content from PDF files using multiple methods."""
        try:
            pdf_file = io.BytesIO(file_content)
            content_parts = []
            page_count = 0
            
            # Try pdfplumber first (better for complex layouts)
            try:
                with pdfplumber.open(pdf_file) as pdf:
                    page_count = len(pdf.pages)
                    max_pages = min(page_count, self.config.document_processing.pdf.max_pages)
                    
                    for i in range(max_pages):
                        page = pdf.pages[i]
                        page_text = page.extract_text()
                        if page_text:
                            content_parts.append(page_text)
                            
            except Exception as e:
                logger.warning(f"pdfplumber failed, trying pypdf: {str(e)}")
                
                # Fallback to pypdf
                pdf_file.seek(0)
                reader = PdfReader(pdf_file)
                page_count = len(reader.pages)
                max_pages = min(page_count, self.config.document_processing.pdf.max_pages)
                
                for i in range(max_pages):
                    page = reader.pages[i]
                    page_text = page.extract_text()
                    if page_text:
                        content_parts.append(page_text)
            
            content = "\n\n".join(content_parts)
            
            metadata = {
                "page_count": page_count
            }
            
            return content.strip(), metadata
            
        except Exception as e:
            logger.error(f"Error extracting PDF content: {str(e)}")
            return "", {}
    
    async def _extract_image_content(self, file_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """Extract content from images using OCR."""
        try:
            # Load image
            image = Image.open(io.BytesIO(file_content))
            
            # Get image dimensions
            width, height = image.size
            
            # Perform OCR
            ocr_config = self.config.document_processing.ocr
            custom_config = f'--oem 3 --psm 6 -l {ocr_config.language}'
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Extract text using Tesseract
            text = pytesseract.image_to_string(
                image,
                config=custom_config
            )
            
            metadata = {
                "image_dimensions": {
                    "width": width,
                    "height": height
                }
            }
            
            return text.strip(), metadata
            
        except Exception as e:
            logger.error(f"Error extracting image content: {str(e)}")
            return "", {}
    
    def _calculate_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content).hexdigest()
    
    def _generate_document_id(self, gcs_path: str, content_hash: str) -> str:
        """Generate unique document ID."""
        combined = f"{gcs_path}:{content_hash}"
        return hashlib.md5(combined.encode()).hexdigest()


class BatchDocumentProcessor:
    """
    Batch processing service for handling multiple documents efficiently.
    """
    
    def __init__(self, max_concurrent: int = 10):
        self.processor = DocumentProcessor()
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(self, file_data: List[Tuple[bytes, str, str]]) -> List[Optional[Document]]:
        """
        Process multiple documents concurrently.
        
        Args:
            file_data: List of (file_content, file_name, gcs_path) tuples
            
        Returns:
            List of processed Documents (None for failed processing)
        """
        async def process_single(data):
            async with self.semaphore:
                file_content, file_name, gcs_path = data
                return await self.processor.process_document(file_content, file_name, gcs_path)
        
        tasks = [process_single(data) for data in file_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing document {file_data[i][1]}: {str(result)}")
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        return processed_results
