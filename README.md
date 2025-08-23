# Bill Splitting Agent

An intelligent WhatsApp-based bill splitting system that helps users split bills among friends and family using AI-powered text, voice, and image processing.

## Project Structure

```
app/
├── __init__.py
├── main.py                 # FastAPI application entry point
├── api/                    # API routes and endpoints
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       ├── webhooks.py     # Siren webhook handlers (active)
│       └── admin.py        # Admin utilities (no auth for now)
├── core/                   # Core application components
│   ├── __init__.py
│   ├── config.py          # Application configuration
│   └── database.py        # Database connection and setup
├── models/                 # Data models and schemas
│   ├── __init__.py
│   ├── enums.py           # Application enums
│   ├── schemas.py         # Pydantic models
│   └── database.py        # SQLAlchemy models
├── interfaces/             # Abstract interfaces
│   ├── __init__.py
│   ├── repositories.py    # Repository interfaces
│   └── services.py        # Service interfaces
├── services/              # Business logic services
│   └── __init__.py
├── repositories/          # Data access layer
│   └── __init__.py
└── utils/                 # Utility functions
    ├── __init__.py
    └── logging.py         # Logging configuration
```

## Features

- Multi-modal input processing (text, voice, image)
- Intelligent bill extraction using AI services
- Automated bill splitting calculations
- Contact management and deduplication
- UPI payment link generation
- WhatsApp and SMS integration via Siren AI Toolkit
- Payment tracking and confirmation
- Conversation state management
- Comprehensive error handling

## Setup

1. Install Poetry (if not already installed):

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install dependencies:

   ```bash
   poetry install
   ```

3. Copy environment variables:

   ```bash
   cp .env.example .env
   ```

4. Configure your environment variables in `.env`

5. Run the application:

   ```bash
   poetry run python -m app.main
   ```

   Or activate the virtual environment and run directly:

   ```bash
   poetry shell
   python -m app.main
   ```

## API Endpoints

- `GET /health` - Health check endpoint
- `POST /api/v1/webhooks/siren/message` - Siren message webhook
- `POST /api/v1/webhooks/siren/delivery-status` - Siren delivery status webhook

## Environment Variables

See `.env.example` for required configuration variables including:

- **DATABASE_URL** (PostgreSQL DSN; Supabase used only as DB)
- **SARVAM_API_KEY**, **GEMINI_API_KEY**
- **SIREN_API_KEY**, **SIREN_WEBHOOK_SECRET**
- **ENCRYPTION_KEY** (>=32 chars)

## Architecture

The application follows a clean architecture pattern with:

- **API Layer**: FastAPI routes and webhook handlers
- **Service Layer**: Business logic and orchestration
- **Repository Layer**: Data access and persistence
- **Model Layer**: Data structures and validation
- **Interface Layer**: Abstract contracts for services and repositories

## Next Steps

This foundational setup provides the core structure for implementing the bill splitting agent. The next tasks will involve:

1. Database models and migrations
2. Siren integration layer
3. Conversation state management
4. AI service integrations
5. Bill processing logic
