# Environment Variables Setup

This document describes the required environment variables for the Bill Splitting Agent.

## Required Environment Variables

Create a `.env` file in the project root with the following variables:

### Database Configuration
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/powersplit
```

### Siren AI Toolkit Configuration
```bash
SIREN_API_KEY=your_siren_api_key_here
SIREN_WEBHOOK_SECRET=your_siren_webhook_secret_here
SIREN_BASE_URL=https://api.siren.ai
```

### AI Service Configuration
```bash
SARVAM_API_KEY=your_sarvam_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### Twilio Configuration (for media downloads)
```bash
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
```

### Security Configuration
```bash
ENCRYPTION_KEY=your_32_character_encryption_key_here
```

### Application Configuration (Optional)
```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
WORKERS=1
```

## Security Notes

- Never commit the `.env` file to version control
- The `.env` file is already included in `.gitignore`
- Use strong, unique values for all secrets and keys
- The `ENCRYPTION_KEY` must be at least 32 characters long

## Twilio Credentials

The Twilio credentials are used for downloading media files (images, audio, vCard contacts) from webhook messages. These credentials authenticate requests to the Twilio API to access media content.