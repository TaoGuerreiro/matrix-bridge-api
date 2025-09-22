#!/usr/bin/env python3
"""
Clever Cloud Production API - Matrix Bridge
Robust production API with comprehensive error handling and diagnostics
"""
import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from loguru import logger
from dotenv import load_dotenv
import uvicorn

# Load environment first
load_dotenv()

# Import configuration manager
try:
    from .config_prod import config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config_prod import config

# Configure logging for production
logger.add("logs/clever_prod.log", rotation="100 MB", level="INFO",
          format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}")

# Global Matrix client
matrix_client: Optional[Any] = None
startup_error: Optional[str] = None

# Pydantic Models
class SendMessageRequest(BaseModel):
    room_id: str
    message: str
    platform: str = "instagram"

class WebhookSetupRequest(BaseModel):
    url: str
    events: List[str] = ["message", "reaction", "typing"]

class MessageResponse(BaseModel):
    id: str
    sender: str
    content: str
    timestamp: str
    platform: str
    room_id: str
    decrypted: bool = True

class HealthResponse(BaseModel):
    status: str
    matrix_connected: bool
    postgres_connected: bool = False
    webhook_configured: bool
    timestamp: str
    version: str = "3.0.0-clever"
    config_valid: bool
    startup_error: Optional[str] = None

class ConfigResponse(BaseModel):
    valid: bool
    errors: List[str]
    warnings: List[str]
    summary: Dict[str, Any]

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with robust error handling"""
    global matrix_client, startup_error

    logger.info("🚀 Starting Clever Cloud Matrix Bridge API")

    # Validate configuration
    if not config.is_valid():
        startup_error = f"Configuration validation failed: {config.errors}"
        logger.error(f"❌ {startup_error}")
        # Continue anyway to allow debugging endpoints
    else:
        logger.info("✅ Configuration validation passed")

        # Initialize Matrix client if config is valid
        try:
            # Import Matrix client
            try:
                from .etke_matrix_client_prod import ProductionMatrixClient
            except ImportError:
                from etke_matrix_client_prod import ProductionMatrixClient

            matrix_config = config.get_matrix_config()
            db_config = config.get_database_config()

            matrix_client = ProductionMatrixClient(
                use_postgres=db_config["use_postgres"],
                pg_config=db_config["pg_config"] if db_config["use_postgres"] else None
            )

            # Override client config with validated values
            matrix_client.homeserver = matrix_config["homeserver"]
            matrix_client.username = matrix_config["username"]
            matrix_client.password = matrix_config["password"]

            logger.info("📱 Starting Matrix client...")
            success = await matrix_client.start()

            if success:
                logger.success("✅ Matrix client connected successfully")

                # Setup webhook if configured
                api_config = config.get_api_config()
                if api_config["webhook_url"]:
                    await matrix_client.setup_webhook(api_config["webhook_url"])
                    logger.info(f"📮 Webhook configured: {api_config['webhook_url']}")

            else:
                startup_error = "Matrix client failed to connect"
                logger.error(f"❌ {startup_error}")

        except Exception as e:
            startup_error = f"Matrix client initialization failed: {str(e)}"
            logger.error(f"❌ {startup_error}")
            matrix_client = None

    yield  # Application runs

    # Cleanup
    logger.info("🛑 Shutting down Clever Cloud Matrix Bridge API")
    if matrix_client:
        try:
            await matrix_client.stop()
            logger.info("✅ Matrix client stopped cleanly")
        except Exception as e:
            logger.error(f"❌ Error stopping Matrix client: {e}")

    logger.info("👋 Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Matrix Bridge API - Clever Cloud",
    description="Production Matrix Bridge API for Instagram/Messenger via etke.cc",
    version="3.0.0-clever",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler for better error reporting
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Routes

@app.get("/")
async def root():
    """Root endpoint with comprehensive status"""
    return {
        "service": "Matrix Bridge API",
        "version": "3.0.0-clever",
        "environment": "Clever Cloud Production",
        "status": "running",
        "config_valid": config.is_valid(),
        "matrix_available": matrix_client is not None,
        "startup_error": startup_error,
        "timestamp": datetime.utcnow().isoformat(),
        "organization": "Chalky"
    }

@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check for monitoring"""
    matrix_connected = False
    postgres_connected = False

    if matrix_client:
        try:
            matrix_connected = bool(matrix_client.client and matrix_client.client.logged_in)
        except:
            pass

        if config.get_database_config()["use_postgres"] and hasattr(matrix_client, 'store'):
            try:
                postgres_connected = hasattr(matrix_client.store, 'connection_pool')
            except:
                pass

    status = "healthy" if (config.is_valid() and matrix_connected) else "degraded"

    return HealthResponse(
        status=status,
        matrix_connected=matrix_connected,
        postgres_connected=postgres_connected,
        webhook_configured=bool(matrix_client and matrix_client.webhook_url),
        timestamp=datetime.utcnow().isoformat(),
        config_valid=config.is_valid(),
        startup_error=startup_error
    )

