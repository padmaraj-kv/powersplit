# Product Overview

## Bill Splitting Agent

An intelligent WhatsApp-based bill splitting system that helps users split bills among friends and family using AI-powered text, voice, and image processing.

## Core Features

- **Multi-modal Input**: Processes text, voice, and image messages for bill information
- **AI-Powered Extraction**: Uses Sarvam, Gemini, and LiteLLM APIs for intelligent bill parsing
- **Automated Calculations**: Smart bill splitting with customizable distribution
- **Contact Management**: Handles participant contact collection and deduplication
- **Payment Integration**: Generates UPI payment links and tracks confirmations
- **WhatsApp/SMS Integration**: Uses Siren AI Toolkit for message delivery with fallback
- **Conversation Management**: Maintains context across multi-step interactions
- **Error Recovery**: Comprehensive error handling with graceful degradation

## User Journey

1. User sends bill information (text/image/voice) via WhatsApp
2. System extracts bill details using AI services
3. User confirms bill information and adds participants
4. System calculates splits and generates payment requests
5. Payment links sent to participants via WhatsApp/SMS
6. System tracks payments and confirms completion

## Key Integrations

- **Siren AI Toolkit**: WhatsApp and SMS messaging
- **Supabase**: Database and authentication
- **AI Services**: Sarvam (voice), Gemini (vision), LiteLLM (text processing)
- **UPI**: Payment link generation for Indian market