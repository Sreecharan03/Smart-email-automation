# ====================================
# UNIFIED AI EMAIL ASSISTANT - EMAIL INGESTION WORKFLOW
# ====================================
# LangGraph workflow for processing Gmail emails and storing in database
# Handles incremental sync, deduplication, and error recovery

import psycopg2
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import json
import uuid
from dataclasses import dataclass
import time
import logging

# LangGraph imports for workflow orchestration
from langgraph.graph import StateGraph, START, END
# from langgraph.checkpoint.postgres import PostgresCheckpoint


# Configuration imports (assuming these exist from Phase 2)
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../email-assistant')))

from config import get_config, get_supabase_connection_params
from database_models import EmailMessage, EmailAccount

# Set up logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EmailProcessingState:
    """
    State object that flows through the LangGraph workflow
    Contains all data needed for email processing pipeline
    """
    # Account information
    account_id: int
    gmail_service: Any = None  # Will hold GmailService instance
    
    # Processing control
    max_emails: int = 100
    sync_cursor: Optional[str] = None
    processing_errors: List[str] = None
    
    # Email data
    raw_emails: List[Dict] = None
    processed_emails: List[Dict] = None
    stored_email_ids: List[int] = None
    
    # Statistics
    total_fetched: int = 0
    total_processed: int = 0
    total_stored: int = 0
    start_time: float = 0
    
    def __post_init__(self):
        """Initialize empty lists and start timing"""
        if self.processing_errors is None:
            self.processing_errors = []
        if self.raw_emails is None:
            self.raw_emails = []
        if self.processed_emails is None:
            self.processed_emails = []
        if self.stored_email_ids is None:
            self.stored_email_ids = []
        self.start_time = time.time()

