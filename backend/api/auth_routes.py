# ====================================
# UNIFIED AI EMAIL ASSISTANT - AUTHENTICATION ROUTES
# ====================================
# FastAPI routes for Gmail OAuth authentication flow
# Handles OAuth authorization, callbacks, and account management

from fastapi import APIRouter, HTTPException, Depends, Request, Query, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
import secrets
import uuid
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
import sys
import os

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
# PYDANTIC MODELS FOR API SCHEMAS
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

# ====================================
# AUTHENTICATION ROUTER SETUP
# ====================================

# Create FastAPI router for authentication endpoints
auth_router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        403: {"model": ErrorResponse, "description": "Access forbidden"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)

# Security scheme for protected endpoints
security = HTTPBearer(auto_error=False)

# Global configuration
config = get_config()

# ====================================
# DEPENDENCY INJECTION FUNCTIONS
# ====================================

def get_oauth_handler() -> GmailOAuthHandler:
    """Dependency injection for OAuth handler"""
    return create_oauth_handler()

def get_user_id(request: Request) -> str:
    """
    Extract or generate user ID from request
    In production, this would come from JWT token or session
    For B.Tech demo, we'll use a demo user ID or generate one
    """
    # Check if user ID is in session or headers
    user_id = request.headers.get("X-User-ID")
    
    if not user_id:
        # For demo purposes, use a demo user ID
        # In production, this would be extracted from authenticated session
        user_id = "demo_user_btechproject"
    
    return user_id

def get_database_connection():
    """Get database connection for account queries"""
    try:
        db_params = get_supabase_connection_params(config)
        return psycopg2.connect(**db_params)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )

# ====================================
# AUTHENTICATION ENDPOINTS
# ====================================

@auth_router.get("/gmail", response_model=AuthStartResponse)
async def start_gmail_auth(
    request: Request,
    oauth_handler: GmailOAuthHandler = Depends(get_oauth_handler),
    user_id: str = Depends(get_user_id)
):
    """
    Start Gmail OAuth authentication flow
    
    Returns authorization URL for user to grant permissions
    """
    try:
        # Generate authorization URL and state token
        authorization_url, state_token = oauth_handler.generate_authorization_url(user_id)
        
        # Log the authentication attempt
        print(f"📧 Starting Gmail OAuth for user: {user_id}")
        
        return AuthStartResponse(
            authorization_url=authorization_url,
            state=state_token,
            message="Please visit the authorization URL to connect your Gmail account"
        )
        
    except Exception as e:
        print(f"❌ Error starting Gmail auth: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="auth_start_failed",
                message="Failed to start Gmail authentication",
                details=str(e)
            ).dict()
        )

@auth_router.get("/gmail/callback", response_model=AuthCallbackResponse)
async def handle_gmail_callback(
    request: Request,
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from OAuth provider"),
    oauth_handler: GmailOAuthHandler = Depends(get_oauth_handler),
    user_id: str = Depends(get_user_id)
):
    """
    Handle OAuth callback from Gmail
    
    Process authorization code and store account tokens
    """
    try:
        # Check for OAuth errors
        if error:
            print(f"❌ OAuth error received: {error}")
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="oauth_error",
                    message=f"OAuth authorization failed: {error}",
                    details="User denied access or other OAuth error occurred"
                ).dict()
            )
        
        # Validate required parameters
        if not code or not state:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="missing_parameters",
                    message="Missing required OAuth parameters",
                    details="Both 'code' and 'state' parameters are required"
                ).dict()
            )
        
        print(f"🔄 Processing Gmail OAuth callback for user: {user_id}")
        
        # Exchange authorization code for tokens
        token_data = oauth_handler.exchange_code_for_tokens(code, state, user_id)
        
        # Store account tokens in database
        account_id = oauth_handler.store_account_tokens(user_id, token_data)
        
        # Log successful connection
        print(f"✅ Gmail account connected successfully: {token_data['user_email']}")
        
        return AuthCallbackResponse(
            success=True,
            message=f"Gmail account '{token_data['user_email']}' connected successfully!",
            account_id=account_id,
            email_address=token_data['user_email'],
            redirect_url="/"  # Redirect to dashboard
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"❌ Error processing Gmail callback: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="callback_processing_failed",
                message="Failed to process Gmail authentication callback",
                details=str(e)
            ).dict()
        )

