#!/usr/bin/env python3
"""
Bill Splitting Agent server startup script
"""
import sys
import os
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """Main entry point for the server"""
    try:
        # Import after path setup
        from app.core.config import settings, validate_configuration
        from app.utils.logging import setup_logging
        
        # Setup logging first
        setup_logging()
        logger = logging.getLogger(__name__)
        
        # Validate configuration
        logger.info("Validating configuration...")
        validate_configuration()
        
        # Import and run the application
        import uvicorn
        from app.main import app
        
        # Get uvicorn configuration
        uvicorn_config = settings.get_uvicorn_config()
        
        logger.info(f"Starting Bill Splitting Agent server...")
        logger.info(f"Environment: {settings.environment}")
        logger.info(f"Debug mode: {settings.debug}")
        logger.info(f"Server configuration: {uvicorn_config}")
        
        # Start the server
        uvicorn.run(
            "app.main:app",
            **uvicorn_config
        )
        
    except Exception as e:
        print(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()