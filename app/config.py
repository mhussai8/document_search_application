"""
Configuration management for the document search application.
"""

import os
import yaml
from typing import List, Optional, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application configuration."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4


class GCSConfig(BaseSettings):
    """Google Cloud Storage configuration."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    bucket_name: str = Field(..., description="GCS bucket name")
    project_id: str = Field(..., description="GCP project ID")
    credentials_path: Optional[str] = Field(None, description="Path to service account JSON")


class ElasticsearchConfig(BaseSettings):
    """Elasticsearch configuration."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    host: str = "localhost"
    port: int = 9200
    username: str = ""
    password: str = ""
    index_name: str = "documents"
    max_retries: int = 3
    timeout: int = 30


class DocumentProcessingConfig(BaseSettings):
    """Document processing configuration."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    max_file_size_mb: int = 8
    supported_formats: List[str] = ["txt", "csv", "pdf", "png"]
    
    class OCRConfig(BaseSettings):
        model_config = SettingsConfigDict(extra="allow")
        language: str = "eng"
        dpi: int = 300
    
    class PDFConfig(BaseSettings):
        model_config = SettingsConfigDict(extra="allow")
        max_pages: int = 100
    
    class CSVConfig(BaseSettings):
        model_config = SettingsConfigDict(extra="allow")
        max_rows: int = 10000
    
    ocr: OCRConfig = OCRConfig()
    pdf: PDFConfig = PDFConfig()
    csv: CSVConfig = CSVConfig()


class SearchConfig(BaseSettings):
    """Search configuration."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    default_limit: int = 10
    max_limit: int = 100
    min_score: float = 0.1
    highlight_fragments: int = 3
    highlight_fragment_size: int = 150
    max_analyzed_offset: int = 1000000  # 1MB limit for highlighting large documents


class PerformanceConfig(BaseSettings):
    """Performance and scaling configuration."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    max_concurrent_downloads: int = 10
    batch_size: int = 50
    index_refresh_interval: str = "5s"
    request_timeout: int = 30


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    level: str = "INFO"
    format: str = "json"
    file: str = "logs/app.log"
    max_size_mb: int = 100
    backup_count: int = 5


class SecurityConfig(BaseSettings):
    """Security configuration."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    enable_cors: bool = True
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    class RateLimitConfig(BaseSettings):
        model_config = SettingsConfigDict(extra="allow")
        requests_per_minute: int = 60
        burst: int = 10
    
    rate_limit: RateLimitConfig = RateLimitConfig()


class Config(BaseSettings):
    """Main application configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"  # Allow extra fields from YAML
    )
    
    app: AppConfig = AppConfig()
    gcs: GCSConfig
    elasticsearch: ElasticsearchConfig = ElasticsearchConfig()
    document_processing: DocumentProcessingConfig = DocumentProcessingConfig()
    search: SearchConfig = SearchConfig()
    performance: PerformanceConfig = PerformanceConfig()
    logging: LoggingConfig = LoggingConfig()
    security: SecurityConfig = SecurityConfig()
    
    @classmethod
    def from_yaml(cls, config_path: str) -> "Config":
        """Load configuration from YAML file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Expand environment variables
        config_data = cls._expand_env_vars(config_data)
        
        return cls(**config_data)
    
    @staticmethod
    def _expand_env_vars(obj: Any) -> Any:
        """Recursively expand environment variables in configuration."""
        if isinstance(obj, dict):
            return {key: Config._expand_env_vars(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [Config._expand_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            return os.path.expandvars(obj)
        else:
            return obj


# Global configuration instance
config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global config
    if config is None:
        config_path = os.getenv("CONFIG_PATH", "config/config.yml")
        config = Config.from_yaml(config_path)
    return config


def set_config(new_config: Config) -> None:
    """Set the global configuration instance."""
    global config
    config = new_config
