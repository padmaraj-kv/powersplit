# Project Context

- Name: Bill Splitting Agent (FastAPI)
- Purpose: WhatsApp-based bill splitting using AI for OCR/voice/text and UPI flows
- Key Areas:
  - API: `app/api/routes` (`webhooks.py`, `bills.py`, `admin.py`)
  - Core: `app/core/config.py`, `app/core/database.py`
  - Services: AI clients (`sarvam_client.py`, `gemini_client.py`, `litellm_client.py`), payments, conversations
  - Models: `app/models/`
  - Database: SQLAlchemy engine; Supabase used only as managed Postgres

## Runtime

- Entry: `app/main.py` (lifespan orchestrates init of DB, services, webhooks)
- Health: `/health`, metrics and admin endpoints under `/api/v1/admin`
- Webhooks: `/api/v1/webhooks/siren/*`

## Configuration

- Env-managed via `pydantic-settings` in `app/core/config.py`
- Required: database URL (or Supabase URL/key for Postgres), Siren keys, AI keys (Sarvam/Gemini), encryption key
- No app auth/JWT needed now; admin token checks will be relaxed

## Notes

- Remove legacy `app/api/routes/webhook.py` in favor of `webhooks.py`
- Keep LiteLLM as a convenience client for model switching
- Supabase SDK not needed beyond DB connection; prefer direct Postgres URL