@app.get("/api/v1/config", response_model=ConfigResponse)
async def get_config_status():
    """Get configuration status for debugging"""
    return ConfigResponse(
        valid=config.is_valid(),
        errors=config.errors,
        warnings=config.warnings,
        summary=config.get_summary()
    )

@app.get("/api/v1/debug/environment")
async def debug_environment():
    """Debug environment variables (production-safe)"""
    critical_vars = [
        "PORT", "DATABASE_URL", "ETKE_HOMESERVER",
        "ETKE_USERNAME", "ETKE_PASSWORD", "USE_POSTGRES_STORE"
    ]

    env_status = {}
    for var in critical_vars:
        value = os.getenv(var)
        if value:
            if "PASSWORD" in var:
                env_status[var] = f"SET (length: {len(value)})"
            elif "DATABASE_URL" == var:
                env_status[var] = f"SET (preview: {value[:20]}...)"
            else:
                env_status[var] = "SET"
        else:
            env_status[var] = "MISSING"

    return {
        "environment_variables": env_status,
        "python_path_entries": len(os.sys.path),
        "working_directory": os.getcwd(),
        "config_valid": config.is_valid(),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/v1/version")
async def version():
    """API version information"""
    return {
        "api_version": "3.0.0-clever",
        "matrix_sdk": "nio",
        "storage": "PostgreSQL" if config.get_database_config()["use_postgres"] else "SQLite",
        "environment": "Clever Cloud Production",
        "python_version": os.sys.version,
        "startup_error": startup_error,
        "organization": "Chalky"
    }

# Matrix API endpoints (require working Matrix client)

@app.post("/api/v1/webhook/setup")
async def setup_webhook(request: WebhookSetupRequest):
    """Configure webhook URL"""
    if not matrix_client:
        raise HTTPException(
            status_code=503,
            detail=f"Matrix client not available. Startup error: {startup_error}"
        )

    try:
        await matrix_client.setup_webhook(request.url)
        logger.info(f"📮 Webhook updated: {request.url}")
        return {"status": "success", "webhook_url": request.url}
    except Exception as e:
        logger.error(f"Failed to setup webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/webhook/status")
async def webhook_status():
    """Get webhook status"""
    if not matrix_client:
        raise HTTPException(
            status_code=503,
            detail=f"Matrix client not available. Startup error: {startup_error}"
        )

    return {
        "configured": bool(matrix_client.webhook_url),
        "url": matrix_client.webhook_url,
        "active": True
    }

@app.get("/api/v1/messages/{platform}")
async def get_messages(platform: str, limit: int = 50):
    """Get messages from platform"""
    if not matrix_client:
        raise HTTPException(
            status_code=503,
            detail=f"Matrix client not available. Startup error: {startup_error}"
        )

    if platform not in ["instagram", "messenger"]:
        raise HTTPException(status_code=400, detail="Platform must be 'instagram' or 'messenger'")

    try:
        messages = await matrix_client.get_platform_messages(platform, limit)
        return {
            "platform": platform,
            "count": len(messages),
            "messages": messages
        }
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/rooms")
async def get_rooms():
    """Get Matrix rooms list"""
    if not matrix_client:
        raise HTTPException(
            status_code=503,
            detail=f"Matrix client not available. Startup error: {startup_error}"
        )

    try:
        rooms = await matrix_client.get_rooms_list()
        return {
            "total": len(rooms),
            "rooms": rooms
        }
    except Exception as e:
        logger.error(f"Failed to get rooms: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/send")
async def send_message(request: SendMessageRequest):
    """Send message to room"""
    if not matrix_client:
        raise HTTPException(
            status_code=503,
            detail=f"Matrix client not available. Startup error: {startup_error}"
        )

    try:
        result = await matrix_client.send_message(
            room_id=request.room_id,
            message=request.message
        )

        return {
            "status": "success",
            "event_id": result.get("event_id"),
            "room_id": request.room_id
        }
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sync")
async def sync_messages():
    """Sync Matrix messages"""
    if not matrix_client:
        raise HTTPException(
            status_code=503,
            detail=f"Matrix client not available. Startup error: {startup_error}"
        )

    try:
        await matrix_client.sync_once()
        return {"status": "success", "message": "Synchronization completed"}
    except Exception as e:
        logger.error(f"Failed to sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Webhook endpoints
@app.post("/webhooks/instagram")
async def instagram_webhook(data: Dict[Any, Any]):
    """Instagram webhook receiver"""
    logger.info(f"📥 Instagram webhook received: {data}")
    return {"status": "received"}

@app.post("/webhooks/messenger")
async def messenger_webhook(data: Dict[Any, Any]):
    """Messenger webhook receiver"""
    logger.info(f"📥 Messenger webhook received: {data}")
    return {"status": "received"}

# Export app for uvicorn
if __name__ == "__main__":
    api_config = config.get_api_config()
    logger.info(f"🚀 Starting API server on {api_config['host']}:{api_config['port']}")

    uvicorn.run(
        app,
        host=api_config["host"],
        port=api_config["port"],
        reload=False,
        log_level="info"
    )