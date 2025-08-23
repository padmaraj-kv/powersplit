"""Initial schema with encrypted fields and constraints

Revision ID: 001
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table with encrypted fields
    op.create_table('users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('phone_number', sa.String(255), nullable=False),  # Encrypted
        sa.Column('name', sa.String(255), nullable=True),  # Encrypted
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('phone_number', name='users_phone_unique'),
    )
    
    # Create contacts table with encrypted fields
    op.create_table('contacts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),  # Encrypted
        sa.Column('phone_number', sa.String(255), nullable=False),  # Encrypted
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'phone_number', name='contacts_user_phone_unique'),
    )
    
    # Create bills table
    op.create_table('bills',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('merchant', sa.String(200), nullable=True),
        sa.Column('bill_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('currency', sa.String(3), nullable=False, default='INR'),
        sa.Column('items_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint('total_amount > 0', name='bills_amount_positive'),
        sa.CheckConstraint("status IN ('active', 'completed', 'cancelled')", name='bills_status_valid'),
    )
    
    # Create bill_participants table
    op.create_table('bill_participants',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('bill_id', UUID(as_uuid=True), nullable=False),
        sa.Column('contact_id', UUID(as_uuid=True), nullable=False),
        sa.Column('amount_owed', sa.Numeric(12, 2), nullable=False),
        sa.Column('payment_status', sa.String(20), nullable=False, default='pending'),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('reminder_count', sa.Integer(), nullable=False, default=0),
        sa.Column('last_reminder_sent', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['bill_id'], ['bills.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.CheckConstraint('amount_owed > 0', name='participants_amount_positive'),
        sa.CheckConstraint("payment_status IN ('pending', 'sent', 'confirmed', 'failed')", name='participants_status_valid'),
        sa.CheckConstraint('reminder_count >= 0', name='participants_reminder_count_positive'),
    )
    
    # Create payment_requests table
    op.create_table('payment_requests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('bill_participant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('upi_link', sa.Text(), nullable=False),
        sa.Column('whatsapp_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('sms_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('delivery_attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('last_delivery_attempt', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['bill_participant_id'], ['bill_participants.id'], ondelete='CASCADE'),
        sa.CheckConstraint("status IN ('pending', 'sent', 'delivered', 'confirmed', 'failed')", name='payment_requests_status_valid'),
        sa.CheckConstraint('delivery_attempts >= 0', name='payment_requests_delivery_attempts_positive'),
    )
    
    # Create conversation_states table
    op.create_table('conversation_states',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.String(100), nullable=False),
        sa.Column('current_step', sa.String(50), nullable=False),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'session_id', name='conv_state_user_session_unique'),
        sa.CheckConstraint('retry_count >= 0', name='conv_state_retry_count_positive'),
        sa.CheckConstraint("""current_step IN ('initial', 'extracting_bill', 'confirming_bill', 
                                              'collecting_contacts', 'calculating_splits', 
                                              'confirming_splits', 'sending_requests', 
                                              'tracking_payments', 'completed')""", 
                          name='conv_step_valid'),
    )
    
    # Create indexes for performance
    op.create_index('idx_users_phone', 'users', ['phone_number'])
    op.create_index('idx_users_created_at', 'users', ['created_at'])
    
    op.create_index('idx_contacts_user_id', 'contacts', ['user_id'])
    op.create_index('idx_contacts_phone', 'contacts', ['phone_number'])
    op.create_index('idx_contacts_created_at', 'contacts', ['created_at'])
    
    op.create_index('idx_bills_user_id', 'bills', ['user_id'])
    op.create_index('idx_bills_status', 'bills', ['status'])
    op.create_index('idx_bills_created_at', 'bills', ['created_at'])
    op.create_index('idx_bills_bill_date', 'bills', ['bill_date'])
    
    op.create_index('idx_bill_participants_bill_id', 'bill_participants', ['bill_id'])
    op.create_index('idx_bill_participants_contact_id', 'bill_participants', ['contact_id'])
    op.create_index('idx_bill_participants_status', 'bill_participants', ['payment_status'])
    op.create_index('idx_bill_participants_created_at', 'bill_participants', ['created_at'])
    
    op.create_index('idx_payment_requests_participant_id', 'payment_requests', ['bill_participant_id'])
    op.create_index('idx_payment_requests_created_at', 'payment_requests', ['created_at'])
    op.create_index('idx_payment_requests_status', 'payment_requests', ['status'])
    
    op.create_index('idx_conv_states_user_id', 'conversation_states', ['user_id'])
    op.create_index('idx_conv_states_session_id', 'conversation_states', ['session_id'])
    op.create_index('idx_conv_states_step', 'conversation_states', ['current_step'])
    op.create_index('idx_conv_states_updated_at', 'conversation_states', ['updated_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_conv_states_updated_at', 'conversation_states')
    op.drop_index('idx_conv_states_step', 'conversation_states')
    op.drop_index('idx_conv_states_session_id', 'conversation_states')
    op.drop_index('idx_conv_states_user_id', 'conversation_states')
    
    op.drop_index('idx_payment_requests_status', 'payment_requests')
    op.drop_index('idx_payment_requests_created_at', 'payment_requests')
    op.drop_index('idx_payment_requests_participant_id', 'payment_requests')
    
    op.drop_index('idx_bill_participants_created_at', 'bill_participants')
    op.drop_index('idx_bill_participants_status', 'bill_participants')
    op.drop_index('idx_bill_participants_contact_id', 'bill_participants')
    op.drop_index('idx_bill_participants_bill_id', 'bill_participants')
    
    op.drop_index('idx_bills_bill_date', 'bills')
    op.drop_index('idx_bills_created_at', 'bills')
    op.drop_index('idx_bills_status', 'bills')
    op.drop_index('idx_bills_user_id', 'bills')
    
    op.drop_index('idx_contacts_created_at', 'contacts')
    op.drop_index('idx_contacts_phone', 'contacts')
    op.drop_index('idx_contacts_user_id', 'contacts')
    
    op.drop_index('idx_users_created_at', 'users')
    op.drop_index('idx_users_phone', 'users')
    
    # Drop tables in reverse order
    op.drop_table('conversation_states')
    op.drop_table('payment_requests')
    op.drop_table('bill_participants')
    op.drop_table('bills')
    op.drop_table('contacts')
    op.drop_table('users')