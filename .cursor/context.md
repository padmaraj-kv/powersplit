# Project Context

- Name: Bill Splitting Agent (FastAPI)
- Purpose: WhatsApp-based bill splitting using AI for OCR/voice/text and UPI flows
- Key Areas:
  - API: `app/api/routes/webhooks.py` (single-ingress Siren/Twilio)
  - Core: `app/core/config.py`, `app/core/database.py`
  - Services: AI clients (`sarvam_client.py`, `gemini_client.py`, `litellm_client.py`), payments, conversations
  - Models: `app/models/`
  - Database: SQLAlchemy engine; Supabase used only as managed Postgres

## Runtime

- Entry: `app/main.py` (lifespan orchestrates init of DB, services, webhooks)
- Health: `/health`
- Webhooks: `/api/v1/webhooks/siren/*`, `/api/v1/webhooks/twilio/whatsapp`

## Configuration

- Env-managed via `pydantic-settings` in `app/core/config.py`
- Required: database URL (or Supabase URL/key for Postgres), Siren keys, AI keys (Sarvam/Gemini), encryption key
- No app auth/JWT needed now; admin token checks will be relaxed

## Notes

- Webhook-only API: bills/admin routers removed; all flows driven from webhook
- Keep LiteLLM as a convenience client for model switching
- Supabase SDK not needed beyond DB connection; prefer direct Postgres URL
