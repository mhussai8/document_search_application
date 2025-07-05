"""
Main FastAPI application for the document search service.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .config import get_config, set_config, Config
from .api import router
from .services import IndexingService, ElasticsearchService
from .utils.logging import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global services
indexing_service: IndexingService = None
elasticsearch_service: ElasticsearchService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Document Search Application")
    
    try:
        # Load configuration
        config_path = os.getenv("CONFIG_PATH", "config/config.yml")
        if not os.path.exists(config_path):
            logger.error(f"Configuration file not found: {config_path}")
            logger.info("Please ensure config/config.yml exists. Copy from config/config.example.yml if needed.")
            sys.exit(1)
        
        try:
            config = Config.from_yaml(config_path)
            set_config(config)
            logger.info(f"Loaded configuration from: {config_path}")
        except Exception as config_error:
            logger.error(f"Failed to load configuration: {str(config_error)}")
            logger.error("Please check your config/config.yml file format and content")
            sys.exit(1)
        
        # Initialize services
        global indexing_service, elasticsearch_service
        indexing_service = IndexingService()
        elasticsearch_service = ElasticsearchService()
        
        # Initialize Elasticsearch index
        try:
            es_initialized = await elasticsearch_service.initialize_index()
            if not es_initialized:
                logger.error("Failed to initialize Elasticsearch index")
                logger.error("Please ensure Elasticsearch is running at the configured location")
                # Don't exit in development, just warn
                logger.warning("Continuing without Elasticsearch - some features may not work")
            else:
                logger.info("Elasticsearch initialized successfully")
        except Exception as es_error:
            logger.error(f"Elasticsearch initialization error: {str(es_error)}")
            logger.warning("Continuing without Elasticsearch - some features may not work")
        
        logger.info("Services initialized successfully")
        
        # Optionally perform initial indexing
        if os.getenv("INITIAL_INDEX", "false").lower() == "true":
            logger.info("Performing initial indexing...")
            await indexing_service.initialize()
            await indexing_service.full_reindex()
            logger.info("Initial indexing completed")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        sys.exit(1)
    
    # Shutdown
    logger.info("Shutting down Document Search Application")
    
    try:
        if elasticsearch_service:
            await elasticsearch_service.close()
        
        if indexing_service:
            await indexing_service.cleanup()
        
        logger.info("Shutdown completed")
        
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    # Try to load configuration, use defaults if not available
    try:
        config = get_config()
    except Exception as e:
        logger.warning(f"Could not load config during app creation: {e}")
        # Create a minimal config for app startup
        from .config import AppConfig, SecurityConfig
        config = type('Config', (), {
            'app': AppConfig(),
            'security': SecurityConfig()
        })()
    
    # Create FastAPI app
    app = FastAPI(
        title=getattr(config.app, 'name', 'Document Search Application'),
        version=getattr(config.app, 'version', '1.0.0'),
        description="""
        A high-performance document search application that indexes and searches 
        documents from Google Cloud Storage using Elasticsearch, LangChain, and FastAPI.
        
        ## Features
        
        * **Multi-format Support**: Search across .csv, .txt, .pdf, and .png files
        * **Fast Search**: Sub-second response times with Elasticsearch
        * **Cloud Integration**: Google Cloud Storage document source
        * **RESTful API**: Clean and intuitive REST endpoints
        * **Scalable**: Handles thousands of documents and concurrent users
        
        ## Usage
        
        Use the `/search` endpoint to search for documents:
        
        ```
        GET /search?q=your-search-term&limit=10&file_type=pdf
        ```
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add middleware
    try:
        if hasattr(config, 'security') and getattr(config.security, 'enable_cors', True):
            cors_origins = getattr(config.security, 'cors_origins', ["http://localhost:3000"])
            app.add_middleware(
                CORSMiddleware,
                allow_origins=cors_origins,
                allow_credentials=True,
                allow_methods=["GET", "POST", "PUT", "DELETE"],
                allow_headers=["*"],
            )
    except Exception as e:
        logger.warning(f"Could not configure CORS middleware: {e}")
    
    # Add trusted host middleware for production
    try:
        if hasattr(config, 'app') and not getattr(config.app, 'debug', True):
            app.add_middleware(
                TrustedHostMiddleware,
                allowed_hosts=["*"]  # Configure appropriately for production
            )
    except Exception as e:
        logger.warning(f"Could not configure trusted host middleware: {e}")
    
    # Include API routes
    app.include_router(router, prefix="/api/v1")
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with application information."""
        try:
            config = get_config()
            return {
                "name": getattr(config.app, 'name', 'Document Search Application'),
                "version": getattr(config.app, 'version', '1.0.0'),
                "status": "running",
                "docs_url": "/docs",
                "health_url": "/api/v1/health"
            }
        except Exception:
            return {
                "name": "Document Search Application",
                "version": "1.0.0",
                "status": "running",
                "docs_url": "/docs",
                "health_url": "/api/v1/health"
            }
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Global exception handler for unhandled errors."""
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "type": type(exc).__name__
            }
        )
    
    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    try:
        config = get_config()
        host = getattr(config.app, 'host', '0.0.0.0')
        port = getattr(config.app, 'port', 8000)
        debug = getattr(config.app, 'debug', True)
        workers = getattr(config.app, 'workers', 1)
    except Exception:
        host = '0.0.0.0'
        port = 8000
        debug = True
        workers = 1
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=debug,
        workers=1 if debug else workers,
        log_level="info"
    )
