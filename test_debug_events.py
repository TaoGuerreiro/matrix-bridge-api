#!/usr/bin/env python3
"""
Script de débogage pour voir tous les types d'événements Matrix
"""
import asyncio
import os
from nio import AsyncClient, LoginResponse
from loguru import logger
from dotenv import load_dotenv

# Configuration
load_dotenv()
ETKE_HOMESERVER = "https://matrix.chalky.etke.host"
ETKE_USERNAME = "@florent:chalky.etke.host"
ETKE_PASSWORD = os.getenv("ETKE_PASSWORD", "")
TARGET_ROOM = "!GHTWDcxXouPfkhMVqy:chalky.etke.host"

async def debug_events():
    """Déboguer les événements Matrix"""
    logger.info("🔍 Démarrage du débogage des événements Matrix")

    client = AsyncClient(ETKE_HOMESERVER, ETKE_USERNAME)

    try:
        # Connexion
        logger.info(f"🔌 Connexion à {ETKE_HOMESERVER}...")
        response = await client.login(ETKE_PASSWORD)

        if not isinstance(response, LoginResponse):
            logger.error(f"❌ Échec de connexion: {response}")
            return

        logger.success(f"✅ Connecté en tant que {ETKE_USERNAME}")

        # Synchronisation
        logger.info("🔄 Synchronisation...")
        sync_response = await client.sync(timeout=30000, full_state=True)

        if TARGET_ROOM in client.rooms:
            room = client.rooms[TARGET_ROOM]
            logger.info(f"✅ Room trouvée: {room.display_name}")
            logger.info(f"   Chiffrée: {room.encrypted}")
            logger.info(f"   Membres: {room.users.keys() if room.users else 'Aucun'}")

            # Récupérer TOUS les messages
            logger.info("\n📥 Récupération des messages...")
            messages_response = await client.room_messages(
                TARGET_ROOM,
                start="",
                limit=20,
                direction="b"
            )

            logger.info(f"📊 Type de réponse: {type(messages_response)}")
            logger.info(f"📊 Attributs de la réponse: {dir(messages_response)}")

            if hasattr(messages_response, 'chunk'):
                logger.info(f"📊 Nombre d'événements: {len(messages_response.chunk)}")

                # Analyser TOUS les types d'événements
                event_types = {}
                for event in messages_response.chunk:
                    event_type = type(event).__name__
                    event_types[event_type] = event_types.get(event_type, 0) + 1

                logger.info("\n📊 Types d'événements trouvés:")
                for event_type, count in event_types.items():
                    logger.info(f"   {event_type}: {count}")

                # Afficher les détails de chaque événement
                logger.info("\n📝 Détails des premiers événements:")
                for i, event in enumerate(messages_response.chunk[:10]):
                    logger.info(f"\n--- Événement #{i+1} ---")
                    logger.info(f"Type: {type(event).__name__}")
                    logger.info(f"Sender: {getattr(event, 'sender', 'N/A')}")
                    logger.info(f"Event ID: {getattr(event, 'event_id', 'N/A')}")

                    # Afficher tous les attributs de l'événement
                    for attr in dir(event):
                        if not attr.startswith('_'):
                            try:
                                value = getattr(event, attr)
                                if not callable(value):
                                    if isinstance(value, str) and len(value) > 100:
                                        value = value[:100] + "..."
                                    logger.info(f"   {attr}: {value}")
                            except:
                                pass

                    # Si c'est un message, essayer de récupérer le contenu
                    if hasattr(event, 'body'):
                        logger.success(f"   💬 Message: {event.body[:200] if len(event.body) > 200 else event.body}")
                    elif hasattr(event, 'ciphertext'):
                        logger.info(f"   🔒 Message chiffré détecté")
                        logger.info(f"      Algorithm: {getattr(event, 'algorithm', 'N/A')}")
                        logger.info(f"      Session ID: {getattr(event, 'session_id', 'N/A')}")
            else:
                logger.warning(f"❌ Pas d'attribut 'chunk' dans la réponse")
                logger.info(f"Contenu de la réponse: {messages_response}")

        # Tester avec une room non chiffrée
        logger.info("\n🔍 Recherche de rooms non chiffrées...")
        for room_id, room in list(client.rooms.items())[:5]:
            if not room.encrypted:
                logger.info(f"\n📍 Room non chiffrée: {room.display_name}")
                msg_response = await client.room_messages(room_id, limit=3)
                if hasattr(msg_response, 'chunk'):
                    for event in msg_response.chunk:
                        if hasattr(event, 'body'):
                            logger.success(f"   ✅ Message en clair: {event.body[:50]}...")

    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())

    finally:
        await client.close()
        logger.info("🔌 Déconnexion")

if __name__ == "__main__":
    asyncio.run(debug_events())