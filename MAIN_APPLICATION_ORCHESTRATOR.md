# Main Application Orchestrator

This document describes the main application orchestrator implementation for the Bill Splitting Agent, which integrates all services into a cohesive FastAPI application.

## Overview

The main application orchestrator (`app/main.py`) serves as the central entry point that:

1. **Initializes all services** and their dependencies
2. **Configures the FastAPI application** with all routes and middleware
3. **Manages application lifecycle** (startup and shutdown)
4. **Provides comprehensive health checks** and monitoring
5. **Handles configuration validation** and environment management

## Architecture

### Application Structure

```
FastAPI Application
├── Middleware Layer
│   └── Error Handling Middleware
├── API Routes
│   ├── Webhooks (/api/v1/webhooks/)
│   ├── Bills Management (/api/v1/bills/)
│   └── Admin & Monitoring (/api/v1/admin/)
├── Health & Monitoring
│   ├── Basic Health Check (/health)
│   ├── Detailed Health Check (/health/detailed)
│   ├── Metrics Endpoint (/metrics)
│   └── Error Summary (/errors/summary)
└── Service Integration
    ├── Conversation Factory
    ├── Database Repositories
    ├── AI Services
    └── External Integrations
```

### Service Initialization Flow

1. **Configuration Validation**: Validates all required environment variables and settings
2. **Database Initialization**: Sets up database connections and runs migrations
3. **Repository Creation**: Instantiates all database repositories
4. **Conversation Factory Setup**: Initializes the conversation factory with dependencies
5. **Webhook Handler Integration**: Connects webhook handlers to conversation manager
6. **Health Check Registration**: Registers all health check functions
7. **Error Monitoring Setup**: Initializes error monitoring and logging

## Key Components

