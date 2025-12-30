# ====================================
# UNIFIED AI EMAIL ASSISTANT - DATABASE MODELS
# ====================================
# SQLAlchemy ORM models for all database tables
# Defines schema for accounts, messages, embeddings, drafts, etc.

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, JSON, Float, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
import uuid

# Create declarative base for all models
Base = declarative_base()

# ====================================
# USER ACCOUNTS TABLE
# ====================================

class EmailAccount(Base):
    """
    Store email provider account connections (Gmail, Outlook)
    Each user can connect multiple email accounts
    """
    __tablename__ = "email_accounts"
    
    # Primary key and identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)  # For future multi-user support
    account_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    
    # Provider information
    provider = Column(String(50), nullable=False)  # 'gmail' or 'outlook'
    email_address = Column(String(255), nullable=False)
    display_name = Column(String(255))
    
    # OAuth tokens (encrypted)
    access_token = Column(Text)  # Short-lived token
    refresh_token = Column(Text, nullable=False)  # Long-lived refresh token
    token_expiry = Column(DateTime(timezone=True))
    
    # Permissions and scopes
    granted_scopes = Column(JSON)  # List of OAuth scopes granted
    
    # Status and metadata
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime(timezone=True))
    sync_cursor = Column(String(255))  # For incremental sync
    
    # Timestamps
    connected_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    messages = relationship("EmailMessage", back_populates="account", cascade="all, delete-orphan")
    drafts = relationship("EmailDraft", back_populates="account", cascade="all, delete-orphan")
    
    # Indexes for better query performance
    __table_args__ = (
        Index('ix_email_accounts_user_provider', 'user_id', 'provider'),
        Index('ix_email_accounts_email', 'email_address'),
        UniqueConstraint('user_id', 'email_address', name='unique_user_email')
    )
    
    def __repr__(self):
        return f"<EmailAccount(email={self.email_address}, provider={self.provider})>"

# ====================================
# EMAIL MESSAGES TABLE
# ====================================

class EmailMessage(Base):
    """
    Store email messages with metadata and content
    Central table for all email data from different providers
    """
    __tablename__ = "email_messages"
    
    # Primary key and identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    
    # Foreign key to account
    account_id = Column(Integer, ForeignKey('email_accounts.id'), nullable=False)
    
    # Provider-specific IDs
    external_message_id = Column(String(255), nullable=False)  # Gmail/Outlook message ID
    thread_id = Column(String(255))  # Conversation thread ID
    
    # Email headers
    sender_email = Column(String(255), nullable=False)
    sender_name = Column(String(255))
    recipients = Column(JSON)  # List of recipient dictionaries
    cc_recipients = Column(JSON)  # CC list
    bcc_recipients = Column(JSON)  # BCC list
    
    # Email content
    subject = Column(Text)
    snippet = Column(Text)  # Short preview text
    body_plain = Column(Text)  # Plain text body (optional)
    body_html = Column(Text)   # HTML body (optional)
    
    # Message metadata
    date_sent = Column(DateTime(timezone=True), nullable=False)
    date_received = Column(DateTime(timezone=True))
    
    # Message properties
    is_read = Column(Boolean, default=False)
    is_important = Column(Boolean, default=False)
    has_attachments = Column(Boolean, default=False)
    attachment_count = Column(Integer, default=0)
    
    # Labels and categories
    labels = Column(JSON)  # Gmail labels or Outlook categories
    folder_name = Column(String(255))  # Inbox, Sent, etc.
    
    # Message size and format
    size_bytes = Column(Integer)
    message_format = Column(String(50))  # 'text', 'html', 'multipart'
    
    # Processing status
    is_processed = Column(Boolean, default=False)  # Has embeddings been generated
    processing_error = Column(Text)  # Store any processing errors
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    account = relationship("EmailAccount", back_populates="messages")
    embeddings = relationship("MessageEmbedding", back_populates="message", cascade="all, delete-orphan")
    importance_score = relationship("ImportanceScore", back_populates="message", uselist=False, cascade="all, delete-orphan")
    drafts = relationship("EmailDraft", back_populates="original_message", cascade="all, delete-orphan")
    
    # Indexes for better query performance
    __table_args__ = (
        Index('ix_email_messages_account_date', 'account_id', 'date_sent'),
        Index('ix_email_messages_sender', 'sender_email'),
        Index('ix_email_messages_thread', 'thread_id'),
        Index('ix_email_messages_external_id', 'external_message_id'),
        Index('ix_email_messages_processed', 'is_processed'),
        UniqueConstraint('account_id', 'external_message_id', name='unique_account_message')
    )
    
    def __repr__(self):
        return f"<EmailMessage(subject='{self.subject[:50]}...', sender={self.sender_email})>"

