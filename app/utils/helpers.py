"""
Utility functions and helpers.
"""

import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any


def calculate_file_hash(content: bytes, algorithm: str = "sha256") -> str:
    """
    Calculate hash of file content.
    
    Args:
        content: File content as bytes
        algorithm: Hash algorithm to use
        
    Returns:
        Hexadecimal hash string
    """
    hash_func = getattr(hashlib, algorithm)()
    hash_func.update(content)
    return hash_func.hexdigest()


def get_file_mime_type(file_path: str) -> Optional[str]:
    """
    Get MIME type of a file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MIME type string or None
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing unsafe characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove path separators and other unsafe characters
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    
    for char in unsafe_chars:
        sanitized = sanitized.replace(char, '_')
    
    return sanitized


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def extract_file_extension(filename: str) -> str:
    """
    Extract file extension from filename.
    
    Args:
        filename: File name
        
    Returns:
        File extension without dot
    """
    return Path(filename).suffix.lower().lstrip('.')


def validate_search_query(query: str) -> Dict[str, Any]:
    """
    Validate and analyze search query.
    
    Args:
        query: Search query string
        
    Returns:
        Dictionary with validation results
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "suggestions": []
    }
    
    # Check minimum length
    if len(query.strip()) < 1:
        result["valid"] = False
        result["errors"].append("Query cannot be empty")
    
    # Check maximum length
    if len(query) > 1000:
        result["valid"] = False
        result["errors"].append("Query too long (max 1000 characters)")
    
    # Check for potential issues
    if query.strip() != query:
        result["warnings"].append("Leading/trailing whitespace will be ignored")
    
    if len(query.split()) == 1 and len(query) < 3:
        result["suggestions"].append("Consider using longer or more specific terms")
    
    return result


def build_gcs_url(bucket_name: str, object_name: str, public: bool = True) -> str:
    """
    Build Google Cloud Storage URL for an object.
    
    Args:
        bucket_name: GCS bucket name
        object_name: Object name/path
        public: Whether to build public URL
        
    Returns:
        GCS URL
    """
    if public:
        return f"https://storage.googleapis.com/{bucket_name}/{object_name}"
    else:
        return f"gs://{bucket_name}/{object_name}"


def parse_gcs_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parse GCS URL to extract bucket and object name.
    
    Args:
        url: GCS URL
        
    Returns:
        Dictionary with bucket and object or None
    """
    if url.startswith("gs://"):
        # gs://bucket/object/path
        parts = url[5:].split("/", 1)
        if len(parts) == 2:
            return {"bucket": parts[0], "object": parts[1]}
    elif "storage.googleapis.com" in url:
        # https://storage.googleapis.com/bucket/object/path
        try:
            path_part = url.split("storage.googleapis.com/")[1]
            parts = path_part.split("/", 1)
            if len(parts) == 2:
                return {"bucket": parts[0], "object": parts[1]}
        except IndexError:
            pass
    
    return None