class EmailIngestionWorkflow:
    """
    LangGraph workflow for email ingestion from Gmail to database
    
    Workflow Steps:
    1. Initialize Gmail Service
    2. Fetch Raw Emails from Gmail API
    3. Process & Normalize Email Data
    4. Store Emails in Database
    5. Update Sync Cursor
    6. Generate Processing Report
    """
    
    def __init__(self):
        """Initialize workflow with configuration and database connection"""
        self.config = get_config()
        self.db_params = get_supabase_connection_params(self.config)
        
        # Create LangGraph workflow
        self.workflow = self._create_workflow()
        
        logger.info("Email Ingestion Workflow initialized")
    
    def _create_workflow(self) -> Any:
        """
        Create the LangGraph workflow with all nodes and edges
        
        Returns:
            Graph: Configured LangGraph workflow
        """
        # Create workflow graph
        workflow = StateGraph(EmailProcessingState)
        
        # Add workflow nodes (each represents a processing step)
        workflow.add_node("initialize_service", self._initialize_gmail_service)
        workflow.add_node("fetch_emails", self._fetch_raw_emails)
        workflow.add_node("process_emails", self._process_email_data)
        workflow.add_node("store_emails", self._store_emails_in_database)
        workflow.add_node("update_cursor", self._update_sync_cursor)
        workflow.add_node("generate_report", self._generate_processing_report)
        
        # Define workflow flow (edge connections)
        workflow.add_edge(START, "initialize_service")
        workflow.add_edge("initialize_service", "fetch_emails")
        workflow.add_edge("fetch_emails", "process_emails")
        workflow.add_edge("process_emails", "store_emails")
        workflow.add_edge("store_emails", "update_cursor")
        workflow.add_edge("update_cursor", "generate_report")
        workflow.add_edge("generate_report", END)
        
        # Compile workflow with checkpoints for error recovery
        return workflow.compile()
    
    def _initialize_gmail_service(self, state: EmailProcessingState) -> EmailProcessingState:
        """
        Initialize Gmail service for the specified account
        
        Args:
            state: Current workflow state containing account_id
            
        Returns:
            EmailProcessingState: Updated state with Gmail service
        """
        logger.info(f"Initializing Gmail service for account {state.account_id}")
        
        try:
            # Get account details from database
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, email_address, refresh_token, sync_cursor 
                        FROM email_accounts 
                        WHERE id = %s AND provider = 'gmail' AND is_active = TRUE
                    """, (state.account_id,))
                    
                    account_row = cur.fetchone()
                    if not account_row:
                        raise ValueError(f"Active Gmail account {state.account_id} not found")
                    
                    # Extract account information
                    account_id, email_address, refresh_token, sync_cursor = account_row
                    state.sync_cursor = sync_cursor
                    
                    logger.info(f"Found Gmail account: {email_address}")
            
            # TODO: Initialize GmailService here
            # This would typically be: state.gmail_service = GmailService(account_id)
            # For now, we'll simulate this initialization
            state.gmail_service = f"gmail_service_{account_id}"
            
            logger.info("Gmail service initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize Gmail service: {str(e)}"
            logger.error(error_msg)
            state.processing_errors.append(error_msg)
        
        return state
    
    def _fetch_raw_emails(self, state: EmailProcessingState) -> EmailProcessingState:
        """
        Fetch raw email data from Gmail API
        
        Args:
            state: Current workflow state with Gmail service
            
        Returns:
            EmailProcessingState: Updated state with raw email data
        """
        logger.info(f"Fetching up to {state.max_emails} emails from Gmail")
        
        try:
            # Simulate email fetching (replace with actual Gmail API call)
            # In real implementation: messages, next_cursor = state.gmail_service.fetch_messages()
            
            # Simulated email data structure
            simulated_emails = [
                {
                    "id": f"gmail_{i}_{''.join([chr(97 + j) for j in range(16)])}",
                    "thread_id": f"thread_{i // 3}",  # Group emails in threads
                    "subject": f"Test Email Subject {i}",
                    "snippet": f"This is a test email snippet for message {i}...",
                    "sender_email": f"sender{i % 5}@example.com",
                    "sender_name": f"Sender {i % 5}",
                    "date_sent": datetime.now(timezone.utc),
                    "recipients": [{"email": "user@gmail.com", "name": "User"}],
                    "labels": ["INBOX"] if i % 2 == 0 else ["INBOX", "IMPORTANT"],
                    "has_attachments": i % 10 == 0,
                    "size_bytes": 1024 + (i * 100),
                    "message_format": "text"
                }
                for i in range(min(state.max_emails, 20))  # Limit simulation to 20 emails
            ]
            
            state.raw_emails = simulated_emails
            state.total_fetched = len(simulated_emails)
            
            logger.info(f"Fetched {state.total_fetched} emails from Gmail")
            
        except Exception as e:
            error_msg = f"Failed to fetch emails from Gmail: {str(e)}"
            logger.error(error_msg)
            state.processing_errors.append(error_msg)
        
        return state
    
    def _process_email_data(self, state: EmailProcessingState) -> EmailProcessingState:
        """
        Process and normalize raw email data for database storage
        
        Args:
            state: Current workflow state with raw emails
            
        Returns:
            EmailProcessingState: Updated state with processed emails
        """
        logger.info(f"Processing {len(state.raw_emails)} raw emails")
        
        try:
            processed_emails = []
            
            for raw_email in state.raw_emails:
                # Normalize email data structure
                processed_email = {
                    "external_message_id": raw_email["id"],
                    "thread_id": raw_email.get("thread_id"),
                    "sender_email": raw_email["sender_email"],
                    "sender_name": raw_email.get("sender_name"),
                    "recipients": raw_email.get("recipients", []),
                    "cc_recipients": raw_email.get("cc_recipients", []),
                    "bcc_recipients": raw_email.get("bcc_recipients", []),
                    "subject": raw_email.get("subject", ""),
                    "snippet": raw_email.get("snippet", ""),
                    "date_sent": raw_email["date_sent"],
                    "date_received": datetime.now(timezone.utc),
                    "is_read": "UNREAD" not in raw_email.get("labels", []),
                    "is_important": "IMPORTANT" in raw_email.get("labels", []),
                    "has_attachments": raw_email.get("has_attachments", False),
                    "attachment_count": raw_email.get("attachment_count", 0),
                    "labels": raw_email.get("labels", []),
                    "folder_name": "INBOX",  # Default to INBOX
                    "size_bytes": raw_email.get("size_bytes"),
                    "message_format": raw_email.get("message_format", "text"),
                    "is_processed": False,  # Will be marked True after embedding generation
                    "processing_error": None,
                    "message_uuid": str(uuid.uuid4()),  # Generate unique UUID
                }
                
                processed_emails.append(processed_email)
            
            state.processed_emails = processed_emails
            state.total_processed = len(processed_emails)
            
            logger.info(f"Processed {state.total_processed} emails successfully")
            
        except Exception as e:
            error_msg = f"Failed to process email data: {str(e)}"
            logger.error(error_msg)
            state.processing_errors.append(error_msg)
        
        return state
    
    def _store_emails_in_database(self, state: EmailProcessingState) -> EmailProcessingState:
        """
        Store processed emails in the database with deduplication
        
        Args:
            state: Current workflow state with processed emails
            
        Returns:
            EmailProcessingState: Updated state with stored email IDs
        """
        logger.info(f"Storing {len(state.processed_emails)} emails in database")
        
        try:
            stored_ids = []
            
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    for email_data in state.processed_emails:
                        try:
                            # Check if email already exists (deduplication)
                            cur.execute("""
                                SELECT id FROM email_messages 
                                WHERE account_id = %s AND external_message_id = %s
                            """, (state.account_id, email_data["external_message_id"]))
                            
                            existing_email = cur.fetchone()
                            
                            if existing_email:
                                # Email already exists, skip insertion
                                logger.debug(f"Email {email_data['external_message_id']} already exists, skipping")
                                stored_ids.append(existing_email[0])
                                continue
                            
                            # Insert new email
                            insert_sql = """
                                INSERT INTO email_messages (
                                    account_id, message_uuid, external_message_id, thread_id,
                                    sender_email, sender_name, recipients, cc_recipients, bcc_recipients,
                                    subject, snippet, date_sent, date_received,
                                    is_read, is_important, has_attachments, attachment_count,
                                    labels, folder_name, size_bytes, message_format,
                                    is_processed, processing_error
                                ) VALUES (
                                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                                ) RETURNING id;
                            """
                            
                            cur.execute(insert_sql, (
                                state.account_id,
                                email_data["message_uuid"],
                                email_data["external_message_id"],
                                email_data["thread_id"],
                                email_data["sender_email"],
                                email_data["sender_name"],
                                json.dumps(email_data["recipients"]),
                                json.dumps(email_data["cc_recipients"]),
                                json.dumps(email_data["bcc_recipients"]),
                                email_data["subject"],
                                email_data["snippet"],
                                email_data["date_sent"],
                                email_data["date_received"],
                                email_data["is_read"],
                                email_data["is_important"],
                                email_data["has_attachments"],
                                email_data["attachment_count"],
                                json.dumps(email_data["labels"]),
                                email_data["folder_name"],
                                email_data["size_bytes"],
                                email_data["message_format"],
                                email_data["is_processed"],
                                email_data["processing_error"]
                            ))
                            
                            # Get the inserted email ID
                            email_id = cur.fetchone()[0]
                            stored_ids.append(email_id)
                            
                        except Exception as e:
                            error_msg = f"Failed to store email {email_data['external_message_id']}: {str(e)}"
                            logger.error(error_msg)
                            state.processing_errors.append(error_msg)
                    
                    # Commit all insertions
                    conn.commit()
            
            state.stored_email_ids = stored_ids
            state.total_stored = len(stored_ids)
            
            logger.info(f"Stored {state.total_stored} emails in database")
            
        except Exception as e:
            error_msg = f"Failed to store emails in database: {str(e)}"
            logger.error(error_msg)
            state.processing_errors.append(error_msg)
        
        return state
    
    def _update_sync_cursor(self, state: EmailProcessingState) -> EmailProcessingState:
        """
        Update sync cursor for incremental email fetching
        
        Args:
            state: Current workflow state
            
        Returns:
            EmailProcessingState: Updated state
        """
        logger.info("Updating sync cursor for incremental sync")
        
        try:
            # Calculate new sync cursor (typically the last processed email's timestamp)
            if state.processed_emails:
                # Use the most recent email's date as the new cursor
                latest_date = max(email["date_sent"] for email in state.processed_emails)
                new_cursor = latest_date.isoformat()
                
                # Update sync cursor in database
                with psycopg2.connect(**self.db_params) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE email_accounts 
                            SET sync_cursor = %s, last_sync_at = %s
                            WHERE id = %s
                        """, (new_cursor, datetime.now(timezone.utc), state.account_id))
                        
                        conn.commit()
                
                logger.info(f"Updated sync cursor to: {new_cursor}")
            
        except Exception as e:
            error_msg = f"Failed to update sync cursor: {str(e)}"
            logger.error(error_msg)
            state.processing_errors.append(error_msg)
        
        return state
    
    def _generate_processing_report(self, state: EmailProcessingState) -> EmailProcessingState:
        """
        Generate final processing report with statistics
        
        Args:
            state: Current workflow state
            
        Returns:
            EmailProcessingState: Final state with processing complete
        """
        processing_time = time.time() - state.start_time
        
        logger.info("=== EMAIL INGESTION COMPLETE ===")
        logger.info(f"Processing Time: {processing_time:.2f} seconds")
        logger.info(f"Emails Fetched: {state.total_fetched}")
        logger.info(f"Emails Processed: {state.total_processed}")
        logger.info(f"Emails Stored: {state.total_stored}")
        logger.info(f"Processing Errors: {len(state.processing_errors)}")
        
        if state.processing_errors:
            logger.warning("Processing Errors:")
            for error in state.processing_errors:
                logger.warning(f"  - {error}")
        
        return state
    
    def run_ingestion(self, account_id: int, max_emails: int = 100) -> Dict[str, Any]:
        """
        Run the complete email ingestion workflow
        
        Args:
            account_id: Database ID of the Gmail account to process
            max_emails: Maximum number of emails to fetch
            
        Returns:
            Dict: Processing results and statistics
        """
        logger.info(f"Starting email ingestion for account {account_id}")
        
        # Create initial state
        initial_state = EmailProcessingState(
            account_id=account_id,
            max_emails=max_emails
        )
        
        # Run the workflow
        final_state = self.workflow.invoke(initial_state)
        
        # Return processing results
        return {
            "success": len(final_state['processing_errors']) == 0,
            "account_id": account_id,
            "emails_fetched": final_state['total_fetched'],
            "emails_processed": final_state['total_processed'],
            "emails_stored": final_state['total_stored'],
            "processing_time": time.time() - final_state['start_time'],
            "errors": final_state['processing_errors'],
            "stored_email_ids": final_state['stored_email_ids']
        }