# ====================================
# MESSAGE EMBEDDINGS TABLE
# ====================================

class MessageEmbedding(Base):
    """
    Store vector embeddings for email content
    Used for semantic search and similarity matching
    """
    __tablename__ = "message_embeddings"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to message
    message_id = Column(Integer, ForeignKey('email_messages.id'), nullable=False)
    
    # Embedding metadata
    field_name = Column(String(50), nullable=False)  # 'subject', 'snippet', 'body'
    embedding_model = Column(String(100), nullable=False)  # Model used for embedding
    
    # Vector storage reference (stored in Qdrant)
    vector_id = Column(String(255), nullable=False)  # UUID reference to Qdrant vector
    qdrant_collection = Column(String(100), nullable=False)  # Qdrant collection name
    
    # Embedding dimensions and metadata
    vector_dimensions = Column(Integer, nullable=False)
    embedding_version = Column(String(50), default="v1")  # For future model updates
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    message = relationship("EmailMessage", back_populates="embeddings")
    
    # Indexes
    __table_args__ = (
        Index('ix_embeddings_message_field', 'message_id', 'field_name'),
        Index('ix_embeddings_vector_id', 'vector_id'),
        UniqueConstraint('message_id', 'field_name', 'embedding_model', name='unique_message_field_embedding')
    )
    
    def __repr__(self):
        return f"<MessageEmbedding(message_id={self.message_id}, field={self.field_name})>"

# ====================================
# EMAIL DRAFTS TABLE
# ====================================

