# ====================================
# UNIFIED AI EMAIL ASSISTANT - COMPLETE SINGLE FILE APPLICATION
# ====================================
# Combined FastAPI application with Gmail OAuth, authentication, and email fetching
# Usage: python unified_app.py

import sys
import os
import time
import json
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import base64

# FastAPI imports
from fastapi import FastAPI, Request, HTTPException, Depends, Query, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

# Google OAuth and API imports
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Database and encryption imports
import psycopg2
from psycopg2.extras import RealDictCursor
from cryptography.fernet import Fernet

# Email parsing imports
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import html
import re

# Add project root to Python path
sys.path.append('/teamspace/studios/this_studio')
sys.path.append('/teamspace/studios/this_studio/email-assistant')

# ====================================
# CONFIGURATION LOADING
# ====================================

# Import config functions using robust approach
import importlib.util
config_path = '/teamspace/studios/this_studio/email-assistant/config.py'
spec = importlib.util.spec_from_file_location("config", config_path)

if spec is None or spec.loader is None:
    raise ImportError(f"Could not load config module from {config_path}")

config_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_module)

# Extract required functions
get_config = config_module.get_config
get_supabase_connection_params = config_module.get_supabase_connection_params
get_cors_settings = config_module.get_cors_settings

# ====================================
# PYDANTIC MODELS
# ====================================

class AuthStatusResponse(BaseModel):
    """Response model for authentication status"""
    authenticated: bool
    user_id: str
    connected_accounts: List[Dict[str, Any]]
    total_accounts: int

class AccountInfo(BaseModel):
    """Model for account information"""
    id: int
    email_address: EmailStr
    display_name: Optional[str]
    provider: str
    is_active: bool
    connected_at: datetime
    last_sync_at: Optional[datetime]

class AuthStartResponse(BaseModel):
    """Response model for starting authentication"""
    authorization_url: str
    state: str
    message: str

class AuthCallbackResponse(BaseModel):
    """Response model for authentication callback"""
    success: bool
    message: str
    account_id: Optional[int]
    email_address: Optional[str]
    redirect_url: str

class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str
    message: str
    details: Optional[str] = None

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

# ====================================
# GMAIL OAUTH HANDLER CLASS
# ====================================

