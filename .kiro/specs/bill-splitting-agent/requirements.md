# Requirements Document

## Introduction

The Bill Splitting Agent is an intelligent WhatsApp-based system that helps users split bills among friends and family. Users can send bill information via text, voice, or images to the agent, which processes the data, calculates splits, and facilitates payment collection through UPI deeplinks. The system maintains contact history and payment tracking to streamline future interactions.

## Requirements

### Requirement 1

**User Story:** As a user, I want to send bill information to the agent via WhatsApp, so that I can quickly initiate a bill splitting process without manual calculations.

#### Acceptance Criteria

1. WHEN a user sends a text message with bill details THEN the system SHALL parse and extract bill amount, items, and participant information
2. WHEN a user sends a voice message THEN the system SHALL convert speech to text using Sarvam AI and extract bill information
3. WHEN a user sends an image of a bill THEN the system SHALL process the image using Gemini to extract bill details
4. IF the extracted information is incomplete or unclear THEN the system SHALL ask clarifying questions to the user
5. WHEN bill information is successfully extracted THEN the system SHALL display a summary for user confirmation

### Requirement 2

**User Story:** As a user, I want the agent to calculate and display bill splits, so that I can review the distribution before sending payment requests.

#### Acceptance Criteria

1. WHEN bill information is confirmed THEN the system SHALL calculate equal splits among all participants by default
2. WHEN a user requests custom split amounts THEN the system SHALL allow manual adjustment of individual amounts
3. WHEN split calculations are complete THEN the system SHALL display each participant's share clearly
4. IF the total split amounts don't match the bill total THEN the system SHALL highlight the discrepancy and request correction
5. WHEN splits are finalized THEN the system SHALL ask for participant contact information

### Requirement 3

**User Story:** As a user, I want to provide contact details for bill participants, so that payment requests can be sent automatically.

#### Acceptance Criteria

1. WHEN the system requests contacts THEN the user SHALL be able to provide phone numbers for each participant
2. IF a contact already exists in the database THEN the system SHALL auto-populate the contact information
3. WHEN new contacts are provided THEN the system SHALL store them in the database for future use
4. IF contact information is missing for any participant THEN the system SHALL request the missing details
5. WHEN all contacts are collected THEN the system SHALL proceed to generate payment requests

### Requirement 4

**User Story:** As a user, I want payment requests to be sent automatically to all participants, so that I don't have to manually contact each person.

#### Acceptance Criteria

1. WHEN all participant contacts are confirmed THEN the system SHALL generate UPI deeplinks for each participant with their specific amount
2. WHEN deeplinks are generated THEN the system SHALL send WhatsApp messages to each participant with their payment link
3. WHEN WhatsApp delivery fails THEN the system SHALL send SMS as a fallback using Siren
4. WHEN all messages are sent THEN the system SHALL send a confirmation message to the original user
5. WHEN payment requests are sent THEN the system SHALL store tracking information in the database

### Requirement 5

**User Story:** As a participant receiving a payment request, I want to confirm my payment easily, so that the bill organizer knows I've completed my part.

#### Acceptance Criteria

1. WHEN a participant receives a payment request THEN they SHALL be able to reply "done" or "paid" to confirm payment
2. WHEN a payment confirmation is received THEN the system SHALL update the payment status in the database
3. WHEN a payment is confirmed THEN the system SHALL notify the original user about the payment completion
4. IF a participant has questions about their payment THEN the system SHALL provide bill details and contact information
5. WHEN all participants have confirmed payment THEN the system SHALL send a completion notification to the original user

### Requirement 6

**User Story:** As a user, I want to query the status of previous bill splits, so that I can track who has paid and follow up if needed.

#### Acceptance Criteria

1. WHEN a user asks about previous bills THEN the system SHALL retrieve and display relevant bill history
2. WHEN displaying bill history THEN the system SHALL show payment status for each participant
3. WHEN a user requests specific bill details THEN the system SHALL provide complete information including amounts and dates
4. IF a user wants to send reminders THEN the system SHALL allow resending payment requests to unpaid participants
5. WHEN querying bill status THEN the system SHALL only show bills initiated by the requesting user

### Requirement 7

**User Story:** As a system administrator, I want the system to handle errors gracefully, so that users have a smooth experience even when issues occur.

#### Acceptance Criteria

1. WHEN external services (Sarvam AI, Gemini, Siren) are unavailable THEN the system SHALL provide appropriate fallback mechanisms
2. WHEN database operations fail THEN the system SHALL retry operations and notify users of temporary issues
3. WHEN message delivery fails THEN the system SHALL attempt alternative delivery methods
4. IF critical errors occur THEN the system SHALL log detailed error information for debugging
5. WHEN errors are resolved THEN the system SHALL automatically resume processing where possible

### Requirement 8

**User Story:** As a user, I want my data to be stored securely, so that my contact information and payment history remain private.

#### Acceptance Criteria

1. WHEN storing contact information THEN the system SHALL encrypt sensitive data in the database
2. WHEN processing payments THEN the system SHALL not store actual payment credentials or UPI details
3. WHEN accessing user data THEN the system SHALL verify user identity before displaying personal information
4. IF data retention limits are reached THEN the system SHALL automatically purge old records according to policy
5. WHEN users request data deletion THEN the system SHALL remove all associated personal information