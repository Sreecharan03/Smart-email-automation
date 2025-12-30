# ====================================
# UNIFIED AI EMAIL ASSISTANT - CONFIGURATION
# ====================================
# Configuration management for loading and validating environment variables
# Provides centralized access to all application settings

import os
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class AppConfig(BaseSettings):
    """
    Main application configuration class
    Loads all settings from environment variables with validation
    """
    
    # ====================================
    # GOOGLE SERVICES CONFIGURATION
    # ====================================
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gemini_api_key: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/auth/gmail/callback"
    
    # ====================================
    # MICROSOFT SERVICES CONFIGURATION
    # ====================================
    outlook_client_id: Optional[str] = None
    outlook_client_secret: Optional[str] = None
    outlook_tenant_id: str = "common"
    outlook_redirect_uri: str = "http://localhost:8000/auth/outlook/callback"
    
    # ====================================
    # SUPABASE DATABASE CONFIGURATION
    # ====================================
    # Individual connection parameters
    db_user: str = ""
    db_password: str = ""
    db_host: str = ""
    db_port: int = 6543
    db_name: str = "postgres"
    
    # Connection URL format (alternative)
    database_url: str = ""
    
    # Supabase project details
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    
    # Connection pool settings
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10
    db_pool_timeout: int = 30
    
    # SSL and timeout settings
    db_ssl_mode: str = "require"
    db_connect_timeout: int = 10
    db_command_timeout: int = 5
    
    # ====================================
    # VECTOR DATABASE (QDRANT)
    # ====================================
    qdrant_url: str = "https://waiting-for-cluster-host:6333"
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "email_vectors"
    
    # ====================================
    # APPLICATION SETTINGS
    # ====================================
    app_name: str = "Unified AI Email Assistant"
    app_version: str = "1.0.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    # ====================================
    # SECURITY SETTINGS
    # ====================================
    secret_key: str = "your_super_secret_key_here_change_in_production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    encryption_key: str = "your_encryption_key_here_32_char"
    token_expire_hours: int = 24
    
    # ====================================
    # EMAIL PROCESSING SETTINGS
    # ====================================
    max_emails_per_sync: int = 100
    embedding_model: str = "models/embedding-001"
    sync_interval_minutes: int = 30
    
    # ====================================
    # DAILY SUMMARY SETTINGS
    # ====================================
    daily_summary_time: str = "08:30"
    daily_summary_timezone: str = "Asia/Kolkata"
    
    # ====================================
    # LOGGING CONFIGURATION
    # ====================================
    log_level: str = "INFO"
    log_file: str = "logs/email_assistant.log"
    
    # ====================================
    # FEATURE FLAGS
    # ====================================
    enable_gmail: bool = True
    enable_outlook: bool = False
    enable_daily_summary: bool = True
    enable_ai_drafting: bool = True
    enable_smart_search: bool = True
    
    # ====================================
    # DEVELOPMENT SETTINGS
    # ====================================
    environment: str = "development"
    allow_origins: List[str] = ["http://localhost:3000", "http://localhost:8501"]
    
    # ====================================
    # RATE LIMITING
    # ====================================
    gmail_api_rate_limit: int = 250
    outlook_api_rate_limit: int = 10000
    gemini_api_rate_limit: int = 15
    
    # ====================================
    # TESTING SETTINGS
    # ====================================
    test_email: Optional[str] = None
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
        
    # ====================================
    # VALIDATORS
    # ====================================
    
    @field_validator('gmail_client_id')
    @classmethod
    def validate_gmail_client_id(cls, v: str) -> str:
        """Validate Gmail client ID format"""
        # Allow empty values for development/testing
        if not v or v == "your_gmail_client_id_here":
            # Only validate in production
            if os.getenv('ENVIRONMENT', 'development') == 'production':
                raise ValueError("Gmail client ID must be set")
            print("⚠️ Warning: Gmail client ID not set - using development mode")
            return v
        if v and not v.endswith('.apps.googleusercontent.com'):
            raise ValueError("Invalid Gmail client ID format")
        return v
    
    @field_validator('gemini_api_key')
    @classmethod
    def validate_gemini_api_key(cls, v: str) -> str:
        """Validate Gemini API key format"""
        # Allow empty values for development/testing
        if not v or v == "your_gemini_api_key_here":
            # Only validate in production
            if os.getenv('ENVIRONMENT', 'development') == 'production':
                raise ValueError("Gemini API key must be set")
            print("⚠️ Warning: Gemini API key not set - using development mode")
            return v
        if v and not v.startswith('AIza'):
            raise ValueError("Invalid Gemini API key format")
        return v
    
    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key strength"""
        if v == "your_super_secret_key_here_change_in_production":
            print("WARNING: Using default secret key. Change in production!")
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters")
        return v
    
    @field_validator('encryption_key')
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Validate encryption key length"""
        if len(v) != 32:
            raise ValueError("Encryption key must be exactly 32 characters")
        return v
    
    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate Supabase database URL format"""
        if v and not v.startswith('postgresql://'):
            raise ValueError("Database URL must start with postgresql://")
        return v

# ====================================
# CONFIGURATION HELPER FUNCTIONS
# ====================================

def get_config() -> AppConfig:
    """
    Get application configuration instance
    Returns validated configuration object
    """
    return AppConfig()

def is_gmail_enabled(config: AppConfig) -> bool:
    """Check if Gmail integration is enabled and configured"""
    return bool(config.enable_gmail and
                config.gmail_client_id and
                config.gmail_client_secret)

def is_outlook_enabled(config: AppConfig) -> bool:
    """Check if Outlook integration is enabled and configured"""
    return bool(config.enable_outlook and
                config.outlook_client_id and
                config.outlook_client_secret)

def is_qdrant_configured(config: AppConfig) -> bool:
    """Check if Qdrant vector database is properly configured"""
    return bool(config.qdrant_url != "https://waiting-for-cluster-host:6333" and
                config.qdrant_api_key)

def is_supabase_configured(config: AppConfig) -> bool:
    """Check if Supabase database is properly configured"""
    # Check if individual connection parameters are set
    individual_params = all([
        config.db_user,
        config.db_password,
        config.db_host,
        config.db_name
    ])
    
    # Check if connection URL is set
    connection_url = bool(config.database_url and
                         config.database_url.startswith('postgresql://'))
    
    return individual_params or connection_url

def get_supabase_connection_params(config: AppConfig) -> dict:
    """Get Supabase connection parameters for psycopg2"""
    return {
        "user": config.db_user,
        "password": config.db_password,
        "host": config.db_host,
        "port": config.db_port,
        "dbname": config.db_name,
        "sslmode": config.db_ssl_mode,
        "connect_timeout": config.db_connect_timeout,
        "options": f"-c statement_timeout={config.db_command_timeout}s"
    }

def get_supabase_pool_settings(config: AppConfig) -> dict:
    """Get Supabase connection pool settings"""
    return {
        "min_size": config.db_pool_min_size,
        "max_size": config.db_pool_max_size,
        "timeout": config.db_pool_timeout
    }

def get_database_settings(config: AppConfig) -> dict:
    """Extract database connection settings (backward compatibility)"""
    if config.database_url:
        return {
            "url": config.database_url,
            "echo": config.debug,
            "pool_pre_ping": True,
            "pool_recycle": 300
        }
    else:
        # Build URL from individual parameters
        url = f"postgresql://{config.db_user}:{config.db_password}@{config.db_host}:{config.db_port}/{config.db_name}"
        return {
            "url": url,
            "echo": config.debug,
            "pool_pre_ping": True,
            "pool_recycle": 300
        }

def get_cors_settings(config: AppConfig) -> dict:
    """Get CORS middleware settings"""
    return {
        "allow_origins": config.allow_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["*"]
    }

def validate_environment() -> bool:
    """
    Validate that all required environment variables are set
    Returns True if environment is properly configured
    """
    try:
        config = get_config()
        
        # Check essential services
        required_checks = [
            ("Gmail", is_gmail_enabled(config)),
            ("Gemini API", bool(config.gemini_api_key)),
            ("Supabase Database", is_supabase_configured(config))
        ]
        
        print("=== Environment Validation ===")
        all_good = True
        
        for service, is_configured in required_checks:
            status = "✅ OK" if is_configured else "❌ MISSING"
            print(f"{service}: {status}")
            if not is_configured:
                all_good = False
        
        # Optional services
        optional_checks = [
            ("Outlook", is_outlook_enabled(config)),
            ("Qdrant", is_qdrant_configured(config))
        ]
        
        print("\n=== Optional Services ===")
        for service, is_configured in optional_checks:
            status = "✅ Configured" if is_configured else "⚠️ Not configured"
            print(f"{service}: {status}")
        
        # Show Supabase connection details
        if is_supabase_configured(config):
            print(f"\n=== Supabase Connection ===")
            print(f"Host: {config.db_host}")
            print(f"Port: {config.db_port}")
            print(f"Database: {config.db_name}")
            print(f"SSL Mode: {config.db_ssl_mode}")
        
        return all_good
        
    except Exception as e:
        print(f"❌ Configuration Error: {e}")
        return False

def test_supabase_connection() -> bool:
    """Test Supabase database connection"""
    try:
        import psycopg2
        config = get_config()
        
        if not is_supabase_configured(config):
            print("❌ Supabase not configured")
            return False
        
        # Get connection parameters
        conn_params = get_supabase_connection_params(config)
        
        print("🔌 Testing Supabase connection...")
        
        # Test connection
        connection = psycopg2.connect(**conn_params)
        cursor = connection.cursor()
        
        # Test query
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        
        print(f"✅ Supabase connection successful!")
        print(f"📅 Current time: {result[0]}")
        
        # Close connection
        cursor.close()
        connection.close()
        
        return True
        
    except ImportError:
        print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

# ====================================
# MAIN FUNCTION FOR TESTING
# ====================================

def main():
    """Test configuration loading and validation"""
    print("🚀 Loading Email Assistant Configuration...")
    
    try:
        # Load configuration
        config = get_config()
        print(f"✅ Configuration loaded successfully!")
        print(f"📧 App Name: {config.app_name}")
        print(f"🔧 Version: {config.app_version}")
        print(f"🌍 Environment: {config.environment}")
        print(f"🔗 Host: {config.host}:{config.port}")
        
        # Validate environment
        if validate_environment():
            print("\n🎉 Environment is ready for Phase 1!")
        else:
            print("\n⚠️ Some configuration is missing. Check your .env file.")
        
        # Test Supabase connection
        print(f"\n🗄️ Testing database connection...")
        test_supabase_connection()
            
        # Show enabled features
        print(f"\n📋 Enabled Features:")
        print(f"Gmail: {config.enable_gmail}")
        print(f"Outlook: {config.enable_outlook}")
        print(f"Smart Search: {config.enable_smart_search}")
        print(f"AI Drafting: {config.enable_ai_drafting}")
        print(f"Daily Summary: {config.enable_daily_summary}")
        
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        print("💡 Make sure your .env file exists and contains all required values")

if __name__ == "__main__":
    main()