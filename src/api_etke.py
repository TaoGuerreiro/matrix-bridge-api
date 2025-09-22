"""
API REST simplifiée pour l'intégration avec etke.cc
Utilise les bridges Instagram/Messenger pré-configurés sur etke.cc
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
from loguru import logger
import aiohttp

from etke_matrix_client import EtkeMatrixClient
from nio import MessageDirection

# Client Matrix global
matrix_client: Optional[EtkeMatrixClient] = None
sync_token: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    global matrix_client
    # Startup
    matrix_client = EtkeMatrixClient()
    connected = await matrix_client.connect()
    if connected:
        logger.info("✅ API connected to etke.cc Matrix server")
    else:
        logger.error("❌ Failed to connect to etke.cc")

    yield

    # Shutdown
    if matrix_client:
        await matrix_client.disconnect()
        logger.info("API disconnected from etke.cc")

# Configuration FastAPI avec lifespan
app = FastAPI(
    title="Beeper Bridge API - etke.cc Edition",
    description="API pour accéder aux messages Instagram/Messenger via etke.cc Matrix bridges",
    version="2.0.0",
    lifespan=lifespan
)

# CORS pour permettre l'accès depuis votre frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles Pydantic
class SendMessageRequest(BaseModel):
    room_id: str
    message: str
    platform: str  # "instagram" ou "messenger"

class MessageResponse(BaseModel):
    success: bool
    event_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None

class SyncResponse(BaseModel):
    success: bool
    messages: Dict[str, List[Dict[str, Any]]]
    next_batch: Optional[str] = None
    timestamp: str

class WebhookSetupRequest(BaseModel):
    webhook_url: str
    platforms: Optional[List[str]] = ["instagram", "messenger"]
    enabled: bool = True

# Endpoints Health & Status
@app.get("/api/v1/health")
async def health_check():
    """Vérifier l'état de l'API et de la connexion Matrix"""
    is_connected = matrix_client is not None and matrix_client.client is not None
    return {
        "status": "healthy" if is_connected else "unhealthy",
        "matrix_connected": is_connected,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/version")
async def get_version():
    """Version de l'API"""
    return {
        "version": "2.0.0",
        "backend": "etke.cc",
        "bridges": ["instagram", "messenger"]
    }

# Endpoints Messages
@app.get("/api/v1/messages/instagram")
async def get_instagram_messages(limit: int = 50):
    """Récupérer les messages Instagram"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not connected")

    messages = await matrix_client.get_instagram_messages(limit=limit)
    return {
        "success": True,
        "count": len(messages),
        "messages": messages
    }

@app.get("/api/v1/messages/messenger")
async def get_messenger_messages(limit: int = 50):
    """Récupérer les messages Messenger"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not connected")

    messages = await matrix_client.get_messenger_messages(limit=limit)
    return {
        "success": True,
        "count": len(messages),
        "messages": messages
    }

@app.post("/api/v1/send", response_model=MessageResponse)
async def send_message(request: SendMessageRequest):
    """Envoyer un message vers Instagram ou Messenger"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not connected")

    if request.platform == "instagram":
        result = await matrix_client.send_to_instagram(request.room_id, request.message)
    elif request.platform == "messenger":
        result = await matrix_client.send_to_messenger(request.room_id, request.message)
    else:
        raise HTTPException(status_code=400, detail="Platform must be 'instagram' or 'messenger'")

    return MessageResponse(**result)

@app.get("/api/v1/sync", response_model=SyncResponse)
async def sync_messages():
    """Synchroniser les nouveaux messages depuis la dernière sync"""
    global sync_token

    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not connected")

    result = await matrix_client.sync_new_messages(since_token=sync_token)

    if result["success"]:
        sync_token = result.get("next_batch")

    return SyncResponse(**result)

@app.get("/api/v1/rooms")
async def get_rooms():
    """Lister toutes les rooms (conversations) par plateforme"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not connected")

    rooms = await matrix_client.get_room_list()
    return {
        "success": True,
        "rooms": rooms,
        "total": {
            "instagram": len(rooms.get("instagram", [])),
            "messenger": len(rooms.get("messenger", []))
        }
    }

