# Technology Stack

## Core Framework
- **FastAPI**: Modern Python web framework with automatic OpenAPI documentation
- **Python 3.11+**: Required Python version for modern async features
- **Uvicorn**: ASGI server for production deployment

## Database & ORM
- **PostgreSQL**: Primary database via Supabase
- **SQLAlchemy 2.0+**: Modern ORM with async support
- **Alembic**: Database migrations management
- **Supabase**: Hosted PostgreSQL with built-in auth and real-time features

## Security & Encryption
- **Cryptography**: Field-level encryption for sensitive data (phone numbers, names)
- **Python-JOSE**: JWT token handling
- **Passlib**: Password hashing with bcrypt
- **HMAC-SHA256**: Webhook signature validation

## External Integrations
- **Siren AI Toolkit**: WhatsApp/SMS messaging platform
- **Sarvam API**: Voice message processing
- **Gemini API**: Image and vision processing
- **LiteLLM**: Text processing and AI orchestration
- **HTTPX**: Async HTTP client for external API calls

## Development Tools
- **Poetry**: Dependency management and packaging
- **Black**: Code formatting (88 char line length)
- **Ruff**: Fast Python linter
- **MyPy**: Static type checking
- **Pytest**: Testing framework with async support

## Common Commands

### Development Setup
```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Run development server
poetry run python -m app.main
# or
python -m app.main
```

### Database Management
```bash
# Run migrations
poetry run alembic upgrade head

# Create new migration
poetry run alembic revision --autogenerate -m "description"

# Database CLI commands
poetry run db-manage --help
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app

# Run specific test file
poetry run pytest tests/test_conversation_state.py -v
```

### Code Quality
```bash
# Format code
poetry run black .

# Lint code
poetry run ruff check .

# Type checking
poetry run mypy app/
```

## Configuration Management
- **Pydantic Settings**: Environment-based configuration
- **Environment Variables**: All secrets and config via .env files
- **Settings Validation**: Automatic validation of configuration on startup

## Architecture Patterns
- **Clean Architecture**: Separation of concerns with interfaces
- **Repository Pattern**: Data access abstraction
- **Factory Pattern**: Dependency injection and service creation
- **State Machine**: Conversation flow management
- **Async/Await**: Non-blocking I/O throughout the application