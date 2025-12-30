# ====================================
# UNIFIED AI EMAIL ASSISTANT - MAIN FASTAPI APPLICATION
# ====================================
# FastAPI server with Gmail OAuth authentication routes
# Usage: uvicorn main:app --reload --host 0.0.0.0 --port 8000

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import sys
import os

# Add project root to Python path
sys.path.append('/teamspace/studios/this_studio')

# Import configuration and routes
try:
    import importlib.util
    config_path = '/teamspace/studios/this_studio/email-assistant/config.py'
    spec = importlib.util.spec_from_file_location("config", config_path)
    
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config module from {config_path}")
    
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    
    get_config = config_module.get_config
    get_cors_settings = config_module.get_cors_settings
    
    # Import authentication routes
    from backend.api.auth_routes import auth_router
    
    CONFIG_LOADED = True
    
except Exception as e:
    CONFIG_LOADED = False
    CONFIG_ERROR = str(e)

# ====================================
# FASTAPI APPLICATION SETUP
# ====================================

app = FastAPI(
    title="Unified AI Email Assistant",
    description="Gmail OAuth authentication and email management API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ====================================
# MIDDLEWARE CONFIGURATION
# ====================================

if CONFIG_LOADED:
    try:
        config = get_config()
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

# ====================================
# ROUTE REGISTRATION
# ====================================

if CONFIG_LOADED:
    # Include authentication routes
    app.include_router(auth_router, prefix="/api")
    print("✅ Authentication routes registered")

# ====================================
# ROOT ENDPOINTS
# ====================================

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Gmail Assistant API",
        "version": "1.0.0",
        "status": "running",
        "config_loaded": CONFIG_LOADED,
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "auth": "/api/auth",
            "gmail_connect": "/api/auth/gmail",
            "auth_status": "/api/auth/status",
            "health": "/api/auth/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "gmail_assistant_api",
        "config_loaded": CONFIG_LOADED
    }

@app.get("/streamlit")
async def redirect_to_streamlit():
    """Redirect to Streamlit test interface"""
    return RedirectResponse(url="http://localhost:8501")

# ====================================
# ERROR HANDLERS
# ====================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "details": str(exc) if CONFIG_LOADED and get_config().debug else "Contact support"
        }
    )

# ====================================
# STARTUP EVENT
# ====================================

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    print("🚀 Gmail Assistant API starting up...")
    
    if not CONFIG_LOADED:
        print(f"❌ Configuration error: {CONFIG_ERROR}")
        print("⚠️ API will run with limited functionality")
    else:
        print("✅ Configuration loaded successfully")
        
        config = get_config()
        print(f"🌐 API running on: http://{config.host}:{config.port}")
        print(f"📖 API Docs: http://{config.host}:{config.port}/docs")
        print(f"🧪 Test with Streamlit: http://localhost:8501")
    
    print("=" * 50)

# ====================================
# MAIN FUNCTION FOR TESTING
# ====================================

def main():
    """Run the FastAPI application"""
    import uvicorn
    
    if CONFIG_LOADED:
        config = get_config()
        print(f"🚀 Starting FastAPI server...")
        print(f"📧 Gmail OAuth testing available at /api/auth/gmail")
        print(f"📖 API documentation at /docs")
        
        uvicorn.run(
            "main:app",
            host=config.host,
            port=config.port,
            reload=config.debug,
            log_level="info"
        )
    else:
        print(f"❌ Cannot start server: {CONFIG_ERROR}")
        print("💡 Check your configuration in email-assistant/config.py")

if __name__ == "__main__":
    main()