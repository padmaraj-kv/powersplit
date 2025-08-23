"""
Application configuration settings with comprehensive validation
"""
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings with environment variable support and validation"""
    
    # Database settings
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_key: str = Field(..., description="Supabase anon/service key")
    database_url: Optional[str] = Field(None, description="Direct database URL (optional)")
    
    # Siren AI Toolkit settings
    siren_api_key: str = Field(..., description="Siren API key")
    siren_webhook_secret: str = Field(..., description="Siren webhook secret for signature validation")
    siren_base_url: str = Field(default="https://api.siren.ai", description="Siren API base URL")
    
    # AI Service settings
    sarvam_api_key: str = Field(..., description="Sarvam AI API key for speech-to-text")
    gemini_api_key: str = Field(..., description="Google Gemini API key for vision and text processing")
    litellm_api_key: Optional[str] = Field(None, description="LiteLLM API key (optional)")
    
    # Application settings
    environment: str = Field(default="development", description="Application environment")
    debug: bool = Field(default=False, description="Debug mode flag")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of worker processes")
    
    # Security settings
    encryption_key: str = Field(..., description="AES encryption key for sensitive data")
    jwt_secret: str = Field(..., description="JWT secret for authentication")
    
    # Rate limiting settings
    rate_limit_requests: int = Field(default=100, description="Requests per minute per user")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")
    
    # Webhook settings
    webhook_timeout: int = Field(default=30, description="Webhook processing timeout in seconds")
    webhook_retry_attempts: int = Field(default=3, description="Number of webhook retry attempts")
    
    # AI Service timeouts
    ai_service_timeout: int = Field(default=30, description="AI service request timeout in seconds")
    ai_service_retry_attempts: int = Field(default=2, description="AI service retry attempts")
    
    # Database settings
    db_pool_size: int = Field(default=10, description="Database connection pool size")
    db_max_overflow: int = Field(default=20, description="Database connection pool overflow")
    db_pool_timeout: int = Field(default=30, description="Database connection timeout")
    
    # Conversation settings
    conversation_timeout_hours: int = Field(default=24, description="Conversation state timeout in hours")
    max_conversation_retries: int = Field(default=3, description="Maximum conversation retry attempts")
    
    # Payment settings
    upi_timeout_minutes: int = Field(default=30, description="UPI payment link timeout in minutes")
    payment_reminder_hours: int = Field(default=24, description="Hours before sending payment reminders")
    
    @validator('environment')
    def validate_environment(cls, v):
        """Validate environment setting"""
        allowed_environments = ['development', 'staging', 'production']
        if v not in allowed_environments:
            raise ValueError(f'Environment must be one of: {allowed_environments}')
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level setting"""
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed_levels:
            raise ValueError(f'Log level must be one of: {allowed_levels}')
        return v.upper()
    
    @validator('port')
    def validate_port(cls, v):
        """Validate port number"""
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v
    
    @validator('encryption_key')
    def validate_encryption_key(cls, v):
        """Validate encryption key length"""
        if len(v) < 32:
            raise ValueError('Encryption key must be at least 32 characters long')
        return v
    
    @validator('jwt_secret')
    def validate_jwt_secret(cls, v):
        """Validate JWT secret length"""
        if len(v) < 32:
            raise ValueError('JWT secret must be at least 32 characters long')
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == "development"
    
    @property
    def database_config(self) -> dict:
        """Get database configuration dictionary"""
        return {
            "pool_size": self.db_pool_size,
            "max_overflow": self.db_max_overflow,
            "pool_timeout": self.db_pool_timeout,
            "echo": self.debug and not self.is_production
        }
    
    @property
    def ai_service_config(self) -> dict:
        """Get AI service configuration dictionary"""
        return {
            "timeout": self.ai_service_timeout,
            "retry_attempts": self.ai_service_retry_attempts,
            "sarvam_api_key": self.sarvam_api_key,
            "gemini_api_key": self.gemini_api_key,
            "litellm_api_key": self.litellm_api_key
        }
    
    @property
    def siren_config(self) -> dict:
        """Get Siren configuration dictionary"""
        return {
            "api_key": self.siren_api_key,
            "webhook_secret": self.siren_webhook_secret,
            "base_url": self.siren_base_url,
            "timeout": self.webhook_timeout,
            "retry_attempts": self.webhook_retry_attempts
        }
    
    def get_uvicorn_config(self) -> dict:
        """Get Uvicorn server configuration"""
        return {
            "host": self.host,
            "port": self.port,
            "reload": self.debug and not self.is_production,
            "log_level": self.log_level.lower(),
            "workers": 1 if self.debug else self.workers,
            "access_log": self.debug
        }
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        validate_assignment = True


# Global settings instance
settings = Settings()


def validate_configuration():
    """Validate all configuration settings on startup"""
    try:
        # Test that all required settings are present
        required_settings = [
            'supabase_url', 'supabase_key', 'siren_api_key', 'siren_webhook_secret',
            'sarvam_api_key', 'gemini_api_key', 'encryption_key', 'jwt_secret'
        ]
        
        missing_settings = []
        for setting in required_settings:
            if not getattr(settings, setting, None):
                missing_settings.append(setting)
        
        if missing_settings:
            raise ValueError(f"Missing required configuration settings: {missing_settings}")
        
        # Log configuration status (without sensitive values)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Configuration validated successfully for environment: {settings.environment}")
        logger.info(f"Debug mode: {settings.debug}")
        logger.info(f"Log level: {settings.log_level}")
        
        return True
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Configuration validation failed: {e}")
        raise