### 1. Application Lifecycle Management

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events with complete service initialization"""
    # Startup sequence
    - Configuration validation
    - Database initialization
    - Service initialization
    - Webhook handler setup
    - Health check registration
    
    # Shutdown sequence
    - Service cleanup
    - Conversation state cleanup
    - Resource cleanup
```

### 2. Service Integration

The orchestrator integrates all major services:

- **Conversation Manager**: Handles multi-step bill splitting conversations
- **AI Services**: Sarvam (speech), Gemini (vision), LiteLLM (text processing)
- **Communication Service**: Siren integration for WhatsApp/SMS
- **Database Services**: All repository implementations
- **Payment Services**: UPI generation and payment tracking
- **Error Handling**: Comprehensive error monitoring and recovery

### 3. API Endpoints

#### Webhook Endpoints (`/api/v1/webhooks/`)
- `POST /siren/message` - Receive messages from Siren
- `POST /siren/delivery-status` - Delivery status updates
- `GET /siren/health` - Siren integration health check

#### Bill Management (`/api/v1/bills/`)
- `GET /user/{phone_number}` - Get user's bills
- `GET /{bill_id}` - Get bill details
- `GET /{bill_id}/status` - Get payment status
- `POST /{bill_id}/reminders` - Send payment reminders
- `POST /{bill_id}/participants/{phone}/confirm-payment` - Confirm payment

#### Admin & Monitoring (`/api/v1/admin/`)
- `GET /health/comprehensive` - Comprehensive health check
- `GET /metrics/system` - System metrics
- `GET /errors/detailed` - Error reports
- `POST /maintenance/cleanup` - Maintenance tasks
- `GET /configuration` - Configuration status
- `POST /services/restart` - Service restart

### 4. Health Monitoring

The application provides multiple levels of health monitoring:

#### Basic Health Check (`/health`)
- Service status
- Environment information
- Timestamp

#### Detailed Health Check (`/health/detailed`)
- Database connectivity
- Memory usage
- External service status
- Conversation manager status
- Repository health

#### System Metrics (`/metrics`)
- Application performance metrics
- Payment request statistics
- Active conversation counts
- Error rates and patterns

### 5. Configuration Management

Comprehensive configuration system with:

- **Environment-based settings** with validation
- **Security configuration** (encryption keys, JWT secrets)
- **Service timeouts and retry policies**
- **Database connection pooling**
- **Rate limiting settings**
- **AI service configuration**

## Environment Configuration

### Required Environment Variables

```bash
# Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Siren AI Toolkit
SIREN_API_KEY=your_siren_api_key
SIREN_WEBHOOK_SECRET=your_webhook_secret

# AI Services
SARVAM_API_KEY=your_sarvam_key
GEMINI_API_KEY=your_gemini_key

# Security
ENCRYPTION_KEY=your_32_char_encryption_key
JWT_SECRET=your_32_char_jwt_secret
```

### Optional Configuration

```bash
# Application
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# Timeouts and Limits
AI_SERVICE_TIMEOUT=30
WEBHOOK_TIMEOUT=30
CONVERSATION_TIMEOUT_HOURS=24
RATE_LIMIT_REQUESTS=100
```

## Running the Application

### Method 1: Direct Python Execution
```bash
python app/main.py
```

### Method 2: Using the Startup Script
```bash
python run_server.py
```

### Method 3: Using Uvicorn Directly
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Error Handling

The orchestrator implements comprehensive error handling:

### 1. Startup Error Handling
- Configuration validation errors
- Database connection failures
- Service initialization failures
- Dependency injection errors

### 2. Runtime Error Handling
- Webhook processing errors
- Conversation management errors
- Database operation failures
- External service timeouts

### 3. Error Recovery
- Automatic service restart capabilities
- Graceful degradation for external service failures
- Conversation state recovery
- Database connection retry logic

## Monitoring and Observability

### 1. Health Checks
- Automated health monitoring for all services
- Configurable health check intervals
- Detailed health status reporting

### 2. Metrics Collection
- Request/response metrics
- Error rate tracking
- Performance monitoring
- Resource usage statistics

### 3. Error Monitoring
- Centralized error logging
- Error categorization and analysis
- Alert generation for critical errors
- Error trend analysis

## Security Features

### 1. Authentication & Authorization
- Admin endpoint protection with JWT tokens
- Webhook signature validation
- User data access control

### 2. Data Protection
- Field-level encryption for sensitive data
- Secure configuration management
- Input validation and sanitization

### 3. Rate Limiting
- Configurable rate limits per endpoint
- User-based rate limiting
- DDoS protection

## Deployment Considerations

### 1. Production Configuration
- Disable debug mode and API documentation
- Configure proper logging levels
- Set up monitoring and alerting
- Configure load balancing

### 2. Scaling
- Horizontal scaling with multiple workers
- Database connection pooling
- Caching strategies
- Queue-based processing for heavy operations

### 3. Monitoring
- Health check endpoints for load balancers
- Metrics export for monitoring systems
- Log aggregation and analysis
- Performance monitoring

## Integration Points

### 1. Siren AI Toolkit
- Webhook message reception
- WhatsApp/SMS message sending
- Delivery status tracking
- Signature validation

### 2. AI Services
- Sarvam for speech-to-text
- Gemini for image processing and text analysis
- LiteLLM for text processing orchestration

### 3. Database
- Supabase PostgreSQL integration
- Repository pattern implementation
- Connection pooling and retry logic

### 4. Payment Systems
- UPI deeplink generation
- Payment confirmation tracking
- Reminder system integration

## Testing

The orchestrator supports comprehensive testing:

### 1. Unit Tests
- Individual service testing
- Configuration validation testing
- Error handling testing

### 2. Integration Tests
- End-to-end conversation flow testing
- Database integration testing
- External service integration testing

### 3. Health Check Testing
- Automated health check validation
- Service dependency testing
- Failure scenario testing

## Maintenance

### 1. Regular Maintenance Tasks
- Conversation state cleanup
- Error log rotation
- Database maintenance
- Performance optimization

### 2. Monitoring Tasks
- Health check monitoring
- Error rate analysis
- Performance trend analysis
- Resource usage monitoring

This main application orchestrator provides a robust, scalable, and maintainable foundation for the Bill Splitting Agent system, integrating all components into a cohesive and reliable service.