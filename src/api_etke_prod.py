#!/usr/bin/env python3
"""
API FastAPI pour etke.cc Matrix Bridge - Version Production Clever Cloud
Compatible avec PostgreSQL et optimisée pour le déploiement cloud
"""
import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from loguru import logger
from dotenv import load_dotenv
import uvicorn

# Import du client Matrix production
from .etke_matrix_client_prod import ProductionMatrixClient

# Configuration Loguru
# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)
logger.add("logs/api_prod.log", rotation="100 MB", level="INFO")

# Charger les variables d'environnement
load_dotenv()

# Configuration depuis variables d'environnement (Clever Cloud)
ETKE_HOMESERVER = os.getenv("ETKE_HOMESERVER", "https://matrix.chalky.etke.host")
ETKE_USERNAME = os.getenv("ETKE_USERNAME", "@florent:chalky.etke.host")
ETKE_PASSWORD = os.getenv("ETKE_PASSWORD", "")

# Configuration de l'API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", os.getenv("API_PORT", "8080")))  # Clever Cloud utilise PORT
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# PostgreSQL via DATABASE_URL (Clever Cloud)
USE_POSTGRES = os.getenv("USE_POSTGRES_STORE", "true").lower() == "true"
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Parser DATABASE_URL pour extraire les paramètres PostgreSQL
pg_config = {}
if DATABASE_URL and USE_POSTGRES:
    try:
        # Format: postgresql://user:password@host:port/database
        import urllib.parse
        result = urllib.parse.urlparse(DATABASE_URL)
        pg_config = {
            "host": result.hostname,
            "port": result.port or 5432,
            "database": result.path[1:],  # Remove leading slash
            "user": result.username,
            "password": result.password
        }
        logger.info(f"PostgreSQL config parsed: host={pg_config['host']}, db={pg_config['database']}")
    except Exception as e:
        logger.error(f"Failed to parse DATABASE_URL: {e}")
        USE_POSTGRES = False

# Instance globale du client Matrix
matrix_client: Optional[ProductionMatrixClient] = None

# Modèles Pydantic
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
    version: str = "2.0.0-prod"

# Lifespan context manager pour gérer le cycle de vie de l'application
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    global matrix_client

    logger.info("🚀 Starting Matrix Bridge API (Production)")
    logger.info(f"PostgreSQL enabled: {USE_POSTGRES}")

    if USE_POSTGRES and pg_config:
        logger.info(f"Using PostgreSQL from DATABASE_URL")

    # Initialiser le client Matrix
    try:
        matrix_client = ProductionMatrixClient(
            use_postgres=USE_POSTGRES,
            pg_config=pg_config if USE_POSTGRES else None
        )

        await matrix_client.start()
        logger.success("✅ Matrix client started successfully")

        # Configurer le webhook si défini
        if WEBHOOK_URL:
            await matrix_client.setup_webhook(WEBHOOK_URL)
            logger.info(f"📮 Webhook configured: {WEBHOOK_URL}")

    except Exception as e:
        logger.error(f"❌ Failed to start Matrix client: {e}")
        matrix_client = None

    yield  # L'application s'exécute

    # Nettoyage à l'arrêt
    logger.info("🛑 Shutting down Matrix Bridge API")
    if matrix_client:
        await matrix_client.stop()
    logger.info("👋 Shutdown complete")

# Créer l'application FastAPI avec lifespan
app = FastAPI(
    title="Matrix Bridge API - Production",
    description="API pour connecter Instagram/Messenger via etke.cc Matrix (Production avec PostgreSQL)",
    version="2.0.0-prod",
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes

@app.get("/")
async def root():
    """Route racine"""
    return {
        "service": "Matrix Bridge API",
        "version": "2.0.0-prod",
        "environment": "production",
        "status": "running",
        "postgres": USE_POSTGRES,
        "organization": "Chalky"
    }

@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint pour Clever Cloud"""
    postgres_status = False
    if USE_POSTGRES and matrix_client and hasattr(matrix_client, 'store'):
        try:
            # Vérifier la connexion PostgreSQL
            if hasattr(matrix_client.store, 'connection_pool'):
                postgres_status = True
        except:
            pass

    return HealthResponse(
        status="healthy" if matrix_client and matrix_client.client else "degraded",
        matrix_connected=bool(matrix_client and matrix_client.client and matrix_client.client.logged_in),
        postgres_connected=postgres_status,
        webhook_configured=bool(matrix_client and matrix_client.webhook_url),
        timestamp=datetime.utcnow().isoformat()
    )

@app.get("/api/v1/version")
async def version():
    """Version de l'API"""
    return {
        "api_version": "2.0.0-prod",
        "matrix_sdk": "nio",
        "storage": "PostgreSQL" if USE_POSTGRES else "SQLite",
        "environment": "Clever Cloud",
        "organization": "Chalky"
    }

@app.post("/api/v1/webhook/setup")
async def setup_webhook(request: WebhookSetupRequest):
    """Configurer l'URL du webhook"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not initialized")

    try:
        await matrix_client.setup_webhook(request.url)
        logger.info(f"📮 Webhook updated: {request.url}")
        return {"status": "success", "webhook_url": request.url}
    except Exception as e:
        logger.error(f"Failed to setup webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/webhook/status")
async def webhook_status():
    """Statut du webhook"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not initialized")

    return {
        "configured": bool(matrix_client.webhook_url),
        "url": matrix_client.webhook_url,
        "active": True
    }

@app.get("/api/v1/messages/{platform}")
async def get_messages(platform: str, limit: int = 50):
    """Récupérer les messages d'une plateforme"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not initialized")

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
    """Liste des conversations Matrix"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not initialized")

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
    """Envoyer un message"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not initialized")

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
    """Synchroniser les messages"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not initialized")

    try:
        # Force une synchronisation
        await matrix_client.sync_once()
        return {"status": "success", "message": "Synchronization completed"}
    except Exception as e:
        logger.error(f"Failed to sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/encryption/status")
async def encryption_status():
    """Statut du chiffrement"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not initialized")

    try:
        status = await matrix_client.get_encryption_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get encryption status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/encryption/fix")
async def fix_encryption(background_tasks: BackgroundTasks):
    """Réparer le chiffrement en arrière-plan"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not initialized")

    background_tasks.add_task(matrix_client.fix_encryption)
    return {
        "status": "initiated",
        "message": "Encryption fix started in background"
    }

# Webhook endpoints pour recevoir les callbacks
@app.post("/webhooks/instagram")
async def instagram_webhook(data: Dict[Any, Any]):
    """Webhook pour recevoir les événements Instagram"""
    logger.info(f"📥 Instagram webhook received: {data}")
    return {"status": "received"}

@app.post("/webhooks/messenger")
async def messenger_webhook(data: Dict[Any, Any]):
    """Webhook pour recevoir les événements Messenger"""
    logger.info(f"📥 Messenger webhook received: {data}")
    return {"status": "received"}

# Point d'entrée pour Clever Cloud (uvicorn)
if __name__ == "__main__":
    logger.info(f"🚀 Starting API server on {API_HOST}:{API_PORT}")
    uvicorn.run(
        "src.api_etke_prod:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,  # Pas de reload en production
        log_level="info"
    )