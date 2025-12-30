# ====================================
# UNIFIED AI EMAIL ASSISTANT - GMAIL OAUTH HANDLER
# ====================================
# Handles Google OAuth 2.0 flow for Gmail API access
# Manages authorization URLs, token exchange, and secure token storage

import os
import json
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode, parse_qs, urlparse

# Google OAuth and API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Database and encryption imports
import psycopg2
from psycopg2.extras import RealDictCursor
from cryptography.fernet import Fernet

# Configuration import
import sys
from pathlib import Path

# Add the email-assistant directory to Python path
email_assistant_path = Path(__file__).parent.parent.parent / 'email-assistant'
sys.path.insert(0, str(email_assistant_path))

try:
    # Import config functions using a more robust approach
    import importlib.util

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

except Exception as e:
    print(f"Warning: Could not import config module: {e}")

    # Fallback to env-based config
    class FallbackConfig:
        def __init__(self):
            self.gmail_client_id = os.getenv('GMAIL_CLIENT_ID', '')
            self.gmail_client_secret = os.getenv('GMAIL_CLIENT_SECRET', '')
            self.gmail_redirect_uri = os.getenv(
                'GMAIL_REDIRECT_URI',
                'http://localhost:8000/auth/gmail/callback'
            )
            self.encryption_key = os.getenv(
                'ENCRYPTION_KEY',
                'your_encryption_key_here_32_char'
            )
            self.db_user = os.getenv('DB_USER', '')
            self.db_password = os.getenv('DB_PASSWORD', '')
            self.db_host = os.getenv('DB_HOST', '')
            self.db_port = int(os.getenv('DB_PORT', '6543'))
            self.db_name = os.getenv('DB_NAME', 'postgres')
            self.db_ssl_mode = os.getenv('DB_SSL_MODE', 'require')
            self.db_connect_timeout = int(os.getenv('DB_CONNECT_TIMEOUT', '10'))
            self.db_command_timeout = int(os.getenv('DB_COMMAND_TIMEOUT', '5'))

    get_config = lambda: FallbackConfig()  # noqa: E731

    def get_supabase_connection_params(config):
        return {
            "user": config.db_user,
            "password": config.db_password,
            "host": config.db_host,
            "port": config.db_port,
            "dbname": config.db_name,
            "sslmode": config.db_ssl_mode,
            "connect_timeout": config.db_connect_timeout,
            "options": f"-c statement_timeout={config.db_command_timeout}s",
        }


