# ====================================
# UNIFIED AI EMAIL ASSISTANT - GMAIL SERVICE
# ====================================
# Gmail API service for email operations: fetch, send, search, manage
# Handles Gmail-specific features like labels, threads, and rate limiting

import time
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
import html
import re
import sys

# Google API imports
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

# Database imports
import psycopg2
from psycopg2.extras import RealDictCursor

# Add project root to path for imports
sys.path.append('/teamspace/studios/this_studio')

# Import our OAuth handler and configuration
from backend.services.gmail.oauth_handler import GmailOAuthHandler, create_oauth_handler

# Import config functions using a more robust approach
import importlib.util
import os

# Load config module from email-assistant directory
config_path = '/teamspace/studios/this_studio/email-assistant/config.py'
spec = importlib.util.spec_from_file_location("config", config_path)

if spec is None or spec.loader is None:
    raise ImportError(f"Could not load config module from {config_path}")

config_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_module)

# Extract the required functions
get_config = config_module.get_config
get_supabase_connection_params = config_module.get_supabase_connection_params

# Pydantic models for request/response schemas
from pydantic import BaseModel, EmailStr

# ====================================
# PYDANTIC MODELS FOR EMAIL DATA
# ====================================

class EmailMessage(BaseModel):
    """Standardized email message model"""
    external_id: str
    thread_id: Optional[str]
    sender_email: str
    sender_name: Optional[str]
    recipients: List[Dict[str, str]]
    cc_recipients: Optional[List[Dict[str, str]]] = []
    bcc_recipients: Optional[List[Dict[str, str]]] = []
    subject: Optional[str]
    snippet: Optional[str]
    body_plain: Optional[str]
    body_html: Optional[str]
    date_sent: datetime
    is_read: bool
    is_important: bool
    has_attachments: bool
    attachment_count: int = 0
    labels: List[str] = []
    folder_name: str = "INBOX"
    size_bytes: int = 0

class SendEmailRequest(BaseModel):
    """Request model for sending emails"""
    to: List[EmailStr]
    cc: Optional[List[EmailStr]] = []
    bcc: Optional[List[EmailStr]] = []
    subject: str
    body_text: Optional[str]
    body_html: Optional[str]
    reply_to_message_id: Optional[str] = None
    thread_id: Optional[str] = None

class EmailSearchQuery(BaseModel):
    """Search query model for Gmail"""
    query: str
    max_results: int = 100
    include_spam_trash: bool = False
    label_ids: Optional[List[str]] = None
    page_token: Optional[str] = None

# ====================================
# GMAIL SERVICE CLASS
# ====================================