@auth_router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(
    request: Request,
    user_id: str = Depends(get_user_id)
):
    """
    Get authentication status and connected accounts
    
    Returns list of connected email accounts and their status
    """
    try:
        # Connect to database
        connection = get_database_connection()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # Query connected accounts for user
        cursor.execute("""
            SELECT 
                id, email_address, display_name, provider,
                is_active, connected_at, last_sync_at,
                CASE 
                    WHEN token_expiry IS NULL THEN NULL
                    WHEN token_expiry > NOW() THEN 'valid'
                    ELSE 'expired'
                END as token_status
            FROM email_accounts 
            WHERE user_id = %s 
            ORDER BY connected_at DESC
        """, (user_id,))
        
        accounts_raw = cursor.fetchall()
        
        # Format account data
        connected_accounts = []
        for account in accounts_raw:
            connected_accounts.append({
                "id": account["id"],
                "email_address": account["email_address"],
                "display_name": account["display_name"],
                "provider": account["provider"],
                "is_active": account["is_active"],
                "connected_at": account["connected_at"].isoformat(),
                "last_sync_at": account["last_sync_at"].isoformat() if account["last_sync_at"] else None,
                "token_status": account["token_status"]
            })
        
        # Close database connection
        cursor.close()
        connection.close()
        
        # Determine authentication status
        authenticated = len([acc for acc in connected_accounts if acc["is_active"]]) > 0
        
        print(f"📊 Auth status for user {user_id}: {len(connected_accounts)} accounts")
        
        return AuthStatusResponse(
            authenticated=authenticated,
            user_id=user_id,
            connected_accounts=connected_accounts,
            total_accounts=len(connected_accounts)
        )
        
    except Exception as e:
        print(f"❌ Error getting auth status: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="status_check_failed",
                message="Failed to check authentication status",
                details=str(e)
            ).dict()
        )

@auth_router.get("/accounts", response_model=List[AccountInfo])
async def list_connected_accounts(
    request: Request,
    user_id: str = Depends(get_user_id)
):
    """
    Get detailed list of connected email accounts
    
    Returns comprehensive account information
    """
    try:
        # Connect to database
        connection = get_database_connection()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # Query account details
        cursor.execute("""
            SELECT 
                id, email_address, display_name, provider,
                is_active, connected_at, last_sync_at
            FROM email_accounts 
            WHERE user_id = %s 
            ORDER BY provider, email_address
        """, (user_id,))
        
        accounts = cursor.fetchall()
        
        # Close database connection
        cursor.close()
        connection.close()
        
        # Convert to Pydantic models
        account_list = []
        for account in accounts:
            account_list.append(AccountInfo(
                id=account["id"],
                email_address=account["email_address"],
                display_name=account["display_name"] or "",
                provider=account["provider"],
                is_active=account["is_active"],
                connected_at=account["connected_at"],
                last_sync_at=account["last_sync_at"]
            ))
        
        print(f"📋 Listed {len(account_list)} accounts for user: {user_id}")
        return account_list
        
    except Exception as e:
        print(f"❌ Error listing accounts: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="account_list_failed",
                message="Failed to list connected accounts",
                details=str(e)
            ).dict()
        )