class GmailOAuthHandler:
    """
    Handles complete Gmail OAuth 2.0 flow with secure token management
    Features: Authorization URL generation, token exchange, refresh handling, secure storage
    """

    def __init__(self):
        """Initialize OAuth handler with configuration and encryption"""
        self.config = get_config()

        # OAuth configuration
        self.client_id = getattr(
            self.config,
            "gmail_client_id",
            os.getenv("GMAIL_CLIENT_ID", "")
        )
        self.client_secret = getattr(
            self.config,
            "gmail_client_secret",
            os.getenv("GMAIL_CLIENT_SECRET", "")
        )

        # ---------- REDIRECT URI LOGIC (FIXED FOR LIGHTNING URL) ----------
        # We want to prefer:
        #   1. GMAIL_REDIRECT_URI from env (what you put in .env)
        #   2. config.gmail_redirect_uri (if present and not localhost)
        #   3. A safe default: your Lightning public URL
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
            # Fall back to the Lightning public URL
            self.redirect_uri = DEFAULT_LIGHTNING_REDIRECT

        print(f"📍 Using Gmail redirect URI: {self.redirect_uri}")

        # Required OAuth scopes for email access
                # Required OAuth scopes for email access
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',   # Read emails
            'https://www.googleapis.com/auth/gmail.send',       # Send emails
            'https://www.googleapis.com/auth/gmail.modify',     # Modify labels
            'https://www.googleapis.com/auth/userinfo.email',   # Get user email
            'https://www.googleapis.com/auth/userinfo.profile', # Get user profile
            'openid',                                           # Needed for Google tokens (avoids scope mismatch)
        ]


        # Initialize encryption for token storage
        try:
            # Ensure the encryption key is valid for Fernet
            encryption_key = self.config.encryption_key.encode()
            if len(encryption_key) != 32:
                import base64
                import hashlib
                # Hash the key to get 32 bytes, then base64 encode for Fernet
                key_hash = hashlib.sha256(encryption_key).digest()
                fernet_key = base64.urlsafe_b64encode(key_hash)
                self.fernet = Fernet(fernet_key)
            else:
                self.fernet = Fernet(encryption_key)
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize encryption with provided key: {e}")
            # Fallback to a default key (in production, this should be handled properly)
            import base64
            import hashlib
            fallback_key = hashlib.sha256(
                b'your_encryption_key_here_32_char_fallback'
            ).digest()
            fernet_key = base64.urlsafe_b64encode(fallback_key)
            self.fernet = Fernet(fernet_key)

        # Database connection parameters
        self.db_params = get_supabase_connection_params(self.config)

        print("✅ Gmail OAuth Handler initialized successfully")

    def generate_authorization_url(self, user_id: str) -> Tuple[str, str]:
        """
        Generate OAuth authorization URL for user to grant permissions

        Args:
            user_id: Unique identifier for the user

        Returns:
            Tuple of (authorization_url, state_token)
        """
        try:
            # Generate secure state parameter to prevent CSRF attacks
            state_token = secrets.token_urlsafe(32)

            # Create OAuth flow configuration
            flow_config = {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            }

            # Initialize OAuth 2.0 flow
            flow = Flow.from_client_config(
                flow_config,
                scopes=self.scopes,
                state=state_token,
                redirect_uri=self.redirect_uri,
            )

            # Generate authorization URL with additional parameters
            authorization_url, state = flow.authorization_url(
                access_type='offline',         # Get refresh token
                include_granted_scopes='true', # Include previously granted scopes
                prompt='consent',              # Force consent screen for refresh token
                login_hint=None                # Optional: can pre-fill email
            )

            # Store state token temporarily for validation
            self._store_oauth_state(user_id, state_token)

            print(f"📝 Generated authorization URL for user: {user_id}")
            return authorization_url, state_token

        except Exception as e:
            print(f"❌ Error generating authorization URL: {e}")
            raise Exception(f"Failed to generate authorization URL: {str(e)}")

    def exchange_code_for_tokens(
        self,
        authorization_code: str,
        state: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens

        Args:
            authorization_code: Code received from OAuth callback
            state: State parameter for CSRF protection
            user_id: User identifier

        Returns:
            Dictionary with token information and user details
        """
        try:
            # Validate state parameter to prevent CSRF attacks
            if not self._validate_oauth_state(user_id, state):
                raise Exception("Invalid state parameter - possible CSRF attack")

            # Create OAuth flow for token exchange
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

            # Exchange authorization code for tokens
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials

            # Get user information from Google API
            user_info = self._get_user_info(credentials)

            # Prepare token data for storage
            token_data = {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_expiry': (
                    credentials.expiry.isoformat()
                    if credentials.expiry else None
                ),
                'scopes': credentials.scopes,
                'user_email': user_info['email'],
                'user_name': user_info.get('name', ''),
                'user_picture': user_info.get('picture', ''),
            }

            print(f"✅ Successfully exchanged code for tokens: {user_info['email']}")
            return token_data

        except Exception as e:
            print(f"❌ Error exchanging authorization code: {e}")
            raise Exception(f"Failed to exchange authorization code: {str(e)}")

    def store_account_tokens(self, user_id: str, token_data: Dict[str, Any]) -> int:
        """
        Store encrypted tokens and account information in Supabase database

        Args:
            user_id: User identifier
            token_data: Token and user information from OAuth exchange

        Returns:
            Account ID of the stored account
        """
        connection = None
        try:
            # Connect to Supabase
            connection = psycopg2.connect(**self.db_params)
            cursor = connection.cursor(cursor_factory=RealDictCursor)

            # Encrypt sensitive tokens before storage
            encrypted_access_token = self._encrypt_token(token_data['access_token'])
            encrypted_refresh_token = self._encrypt_token(token_data['refresh_token'])

            # Check if account already exists
            cursor.execute(
                """
                SELECT id, email_address FROM email_accounts 
                WHERE user_id = %s AND provider = 'gmail' AND email_address = %s
                """,
                (user_id, token_data['user_email']),
            )

            existing_account = cursor.fetchone()

            if existing_account:
                # Update existing account with new tokens
                cursor.execute(
                    """
                    UPDATE email_accounts 
                    SET access_token = %s,
                        refresh_token = %s,
                        token_expiry = %s,
                        granted_scopes = %s,
                        display_name = %s,
                        is_active = TRUE,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        encrypted_access_token,
                        encrypted_refresh_token,
                        token_data['token_expiry'],
                        json.dumps(token_data['scopes']),
                        token_data['user_name'],
                        existing_account['id'],
                    ),
                )

                account_id = cursor.fetchone()['id']
                print(f"🔄 Updated existing Gmail account: {token_data['user_email']}")

            else:
                # Insert new account
                cursor.execute(
                    """
                    INSERT INTO email_accounts (
                        user_id, provider, email_address, display_name,
                        access_token, refresh_token, token_expiry, granted_scopes,
                        is_active, connected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        'gmail',
                        token_data['user_email'],
                        token_data['user_name'],
                        encrypted_access_token,
                        encrypted_refresh_token,
                        token_data['token_expiry'],
                        json.dumps(token_data['scopes']),
                        True,
                        datetime.now(timezone.utc),
                    ),
                )

                account_id = cursor.fetchone()['id']
                print(f"🆕 Created new Gmail account: {token_data['user_email']}")

            # Commit transaction
            connection.commit()

            # Close connection
            cursor.close()
            connection.close()

            print(f"💾 Account tokens stored successfully with ID: {account_id}")
            return account_id

        except Exception as e:
            print(f"❌ Error storing account tokens: {e}")
            if connection:
                connection.rollback()
                connection.close()
            raise Exception(f"Failed to store account tokens: {str(e)}")

    def refresh_access_token(self, account_id: int) -> Optional[str]:
        """
        Refresh expired access token using stored refresh token

        Args:
            account_id: Database ID of the email account

        Returns:
            New access token or None if refresh failed
        """
        try:
            # Get account details from database
            account_data = self._get_account_from_db(account_id)
            if not account_data:
                raise Exception(f"Account not found: {account_id}")

            # Decrypt refresh token
            refresh_token = self._decrypt_token(account_data['refresh_token'])

            # Create credentials object for refresh
            credentials = Credentials(
                token=None,  # Will be refreshed
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=json.loads(account_data['granted_scopes'] or '[]'),
            )

            # Refresh the token
            request = Request()
            credentials.refresh(request)

            # Update database with new access token
            if credentials.token and credentials.expiry:
                self._update_access_token(
                    account_id,
                    credentials.token,
                    credentials.expiry
                )
            else:
                raise Exception("Failed to refresh token: missing token or expiry")

            print(f"🔄 Successfully refreshed access token for account: {account_id}")
            return credentials.token

        except Exception as e:
            print(f"❌ Error refreshing access token: {e}")
            # Mark account as inactive if refresh fails
            self._mark_account_inactive(account_id)
            return None

    def get_valid_credentials(self, account_id: int) -> Optional[Credentials]:
        """
        Get valid credentials for API calls, refreshing if necessary

        Args:
            account_id: Database ID of the email account

        Returns:
            Valid Credentials object or None if unavailable
        """
        try:
            # Get account data from database
            account_data = self._get_account_from_db(account_id)
            if not account_data or not account_data['is_active']:
                return None

            # Decrypt tokens
            access_token = self._decrypt_token(account_data['access_token'])
            refresh_token = self._decrypt_token(account_data['refresh_token'])

            # Parse token expiry
            token_expiry = None
            if account_data['token_expiry']:
                token_expiry = datetime.fromisoformat(
                    account_data['token_expiry'].replace('Z', '+00:00')
                )

            # Create credentials object
            credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=json.loads(account_data['granted_scopes'] or '[]'),
                expiry=token_expiry,
            )

            # Check if token needs refresh (expires within 5 minutes)
            if credentials.expired or (
                credentials.expiry
                and credentials.expiry
                < datetime.now(timezone.utc) + timedelta(minutes=5)
            ):
                print(f"🔄 Token expired, refreshing for account: {account_id}")
                request = Request()
                credentials.refresh(request)

                # Update database with refreshed token
                if credentials.token and credentials.expiry:
                    self._update_access_token(
                        account_id,
                        credentials.token,
                        credentials.expiry
                    )
                else:
                    raise Exception(
                        "Failed to refresh token: missing token or expiry"
                    )

            return credentials

        except Exception as e:
            print(f"❌ Error getting valid credentials: {e}")
            return None

    def revoke_account_access(self, account_id: int) -> bool:
        """
        Revoke OAuth access and deactivate account

        Args:
            account_id: Database ID of the email account

        Returns:
            True if successfully revoked, False otherwise
        """
        try:
            # Get credentials
            credentials = self.get_valid_credentials(account_id)
            if not credentials:
                print(f"⚠️ No valid credentials found for account: {account_id}")
                return False

            # Revoke token with Google
            revoke_url = f"https://oauth2.googleapis.com/revoke?token={credentials.token}"
            request = Request()
            response = request(revoke_url)

            # Mark account as inactive in database
            self._mark_account_inactive(account_id)

            print(f"✅ Successfully revoked access for account: {account_id}")
            return True

        except Exception as e:
            print(f"❌ Error revoking account access: {e}")
            return False

    # ====================================
    # PRIVATE HELPER METHODS
    # ====================================

    def _encrypt_token(self, token: str) -> str:
        """Encrypt token for secure storage"""
        return self.fernet.encrypt(token.encode()).decode()

    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt token from storage"""
        return self.fernet.decrypt(encrypted_token.encode()).decode()

    def _store_oauth_state(self, user_id: str, state_token: str):
        """Store OAuth state temporarily for CSRF protection"""
        # In production, store in Redis or similar cache
        # For now, store in file system (not ideal for production)
        state_file = f"/tmp/oauth_state_{user_id}.json"
        with open(state_file, 'w') as f:
            json.dump(
                {
                    'state': state_token,
                    'timestamp': datetime.now().isoformat(),
                },
                f,
            )

    def _validate_oauth_state(self, user_id: str, state: str) -> bool:
        """Validate OAuth state parameter"""
        try:
            state_file = f"/tmp/oauth_state_{user_id}.json"
            if not os.path.exists(state_file):
                return False

            with open(state_file, 'r') as f:
                stored_data = json.load(f)

            # Check if state matches and is not too old (5 minutes)
            stored_time = datetime.fromisoformat(stored_data['timestamp'])
            if (datetime.now() - stored_time).seconds > 300:
                os.remove(state_file)
                return False

            # Validate state and clean up
            is_valid = stored_data['state'] == state
            os.remove(state_file)

            return is_valid

        except Exception:
            return False

    def _get_user_info(self, credentials: Any) -> Dict[str, Any]:
        """Get user information from Google API"""
        try:
            # Build OAuth2 service
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()

            return {
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture'),
                'verified_email': user_info.get('verified_email', False),
            }

        except Exception as e:
            print(f"❌ Error getting user info: {e}")
            return {'email': 'unknown@gmail.com', 'name': 'Unknown User'}

    def _get_account_from_db(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Get account data from database"""
        try:
            connection = psycopg2.connect(**self.db_params)
            cursor = connection.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                """
                SELECT * FROM email_accounts WHERE id = %s AND provider = 'gmail'
                """,
                (account_id,),
            )

            result = cursor.fetchone()

            cursor.close()
            connection.close()

            return dict(result) if result else None

        except Exception as e:
            print(f"❌ Error getting account from database: {e}")
            return None

    def _update_access_token(
        self,
        account_id: int,
        access_token: str,
        expiry: Any
    ):
        """Update access token in database"""
        try:
            connection = psycopg2.connect(**self.db_params)
            cursor = connection.cursor()

            encrypted_token = self._encrypt_token(access_token)
            expiry_str = expiry.isoformat() if expiry else None

            cursor.execute(
                """
                UPDATE email_accounts 
                SET access_token = %s, token_expiry = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (encrypted_token, expiry_str, account_id),
            )

            connection.commit()
            cursor.close()
            connection.close()

        except Exception as e:
            print(f"❌ Error updating access token: {e}")

    def _mark_account_inactive(self, account_id: int):
        """Mark account as inactive due to authentication failure"""
        try:
            connection = psycopg2.connect(**self.db_params)
            cursor = connection.cursor()

            cursor.execute(
                """
                UPDATE email_accounts 
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = %s
                """,
                (account_id,),
            )

            connection.commit()
            cursor.close()
            connection.close()

            print(f"⚠️ Marked account {account_id} as inactive")

        except Exception as e:
            print(f"❌ Error marking account inactive: {e}")


# ====================================
# CONVENIENCE FUNCTIONS
# ====================================

def create_oauth_handler() -> GmailOAuthHandler:
    """Factory function to create OAuth handler"""
    return GmailOAuthHandler()


def generate_gmail_auth_url(user_id: str) -> Tuple[str, str]:
    """Quick function to generate Gmail authorization URL"""
    handler = create_oauth_handler()
    return handler.generate_authorization_url(user_id)


def process_gmail_callback(auth_code: str, state: str, user_id: str) -> int:
    """Quick function to process OAuth callback and store tokens"""
    handler = create_oauth_handler()
    token_data = handler.exchange_code_for_tokens(auth_code, state, user_id)
    account_id = handler.store_account_tokens(user_id, token_data)
    return account_id


# ====================================
# MAIN FUNCTION FOR TESTING
# ====================================

def main():
    """Test OAuth handler functionality"""
    print("🔐 Testing Gmail OAuth Handler")
    print("=" * 50)

    try:
        # Initialize handler
        handler = GmailOAuthHandler()
        print("✅ OAuth handler created successfully")

        # Test authorization URL generation
        test_user_id = f"test_user_{secrets.token_hex(4)}"
        auth_url, state = handler.generate_authorization_url(test_user_id)

        print("🔗 Authorization URL generated:")
        print(f"   {auth_url[:100]}...")
        print(f"🔑 State token: {state[:20]}...")

        # Test configuration
        print("\n📋 Configuration Check:")
        print(f"   Client ID: {handler.client_id[:20]}...")
        print(f"   Redirect URI: {handler.redirect_uri}")
        print(f"   Scopes: {len(handler.scopes)} scopes configured")

        print("\n✅ OAuth handler test completed successfully!")
        print("💡 Next: Use the authorization URL in your browser to test the full flow")

    except Exception as e:
        print(f"❌ OAuth handler test failed: {e}")


if __name__ == "__main__":
    main()