class GmailService:
    """
    Gmail API service for comprehensive email operations
    Handles authentication, API calls, rate limiting, and error management
    """
    
    def __init__(self, account_id: int):
        """
        Initialize Gmail service for a specific account
        
        Args:
            account_id: Database ID of the email account
        """
        self.account_id = account_id
        self.config = get_config()
        self.oauth_handler = create_oauth_handler()
        
        # Rate limiting configuration
        self.rate_limit_delay = 60 / self.config.gmail_api_rate_limit  # Delay between requests
        self.last_request_time = 0
        
        # Gmail service instance (lazy loaded)
        self._service = None
        
        # Database connection parameters
        self.db_params = get_supabase_connection_params(self.config)
        
        print(f"🔧 Gmail service initialized for account ID: {account_id}")
    
    def _get_service(self):
        """
        Get authenticated Gmail service instance with lazy loading
        
        Returns:
            Authenticated Gmail service or None if authentication fails
        """
        try:
            if self._service is None:
                # Get valid credentials from OAuth handler
                credentials = self.oauth_handler.get_valid_credentials(self.account_id)
                if not credentials:
                    print(f"❌ No valid credentials for account ID: {self.account_id}")
                    return None
                
                # Build Gmail service
                self._service = build('gmail', 'v1', credentials=credentials)
                print(f"✅ Gmail service authenticated for account: {self.account_id}")
            
            return self._service
            
        except Exception as e:
            print(f"❌ Error getting Gmail service: {e}")
            self._service = None
            return None
    
    def _rate_limit_check(self):
        """Implement rate limiting to respect Gmail API quotas"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_request
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        Get Gmail account profile information
        
        Returns:
            Dictionary with account details or None if failed
        """
        try:
            service = self._get_service()
            if not service:
                return None
            
            self._rate_limit_check()
            
            # Get user profile
            profile = service.users().getProfile(userId='me').execute()
            
            return {
                'email_address': profile.get('emailAddress'),
                'messages_total': profile.get('messagesTotal', 0),
                'threads_total': profile.get('threadsTotal', 0),
                'history_id': profile.get('historyId'),
            }
            
        except HttpError as e:
            print(f"❌ Gmail API error getting account info: {e}")
            return None
        except Exception as e:
            print(f"❌ Error getting account info: {e}")
            return None
    
    def fetch_messages(
        self, 
        max_results: int = 100, 
        query: str = "", 
        page_token: Optional[str] = None
    ) -> Tuple[List[EmailMessage], Optional[str]]:
        """
        Fetch email messages from Gmail with pagination
        
        Args:
            max_results: Maximum number of messages to fetch
            query: Gmail search query (e.g., "in:inbox", "from:example@gmail.com")
            page_token: Token for pagination
            
        Returns:
            Tuple of (list of EmailMessage objects, next_page_token)
        """
        try:
            service = self._get_service()
            if not service:
                return [], None
            
            self._rate_limit_check()
            
            # List messages with query
            list_params = {
                'userId': 'me',
                'q': query,
                'maxResults': min(max_results, 500)  # Gmail API limit
            }
            
            if page_token:
                list_params['pageToken'] = page_token
            
            messages_result = service.users().messages().list(**list_params).execute()
            message_ids = messages_result.get('messages', [])
            next_page_token = messages_result.get('nextPageToken')
            
            if not message_ids:
                print(f"📭 No messages found for query: '{query}'")
                return [], None
            
            print(f"📬 Found {len(message_ids)} messages for query: '{query}'")
            
            # Fetch detailed message data
            messages = []
            for msg_data in message_ids:
                try:
                    self._rate_limit_check()
                    
                    # Get full message details
                    message = service.users().messages().get(
                        userId='me', 
                        id=msg_data['id'],
                        format='full'
                    ).execute()
                    
                    # Parse message into standardized format
                    parsed_message = self._parse_gmail_message(message)
                    if parsed_message:
                        messages.append(parsed_message)
                    
                except Exception as e:
                    print(f"❌ Error fetching message {msg_data['id']}: {e}")
                    continue
            
            print(f"✅ Successfully parsed {len(messages)} messages")
            return messages, next_page_token
            
        except HttpError as e:
            print(f"❌ Gmail API error fetching messages: {e}")
            return [], None
        except Exception as e:
            print(f"❌ Error fetching messages: {e}")
            return [], None
    
    def get_message_by_id(self, message_id: str) -> Optional[EmailMessage]:
        """
        Get a specific message by its Gmail ID
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            EmailMessage object or None if not found
        """
        try:
            service = self._get_service()
            if not service:
                return None
            
            self._rate_limit_check()
            
            # Get message details
            message = service.users().messages().get(
                userId='me', 
                id=message_id,
                format='full'
            ).execute()
            
            return self._parse_gmail_message(message)
            
        except HttpError as e:
            print(f"❌ Gmail API error getting message {message_id}: {e}")
            return None
        except Exception as e:
            print(f"❌ Error getting message: {e}")
            return None
    
    def send_email(self, email_request: SendEmailRequest) -> Optional[str]:
        """
        Send an email through Gmail API
        
        Args:
            email_request: SendEmailRequest object with email details
            
        Returns:
            Sent message ID or None if failed
        """
        try:
            service = self._get_service()
            if not service:
                return None
            
            # Create email message
            message = MIMEMultipart('alternative')
            
            # Set headers
            message['To'] = ', '.join(email_request.to)
            if email_request.cc:
                message['Cc'] = ', '.join(email_request.cc)
            if email_request.bcc:
                message['Bcc'] = ', '.join(email_request.bcc)
            
            message['Subject'] = email_request.subject
            
            # Handle reply threading
            if email_request.reply_to_message_id:
                message['In-Reply-To'] = email_request.reply_to_message_id
                message['References'] = email_request.reply_to_message_id
            
            # Add message bodies
            if email_request.body_text:
                text_part = MIMEText(email_request.body_text, 'plain', 'utf-8')
                message.attach(text_part)
            
            if email_request.body_html:
                html_part = MIMEText(email_request.body_html, 'html', 'utf-8')
                message.attach(html_part)
            
            # If only one body type provided, use that
            if not email_request.body_text and not email_request.body_html:
                raise ValueError("Either body_text or body_html must be provided")
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            self._rate_limit_check()
            
            # Send email
            send_request = {
                'raw': raw_message
            }
            
            if email_request.thread_id:
                send_request['threadId'] = email_request.thread_id
            
            result = service.users().messages().send(
                userId='me',
                body=send_request
            ).execute()
            
            sent_message_id = result.get('id')
            print(f"✅ Email sent successfully: {sent_message_id}")
            
            return sent_message_id
            
        except HttpError as e:
            print(f"❌ Gmail API error sending email: {e}")
            return None
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return None
    
    def search_emails(self, search_query: EmailSearchQuery) -> Tuple[List[EmailMessage], Optional[str]]:
        """
        Search emails using Gmail query syntax
        
        Args:
            search_query: EmailSearchQuery object with search parameters
            
        Returns:
            Tuple of (matching EmailMessage objects, next_page_token)
        """
        try:
            # Construct Gmail search query
            query_parts = [search_query.query]
            
            # Add label filters
            if search_query.label_ids:
                for label_id in search_query.label_ids:
                    query_parts.append(f"label:{label_id}")
            
            # Exclude spam and trash by default
            if not search_query.include_spam_trash:
                query_parts.extend(["-in:spam", "-in:trash"])
            
            full_query = " ".join(query_parts)
            
            print(f"🔍 Searching emails with query: '{full_query}'")
            
            # Use fetch_messages with search query
            return self.fetch_messages(
                max_results=search_query.max_results,
                query=full_query,
                page_token=search_query.page_token
            )
            
        except Exception as e:
            print(f"❌ Error searching emails: {e}")
            return [], None
    
    def get_labels(self) -> List[Dict[str, Any]]:
        """
        Get all Gmail labels for the account
        
        Returns:
            List of label dictionaries
        """
        try:
            service = self._get_service()
            if not service:
                return []
            
            self._rate_limit_check()
            
            # Get labels
            labels_result = service.users().labels().list(userId='me').execute()
            labels = labels_result.get('labels', [])
            
            print(f"📋 Found {len(labels)} labels")
            return labels
            
        except HttpError as e:
            print(f"❌ Gmail API error getting labels: {e}")
            return []
        except Exception as e:
            print(f"❌ Error getting labels: {e}")
            return []
    
    def mark_as_read(self, message_ids: List[str]) -> bool:
        """
        Mark messages as read
        
        Args:
            message_ids: List of Gmail message IDs
            
        Returns:
            True if successful, False otherwise
        """
        try:
            service = self._get_service()
            if not service:
                return False
            
            self._rate_limit_check()
            
            # Remove UNREAD label
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': message_ids,
                    'removeLabelIds': ['UNREAD']
                }
            ).execute()
            
            print(f"✅ Marked {len(message_ids)} messages as read")
            return True
            
        except HttpError as e:
            print(f"❌ Gmail API error marking as read: {e}")
            return False
        except Exception as e:
            print(f"❌ Error marking as read: {e}")
            return False
    
    def _parse_gmail_message(self, gmail_message: Dict[str, Any]) -> Optional[EmailMessage]:
        """
        Parse Gmail API message into standardized EmailMessage format
        
        Args:
            gmail_message: Raw message from Gmail API
            
        Returns:
            EmailMessage object or None if parsing fails
        """
        try:
            # Extract basic message data
            message_id = gmail_message['id']
            thread_id = gmail_message.get('threadId')
            labels = gmail_message.get('labelIds', [])
            snippet = gmail_message.get('snippet', '')
            
            # Parse headers
            headers = {}
            payload = gmail_message.get('payload', {})
            for header in payload.get('headers', []):
                headers[header['name'].lower()] = header['value']
            
            # Extract key header information
            sender_email, sender_name = self._parse_email_address(headers.get('from', ''))
            subject = headers.get('subject', '')
            date_str = headers.get('date', '')
            
            # Parse date
            date_sent = self._parse_email_date(date_str)
            
            # Extract recipients
            recipients = self._parse_recipients(headers.get('to', ''))
            cc_recipients = self._parse_recipients(headers.get('cc', ''))
            bcc_recipients = self._parse_recipients(headers.get('bcc', ''))
            
            # Extract message body
            body_plain, body_html = self._extract_message_body(payload)
            
            # Determine message properties
            is_read = 'UNREAD' not in labels
            is_important = 'IMPORTANT' in labels or 'CATEGORY_PERSONAL' in labels
            has_attachments = self._has_attachments(payload)
            attachment_count = self._count_attachments(payload)
            
            # Determine folder name from labels
            folder_name = self._determine_folder(labels)
            
            # Calculate message size
            size_bytes = int(gmail_message.get('sizeEstimate', 0))
            
            # Create EmailMessage object
            return EmailMessage(
                external_id=message_id,
                thread_id=thread_id,
                sender_email=sender_email,
                sender_name=sender_name,
                recipients=recipients,
                cc_recipients=cc_recipients,
                bcc_recipients=bcc_recipients,
                subject=subject,
                snippet=snippet,
                body_plain=body_plain,
                body_html=body_html,
                date_sent=date_sent,
                is_read=is_read,
                is_important=is_important,
                has_attachments=has_attachments,
                attachment_count=attachment_count,
                labels=labels,
                folder_name=folder_name,
                size_bytes=size_bytes
            )
            
        except Exception as e:
            print(f"❌ Error parsing Gmail message {gmail_message.get('id', 'unknown')}: {e}")
            return None
    
    def _parse_email_address(self, address_str: str) -> Tuple[str, Optional[str]]:
        """Parse email address string into email and name components"""
        try:
            if not address_str:
                return "unknown@example.com", None
            
            # Handle format: "Name <email@domain.com>" or just "email@domain.com"
            import re
            match = re.match(r'^(.*?)\s*<(.+?)>$', address_str.strip())
            if match:
                name = match.group(1).strip().strip('"\'')
                email = match.group(2).strip()
                return email, name if name else None
            else:
                # Just email address
                email = address_str.strip()
                return email, None
                
        except Exception:
            return address_str, None
    
    def _parse_recipients(self, recipients_str: str) -> List[Dict[str, str]]:
        """Parse recipients string into list of email/name dictionaries"""
        try:
            if not recipients_str:
                return []
            
            recipients = []
            # Split by comma for multiple recipients
            for recipient in recipients_str.split(','):
                email, name = self._parse_email_address(recipient.strip())
                recipients.append({
                    'email': email,
                    'name': name or ''
                })
            
            return recipients
            
        except Exception:
            return []
    
    def _parse_email_date(self, date_str: str) -> datetime:
        """Parse email date string into datetime object"""
        try:
            if not date_str:
                return datetime.now(timezone.utc)
            
            # Try to parse various date formats
            import email.utils
            timestamp = email.utils.parsedate_tz(date_str)
            if timestamp:
                # Convert to datetime
                dt = datetime(*timestamp[:6], tzinfo=timezone.utc)
                if timestamp[9]:  # timezone offset
                    offset = timedelta(seconds=timestamp[9])
                    dt = dt - offset
                return dt
            else:
                # Fallback to current time
                return datetime.now(timezone.utc)
                
        except Exception:
            return datetime.now(timezone.utc)
    
    def _extract_message_body(self, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Extract plain text and HTML body from Gmail payload"""
        try:
            body_plain = None
            body_html = None
            
            def extract_from_part(part):
                nonlocal body_plain, body_html
                
                mime_type = part.get('mimeType', '')
                body = part.get('body', {})
                
                if mime_type == 'text/plain' and body.get('data'):
                    body_plain = base64.urlsafe_b64decode(body['data']).decode('utf-8')
                elif mime_type == 'text/html' and body.get('data'):
                    body_html = base64.urlsafe_b64decode(body['data']).decode('utf-8')
                
                # Recursively check parts
                for subpart in part.get('parts', []):
                    extract_from_part(subpart)
            
            # Start extraction from payload
            extract_from_part(payload)
            
            return body_plain, body_html
            
        except Exception as e:
            print(f"❌ Error extracting message body: {e}")
            return None, None
    
    def _has_attachments(self, payload: Dict[str, Any]) -> bool:
        """Check if message has attachments"""
        try:
            def check_parts(part):
                # Check if this part is an attachment
                if part.get('filename') and part.get('body', {}).get('attachmentId'):
                    return True
                
                # Check subparts recursively
                for subpart in part.get('parts', []):
                    if check_parts(subpart):
                        return True
                
                return False
            
            return check_parts(payload)
            
        except Exception:
            return False
    
    def _count_attachments(self, payload: Dict[str, Any]) -> int:
        """Count number of attachments in message"""
        try:
            count = 0
            
            def count_parts(part):
                nonlocal count
                
                # Check if this part is an attachment
                if part.get('filename') and part.get('body', {}).get('attachmentId'):
                    count += 1
                
                # Check subparts recursively
                for subpart in part.get('parts', []):
                    count_parts(subpart)
            
            count_parts(payload)
            return count
            
        except Exception:
            return 0
    
    def _determine_folder(self, labels: List[str]) -> str:
        """Determine folder name from Gmail labels"""
        try:
            # Gmail system labels mapping
            if 'INBOX' in labels:
                return 'INBOX'
            elif 'SENT' in labels:
                return 'SENT'
            elif 'DRAFT' in labels:
                return 'DRAFT'
            elif 'SPAM' in labels:
                return 'SPAM'
            elif 'TRASH' in labels:
                return 'TRASH'
            elif 'STARRED' in labels:
                return 'STARRED'
            else:
                # Check for custom labels (non-system labels)
                for label in labels:
                    if not label.startswith('CATEGORY_') and label not in ['IMPORTANT', 'UNREAD']:
                        return label
                
                return 'INBOX'  # Default fallback
                
        except Exception:
            return 'INBOX'

# ====================================
# CONVENIENCE FUNCTIONS
# ====================================

def create_gmail_service(account_id: int) -> GmailService:
    """Factory function to create Gmail service"""
    return GmailService(account_id)

def get_account_emails(account_id: int, max_results: int = 100) -> List[EmailMessage]:
    """Quick function to get emails for an account"""
    service = create_gmail_service(account_id)
    messages, _ = service.fetch_messages(max_results=max_results, query="in:inbox")
    return messages

def send_gmail(account_id: int, email_request: SendEmailRequest) -> Optional[str]:
    """Quick function to send email through Gmail"""
    service = create_gmail_service(account_id)
    return service.send_email(email_request)

# ====================================
# MAIN FUNCTION FOR TESTING
# ====================================

def main():
    """Test Gmail service functionality"""
    print("📧 Testing Gmail Service")
    print("=" * 50)
    
    try:
        # Test with a demo account ID (would need real account in database)
        test_account_id = 1
        
        # Initialize Gmail service
        gmail_service = create_gmail_service(test_account_id)
        print("✅ Gmail service created successfully")
        
        # Test account info
        print("\n🔍 Testing account info...")
        account_info = gmail_service.get_account_info()
        if account_info:
            print(f"   Email: {account_info['email_address']}")
            print(f"   Total Messages: {account_info['messages_total']}")
            print(f"   Total Threads: {account_info['threads_total']}")
        else:
            print("   ⚠️  No valid credentials found (expected for test)")
        
        # Test labels
        print("\n📋 Testing labels retrieval...")
        labels = gmail_service.get_labels()
        print(f"   Found {len(labels)} labels")
        
        print(f"\n✅ Gmail service test completed!")
        print(f"💡 Connect a real Gmail account to test email operations")
        
    except Exception as e:
        print(f"❌ Gmail service test failed: {e}")

if __name__ == "__main__":
    main()