@auth_router.post("/revoke/{account_id}")
async def revoke_account_access(
    account_id: int,
    request: Request,
    oauth_handler: GmailOAuthHandler = Depends(get_oauth_handler),
    user_id: str = Depends(get_user_id)
):
    """
    Revoke access for a connected email account
    
    Removes OAuth tokens and deactivates account
    """
    try:
        # Verify account ownership
        connection = get_database_connection()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT id, email_address, provider 
            FROM email_accounts 
            WHERE id = %s AND user_id = %s
        """, (account_id, user_id))
        
        account = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not account:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error="account_not_found",
                    message=f"Account with ID {account_id} not found or not owned by user",
                    details="Account may not exist or belong to different user"
                ).dict()
            )
        
        # Revoke access using OAuth handler
        success = oauth_handler.revoke_account_access(account_id)
        
        if success:
            print(f"✅ Successfully revoked access for account: {account['email_address']}")
            return {
                "success": True,
                "message": f"Access revoked for {account['email_address']}",
                "account_id": account_id
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error="revoke_failed",
                    message="Failed to revoke account access",
                    details="OAuth revocation failed or account was already inactive"
                ).dict()
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"❌ Error revoking account access: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="revoke_error",
                message="Error occurred while revoking account access",
                details=str(e)
            ).dict()
        )

@auth_router.get("/test-connection/{account_id}")
async def test_account_connection(
    account_id: int,
    request: Request,
    oauth_handler: GmailOAuthHandler = Depends(get_oauth_handler),
    user_id: str = Depends(get_user_id)
):
    """
    Test if account credentials are still valid
    
    Attempts to refresh tokens and verify API access
    """
    try:
        # Verify account ownership
        connection = get_database_connection()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT id, email_address, provider, is_active
            FROM email_accounts 
            WHERE id = %s AND user_id = %s
        """, (account_id, user_id))
        
        account = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not account:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error="account_not_found",
                    message=f"Account with ID {account_id} not found"
                ).dict()
            )
        
        # Test credentials
        credentials = oauth_handler.get_valid_credentials(account_id)
        
        if credentials:
            # Try to make a simple API call to verify access
            from googleapiclient.discovery import build
            service = build('gmail', 'v1', credentials=credentials)
            profile = service.users().getProfile(userId='me').execute()
            
            print(f"✅ Account connection test successful: {account['email_address']}")
            return {
                "success": True,
                "message": f"Account {account['email_address']} is connected and working",
                "account_id": account_id,
                "email_address": profile.get('emailAddress'),
                "messages_total": profile.get('messagesTotal', 0),
                "threads_total": profile.get('threadsTotal', 0)
            }
        else:
            print(f"❌ Account connection test failed: {account['email_address']}")
            return {
                "success": False,
                "message": f"Account {account['email_address']} credentials are invalid",
                "account_id": account_id,
                "error": "Invalid or expired credentials"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error testing account connection: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="connection_test_failed",
                message="Failed to test account connection",
                details=str(e)
            ).dict()
        )

# ====================================
# HEALTH CHECK AND STATUS ENDPOINTS
# ====================================

@auth_router.get("/health")
async def health_check():
    """
    Health check endpoint for authentication service
    
    Verifies OAuth handler and database connectivity
    """
    try:
        # Test OAuth handler initialization
        oauth_handler = create_oauth_handler()
        
        # Test database connection
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
        print(f"❌ Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error="service_unhealthy",
                message="Authentication service health check failed",
                details=str(e)
            ).dict()
        )

# ====================================
# ERROR HANDLERS
# ====================================

# Exception handler should be registered on the app, not the router
# For now, we'll handle exceptions within each endpoint
# In the main app, register: app.add_exception_handler(Exception, general_exception_handler)

def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions in auth routes"""
    print(f"❌ Unhandled exception in auth routes: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_server_error",
            message="An unexpected error occurred",
            details=str(exc) if config.debug else "Contact support for assistance"
        ).dict()
    )

# ====================================
# MAIN FUNCTION FOR TESTING
# ====================================

def main():
    """Test authentication routes functionality"""
    print("🔐 Testing Authentication Routes")
    print("=" * 50)
    
    try:
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        
        # Create test FastAPI app
        app = FastAPI(title="Test Auth Routes")
        app.include_router(auth_router)
        
        client = TestClient(app)
        
        # Test health check
        print("🏥 Testing health check...")
        response = client.get("/auth/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Health check passed")
        else:
            print(f"   ❌ Health check failed: {response.text}")
        
        # Test auth status
        print("\n📊 Testing auth status...")
        response = client.get("/auth/status", headers={"X-User-ID": "test_user"})
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Auth status: {data['total_accounts']} accounts")
        else:
            print(f"   ❌ Auth status failed: {response.text}")
        
        # Test Gmail auth start
        print("\n🚀 Testing Gmail auth start...")
        response = client.get("/auth/gmail", headers={"X-User-ID": "test_user"})
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Auth URL generated: {data['authorization_url'][:50]}...")
        else:
            print(f"   ❌ Gmail auth start failed: {response.text}")
        
        print(f"\n✅ Authentication routes test completed!")
        
    except Exception as e:
        print(f"❌ Authentication routes test failed: {e}")

if __name__ == "__main__":
    main()