class EmailDraft(Base):
    """
    Store AI-generated email drafts for human review
    Tracks draft generation, edits, and sending status
    """
    __tablename__ = "email_drafts"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    draft_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    
    # Foreign keys
    account_id = Column(Integer, ForeignKey('email_accounts.id'), nullable=False)
    original_message_id = Column(Integer, ForeignKey('email_messages.id'))  # If replying
    
    # Draft content
    recipient_email = Column(String(255), nullable=False)
    subject = Column(Text, nullable=False)
    body_text = Column(Text, nullable=False)
    body_html = Column(Text)
    
    # Draft metadata
    draft_type = Column(String(50), nullable=False)  # 'reply', 'forward', 'new'
    tone = Column(String(50))  # 'formal', 'casual', 'professional'
    length = Column(String(50))  # 'short', 'medium', 'long'
    
    # AI generation info
    ai_model_used = Column(String(100))  # Which LLM generated this
    generation_prompt = Column(Text)  # Original prompt used
    ai_confidence = Column(Float)  # Confidence score (0-1)
    
    # Human interaction
    user_edits = Column(JSON)  # Track what user changed
    edit_count = Column(Integer, default=0)
    approval_status = Column(String(50), default='pending')  # 'pending', 'approved', 'rejected'
    
    # Sending status
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True))
    sent_message_id = Column(String(255))  # Provider message ID after sending
    
    # Safety checks
    safety_check_passed = Column(Boolean, default=False)
    safety_issues = Column(JSON)  # List of detected issues
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    account = relationship("EmailAccount", back_populates="drafts")
    original_message = relationship("EmailMessage", back_populates="drafts")
    
    # Indexes
    __table_args__ = (
        Index('ix_drafts_account_status', 'account_id', 'approval_status'),
        Index('ix_drafts_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<EmailDraft(subject='{self.subject[:30]}...', status={self.approval_status})>"

# ====================================
# IMPORTANCE SCORES TABLE
# ====================================

class ImportanceScore(Base):
    """
    Store AI-calculated importance scores for emails
    Used for prioritizing emails in daily summaries
    """
    __tablename__ = "importance_scores"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to message
    message_id = Column(Integer, ForeignKey('email_messages.id'), nullable=False)
    
    # Importance scoring
    overall_score = Column(Float, nullable=False)  # 0.0 to 1.0
    urgency_score = Column(Float)  # How urgent is this email
    relevance_score = Column(Float)  # How relevant to user
    sender_importance = Column(Float)  # Importance of sender
    
    # Scoring factors (for explainability)
    scoring_factors = Column(JSON)  # Dict of factors that contributed to score
    scoring_reasons = Column(ARRAY(String))  # Human-readable reasons
    
    # AI model info
    model_used = Column(String(100))
    model_version = Column(String(50))
    
    # Timestamps
    calculated_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    message = relationship("EmailMessage", back_populates="importance_score")
    
    # Indexes
    __table_args__ = (
        Index('ix_importance_scores_score', 'overall_score'),
        Index('ix_importance_scores_message', 'message_id'),
    )
    
    def __repr__(self):
        return f"<ImportanceScore(message_id={self.message_id}, score={self.overall_score:.3f})>"

# ====================================
# DAILY DIGESTS TABLE
# ====================================

class DailyDigest(Base):
    """
    Store daily email summaries and digests
    Tracks what summaries were generated and delivered
    """
    __tablename__ = "daily_digests"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    digest_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    
    # User and date info
    user_id = Column(String(255), nullable=False)
    digest_date = Column(DateTime(timezone=True), nullable=False)
    
    # Summary content
    summary_text = Column(Text, nullable=False)
    summary_html = Column(Text)
    
    # Email statistics
    total_emails = Column(Integer, default=0)
    important_emails = Column(Integer, default=0)
    unread_emails = Column(Integer, default=0)
    
    # Action items
    action_items = Column(JSON)  # List of extracted action items
    pending_replies = Column(JSON)  # Emails that need replies
    
    # Delivery info
    delivery_method = Column(String(50))  # 'email', 'push', 'none'
    is_delivered = Column(Boolean, default=False)
    delivered_at = Column(DateTime(timezone=True))
    
    # Generation metadata
    ai_model_used = Column(String(100))
    generation_time_seconds = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('ix_daily_digests_user_date', 'user_id', 'digest_date'),
        UniqueConstraint('user_id', 'digest_date', name='unique_user_digest_date')
    )
    
    def __repr__(self):
        return f"<DailyDigest(user={self.user_id}, date={self.digest_date.date()})>"

# ====================================
# SYSTEM LOGS TABLE
# ====================================

class SystemLog(Base):
    """
    Store system events and metrics for monitoring
    Track API calls, errors, and performance metrics
    """
    __tablename__ = "system_logs"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Log metadata
    log_level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR
    event_type = Column(String(100), nullable=False)  # 'oauth', 'sync', 'search', etc.
    message = Column(Text, nullable=False)
    
    # Context information
    user_id = Column(String(255))
    account_id = Column(Integer)
    session_id = Column(String(255))
    
    # Performance metrics
    execution_time_ms = Column(Float)  # How long operation took
    memory_usage_mb = Column(Float)
    
    # Additional metadata
    meta_data = Column(JSON)  # Additional context data
    stack_trace = Column(Text)  # For errors
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('ix_system_logs_level_type', 'log_level', 'event_type'),
        Index('ix_system_logs_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SystemLog({self.log_level}: {self.event_type})>"

# ====================================
# DATABASE HELPER FUNCTIONS
# ====================================

def get_table_names():
    """Get list of all table names"""
    return [
        'email_accounts',
        'email_messages', 
        'message_embeddings',
        'email_drafts',
        'importance_scores',
        'daily_digests',
        'system_logs'
    ]

def get_model_classes():
    """Get list of all model classes"""
    return [
        EmailAccount,
        EmailMessage,
        MessageEmbedding,
        EmailDraft,
        ImportanceScore,
        DailyDigest,
        SystemLog
    ]

# ====================================
# MAIN FUNCTION FOR TESTING
# ====================================

def main():
    """Test database models and show schema information"""
    print("🗄️ Email Assistant Database Models")
    print("=" * 50)
    
    # Show all tables
    tables = get_table_names()
    print(f"📊 Total Tables: {len(tables)}")
    for i, table in enumerate(tables, 1):
        print(f"  {i}. {table}")
    
    # Show model information
    print(f"\n📋 Model Classes:")
    models = get_model_classes()
    for model in models:
        table_name = model.__tablename__
        print(f"  • {model.__name__} → {table_name}")
    
    print(f"\n✅ All models defined successfully!")
    print(f"💡 Run 'python database_setup.py' to create tables")

if __name__ == "__main__":
    main()