def main():
    """
    Test function for email ingestion workflow
    Tests the workflow with simulated data
    """
    print("🚀 Testing Email Ingestion Workflow")
    print("=" * 50)
    
    try:
        # Initialize workflow
        workflow = EmailIngestionWorkflow()
        print("✅ Workflow initialized successfully")
        
        # Get a valid account ID from the database for testing
        test_account_id = 1
        try:
            with psycopg2.connect(**workflow.db_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM email_accounts WHERE is_active = TRUE LIMIT 1")
                    row = cur.fetchone()
                    if row:
                        test_account_id = row[0]
                        print(f"🔍 Found valid account ID {test_account_id} for testing")
                    else:
                        print("⚠️ No active email accounts found in database. Using default ID 1.")
        except Exception as e:
            print(f"⚠️ Failed to fetch account ID from DB: {e}")
        
        test_max_emails = 10
        
        print(f"📧 Starting ingestion test for account {test_account_id}")
        print(f"📊 Max emails to process: {test_max_emails}")
        
        # Run ingestion workflow
        results = workflow.run_ingestion(
            account_id=test_account_id,
            max_emails=test_max_emails
        )
        
        # Display results
        print("\n📈 Processing Results:")
        print(f"Success: {results['success']}")
        print(f"Emails Fetched: {results['emails_fetched']}")
        print(f"Emails Processed: {results['emails_processed']}")
        print(f"Emails Stored: {results['emails_stored']}")
        print(f"Processing Time: {results['processing_time']:.2f} seconds")
        
        if results['errors']:
            print(f"\n⚠️ Errors ({len(results['errors'])}):")
            for error in results['errors']:
                print(f"  - {error}")
        
        if results['success']:
            print("\n🎉 Email ingestion workflow completed successfully!")
        else:
            print("\n❌ Email ingestion workflow completed with errors")
        
    except Exception as e:
        print(f"❌ Workflow test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()