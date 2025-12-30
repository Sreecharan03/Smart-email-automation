# ====================================
# UNIFIED AI EMAIL ASSISTANT - ENDPOINT-BASED GMAIL INGESTION
# ====================================
# Fetches emails from your working /recent-emails endpoint
# Uses your existing Gmail service that's already working

import requests
import psycopg2
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import json
import uuid
import time
import logging
from dataclasses import dataclass

# LangGraph imports
from langgraph.graph import StateGraph, START, END

# Configuration imports
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../email-assistant')))

from config import get_config, get_supabase_connection_params

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EmailProcessingState:
    """State for email processing workflow"""
    account_id: int
    max_emails: int = 100
    raw_emails: List[Dict] = None
    processed_emails: List[Dict] = None
    stored_email_ids: List[int] = None
    total_fetched: int = 0
    total_processed: int = 0
    total_stored: int = 0
    processing_errors: List[str] = None
    start_time: float = 0
    
    def __post_init__(self):
        if self.raw_emails is None:
            self.raw_emails = []
        if self.processed_emails is None:
            self.processed_emails = []
        if self.stored_email_ids is None:
            self.stored_email_ids = []
        if self.processing_errors is None:
            self.processing_errors = []
        self.start_time = time.time()

class EndpointGmailIngestion:
    """
    Gmail ingestion using your working endpoint
    Fetches from /recent-emails and processes the data
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize with your working endpoint"""
        self.base_url = base_url
        self.config = get_config()
        self.db_params = get_supabase_connection_params(self.config)
        self.workflow = self._create_workflow()
        
        logger.info(f"Endpoint Gmail Ingestion initialized with base URL: {base_url}")
    
    def _create_workflow(self):
        """Create LangGraph workflow"""
        workflow = StateGraph(EmailProcessingState)
        
        workflow.add_node("fetch_from_endpoint", self._fetch_from_endpoint)
        workflow.add_node("process_emails", self._process_email_data)
        workflow.add_node("store_emails", self._store_emails_in_database)
        workflow.add_node("generate_report", self._generate_processing_report)
        
        workflow.add_edge(START, "fetch_from_endpoint")
        workflow.add_edge("fetch_from_endpoint", "process_emails")
        workflow.add_edge("process_emails", "store_emails")
        workflow.add_edge("store_emails", "generate_report")
        workflow.add_edge("generate_report", END)
        
        return workflow.compile()
    
    def _fetch_from_endpoint(self, state: EmailProcessingState) -> EmailProcessingState:
        """Fetch emails from your working /recent-emails endpoint"""
        logger.info(f"Fetching emails from your working endpoint: {self.base_url}/recent-emails")
        
        try:
            # Call your working endpoint
            response = requests.get(
                f"{self.base_url}/recent-emails",
                params={"limit": state.max_emails},
                timeout=120  # Increased timeout to 120 seconds
            )
            
            if response.status_code == 200:
                emails_data = response.json()
                
                # Extract emails from response
                if isinstance(emails_data, dict) and "emails" in emails_data:
                    state.raw_emails = emails_data["emails"]
                elif isinstance(emails_data, list):
                    state.raw_emails = emails_data
                else:
                    # If it's a different structure, adapt accordingly
                    state.raw_emails = emails_data if emails_data else []
                
                state.total_fetched = len(state.raw_emails)
                logger.info(f"Successfully fetched {state.total_fetched} emails from endpoint")
                
                # Log first email to verify structure
                if state.raw_emails:
                    first_email = state.raw_emails[0]
                    logger.info(f"First email structure: {list(first_email.keys())}")
                    logger.info(f"Sample subject: {first_email.get('subject', 'N/A')[:50]}...")
                
            else:
                error_msg = f"Endpoint returned status {response.status_code}: {response.text}"
                logger.error(error_msg)
                state.processing_errors.append(error_msg)
                
        except requests.exceptions.ConnectionError:
            error_msg = "Cannot connect to your Gmail endpoint. Make sure your server is running on port 8000."
            logger.error(error_msg)
            state.processing_errors.append(error_msg)
        except Exception as e:
            error_msg = f"Failed to fetch from endpoint: {str(e)}"
            logger.error(error_msg)
            state.processing_errors.append(error_msg)
        
        return state
    
    def _process_email_data(self, state: EmailProcessingState) -> EmailProcessingState:
        """Process email data from endpoint response"""
        logger.info(f"Processing {len(state.raw_emails)} emails from endpoint")
        
        try:
            processed_emails = []
            
            for raw_email in state.raw_emails:
                try:
                    # Adapt the email data structure from your endpoint
                    # This will depend on what your /recent-emails returns
                    
                    processed_email = {
                        "external_message_id": raw_email.get("id", raw_email.get("message_id", str(uuid.uuid4()))),
                        "thread_id": raw_email.get("thread_id", raw_email.get("threadId")),
                        "sender_email": raw_email.get("sender_email", raw_email.get("from", "")),
                        "sender_name": raw_email.get("sender_name", ""),
                        "recipients": self._parse_recipients(raw_email.get("to", "")),
                        "cc_recipients": self._parse_recipients(raw_email.get("cc", "")),
                        "bcc_recipients": [],
                        "subject": raw_email.get("subject", ""),
                        "snippet": raw_email.get("snippet", raw_email.get("preview", "")),
                        "date_sent": self._parse_date(raw_email.get("date", raw_email.get("timestamp"))),
                        "date_received": datetime.now(timezone.utc),
                        "is_read": not raw_email.get("unread", True),
                        "is_important": raw_email.get("important", False),
                        "has_attachments": raw_email.get("has_attachments", False),
                        "attachment_count": raw_email.get("attachment_count", 0),
                        "labels": raw_email.get("labels", []),
                        "folder_name": "INBOX",
                        "size_bytes": raw_email.get("size", 0),
                        "message_format": "text",
                        "is_processed": False,
                        "processing_error": None,
                        "message_uuid": str(uuid.uuid4())
                    }
                    
                    processed_emails.append(processed_email)
                    
                except Exception as e:
                    error_msg = f"Failed to process email: {str(e)}"
                    logger.warning(error_msg)
                    state.processing_errors.append(error_msg)
                    continue
            
            state.processed_emails = processed_emails
            state.total_processed = len(processed_emails)
            
            logger.info(f"Successfully processed {state.total_processed} emails")
            
        except Exception as e:
            error_msg = f"Failed to process email data: {str(e)}"
            logger.error(error_msg)
            state.processing_errors.append(error_msg)
        
        return state
    
    def _store_emails_in_database(self, state: EmailProcessingState) -> EmailProcessingState:
        """Store processed emails in database"""
        logger.info(f"Storing {len(state.processed_emails)} emails in database")
        
        try:
            stored_ids = []
            
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    for email_data in state.processed_emails:
                        try:
                            # Check for duplicates
                            cur.execute("""
                                SELECT id FROM email_messages 
                                WHERE account_id = %s AND external_message_id = %s
                            """, (state.account_id, email_data["external_message_id"]))
                            
                            existing = cur.fetchone()
                            if existing:
                                logger.debug(f"Email {email_data['external_message_id']} already exists")
                                stored_ids.append(existing[0])
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
                            
                            email_id = cur.fetchone()[0]
                            stored_ids.append(email_id)
                            
                            logger.debug(f"Stored: {email_data['subject'][:30]}... (ID: {email_id})")
                            
                        except Exception as e:
                            error_msg = f"Failed to store email: {str(e)}"
                            logger.error(error_msg)
                            state.processing_errors.append(error_msg)
                    
                    conn.commit()
            
            state.stored_email_ids = stored_ids
            state.total_stored = len(stored_ids)
            
            logger.info(f"Successfully stored {state.total_stored} emails")
            
        except Exception as e:
            error_msg = f"Database error: {str(e)}"
            logger.error(error_msg)
            state.processing_errors.append(error_msg)
        
        return state
    
    def _generate_processing_report(self, state: EmailProcessingState) -> EmailProcessingState:
        """Generate final processing report"""
        processing_time = time.time() - state.start_time
        
        logger.info("=== ENDPOINT GMAIL INGESTION COMPLETE ===")
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
    
    def _parse_recipients(self, recipients_str: str) -> List[Dict[str, str]]:
        """Parse recipients string into list of dicts"""
        if not recipients_str:
            return []
        
        recipients = []
        for recipient in recipients_str.split(','):
            recipient = recipient.strip()
            if recipient:
                recipients.append({"email": recipient, "name": ""})
        
        return recipients
    
    def _parse_date(self, date_str: Any) -> datetime:
        """Parse date string to datetime"""
        if not date_str:
            return datetime.now(timezone.utc)
        
        if isinstance(date_str, datetime):
            return date_str
        
        try:
            # Try parsing common date formats
            if isinstance(date_str, str):
                # ISO format
                if 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                # Simple date
                return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            
            # If it's a timestamp
            if isinstance(date_str, (int, float)):
                return datetime.fromtimestamp(date_str, tz=timezone.utc)
                
        except Exception as e:
            logger.warning(f"Failed to parse date {date_str}: {e}")
        
        return datetime.now(timezone.utc)
    
    def run_ingestion(self, account_id: int, max_emails: int = 50) -> Dict[str, Any]:
        """Run the complete ingestion workflow"""
        logger.info(f"Starting endpoint-based Gmail ingestion for account {account_id}")
        
        initial_state = EmailProcessingState(
            account_id=account_id,
            max_emails=max_emails
        )
        
        final_state = self.workflow.invoke(initial_state)
        
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
    Test the endpoint-based Gmail ingestion
    """
    print("🔗 Testing Endpoint-Based Gmail Ingestion")
    print("=" * 60)
    
    try:
        # Your Lightning AI URL
        base_url = "https://8000-01kb5kythhgsxk5vqz7yekpc49.cloudspaces.litng.ai"
        
        # Initialize workflow
        workflow = EndpointGmailIngestion(base_url=base_url)
        print(f"✅ Endpoint ingestion initialized with URL: {base_url}")
        
        # Get account ID
        test_account_id = 2
        test_max_emails = 200  # Decreased to 200 to balance fetch size and timeout

        
        print(f"📧 Fetching emails from your working endpoint")
        print(f"📊 Max emails: {test_max_emails}")
        print("⏳ Calling your /recent-emails endpoint...")
        
        # Run ingestion
        results = workflow.run_ingestion(
            account_id=test_account_id,
            max_emails=test_max_emails
        )
        
        # Display results
        print("\n📈 Endpoint Ingestion Results:")
        print(f"Success: {results['success']}")
        print(f"Emails Fetched: {results['emails_fetched']}")
        print(f"Emails Processed: {results['emails_processed']}")
        print(f"Emails Stored: {results['emails_stored']}")
        print(f"Processing Time: {results['processing_time']:.2f} seconds")
        
        if results['errors']:
            print(f"\n⚠️ Errors ({len(results['errors'])}):")
            for error in results['errors'][:3]:
                print(f"  - {error}")
        
        if results['success'] and results['emails_stored'] > 0:
            print(f"\n🎉 Successfully ingested {results['emails_stored']} emails from your endpoint!")
            print("✨ These are the REAL emails from your working Gmail service!")
        else:
            print(f"\nℹ️ Check if your server is running and accessible")
        
    except Exception as e:
        print(f"❌ Endpoint ingestion test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()