class GmailOAuthHandler:
    """Handles complete Gmail OAuth 2.0 flow with secure token management"""
    
    def __init__(self):
        """Initialize OAuth handler with configuration and encryption"""
        self.config = get_config()
        
        # OAuth configuration
        self.client_id = self.config.gmail_client_id
        self.client_secret = self.config.gmail_client_secret
        
        # Redirect URI with fallback logic
        DEFAULT_LIGHTNING_REDIRECT = (
            "https://8000-01kb5kythhgsxk5vqz7yekpc49.cloudspaces.litng.ai"
            "/api/auth/gmail/callback"
        )
        
        env_redirect = os.getenv("GMAIL_REDIRECT_URI", "").strip()
        config_redirect = getattr(self.config, "gmail_redirect_uri", "").strip()
        
        def is_valid_non_localhost(url: str) -> bool:
            return bool(url) and "localhost" not in url and "127.0.0.1" not in url
        
        if is_valid_non_localhost(env_redirect):
            self.redirect_uri = env_redirect
        elif is_valid_non_localhost(config_redirect):
            self.redirect_uri = config_redirect
        else:
            self.redirect_uri = DEFAULT_LIGHTNING_REDIRECT
        
        # Required OAuth scopes for email access
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'openid',
        ]
        
        # Initialize encryption for token storage
        try:
            # Get the encryption key from config
            encryption_key = getattr(self.config, 'encryption_key', 'your_encryption_key_here_32_char')
            
            # Ensure we have a proper 32-byte key for Fernet
            if len(encryption_key) == 32:
                # Key is already the right length, encode it
                key_bytes = encryption_key.encode('utf-8')
                fernet_key = base64.urlsafe_b64encode(key_bytes)
            else:
                # Hash the key to get exactly 32 bytes
                import hashlib
                key_hash = hashlib.sha256(encryption_key.encode('utf-8')).digest()
                fernet_key = base64.urlsafe_b64encode(key_hash)
            
            self.fernet = Fernet(fernet_key)
            
        except Exception as e:
            # Fallback: create a deterministic key from a known string
            print(f"⚠️ Warning: Using fallback encryption key due to: {e}")
            import hashlib
            fallback_string = 'unified_email_assistant_encryption_fallback_key_2024'
            fallback_key = hashlib.sha256(fallback_string.encode('utf-8')).digest()
            fernet_key = base64.urlsafe_b64encode(fallback_key)
            self.fernet = Fernet(fernet_key)
        
        # Database connection parameters
        self.db_params = get_supabase_connection_params(self.config)
    
    def generate_authorization_url(self, user_id: str) -> Tuple[str, str]:
        """Generate OAuth authorization URL for user to grant permissions"""
        try:
            state_token = secrets.token_urlsafe(32)
            
            flow_config = {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            }
            
            flow = Flow.from_client_config(
                flow_config,
                scopes=self.scopes,
                state=state_token,
                redirect_uri=self.redirect_uri,
            )
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent',
                login_hint=None
            )
            
            self._store_oauth_state(user_id, state_token)
            return authorization_url, state_token
            
        except Exception as e:
            raise Exception(f"Failed to generate authorization URL: {str(e)}")
    
    def exchange_code_for_tokens(self, authorization_code: str, state: str, user_id: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            if not self._validate_oauth_state(user_id, state):
                raise Exception("Invalid state parameter - possible CSRF attack")
            
            flow_config = {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            }
            
            flow = Flow.from_client_config(
                flow_config,
                scopes=self.scopes,
                state=state,
                redirect_uri=self.redirect_uri,
            )
            
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials
            
            user_info = self._get_user_info(credentials)
            
            token_data = {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_expiry': credentials.expiry.isoformat() if credentials.expiry else None,
                'scopes': credentials.scopes,
                'user_email': user_info['email'],
                'user_name': user_info.get('name', ''),
                'user_picture': user_info.get('picture', ''),
            }
            
            return token_data
            
        except Exception as e:
            raise Exception(f"Failed to exchange authorization code: {str(e)}")
    
    def store_account_tokens(self, user_id: str, token_data: Dict[str, Any]) -> int:
        """Store encrypted tokens and account information in Supabase database"""
        connection = None
        try:
            connection = psycopg2.connect(**self.db_params)
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            encrypted_access_token = self._encrypt_token(token_data['access_token'])
            encrypted_refresh_token = self._encrypt_token(token_data['refresh_token'])
            
            cursor.execute("""
                SELECT id, email_address FROM email_accounts 
                WHERE user_id = %s AND provider = 'gmail' AND email_address = %s
            """, (user_id, token_data['user_email']))
            
            existing_account = cursor.fetchone()
            
            if existing_account:
                cursor.execute("""
                    UPDATE email_accounts 
                    SET access_token = %s, refresh_token = %s, token_expiry = %s,
                        granted_scopes = %s, display_name = %s, is_active = TRUE, updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                """, (
                    encrypted_access_token, encrypted_refresh_token, token_data['token_expiry'],
                    json.dumps(token_data['scopes']), token_data['user_name'], existing_account['id']
                ))
                account_id = cursor.fetchone()['id']
            else:
                cursor.execute("""
                    INSERT INTO email_accounts (
                        user_id, provider, email_address, display_name,
                        access_token, refresh_token, token_expiry, granted_scopes,
                        is_active, connected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    user_id, 'gmail', token_data['user_email'], token_data['user_name'],
                    encrypted_access_token, encrypted_refresh_token, token_data['token_expiry'],
                    json.dumps(token_data['scopes']), True, datetime.now(timezone.utc)
                ))
                account_id = cursor.fetchone()['id']
            
            connection.commit()
            cursor.close()
            connection.close()
            
            return account_id
            
        except Exception as e:
            if connection:
                connection.rollback()
                connection.close()
            raise Exception(f"Failed to store account tokens: {str(e)}")
    
    def get_valid_credentials(self, account_id: int) -> Optional[Credentials]:
        """Get valid credentials for API calls, refreshing if necessary"""
        try:
            # Get account data from database
            account_data = self._get_account_from_db(account_id)
            if not account_data or not account_data['is_active']:
                print(f"❌ Account {account_id} not found or inactive")
                return None

            # Decrypt tokens
            try:
                access_token = self._decrypt_token(account_data['access_token'])
                refresh_token = self._decrypt_token(account_data['refresh_token'])
                print(f"✅ Tokens decrypted successfully for account {account_id}")
            except Exception as e:
                print(f"❌ Token decryption failed: {e}")
                return None

            # Parse token expiry - Google Credentials expects timezone-naive datetime
            token_expiry = None
            if account_data['token_expiry']:
                try:
                    expiry_str = str(account_data['token_expiry'])
                    # Handle both string and datetime objects
                    if isinstance(account_data['token_expiry'], str):
                        # Remove any timezone suffix for parsing
                        if '+' in expiry_str:
                            expiry_str = expiry_str.split('+')[0]
                        elif 'Z' in expiry_str:
                            expiry_str = expiry_str.replace('Z', '')
                        
                        # Parse as naive datetime (Google expects this)
                        token_expiry = datetime.fromisoformat(expiry_str)
                    else:
                        # Already a datetime object - make it naive
                        token_expiry = account_data['token_expiry']
                        if token_expiry.tzinfo is not None:
                            # Convert to naive UTC datetime
                            token_expiry = token_expiry.utctimetuple()
                            token_expiry = datetime(*token_expiry[:6])
                    
                    print(f"✅ Token expiry parsed as naive datetime: {token_expiry}")
                    
                except Exception as e:
                    print(f"⚠️ Warning: Could not parse token expiry '{account_data['token_expiry']}': {e}")
                    # Set expiry to None and let Google handle it
                    token_expiry = None

            # Parse granted scopes - handle both JSON string and already-parsed list
            try:
                granted_scopes = account_data['granted_scopes']
                if isinstance(granted_scopes, str):
                    # It's a JSON string, parse it
                    scopes = json.loads(granted_scopes)
                elif isinstance(granted_scopes, list):
                    # It's already a list, use it directly
                    scopes = granted_scopes
                else:
                    # Fallback to default scopes
                    print(f"⚠️ Warning: Unexpected scopes format: {type(granted_scopes)}")
                    scopes = self.scopes
                    
                print(f"✅ Scopes parsed: {len(scopes)} scopes")
            except Exception as e:
                print(f"⚠️ Warning: Could not parse scopes: {e}")
                scopes = self.scopes  # Use default scopes

            # Create credentials object
            try:
                credentials = Credentials(
                    token=access_token,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    scopes=scopes,
                    expiry=token_expiry,
                )
                print(f"✅ Credentials object created successfully")
                
            except Exception as e:
                print(f"❌ Failed to create credentials object: {e}")
                return None

            # Check if token needs refresh (expires within 5 minutes)
            needs_refresh = False
            if token_expiry:
                # Compare using naive datetimes (both UTC)
                now_utc_naive = datetime.utcnow()  # This is naive UTC
                time_until_expiry = token_expiry - now_utc_naive
                if time_until_expiry.total_seconds() < 300:  # 5 minutes
                    needs_refresh = True
                    print(f"🔄 Token expires in {time_until_expiry}, needs refresh")
            
            # Also check Google's built-in expiry check
            try:
                if credentials.expired:
                    needs_refresh = True
                    print(f"🔄 Google says token is expired, needs refresh")
            except Exception as e:
                print(f"⚠️ Warning: Could not check credential expiry: {e}")
                # If we can't check expiry, assume it's fine

            if needs_refresh:
                try:
                    print(f"🔄 Refreshing token for account: {account_id}")
                    request = GoogleRequest()
                    credentials.refresh(request)

                    # Update database with refreshed token
                    if credentials.token and credentials.expiry:
                        self._update_access_token(account_id, credentials.token, credentials.expiry)
                        print(f"✅ Token refreshed and updated in database")
                    else:
                        print(f"⚠️ Token refresh succeeded but missing token or expiry")
                        
                except Exception as e:
                    print(f"❌ Token refresh failed: {e}")
                    return None

            print(f"✅ Valid credentials ready for account {account_id}")
            return credentials

        except Exception as e:
            print(f"❌ Error getting valid credentials for account {account_id}: {e}")
            import traceback
            print(f"📋 Traceback: {traceback.format_exc()}")
            return None
    
    # Helper methods
    def _encrypt_token(self, token: str) -> str:
        return self.fernet.encrypt(token.encode()).decode()
    
    def _decrypt_token(self, encrypted_token: str) -> str:
        return self.fernet.decrypt(encrypted_token.encode()).decode()
    
    def _store_oauth_state(self, user_id: str, state_token: str):
        state_file = f"/tmp/oauth_state_{user_id}.json"
        with open(state_file, 'w') as f:
            json.dump({'state': state_token, 'timestamp': datetime.now().isoformat()}, f)
    
    def _validate_oauth_state(self, user_id: str, state: str) -> bool:
        try:
            state_file = f"/tmp/oauth_state_{user_id}.json"
            if not os.path.exists(state_file):
                return False
            
            with open(state_file, 'r') as f:
                stored_data = json.load(f)
            
            stored_time = datetime.fromisoformat(stored_data['timestamp'])
            if (datetime.now() - stored_time).seconds > 300:
                os.remove(state_file)
                return False
            
            is_valid = stored_data['state'] == state
            os.remove(state_file)
            return is_valid
        except Exception:
            return False
    
    def _get_user_info(self, credentials: Credentials) -> Dict[str, Any]:
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            
            return {
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture'),
                'verified_email': user_info.get('verified_email', False),
            }
        except Exception as e:
            return {'email': 'unknown@gmail.com', 'name': 'Unknown User'}
    
    def _get_account_from_db(self, account_id: int) -> Optional[Dict[str, Any]]:
        try:
            connection = psycopg2.connect(**self.db_params)
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("SELECT * FROM email_accounts WHERE id = %s AND provider = 'gmail'", (account_id,))
            result = cursor.fetchone()
            
            cursor.close()
            connection.close()
            
            return dict(result) if result else None
        except Exception as e:
            return None
    
    def _update_access_token(self, account_id: int, access_token: str, expiry: datetime):
        try:
            connection = psycopg2.connect(**self.db_params)
            cursor = connection.cursor()
            
            encrypted_token = self._encrypt_token(access_token)
            expiry_str = expiry.isoformat() if expiry else None
            
            cursor.execute("""
                UPDATE email_accounts 
                SET access_token = %s, token_expiry = %s, updated_at = NOW()
                WHERE id = %s
            """, (encrypted_token, expiry_str, account_id))
            
            connection.commit()
            cursor.close()
            connection.close()
        except Exception as e:
            pass

# ====================================
# GMAIL SERVICE CLASS
# ====================================

class GmailService:
    """Gmail API service for comprehensive email operations"""
    
    def __init__(self, account_id: int):
        self.account_id = account_id
        self.config = get_config()
        self.oauth_handler = GmailOAuthHandler()
        self.rate_limit_delay = 60 / self.config.gmail_api_rate_limit
        self.last_request_time = 0
        self._service = None
        self.db_params = get_supabase_connection_params(self.config)
    
    def _get_service(self):
        try:
            if self._service is None:
                credentials = self.oauth_handler.get_valid_credentials(self.account_id)
                if not credentials:
                    return None
                self._service = build('gmail', 'v1', credentials=credentials)
            return self._service
        except Exception as e:
            self._service = None
            return None
    
    def _rate_limit_check(self):
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_request
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        try:
            service = self._get_service()
            if not service:
                return None
            
            self._rate_limit_check()
            profile = service.users().getProfile(userId='me').execute()
            
            return {
                'email_address': profile.get('emailAddress'),
                'messages_total': profile.get('messagesTotal', 0),
                'threads_total': profile.get('threadsTotal', 0),
                'history_id': profile.get('historyId'),
            }
        except Exception as e:
            return None
    
    def fetch_messages(self, max_results: int = 100, query: str = "", page_token: Optional[str] = None) -> Tuple[List[EmailMessage], Optional[str]]:
        try:
            service = self._get_service()
            if not service:
                return [], None
            
            self._rate_limit_check()
            
            list_params = {
                'userId': 'me',
                'q': query,
                'maxResults': min(max_results, 500)
            }
            
            if page_token:
                list_params['pageToken'] = page_token
            
            messages_result = service.users().messages().list(**list_params).execute()
            message_ids = messages_result.get('messages', [])
            next_page_token = messages_result.get('nextPageToken')
            
            if not message_ids:
                return [], None
            
            messages = []
            for msg_data in message_ids:
                try:
                    self._rate_limit_check()
                    message = service.users().messages().get(
                        userId='me', 
                        id=msg_data['id'],
                        format='full'
                    ).execute()
                    
                    parsed_message = self._parse_gmail_message(message)
                    if parsed_message:
                        messages.append(parsed_message)
                except Exception as e:
                    continue
            
            return messages, next_page_token
            
        except Exception as e:
            return [], None
    
    def _parse_gmail_message(self, gmail_message: Dict[str, Any]) -> Optional[EmailMessage]:
        try:
            message_id = gmail_message['id']
            thread_id = gmail_message.get('threadId')
            labels = gmail_message.get('labelIds', [])
            snippet = gmail_message.get('snippet', '')
            
            headers = {}
            payload = gmail_message.get('payload', {})
            for header in payload.get('headers', []):
                headers[header['name'].lower()] = header['value']
            
            sender_email, sender_name = self._parse_email_address(headers.get('from', ''))
            subject = headers.get('subject', '')
            date_str = headers.get('date', '')
            
            date_sent = self._parse_email_date(date_str)
            
            recipients = self._parse_recipients(headers.get('to', ''))
            cc_recipients = self._parse_recipients(headers.get('cc', ''))
            bcc_recipients = self._parse_recipients(headers.get('bcc', ''))
            
            body_plain, body_html = self._extract_message_body(payload)
            
            is_read = 'UNREAD' not in labels
            is_important = 'IMPORTANT' in labels or 'CATEGORY_PERSONAL' in labels
            has_attachments = self._has_attachments(payload)
            attachment_count = self._count_attachments(payload)
            
            folder_name = self._determine_folder(labels)
            size_bytes = int(gmail_message.get('sizeEstimate', 0))
            
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
            return None
    
    def _parse_email_address(self, address_str: str) -> Tuple[str, Optional[str]]:
        try:
            if not address_str:
                return "unknown@example.com", None
            
            import re
            match = re.match(r'^(.*?)\s*<(.+?)>$', address_str.strip())
            if match:
                name = match.group(1).strip().strip('"\'')
                email = match.group(2).strip()
                return email, name if name else None
            else:
                email = address_str.strip()
                return email, None
        except Exception:
            return address_str, None
    
    def _parse_recipients(self, recipients_str: str) -> List[Dict[str, str]]:
        try:
            if not recipients_str:
                return []
            
            recipients = []
            for recipient in recipients_str.split(','):
                email, name = self._parse_email_address(recipient.strip())
                recipients.append({'email': email, 'name': name or ''})
            
            return recipients
        except Exception:
            return []
    
    def _parse_email_date(self, date_str: str) -> datetime:
        try:
            if not date_str:
                return datetime.now(timezone.utc)
            
            import email.utils
            timestamp = email.utils.parsedate_tz(date_str)
            if timestamp:
                dt = datetime(*timestamp[:6], tzinfo=timezone.utc)
                if timestamp[9]:
                    offset = timedelta(seconds=timestamp[9])
                    dt = dt - offset
                return dt
            else:
                return datetime.now(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)
    
    def _extract_message_body(self, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
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
                
                for subpart in part.get('parts', []):
                    extract_from_part(subpart)
            
            extract_from_part(payload)
            return body_plain, body_html
        except Exception as e:
            return None, None
    
    def _has_attachments(self, payload: Dict[str, Any]) -> bool:
        try:
            def check_parts(part):
                if part.get('filename') and part.get('body', {}).get('attachmentId'):
                    return True
                for subpart in part.get('parts', []):
                    if check_parts(subpart):
                        return True
                return False
            
            return check_parts(payload)
        except Exception:
            return False
    
    def _count_attachments(self, payload: Dict[str, Any]) -> int:
        try:
            count = 0
            
            def count_parts(part):
                nonlocal count
                if part.get('filename') and part.get('body', {}).get('attachmentId'):
                    count += 1
                for subpart in part.get('parts', []):
                    count_parts(subpart)
            
            count_parts(payload)
            return count
        except Exception:
            return 0
    
    def _determine_folder(self, labels: List[str]) -> str:
        try:
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
                for label in labels:
                    if not label.startswith('CATEGORY_') and label not in ['IMPORTANT', 'UNREAD']:
                        return label
                return 'INBOX'
        except Exception:
            return 'INBOX'

# ====================================
# FASTAPI APPLICATION SETUP
# ====================================

def create_unified_app():
    """Create a unified FastAPI application with integrated Gmail functionality"""
    
    config = get_config()
    
    app = FastAPI(
        title="Unified AI Email Assistant",
        description="Gmail OAuth authentication and email management API with integrated UI",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add CORS middleware
    try:
        cors_settings = get_cors_settings(config)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_settings["allow_origins"],
            allow_credentials=cors_settings["allow_credentials"],
            allow_methods=cors_settings["allow_methods"],
            allow_headers=cors_settings["allow_headers"],
        )
    except Exception as e:
        print(f"⚠️ CORS configuration error: {e}")
    
    # Security scheme
    security = HTTPBearer(auto_error=False)
    
    # ====================================
    # DEPENDENCY INJECTION FUNCTIONS
    # ====================================
    
    def get_oauth_handler() -> GmailOAuthHandler:
        return GmailOAuthHandler()
    
    def get_user_id(request: Request) -> str:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            user_id = "demo_user_btechproject"
        return user_id
    
    def get_database_connection():
        try:
            db_params = get_supabase_connection_params(config)
            return psycopg2.connect(**db_params)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")
    
    # ====================================
    # ROOT ENDPOINTS
    # ====================================
    
    @app.get("/")
    async def root():
        """Root endpoint with unified interface"""
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Unified AI Email Assistant</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    min-height: 100vh;
                }
                .container {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 15px;
                    padding: 40px;
                    backdrop-filter: blur(10px);
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                }
                h1 {
                    text-align: center;
                    margin-bottom: 10px;
                    font-size: 2.5em;
                }
                .subtitle {
                    text-align: center;
                    margin-bottom: 40px;
                    opacity: 0.9;
                    font-size: 1.2em;
                }
                .features {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                    margin: 30px 0;
                }
                .feature-card {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 10px;
                    padding: 20px;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                }
                .feature-card h3 {
                    margin-top: 0;
                    color: #fff;
                }
                .btn {
                    display: inline-block;
                    padding: 12px 24px;
                    background: #4CAF50;
                    color: white;
                    text-decoration: none;
                    border-radius: 25px;
                    transition: all 0.3s ease;
                    margin: 10px 5px;
                    border: none;
                    cursor: pointer;
                    font-size: 16px;
                }
                .btn:hover {
                    background: #45a049;
                    transform: translateY(-2px);
                    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
                }
                .btn-secondary {
                    background: #2196F3;
                }
                .btn-secondary:hover {
                    background: #1976D2;
                }
                .status {
                    text-align: center;
                    margin: 20px 0;
                    padding: 15px;
                    border-radius: 10px;
                    background: rgba(255, 255, 255, 0.1);
                }
                .success { color: #4CAF50; }
                .warning { color: #FFC107; }
                .error { color: #f44336; }
                .code-block {
                    background: rgba(0, 0, 0, 0.3);
                    border-radius: 5px;
                    padding: 15px;
                    margin: 10px 0;
                    font-family: 'Courier New', monospace;
                    overflow-x: auto;
                }
                .grid-2 {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin: 20px 0;
                }
                @media (max-width: 768px) {
                    .grid-2 { grid-template-columns: 1fr; }
                    body { padding: 10px; }
                    h1 { font-size: 2em; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📧 Unified AI Email Assistant</h1>
                <div class="subtitle">Gmail OAuth Authentication & Email Management</div>
                
                <div class="status">
                    <div>🟢 System Status: <span class="success">All Services Running</span></div>
                    <div>🔗 API Base: <strong>/api</strong> | 📖 Docs: <strong>/docs</strong></div>
                </div>
                
                <div class="features">
                    <div class="feature-card">
                        <h3>🔐 Gmail OAuth</h3>
                        <p>Connect any Gmail account securely using OAuth 2.0</p>
                        <div class="code-block">GET /api/auth/gmail</div>
                        <a href="/api/auth/gmail" class="btn">Connect Gmail</a>
                    </div>
                    
                    <div class="feature-card">
                        <h3>📧 Recent Emails</h3>
                        <p>Fetch your latest emails from connected Gmail account</p>
                        <div class="code-block">GET /recent-emails</div>
                        <a href="/recent-emails" class="btn">View Recent Emails</a>
                    </div>
                    
                    <div class="feature-card">
                        <h3>📊 Account Status</h3>
                        <p>Check authentication status and connected accounts</p>
                        <div class="code-block">GET /api/auth/status</div>
                        <a href="/api/auth/status" class="btn btn-secondary">Check Status</a>
                    </div>
                    
                    <div class="feature-card">
                        <h3>📚 API Documentation</h3>
                        <p>Interactive API documentation and testing interface</p>
                        <div class="code-block">GET /docs</div>
                        <a href="/docs" class="btn btn-secondary">View Docs</a>
                    </div>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <h3>🚀 Quick Test</h3>
                    <p>Test the Gmail OAuth and Email fetching:</p>
                    <div class="code-block">
# 1. Connect Gmail account
curl -X GET "http://localhost:8000/api/auth/gmail" -H "X-User-ID: test_user"

# 2. Check account status  
curl -X GET "http://localhost:8000/api/auth/status" -H "X-User-ID: test_user"

# 3. Fetch recent emails
curl -X GET "http://localhost:8000/recent-emails?user_id=test_user&limit=10"
                    </div>
                </div>
            </div>
        </body>
        </html>
        """)
    
    # ====================================
    # AUTHENTICATION ENDPOINTS
    # ====================================
    
    @app.get("/api/auth/gmail", response_model=AuthStartResponse)
    async def start_gmail_auth(
        request: Request,
        oauth_handler: GmailOAuthHandler = Depends(get_oauth_handler),
        user_id: str = Depends(get_user_id)
    ):
        """Start Gmail OAuth authentication flow"""
        try:
            authorization_url, state_token = oauth_handler.generate_authorization_url(user_id)
            
            return AuthStartResponse(
                authorization_url=authorization_url,
                state=state_token,
                message="Please visit the authorization URL to connect your Gmail account"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error="auth_start_failed",
                    message="Failed to start Gmail authentication",
                    details=str(e)
                ).dict()
            )
    
    @app.get("/api/auth/gmail/callback", response_model=AuthCallbackResponse)
    async def handle_gmail_callback(
        request: Request,
        code: str = Query(..., description="Authorization code from Google"),
        state: str = Query(..., description="State parameter for CSRF protection"),
        error: Optional[str] = Query(None, description="Error from OAuth provider"),
        oauth_handler: GmailOAuthHandler = Depends(get_oauth_handler),
        user_id: str = Depends(get_user_id)
    ):
        """Handle OAuth callback from Gmail"""
        try:
            if error:
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponse(
                        error="oauth_error",
                        message=f"OAuth authorization failed: {error}",
                        details="User denied access or other OAuth error occurred"
                    ).dict()
                )
            
            if not code or not state:
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponse(
                        error="missing_parameters",
                        message="Missing required OAuth parameters",
                        details="Both 'code' and 'state' parameters are required"
                    ).dict()
                )
            
            token_data = oauth_handler.exchange_code_for_tokens(code, state, user_id)
            account_id = oauth_handler.store_account_tokens(user_id, token_data)
            
            return AuthCallbackResponse(
                success=True,
                message=f"Gmail account '{token_data['user_email']}' connected successfully!",
                account_id=account_id,
                email_address=token_data['user_email'],
                redirect_url="/"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error="callback_processing_failed",
                    message="Failed to process Gmail authentication callback",
                    details=str(e)
                ).dict()
            )
    
    @app.get("/api/auth/status", response_model=AuthStatusResponse)
    async def get_auth_status(
        request: Request,
        user_id: str = Depends(get_user_id)
    ):
        """Get authentication status and connected accounts"""
        try:
            connection = get_database_connection()
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    id, email_address, display_name, provider,
                    is_active, connected_at, last_sync_at
                FROM email_accounts 
                WHERE user_id = %s 
                ORDER BY connected_at DESC
            """, (user_id,))
            
            accounts_raw = cursor.fetchall()
            
            connected_accounts = []
            for account in accounts_raw:
                connected_accounts.append({
                    "id": account["id"],
                    "email_address": account["email_address"],
                    "display_name": account["display_name"],
                    "provider": account["provider"],
                    "is_active": account["is_active"],
                    "connected_at": account["connected_at"].isoformat(),
                    "last_sync_at": account["last_sync_at"].isoformat() if account["last_sync_at"] else None
                })
            
            cursor.close()
            connection.close()
            
            authenticated = len([acc for acc in connected_accounts if acc["is_active"]]) > 0
            
            return AuthStatusResponse(
                authenticated=authenticated,
                user_id=user_id,
                connected_accounts=connected_accounts,
                total_accounts=len(connected_accounts)
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error="status_check_failed",
                    message="Failed to check authentication status",
                    details=str(e)
                ).dict()
            )
    
    @app.get("/api/auth/health")
    async def health_check():
        """Health check endpoint for authentication service"""
        try:
            oauth_handler = GmailOAuthHandler()
            connection = get_database_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM email_accounts")
            account_count = cursor.fetchone()[0]
            cursor.close()
            connection.close()
            
            return {
                "status": "healthy",
                "service": "authentication",
                "oauth_handler": "initialized",
                "database": "connected",
                "total_accounts": account_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=ErrorResponse(
                    error="service_unhealthy",
                    message="Authentication service health check failed",
                    details=str(e)
                ).dict()
            )
    
    @app.get("/debug/credentials/{account_id}")
    async def debug_credentials(account_id: int):
        """Debug endpoint to check credential retrieval"""
        try:
            oauth_handler = GmailOAuthHandler()
            
            # Check if account exists in database
            db_params = get_supabase_connection_params(config)
            connection = psycopg2.connect(**db_params)
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT id, email_address, is_active, token_expiry, 
                       LENGTH(access_token) as access_token_length,
                       LENGTH(refresh_token) as refresh_token_length
                FROM email_accounts 
                WHERE id = %s AND provider = 'gmail'
            """, (account_id,))
            
            account_data = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if not account_data:
                return {"error": "Account not found", "account_id": account_id}
            
            # Try to get credentials with detailed error tracking
            try:
                credentials = oauth_handler.get_valid_credentials(account_id)
                
                return {
                    "account_found": True,
                    "account_id": account_data['id'],
                    "email_address": account_data['email_address'],
                    "is_active": account_data['is_active'],
                    "token_expiry": account_data['token_expiry'],
                    "access_token_length": account_data['access_token_length'],
                    "refresh_token_length": account_data['refresh_token_length'],
                    "credentials_retrieved": credentials is not None,
                    "credentials_valid": bool(credentials and hasattr(credentials, 'token')),
                    "credential_test_success": True
                }
            except Exception as cred_error:
                import traceback
                return {
                    "account_found": True,
                    "credentials_retrieved": False,
                    "credentials_error": str(cred_error),
                    "credentials_traceback": traceback.format_exc(),
                    "credential_test_success": False
                }
            
        except Exception as e:
            import traceback
            return {
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    @app.get("/debug/direct-creds/{account_id}")
    async def debug_direct_credentials(account_id: int):
        """Direct test of credential creation step by step"""
        try:
            # Get raw account data
            config = get_config()
            db_params = get_supabase_connection_params(config)
            connection = psycopg2.connect(**db_params)
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM email_accounts 
                WHERE id = %s AND provider = 'gmail'
            """, (account_id,))
            
            account = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if not account:
                return {"error": "Account not found"}
            
            # Initialize OAuth handler
            oauth_handler = GmailOAuthHandler()
            
            # Step 1: Decrypt tokens
            try:
                access_token = oauth_handler._decrypt_token(account['access_token'])
                refresh_token = oauth_handler._decrypt_token(account['refresh_token'])
                step1_success = True
                step1_error = None
            except Exception as e:
                step1_success = False
                step1_error = str(e)
                access_token = refresh_token = None
            
            # Step 2: Parse expiry
            try:
                token_expiry = None
                if account['token_expiry']:
                    expiry_str = str(account['token_expiry'])
                    if isinstance(account['token_expiry'], str):
                        if '+' in expiry_str:
                            expiry_str = expiry_str.split('+')[0]
                        elif 'Z' in expiry_str:
                            expiry_str = expiry_str.replace('Z', '')
                        token_expiry = datetime.fromisoformat(expiry_str).replace(tzinfo=timezone.utc)
                    else:
                        token_expiry = account['token_expiry']
                        if token_expiry.tzinfo is None:
                            token_expiry = token_expiry.replace(tzinfo=timezone.utc)
                
                step2_success = True
                step2_error = None
            except Exception as e:
                step2_success = False
                step2_error = str(e)
                token_expiry = None
            
            # Step 3: Parse scopes
            try:
                scopes = json.loads(account['granted_scopes'] or '[]')
                step3_success = True
                step3_error = None
            except Exception as e:
                step3_success = False
                step3_error = str(e)
                scopes = []
            
            # Step 4: Create credentials
            credentials = None
            step4_success = False
            step4_error = None
            
            if step1_success and access_token and refresh_token:
                try:
                    credentials = Credentials(
                        token=access_token,
                        refresh_token=refresh_token,
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=oauth_handler.client_id,
                        client_secret=oauth_handler.client_secret,
                        scopes=scopes,
                        expiry=token_expiry,
                    )
                    step4_success = True
                except Exception as e:
                    step4_error = str(e)
            
            return {
                "account_id": account_id,
                "email": account['email_address'],
                "step1_decrypt_tokens": {
                    "success": step1_success,
                    "error": step1_error,
                    "access_token_length": len(access_token) if access_token else 0,
                    "refresh_token_length": len(refresh_token) if refresh_token else 0
                },
                "step2_parse_expiry": {
                    "success": step2_success,
                    "error": step2_error,
                    "parsed_expiry": str(token_expiry) if token_expiry else None,
                    "raw_expiry": str(account['token_expiry'])
                },
                "step3_parse_scopes": {
                    "success": step3_success,
                    "error": step3_error,
                    "scopes_count": len(scopes),
                    "raw_scopes": account['granted_scopes']
                },
                "step4_create_credentials": {
                    "success": step4_success,
                    "error": step4_error,
                    "client_id_available": bool(oauth_handler.client_id),
                    "client_secret_available": bool(oauth_handler.client_secret)
                },
                "final_credentials_valid": bool(credentials and hasattr(credentials, 'token'))
            }
            
        except Exception as e:
            import traceback
            return {"error": str(e), "traceback": traceback.format_exc()}

    @app.get("/debug/decrypt-test/{account_id}")
    async def debug_decrypt_test(account_id: int):
        """Test token decryption specifically"""
        try:
            oauth_handler = GmailOAuthHandler()
            
            # Get raw account data
            db_params = get_supabase_connection_params(config)
            connection = psycopg2.connect(**db_params)
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT access_token, refresh_token, token_expiry, granted_scopes
                FROM email_accounts 
                WHERE id = %s AND provider = 'gmail'
            """, (account_id,))
            
            account = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if not account:
                return {"error": "Account not found"}
            
            # Test decryption
            try:
                access_token = oauth_handler._decrypt_token(account['access_token'])
                refresh_token = oauth_handler._decrypt_token(account['refresh_token'])
                
                return {
                    "decryption_success": True,
                    "access_token_decrypted": len(access_token) > 0,
                    "refresh_token_decrypted": len(refresh_token) > 0,
                    "access_token_preview": access_token[:20] + "..." if access_token else None,
                    "refresh_token_preview": refresh_token[:20] + "..." if refresh_token else None,
                    "token_expiry": account['token_expiry'],
                    "granted_scopes": account['granted_scopes']
                }
                
            except Exception as decrypt_error:
                return {
                    "decryption_success": False,
                    "decrypt_error": str(decrypt_error),
                    "raw_token_length": len(account['access_token']) if account['access_token'] else 0
                }
                
        except Exception as e:
            import traceback
            return {"error": str(e), "traceback": traceback.format_exc()}

    # ====================================
    # EMAIL ENDPOINTS
    # ====================================
    
    @app.get("/recent-emails")
    async def recent_emails(user_id: str = "demo_user_btechproject", limit: int = 10):
        """Fetch recent emails from connected Gmail account"""
        try:
            # Get the user's connected Gmail accounts
            db_params = get_supabase_connection_params(config)
            connection = psycopg2.connect(**db_params)
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            # Find active Gmail account for user
            cursor.execute("""
                SELECT id, email_address, display_name, is_active 
                FROM email_accounts 
                WHERE user_id = %s AND provider = 'gmail' AND is_active = TRUE
                ORDER BY connected_at DESC
                LIMIT 1
            """, (user_id,))
            
            account = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if not account:
                return JSONResponse(content={
                    "status": "error",
                    "message": "No active Gmail account found",
                    "user_id": user_id,
                    "suggestion": "Connect Gmail account first using /api/auth/gmail",
                    "gmail_connected": False
                }, status_code=404)
            
            # Use Gmail service to fetch emails
            gmail_service = GmailService(account['id'])
            
            # Test account connection first
            account_info = gmail_service.get_account_info()
            if not account_info:
                return JSONResponse(content={
                    "status": "error",
                    "message": "Unable to connect to Gmail API - check OAuth tokens",
                    "user_id": user_id,
                    "account_email": account['email_address'],
                    "suggestion": "Try reconnecting your Gmail account",
                    "gmail_connected": False
                }, status_code=401)
            
            # Fetch recent emails from inbox
            messages, next_page_token = gmail_service.fetch_messages(
                max_results=limit,
                query="in:inbox"
            )
            
            if not messages:
                return JSONResponse(content={
                    "status": "success",
                    "message": "No emails found in inbox",
                    "user_id": user_id,
                    "account_email": account['email_address'],
                    "account_name": account['display_name'],
                    "total_emails": 0,
                    "emails": [],
                    "gmail_connected": True
                })
            
            # Convert EmailMessage objects to JSON-serializable format
            emails_data = []
            for msg in messages:
                emails_data.append({
                    "id": msg.external_id,
                    "thread_id": msg.thread_id,
                    "subject": msg.subject or "No Subject",
                    "from": f"{msg.sender_name or ''} <{msg.sender_email}>".strip(" <>"),
                    "sender_email": msg.sender_email,
                    "sender_name": msg.sender_name,
                    "recipients": [f"{r.get('name', '')} <{r['email']}>".strip(" <>") for r in msg.recipients],
                    "date_sent": msg.date_sent.isoformat(),
                    "date_sent_formatted": msg.date_sent.strftime('%Y-%m-%d %H:%M:%S UTC'),
                    "snippet": msg.snippet or "",
                    "is_read": msg.is_read,
                    "is_important": msg.is_important,
                    "has_attachments": msg.has_attachments,
                    "attachment_count": msg.attachment_count,
                    "labels": msg.labels,
                    "folder_name": msg.folder_name,
                    "size_bytes": msg.size_bytes,
                    "size_formatted": f"{msg.size_bytes / 1024:.1f} KB" if msg.size_bytes else "0 KB",
                    "body_preview": (msg.snippet or "")[:200] + "..." if msg.snippet and len(msg.snippet) > 200 else msg.snippet
                })
            
            return JSONResponse(content={
                "status": "success",
                "message": f"Successfully fetched {len(emails_data)} recent emails",
                "user_id": user_id,
                "account_email": account['email_address'],
                "account_name": account['display_name'],
                "total_messages_in_account": account_info['messages_total'],
                "total_emails_fetched": len(emails_data),
                "limit": limit,
                "emails": emails_data,
                "next_page_token": next_page_token,
                "gmail_connected": True,
                "fetch_time": datetime.now().isoformat(),
                "account_info": {
                    "email_address": account_info['email_address'],
                    "messages_total": account_info['messages_total'],
                    "threads_total": account_info['threads_total'],
                    "history_id": account_info['history_id']
                }
            })
            
        except Exception as e:
            import traceback
            print(f"❌ Error fetching recent emails: {e}")
            print(f"📋 Traceback: {traceback.format_exc()}")
            
            return JSONResponse(content={
                "status": "error",
                "message": f"Failed to fetch recent emails: {str(e)}",
                "user_id": user_id,
                "error_details": str(e),
                "suggestion": "Check if Gmail account is properly connected and authenticated"
            }, status_code=500)
    
    @app.get("/health")
    async def health():
        """General health check"""
        return {
            "status": "healthy",
            "service": "gmail_assistant_api",
            "timestamp": datetime.now().isoformat()
        }
    
    @app.get("/info")
    async def info():
        """System information"""
        return JSONResponse(content={
            "app_name": config.app_name,
            "version": config.app_version,
            "environment": config.environment,
            "gmail_enabled": config.enable_gmail,
            "debug": config.debug,
            "endpoints": {
                "root": "/",
                "docs": "/docs",
                "auth": "/api/auth",
                "gmail_connect": "/api/auth/gmail",
                "auth_status": "/api/auth/status",
                "recent_emails": "/recent-emails",
                "health": "/health"
            }
        })
    
    return app

