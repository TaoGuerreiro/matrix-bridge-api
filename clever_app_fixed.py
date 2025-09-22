#!/usr/bin/env python3
"""
Clever Cloud Fixed Entry Point - Minimal, Robust FastAPI
No logs directory, no complex imports, maximum reliability
"""
import os
import sys
import logging

# Setup Python logging to stdout (Clever Cloud compatible)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

logger.info("🚀 Clever Cloud Matrix Bridge API Starting (Fixed Version)")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"PORT env: {os.getenv('PORT', 'NOT_SET')}")
logger.info(f"Python version: {sys.version}")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

# Global state
app_status = {
    "status": "healthy",
    "version": "1.0.0-fixed",
    "deployment": "clever_cloud",
    "started_at": None,
    "matrix_connected": False
}

@asynccontextmanager
async def lifespan(app_instance):
    """Initialize the application"""
    import datetime
    app_status["started_at"] = datetime.datetime.now().isoformat()
    logger.info("✅ FastAPI application started successfully")

    # Check environment variables without importing Matrix client
    required_vars = ["ETKE_HOMESERVER", "ETKE_USERNAME", "ETKE_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.warning(f"Missing Matrix environment variables: {missing_vars}")
        app_status["matrix_connected"] = False
    else:
        logger.info("✅ Matrix environment variables present")
        app_status["matrix_connected"] = True

    yield

# Create minimal but functional FastAPI app
app = FastAPI(
    title="Matrix Bridge API - Clever Cloud",
    description="Robust Matrix Bridge API for Instagram/Messenger via etke.cc",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint - Always works"""
    return {
        "message": "Matrix Bridge API - Clever Cloud",
        "status": "operational",
        "version": "1.0.0-fixed",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "environment": "/env",
            "matrix": "/matrix/status"
        },
        "deployment": {
            "platform": "clever_cloud",
            "port": os.getenv("PORT", "8080"),
            "working_dir": os.getcwd()
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer"""
    return {
        "status": "healthy",
        "timestamp": app_status.get("started_at"),
        "uptime_check": "ok"
    }

@app.get("/status")
async def status():
    """Detailed status information"""
    return {
        "application": app_status,
        "environment": {
            "port": os.getenv("PORT", "NOT_SET"),
            "database_url_set": bool(os.getenv("DATABASE_URL")),
            "etke_homeserver_set": bool(os.getenv("ETKE_HOMESERVER")),
            "etke_username_set": bool(os.getenv("ETKE_USERNAME")),
            "etke_password_set": bool(os.getenv("ETKE_PASSWORD"))
        },
        "system": {
            "python_version": sys.version,
            "working_directory": os.getcwd(),
            "python_path_count": len(sys.path)
        }
    }

@app.get("/env")
async def environment_check():
    """Environment variables check (security conscious)"""
    critical_vars = [
        "PORT", "DATABASE_URL", "ETKE_HOMESERVER",
        "ETKE_USERNAME", "ETKE_PASSWORD", "USE_POSTGRES_STORE"
    ]

    env_status = {}
    for var in critical_vars:
        value = os.getenv(var)
        env_status[var] = {
            "set": bool(value),
            "length": len(value) if value else 0
        }
        # Safe preview for non-sensitive vars
        if var in ["PORT", "ETKE_HOMESERVER", "ETKE_USERNAME"] and value:
            env_status[var]["preview"] = value

    return {
        "environment_variables": env_status,
        "total_env_vars": len(os.environ)
    }

@app.get("/matrix/status")
async def matrix_status():
    """Matrix connection status"""
    return {
        "matrix_connected": app_status["matrix_connected"],
        "homeserver": os.getenv("ETKE_HOMESERVER", "not_set"),
        "username": os.getenv("ETKE_USERNAME", "not_set"),
        "password_set": bool(os.getenv("ETKE_PASSWORD"))
    }

@app.get("/test")
async def test_endpoint():
    """Simple test endpoint"""
    return {
        "test": "success",
        "message": "API is responding correctly",
        "timestamp": app_status.get("started_at")
    }

# Advanced endpoints (placeholders for future Matrix functionality)
@app.get("/api/v1/rooms")
async def list_rooms():
    """List Matrix rooms (placeholder)"""
    return {
        "rooms": [],
        "status": "placeholder",
        "message": "Matrix integration will be added once basic deployment is stable"
    }

@app.post("/api/v1/send")
async def send_message():
    """Send message endpoint (placeholder)"""
    return {
        "status": "placeholder",
        "message": "Send functionality will be added once deployment is stable"
    }

# Export for uvicorn
__all__ = ['app']

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"🚀 Starting fixed app on port {port}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )