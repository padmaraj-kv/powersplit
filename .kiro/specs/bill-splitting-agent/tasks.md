# Implementation Plan

- [x] 1. Set up project structure and core interfaces
  - Create FastAPI application structure with proper directory organization
  - Define core data models and enums for conversation state management
  - Set up Supabase database connection and configuration
  - Create base interfaces for services and repositories
  - _Requirements: All requirements - foundational setup_

- [x] 2. Implement database models and migrations
  - Create Supabase database schema with all required tables ✅
  - Implement database models using SQLAlchemy or similar ORM ✅
  - Create database migration scripts for schema setup ✅
  - Add database connection pooling and error handling ✅
  - _Requirements: 3.2, 3.3, 5.2, 6.1, 8.1_
  
  **Implementation Summary:**
  - ✅ Complete SQLAlchemy models with encryption support (User, Contact, Bill, BillParticipant, PaymentRequest, ConversationState)
  - ✅ Comprehensive database migration system with Alembic integration
  - ✅ Advanced connection pooling with retry logic and error handling
  - ✅ Repository pattern implementation for clean data access
  - ✅ CLI management tools for database operations
  - ✅ Comprehensive test suite for database functionality
  - ✅ AES-256 encryption for sensitive data (phone numbers, names)
  - ✅ Database constraints, indexes, and validation
  - ✅ Health checks and monitoring capabilities

- [x] 3. Create Siren integration layer
  - Implement Siren AI Toolkit client wrapper
  - Create webhook handler for receiving Siren messages
  - Implement message sending functionality (WhatsApp and SMS)
  - Add webhook signature validation for security

  - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.2, 4.3_

- [x] 4. Implement conversation state management
  - Create ConversationState model and state machine logic
  - Implement state persistence and retrieval from database
  - Create conversation flow orchestrator with step transitions
  - Add state validation and error recovery mechanisms

  - _Requirements: 1.4, 2.5, 3.4, 7.2_

- [x] 5. Build AI service integration layer
  - Implement Sarvam AI client for speech-to-text conversion
  - Create Gemini Vision client for bill image processing
  - Implement LiteLLM/Gemini client for text processing and intent recognition
  - Add fallback mechanisms when AI services are unavailable

  - _Requirements: 1.1, 1.2, 1.3, 1.4, 7.1_

- [x] 6. Create bill extraction and processing logic
  - Implement BillExtractor class with multi-modal input support
  - Create bill data validation and normalization functions
  - Implement clarifying question generation for incomplete data
  - Add bill confirmation and summary display functionality

  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 7. Implement participant and contact management
  - Create ContactManager for storing and retrieving participant information
  - Implement contact deduplication and auto-population logic
  - Add contact validation and phone number formatting
  - Create participant collection workflow with missing contact handling

  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 8. Build bill splitting calculation engine
  - Implement equal split calculation as default behavior
  - Create custom split adjustment functionality
  - Add split validation to ensure amounts match bill total
  - Implement split confirmation and display formatting

  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 9. Create UPI payment link generation
  - Implement UPI deeplink generator with proper formatting
  - Support multiple UPI apps (GPay, PhonePe, Paytm, etc.)
  - Add UPI link validation and error handling
  - Create payment request data structures

  - _Requirements: 4.1, 4.5_

- [x] 10. Implement payment request distribution system
  - Create payment request sender using Siren integration
  - Implement WhatsApp message sending with SMS fallback
  - Add delivery confirmation tracking and status updates
  - Create personalized message templates for payment requests

  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 11. Build payment confirmation tracking
  - Implement payment confirmation message processing
  - Create payment status update functionality in database
  - Add notification system for payment confirmations to bill creator
  - Implement completion detection when all payments are confirmed

  - _Requirements: 5.1, 5.2, 5.3, 5.5_

- [x] 12. Create bill query and history system
  - Implement BillQueryService for retrieving user bill history
  - Create bill status display with payment tracking information
  - Add detailed bill information retrieval functionality
  - Implement payment reminder system for unpaid participants

  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 13. Implement comprehensive error handling
  - Create error handling middleware for FastAPI application
  - Implement retry mechanisms with exponential backoff for database operations
  - Add graceful degradation for external service failures
  - Create error logging and monitoring system

  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 14. Add security and data protection features
  - [x] 14.1 Implement data encryption for sensitive contact information
    - Complete AES-256 encryption system for phone numbers and names
    - Field-level encryption utilities with Fernet encryption
    - Encryption integration in database models and repositories
    - _Requirements: 8.1_
  
  - [ ] 14.2 Create user authentication and authorization middleware
    - Implement user identity verification middleware for API endpoints
    - Add phone number-based user authentication system
    - Create authorization checks to ensure users only access their own data
    - Add webhook signature validation for Siren integration security
    - _Requirements: 8.3_
  
  - [ ] 14.3 Implement comprehensive data retention and cleanup system
    - Create automated data retention policies with configurable periods
    - Implement data anonymization for old bills beyond retention period
    - Add scheduled cleanup jobs for expired data
    - Create data archival system for compliance
    - _Requirements: 8.4_
  
  - [ ] 14.4 Implement user data deletion capabilities
    - Create user data deletion API endpoints with proper authorization
    - Implement cascading deletion for all user-related data
    - Add data deletion confirmation and audit logging
    - Ensure complete removal of encrypted sensitive information
    - _Requirements: 8.5_
  
  - [ ] 14.5 Create security audit logging and monitoring
    - Implement security event logging for authentication attempts
    - Add audit trails for data access and modifications
    - Create security monitoring dashboard and alerts
    - Add rate limiting and abuse detection mechanisms
    - _Requirements: 8.1, 8.2, 8.3_

- [x] 15. Create main application orchestrator
  - Implement main FastAPI application with all route handlers
  - Create webhook endpoint for Siren message processing
  - Add health check and monitoring endpoints
  - Integrate all services into cohesive application flow
  - Create application configuration and environment management
  - _Requirements: All requirements - integration_