# ====================================
# MAIN FUNCTION
# ====================================

def main():
    """Run the unified FastAPI application"""
    print("🚀 Starting Unified AI Email Assistant - FastAPI Server")
    print("=" * 60)
    
    try:
        # Get configuration
        config = get_config()
        
        print("✅ Configuration loaded successfully!")
        print(f"🌐 Server starting on: http://{config.host}:{config.port}")
        print(f"📖 API Documentation: http://{config.host}:{config.port}/docs")
        print(f"🧪 Test Interface: http://{config.host}:{config.port}/")
        print(f"🔐 Gmail OAuth: http://{config.host}:{config.port}/api/auth/gmail")
        print(f"📧 Recent Emails: http://{config.host}:{config.port}/recent-emails")
        print("=" * 60)
        print("📝 Note: After connecting Gmail via OAuth, visit /recent-emails to see your emails")
        print("=" * 60)
        
        # Import uvicorn and run the FastAPI server
        import uvicorn
        
        # Create and run the app
        uvicorn.run(
            create_unified_app(),
            host=config.host,
            port=config.port,
            log_level="info",
            access_log=True
        )
        
    except Exception as e:
        print(f"❌ Failed to start FastAPI server: {e}")
        import traceback
        print(f"📋 Error details: {traceback.format_exc()}")
        print("💡 Check your configuration and dependencies")
        sys.exit(1)

if __name__ == "__main__":
    main()