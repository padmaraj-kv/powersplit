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
│       └── webhooks.py     # Webhook handlers (Siren/Twilio inbound only)
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

## API Surface (webhook-only)

- `POST /api/v1/webhooks/siren/message` - Siren message webhook
- `POST /api/v1/webhooks/siren/delivery-status` - Siren delivery status webhook
- `POST /api/v1/webhooks/twilio/whatsapp` - Twilio WhatsApp inbound (normalized)
- `GET /health` - Basic health

## Environment Variables

See `.env.example` for required configuration variables including:

- **DATABASE_URL** (PostgreSQL DSN)
- **SARVAM_API_KEY**, **GEMINI_API_KEY** (AI)
- **SIREN_API_KEY**, **SIREN_WEBHOOK_SECRET** (Messaging)
- **ENCRYPTION_KEY** (>=32 chars)

## Architecture

The application follows a clean architecture pattern with:

- **API Layer**: FastAPI routes and webhook handlers
- **Service Layer**: Business logic and orchestration
- **Repository Layer**: Data access and persistence
- **Model Layer**: Data structures and validation
- **Interface Layer**: Abstract contracts for services and repositories

## Design Notes

- Single-ingress architecture: all user interactions come via WhatsApp and are processed through a single webhook pipeline.
- No REST UI: bill/admin endpoints were removed as the assistant operates purely via messaging.
