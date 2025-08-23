# Project Structure

## Directory Organization

```
app/
├── __init__.py
├── main.py                 # FastAPI application entry point
├── api/                    # API routes and endpoints
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       └── webhooks.py     # Siren webhook handlers
├── core/                   # Core application components
│   ├── __init__.py
│   ├── config.py          # Pydantic settings and configuration
│   └── database.py        # Database connection and setup
├── models/                 # Data models and schemas
│   ├── __init__.py
│   ├── enums.py           # Application enums and constants
│   ├── schemas.py         # Pydantic models for API/validation
│   └── database.py        # SQLAlchemy ORM models
├── interfaces/             # Abstract interfaces (contracts)
│   ├── __init__.py
│   ├── repositories.py    # Repository interface definitions
│   └── services.py        # Service interface definitions
├── services/              # Business logic services
│   ├── __init__.py
│   ├── communication_service.py  # Message delivery service
│   ├── conversation_factory.py   # Dependency injection factory
│   ├── conversation_manager.py   # Main conversation orchestrator
│   ├── error_handler.py          # Error handling and recovery
│   ├── siren_client.py           # Siren API client
│   ├── state_machine.py          # Conversation state machine
│   └── step_handlers.py          # Individual step processors
├── repositories/          # Data access layer implementations
│   └── __init__.py
├── database/              # Database utilities and management
│   ├── __init__.py
│   ├── cli.py            # Database CLI commands
│   ├── encryption.py     # Field-level encryption utilities
│   ├── factory.py        # Database factory and connection management
│   ├── migrations.py     # Migration utilities
│   └── repositories.py   # Repository implementations
└── utils/                 # Utility functions and helpers
    ├── __init__.py
    └── logging.py         # Logging configuration
```

## Key Architectural Principles

### Clean Architecture Layers
- **API Layer** (`api/`): HTTP endpoints and request/response handling
- **Service Layer** (`services/`): Business logic and orchestration
- **Repository Layer** (`repositories/`, `database/`): Data access and persistence
- **Model Layer** (`models/`): Data structures and validation
- **Interface Layer** (`interfaces/`): Abstract contracts between layers

### Naming Conventions
- **Files**: Snake_case for Python files (`conversation_manager.py`)
- **Classes**: PascalCase (`ConversationManager`, `BillParticipant`)
- **Functions/Methods**: Snake_case (`process_message`, `get_conversation_state`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_RETRY_ATTEMPTS`, `SESSION_TIMEOUT`)
- **Database Tables**: Snake_case (`conversation_states`, `bill_participants`)

### Module Organization
- **Single Responsibility**: Each module has a clear, focused purpose
- **Interface Segregation**: Separate interfaces for different concerns
- **Dependency Injection**: Services receive dependencies via constructor
- **Factory Pattern**: Centralized object creation and wiring

## Configuration Files

### Root Level
- `pyproject.toml`: Poetry configuration, dependencies, and tool settings
- `alembic.ini`: Database migration configuration
- `.env.example`: Template for environment variables
- `.gitignore`: Git ignore patterns for Python projects

### Database Migrations
```
alembic/
├── env.py              # Alembic environment configuration
├── script.py.mako      # Migration script template
└── versions/           # Individual migration files
    └── 001_initial_schema.py
```

### Testing Structure
```
tests/
├── test_conversation_integration.py  # Integration tests
├── test_conversation_state.py        # Unit tests for state management
├── test_database_setup.py           # Database setup tests
└── test_siren_integration.py        # Siren API integration tests
```

## Import Conventions

### Absolute Imports
Always use absolute imports from the app root:
```python
from app.services.conversation_manager import ConversationManager
from app.models.database import User, Bill
from app.interfaces.repositories import ConversationRepositoryInterface
```

### Interface Dependencies
Services depend on interfaces, not concrete implementations:
```python
from app.interfaces.repositories import ConversationRepositoryInterface
from app.interfaces.services import CommunicationServiceInterface
```

### Circular Import Prevention
- Interfaces in separate modules from implementations
- Factory pattern for dependency injection
- Type hints with `TYPE_CHECKING` for forward references

## File Responsibilities

### Core Files
- `main.py`: Application startup, lifespan events, route registration
- `config.py`: Environment-based configuration with validation
- `database.py`: Database connection, session management, initialization

### Service Layer
- `conversation_manager.py`: Main orchestrator for conversation flow
- `state_machine.py`: State transition logic and validation
- `step_handlers.py`: Individual step processing logic
- `error_handler.py`: Error classification and recovery strategies

### Data Layer
- `database.py` (models): SQLAlchemy ORM models with encryption
- `schemas.py`: Pydantic models for API validation
- `repositories.py`: Data access implementations
- `encryption.py`: Field-level encryption utilities

## Documentation Structure
```
docs/
└── SIREN_INTEGRATION.md    # Integration-specific documentation

examples/
└── siren_integration_example.py  # Usage examples
```

## Environment Management
- Development: `.env` file with local settings
- Production: Environment variables set by deployment system
- Testing: Separate test database configuration
- Secrets: Never committed to version control