# Configuration webhook globale
webhook_config = {
    "url": None,
    "platforms": ["instagram", "messenger"],
    "enabled": False
}

# Webhook pour recevoir les messages en temps réel
@app.post("/api/v1/webhook/setup")
async def setup_webhook(request: WebhookSetupRequest, background_tasks: BackgroundTasks):
    """Configurer l'écoute des messages en temps réel avec URL webhook"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not connected")

    # Mettre à jour la configuration
    webhook_config["url"] = request.webhook_url
    webhook_config["platforms"] = request.platforms
    webhook_config["enabled"] = request.enabled

    logger.info(f"🪝 Webhook configured: {request.webhook_url}")

    if request.enabled:
        async def message_callback(room, event):
            """Callback pour traiter les nouveaux messages et les envoyer au webhook"""
            try:
                logger.info(f"🔍 Message callback triggered - Room: {room.room_id}, Sender: {event.sender}, Message: {event.body[:50]}...")

                # Vérifier que le webhook est toujours actif
                if not webhook_config.get("enabled", False):
                    logger.debug("🚫 Webhook disabled, ignoring message")
                    return

                # Ignorer nos propres messages pour éviter les boucles
                if event.sender == matrix_client.user_id:
                    logger.debug(f"🚫 Ignoring own message: {event.body[:50]}...")
                    return

                # Déterminer la plateforme
                platform = "unknown"
                if room.room_id in matrix_client.instagram_rooms:
                    platform = "instagram"
                elif room.room_id in matrix_client.messenger_rooms:
                    platform = "messenger"
                else:
                    logger.debug(f"😒 Unknown room platform: {room.room_id}")
                    logger.debug(f"📋 Instagram rooms: {list(matrix_client.instagram_rooms.keys())}")
                    logger.debug(f"📋 Messenger rooms: {list(matrix_client.messenger_rooms.keys())}")
                    return  # Ignorer les rooms inconnues

                # Filtrer par plateforme si configuré
                if platform not in webhook_config["platforms"]:
                    logger.debug(f"💭 Platform {platform} not in webhook config {webhook_config['platforms']}")
                    return

                logger.info(f"🔔 New {platform} message from {event.sender}: {event.body[:50] if hasattr(event, 'body') else 'Encrypted'}...")

                # Si le message est chiffré ou n'a pas de body, utiliser un placeholder
                message_content = event.body if hasattr(event, 'body') and event.body else None

                if not message_content or "[" in message_content:
                    logger.info(f"📥 Message chiffré détecté pour room {room.room_id}")
                    message_content = "[Nouveau message Instagram]"

                # Préparer les données du message
                message_data = {
                    "room_id": room.room_id,
                    "room_name": matrix_client.instagram_rooms.get(room.room_id) or matrix_client.messenger_rooms.get(room.room_id),
                    "platform": platform,
                    "sender": event.sender,
                    "message": message_content,
                    "timestamp": datetime.now().isoformat(),
                    "event_id": event.event_id if hasattr(event, 'event_id') else None,
                    "is_incoming": True,  # Flag pour identifier les messages entrants
                    "server_timestamp": event.server_timestamp if hasattr(event, 'server_timestamp') else None,
                    "source": platform  # Ajout du champ source pour le webhook
                }

                # Envoyer vers le webhook
                if webhook_config.get("url"):
                    await forward_to_webhook(webhook_config["url"], message_data)
                else:
                    logger.warning("🚨 No webhook URL configured")

            except Exception as e:
                logger.error(f"Webhook callback error: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

        # Lancer l'écoute en arrière-plan
        background_tasks.add_task(matrix_client.listen_for_messages, message_callback)

        return {
            "success": True,
            "message": f"Webhook listener started for {request.webhook_url}",
            "config": webhook_config
        }
    else:
        return {
            "success": True,
            "message": "Webhook configured but disabled",
            "config": webhook_config
        }

@app.get("/api/v1/webhook/status")
async def webhook_status():
    """Obtenir le statut du webhook"""
    return {
        "webhook_config": webhook_config,
        "active": webhook_config["enabled"]
    }

@app.delete("/api/v1/webhook")
async def disable_webhook():
    """Désactiver le webhook"""
    webhook_config["enabled"] = False
    webhook_config["url"] = None
    return {
        "success": True,
        "message": "Webhook disabled"
    }

async def forward_to_webhook(webhook_url: str, message_data: dict):
    """Envoyer les données vers l'URL webhook"""
    try:
        logger.debug(f"📤 Sending to webhook: {webhook_url}")
        logger.debug(f"📄 Message data: {message_data}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=message_data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "EtkeMatrix-Webhook/1.0"
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                response_text = await response.text()

                if response.status == 200:
                    logger.info(f"📤 Message sent to webhook ({message_data['platform']}): {message_data['message'][:50]}...")
                    logger.debug(f"✅ Webhook response: {response_text[:200]}...")
                else:
                    logger.warning(f"⚠️ Webhook responded with status {response.status}")
                    logger.warning(f"🔍 Webhook response: {response_text[:500]}...")

    except asyncio.TimeoutError:
        logger.error(f"⏰ Webhook timeout for {webhook_url}")
    except aiohttp.ClientError as e:
        logger.error(f"🌐 Webhook connection error for {webhook_url}: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to send to webhook {webhook_url}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

# Endpoints spécifiques aux threads/conversations
@app.get("/api/v1/threads/{platform}")
async def get_threads(platform: str):
    """Obtenir la liste des threads/conversations pour une plateforme"""
    if platform not in ["instagram", "messenger"]:
        raise HTTPException(status_code=400, detail="Platform must be 'instagram' or 'messenger'")

    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not connected")

    rooms = await matrix_client.get_room_list()
    return {
        "success": True,
        "platform": platform,
        "threads": rooms.get(platform, [])
    }

@app.get("/api/v1/threads/{platform}/{room_id}/messages")
async def get_thread_messages(platform: str, room_id: str, limit: int = 50):
    """Obtenir les messages d'un thread spécifique"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not connected")

    # Récupérer les messages selon la plateforme
    if platform == "instagram":
        messages = await matrix_client.get_instagram_messages(limit=limit)
    elif platform == "messenger":
        messages = await matrix_client.get_messenger_messages(limit=limit)
    else:
        raise HTTPException(status_code=400, detail="Invalid platform")

    # Filtrer par room_id
    thread_messages = [msg for msg in messages if msg["room_id"] == room_id]

    return {
        "success": True,
        "room_id": room_id,
        "platform": platform,
        "count": len(thread_messages),
        "messages": thread_messages
    }

# Endpoint de test pour simuler un message entrant
@app.post("/api/v1/test/simulate-incoming")
async def simulate_incoming_message():
    """Simuler un message entrant pour tester le webhook"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not connected")

    # Simuler un message entrant
    from nio import RoomMessageText
    from datetime import datetime

    # Créer un faux événement
    class FakeEvent:
        def __init__(self):
            self.sender = "@flo_chalky_ig:chalky.etke.host"  # Simuler un utilisateur Instagram réaliste
            self.body = f"Message test entrant - {datetime.now().strftime('%H:%M:%S')}"
            self.event_id = f"$test_{datetime.now().timestamp()}"
            self.server_timestamp = datetime.now().timestamp() * 1000

    class FakeRoom:
        def __init__(self):
            self.room_id = "!GHTWDcxXouPfkhMVqy:chalky.etke.host"  # Room Instagram de Flo

    # Si un webhook est configuré, déclencher le callback
    if webhook_config.get("enabled", False) and webhook_config.get("url"):
        fake_event = FakeEvent()
        fake_room = FakeRoom()

        logger.info(f"🧪 Simulating incoming message from {fake_event.sender}")

        # Créer les données du message
        message_data = {
            "room_id": fake_room.room_id,
            "room_name": matrix_client.instagram_rooms.get(fake_room.room_id, "Unknown"),
            "platform": "instagram",
            "sender": fake_event.sender,
            "message": fake_event.body,
            "timestamp": datetime.now().isoformat(),
            "event_id": fake_event.event_id,
            "is_incoming": True,
            "is_simulation": True
        }

        # Envoyer vers le webhook
        await forward_to_webhook(webhook_config["url"], message_data)

        return {
            "success": True,
            "message": "Simulated incoming message sent to webhook",
            "webhook_url": webhook_config["url"],
            "simulated_data": message_data
        }
    else:
        return {
            "success": False,
            "message": "No webhook configured",
            "webhook_config": webhook_config
        }

# Endpoint pour diagnostiquer les messages récents
@app.get("/api/v1/debug/recent-messages")
async def debug_recent_messages(limit: int = 5):
    """Debug: voir les messages récents dans toutes les rooms"""
    if not matrix_client:
        raise HTTPException(status_code=503, detail="Matrix client not connected")

    results = {}

    # Vérifier les messages Instagram
    for room_id, room_name in matrix_client.instagram_rooms.items():
        try:
            response = await matrix_client.client.room_messages(
                room_id=room_id,
                start="",
                limit=limit,
                direction=MessageDirection.back
            )

            messages = []
            if hasattr(response, 'chunk'):
                for event in response.chunk:
                    if hasattr(event, 'body') and hasattr(event, 'sender'):
                        messages.append({
                            "sender": event.sender,
                            "message": event.body,
                            "timestamp": getattr(event, 'server_timestamp', 'unknown'),
                            "event_id": getattr(event, 'event_id', 'unknown'),
                            "event_type": type(event).__name__
                        })

            results[room_id] = {
                "room_name": room_name,
                "platform": "instagram",
                "message_count": len(messages),
                "messages": messages
            }

        except Exception as e:
            results[room_id] = {
                "room_name": room_name,
                "platform": "instagram",
                "error": str(e)
            }

    # Vérifier les messages Messenger
    for room_id, room_name in matrix_client.messenger_rooms.items():
        try:
            response = await matrix_client.client.room_messages(
                room_id=room_id,
                start="",
                limit=limit,
                direction=MessageDirection.back
            )

            messages = []
            if hasattr(response, 'chunk'):
                for event in response.chunk:
                    if hasattr(event, 'body') and hasattr(event, 'sender'):
                        messages.append({
                            "sender": event.sender,
                            "message": event.body,
                            "timestamp": getattr(event, 'server_timestamp', 'unknown'),
                            "event_id": getattr(event, 'event_id', 'unknown'),
                            "event_type": type(event).__name__
                        })

            results[room_id] = {
                "room_name": room_name,
                "platform": "messenger",
                "message_count": len(messages),
                "messages": messages
            }

        except Exception as e:
            results[room_id] = {
                "room_name": room_name,
                "platform": "messenger",
                "error": str(e)
            }

    return {
        "success": True,
        "rooms_checked": len(results),
        "webhook_status": webhook_config,
        "results": results
    }

# Endpoint de test pour vérifier la configuration
@app.get("/api/v1/test")
async def test_connection():
    """Tester la connexion et récupérer des infos de debug"""
    if not matrix_client:
        return {
            "connected": False,
            "error": "Matrix client not initialized"
        }

    try:
        rooms = await matrix_client.get_room_list()
        return {
            "connected": True,
            "user_id": matrix_client.user_id,
            "homeserver": matrix_client.homeserver,
            "rooms_count": {
                "instagram": len(rooms.get("instagram", [])),
                "messenger": len(rooms.get("messenger", []))
            },
            "status": "Ready to bridge messages!"
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }

# Endpoint SSE pour streaming temps réel (temporairement désactivé)
# @app.get("/api/v1/stream")
# async def stream_messages():
#     return {"message": "SSE endpoint temporairement désactivé"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_etke:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )