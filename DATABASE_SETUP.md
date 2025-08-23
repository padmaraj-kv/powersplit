# Database Setup and Management

This document describes the database setup, models, and management utilities for the Bill Splitting Agent.

## Overview

The application uses PostgreSQL via Supabase with SQLAlchemy ORM for database operations. Key features include:

- **Encrypted sensitive data** (phone numbers, names) - Requirement 8.1
- **Connection pooling** with retry logic and error handling
- **Database migrations** using Alembic
- **Comprehensive constraints** and indexes for data integrity
- **CLI management tools** for database operations

## Database Models

### Core Models

1. **User** - Stores user information with encrypted phone numbers and names
2. **Contact** - Stores participant contact information (encrypted)
3. **Bill** - Stores bill information with validation constraints
4. **BillParticipant** - Links contacts to bills with payment tracking
5. **PaymentRequest** - Tracks UPI payment requests and delivery status
6. **ConversationState** - Maintains conversation context and state

### Encryption

Sensitive data is encrypted using AES-256 encryption:
- User phone numbers and names
- Contact phone numbers and names
- Encryption key configured via `ENCRYPTION_KEY` environment variable

### Database Schema

```sql
-- Users table (encrypted fields)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(255) UNIQUE NOT NULL,  -- Encrypted
    name VARCHAR(255),                          -- Encrypted
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Contacts table (encrypted fields)
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,                 -- Encrypted
    phone_number VARCHAR(255) NOT NULL,         -- Encrypted
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, phone_number)
);

-- Bills table with constraints
CREATE TABLE bills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    total_amount DECIMAL(12,2) NOT NULL CHECK (total_amount > 0),
    description TEXT,
    merchant VARCHAR(200),
    bill_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    currency VARCHAR(3) DEFAULT 'INR',
    items_data JSONB
);

-- Bill participants with payment tracking
CREATE TABLE bill_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id UUID REFERENCES bills(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    amount_owed DECIMAL(12,2) NOT NULL CHECK (amount_owed > 0),
    payment_status VARCHAR(20) DEFAULT 'pending' CHECK (payment_status IN ('pending', 'sent', 'confirmed', 'failed')),
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    reminder_count INTEGER DEFAULT 0 CHECK (reminder_count >= 0),
    last_reminder_sent TIMESTAMP
);

-- Payment requests tracking
CREATE TABLE payment_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_participant_id UUID REFERENCES bill_participants(id) ON DELETE CASCADE,
    upi_link TEXT NOT NULL,
    whatsapp_sent BOOLEAN DEFAULT FALSE,
    sms_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'delivered', 'confirmed', 'failed')),
    delivery_attempts INTEGER DEFAULT 0 CHECK (delivery_attempts >= 0),
    last_delivery_attempt TIMESTAMP,
    delivery_error TEXT
);

-- Conversation state management
CREATE TABLE conversation_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(100) NOT NULL,
    current_step VARCHAR(50) NOT NULL CHECK (current_step IN ('initial', 'extracting_bill', 'confirming_bill', 'collecting_contacts', 'calculating_splits', 'confirming_splits', 'sending_requests', 'tracking_payments', 'completed')),
    context JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    retry_count INTEGER DEFAULT 0 CHECK (retry_count >= 0),
    last_error TEXT,
    expires_at TIMESTAMP,
    UNIQUE(user_id, session_id)
);
```

## Setup Instructions

### 1. Environment Configuration

Create a `.env` file with the following variables:

```bash
# Database Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
DATABASE_URL=postgresql://postgres:password@localhost:5432/bill_splitting

# Security Configuration
ENCRYPTION_KEY=your-32-character-encryption-key

# Other required variables...
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
# or
poetry install
```

### 3. Initialize Database

Using the CLI tool:

```bash
# Check database health
db-manage health

# Initialize database with tables and constraints
db-manage init

# Or create tables manually
db-manage create-tables
```

Using Python:

```python
from app.core.database import init_database
import asyncio

asyncio.run(init_database())
```

### 4. Run Migrations

Using Alembic:

```bash
# Generate new migration
alembic revision --autogenerate -m "Description of changes"

# Run migrations
alembic upgrade head

# Downgrade if needed
alembic downgrade -1
```

Using the CLI tool:

```bash
# Run specific migration
db-manage migrate initial
```

## Database Management

### CLI Commands

The `db-manage` command provides several utilities:

```bash
# Check database health and connection
db-manage health

# Initialize database
db-manage init

# Create all tables
db-manage create-tables

# Run specific migration
db-manage migrate <migration_name>

# Reset database (WARNING: destroys all data)
db-manage reset --confirm

# Execute raw SQL query
db-manage query "SELECT COUNT(*) FROM users"

# Clean up old data
db-manage cleanup
```

### Connection Pooling

The database connection is configured with:

- **Pool size**: 10 connections
- **Max overflow**: 20 additional connections
- **Pool timeout**: 30 seconds
- **Connection recycling**: 1 hour
- **Pre-ping validation**: Enabled
- **Retry logic**: Exponential backoff for failed connections

### Error Handling

The database layer includes comprehensive error handling:

- **Connection failures**: Automatic retry with exponential backoff
- **Transaction rollbacks**: Automatic rollback on errors
- **Graceful degradation**: Fallback mechanisms for service failures
- **Detailed logging**: Error tracking and monitoring

### Data Encryption

Sensitive data is automatically encrypted/decrypted:

```python
# Creating a user (automatic encryption)
user = User(phone_number="+1234567890", name="John Doe")
db.add(user)
db.commit()

# Accessing data (automatic decryption)
print(user.phone_number)  # "+1234567890"
print(user._phone_number)  # "encrypted_data_here"
```

### Performance Optimization

The database includes several performance optimizations:

- **Indexes** on frequently queried columns
- **Connection pooling** to reduce connection overhead
- **Query optimization** with proper foreign key relationships
- **Batch operations** support for bulk inserts/updates

## Testing

Run database tests:

```bash
# Run all database tests
pytest tests/test_database_models.py -v

# Run migration tests
pytest tests/test_migrations.py -v

# Run with coverage
pytest tests/ --cov=app.models --cov=app.database
```

## Monitoring and Maintenance

### Health Checks

Regular health checks should be performed:

```python
from app.core.database import check_database_health

health = await check_database_health()
print(health['status'])  # 'healthy', 'missing_tables', or 'unhealthy'
```

### Data Cleanup

Automatic cleanup of old data:

```bash
# Clean up expired conversation states and old payment requests
db-manage cleanup
```

### Backup and Recovery

For production environments:

1. **Regular backups** of the Supabase database
2. **Point-in-time recovery** configuration
3. **Monitoring** of database performance and errors
4. **Alerting** for critical database issues

## Security Considerations

- **Encryption at rest**: All sensitive data is encrypted using AES-256
- **Connection security**: All connections use TLS/SSL
- **Access control**: Database access restricted to application
- **Data retention**: Automatic cleanup of old data
- **Audit logging**: Database operations are logged for security auditing

## Troubleshooting

### Common Issues

1. **Connection failures**: Check Supabase URL and credentials
2. **Migration errors**: Ensure database schema is up to date
3. **Encryption errors**: Verify encryption key is properly configured
4. **Performance issues**: Check connection pool settings and indexes

### Debug Mode

Enable debug mode for detailed SQL logging:

```bash
DEBUG=true python -m app.main
```

This will log all SQL queries and connection pool activity.