#!/usr/bin/env python3
"""
Point d'entrée pour Clever Cloud - Version simplifiée avec imports absolus
"""
import os
import sys
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

# Configuration
load_dotenv()

# Configuration Loguru
logger.remove()
logger.add(
    sink=sys.stdout,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True
)

# Variable globale pour le client
matrix_client = None

# Modèles Pydantic
class MessageRequest(BaseModel):
    room_id: str
    content: str
    message_type: str = "text"

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class MessageData(BaseModel):
    id: str
    sender: str
    content: str
    timestamp: str
    room_id: str
    type: str = "text"
    decrypted: bool = True

class RoomMessagesResponse(BaseModel):
    room_id: str
    platform: str
    count: int
    messages: List[MessageData]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    global matrix_client

    try:
        logger.info("🚀 Démarrage de l'API Matrix etke.cc")

        # Import du client Matrix seulement quand nécessaire pour éviter les erreurs d'import au niveau module
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
            from etke_matrix_client_prod import ProductionMatrixClient
            matrix_client = ProductionMatrixClient()
            await matrix_client.start()
            logger.success("✅ Client Matrix initialisé")
        except Exception as e:
            logger.warning(f"⚠️ Impossible d'initialiser le client Matrix: {e}")
            matrix_client = None

        yield

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation: {e}")
        yield
    finally:
        # Cleanup
        if matrix_client:
            try:
                await matrix_client.close()
                logger.info("🔌 Client Matrix fermé")
            except Exception as e:
                logger.error(f"Erreur lors de la fermeture: {e}")

# Créer l'application FastAPI
app = FastAPI(
    title="API Matrix etke.cc",
    description="API pour la gestion des messages via etke.cc Matrix Bridge",
    version="1.0.0",
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

@app.get("/", response_model=ApiResponse)
async def root():
    """Point d'entrée principal"""
    return ApiResponse(
        success=True,
        message="API Matrix etke.cc opérationnelle",
        data={"version": "1.0.0", "status": "active"}
    )

@app.get("/api/v1/health", response_model=ApiResponse)
async def health_check():
    """Vérification de l'état de l'API"""
    global matrix_client

    matrix_status = "connected" if matrix_client and matrix_client.logged_in else "disconnected"

    return ApiResponse(
        success=True,
        message="API en fonctionnement",
        data={
            "timestamp": datetime.now().isoformat(),
            "matrix_status": matrix_status,
            "version": "1.0.0"
        }
    )

@app.get("/api/v1/rooms/{room_id}/messages", response_model=RoomMessagesResponse)
async def get_room_messages(
    room_id: str,
    limit: int = 20,
    since: Optional[str] = None
):
    """Récupérer les messages d'une room"""
    global matrix_client

    try:
        if not matrix_client or not matrix_client.logged_in:
            # Retourner des messages factices pour les tests si pas connecté
            logger.warning(f"⚠️ Client Matrix non connecté - retour de données fictives pour {room_id}")
            return RoomMessagesResponse(
                room_id=room_id,
                platform="unknown",
                count=1,
                messages=[MessageData(
                    id="fake_msg_1",
                    sender="@system:chalky.etke.host",
                    content="[Message chiffré - Client Matrix non connecté]",
                    timestamp=datetime.now().isoformat(),
                    room_id=room_id,
                    type="encrypted",
                    decrypted=False
                )]
            )

        logger.info(f"📥 Récupération des messages pour room: {room_id}")

        # Récupérer les messages via le client Matrix
        messages = await matrix_client.get_room_messages(room_id, limit=limit)

        # Déterminer la plateforme basée sur l'ID de room
        platform = "unknown"
        if "instagram" in room_id.lower():
            platform = "instagram"
        elif "messenger" in room_id.lower():
            platform = "messenger"
        elif "whatsapp" in room_id.lower():
            platform = "whatsapp"

        # Convertir en format API
        message_data = []
        for msg in messages:
            message_data.append(MessageData(
                id=msg.get('id', ''),
                sender=msg.get('sender', ''),
                content=msg.get('content', ''),
                timestamp=msg.get('timestamp', ''),
                room_id=msg.get('room_id', room_id),
                type=msg.get('type', 'text'),
                decrypted=msg.get('decrypted', True)
            ))

        logger.success(f"✅ {len(message_data)} messages récupérés pour {room_id}")

        return RoomMessagesResponse(
            room_id=room_id,
            platform=platform,
            count=len(message_data),
            messages=message_data
        )

    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des messages: {e}")
        # Retourner une réponse avec message d'erreur plutôt qu'une erreur pour éviter les crashes
        return RoomMessagesResponse(
            room_id=room_id,
            platform="unknown",
            count=1,
            messages=[MessageData(
                id="error_msg",
                sender="@system:chalky.etke.host",
                content=f"[Erreur: {str(e)}]",
                timestamp=datetime.now().isoformat(),
                room_id=room_id,
                type="error",
                decrypted=False
            )]
        )

@app.get("/api/v1/rooms", response_model=ApiResponse)
async def get_rooms():
    """Lister les rooms disponibles"""
    global matrix_client

    try:
        if not matrix_client or not matrix_client.logged_in:
            return ApiResponse(
                success=False,
                message="Client Matrix non connecté",
                data={"rooms": []}
            )

        rooms_data = await matrix_client.get_rooms_list()

        return ApiResponse(
            success=True,
            message=f"{rooms_data['total']} rooms trouvées",
            data={"rooms": rooms_data['rooms']}
        )

    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des rooms: {e}")
        return ApiResponse(
            success=False,
            message=f"Erreur: {str(e)}",
            data={"rooms": []}
        )

@app.post("/api/v1/send", response_model=ApiResponse)
async def send_message(message_request: MessageRequest):
    """Envoyer un message"""
    global matrix_client

    try:
        if not matrix_client or not matrix_client.logged_in:
            raise HTTPException(status_code=503, detail="Client Matrix non connecté")

        result = await matrix_client.send_message(
            message_request.room_id,
            message_request.content,
            message_request.message_type
        )

        return ApiResponse(
            success=True,
            message="Message envoyé avec succès",
            data={"event_id": result}
        )

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'envoi du message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/version", response_model=ApiResponse)
async def get_version():
    """Version de l'API"""
    return ApiResponse(
        success=True,
        message="Version de l'API",
        data={"version": "1.0.0", "build": "production"}
    )

@app.get("/api/v1/test", response_model=ApiResponse)
async def test_connection():
    """Test de connexion Matrix"""
    global matrix_client

    matrix_status = "connected" if matrix_client and matrix_client.logged_in else "disconnected"

    return ApiResponse(
        success=matrix_client and matrix_client.logged_in,
        message=f"Statut Matrix: {matrix_status}",
        data={"matrix_connected": matrix_client and matrix_client.logged_in}
    )

# Point d'entrée pour uvicorn
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))

    logger.info(f"🚀 Démarrage de l'API sur le port {port}")

    uvicorn.run(
        "clever_app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )