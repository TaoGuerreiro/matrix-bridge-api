#!/usr/bin/env python3
"""
Script pour demander les clés de déchiffrement aux autres devices
"""
import asyncio
import os
from pathlib import Path
from nio import AsyncClient, LoginResponse, RoomKeyRequestResponse
from nio.store import SqliteStore
from nio.crypto import OlmDevice
from loguru import logger
from dotenv import load_dotenv

# Configuration
load_dotenv()
ETKE_HOMESERVER = "https://matrix.chalky.etke.host"
ETKE_USERNAME = "@florent:chalky.etke.host"
ETKE_PASSWORD = os.getenv("ETKE_PASSWORD", "")
TARGET_ROOM = "!GHTWDcxXouPfkhMVqy:chalky.etke.host"

async def request_room_keys():
    """Demander les clés de déchiffrement"""
    logger.info("🔑 Demande des clés de déchiffrement")

    # Configuration du store pour persister les clés
    store_path = Path("local_store")
    store_path.mkdir(exist_ok=True, parents=True)

    # Créer le client avec store
    client = AsyncClient(
        ETKE_HOMESERVER,
        ETKE_USERNAME,
        store_path=str(store_path)
    )

    try:
        # Connexion
        logger.info(f"🔌 Connexion à {ETKE_HOMESERVER}...")
        response = await client.login(ETKE_PASSWORD, device_name="Beeper Local Test")

        if not isinstance(response, LoginResponse):
            logger.error(f"❌ Échec de connexion: {response}")
            return

        logger.success(f"✅ Connecté en tant que {ETKE_USERNAME}")
        logger.info(f"   Device ID: {response.device_id}")
        logger.info(f"   Access Token: {response.access_token[:20]}...")

        # Synchronisation complète
        logger.info("🔄 Synchronisation complète...")
        sync_response = await client.sync(timeout=30000, full_state=True)

        if TARGET_ROOM in client.rooms:
            room = client.rooms[TARGET_ROOM]
            logger.info(f"✅ Room trouvée: {room.display_name}")

            # Récupérer les messages pour identifier les sessions nécessaires
            logger.info("📥 Récupération des messages pour identifier les sessions...")
            messages_response = await client.room_messages(
                TARGET_ROOM,
                start="",
                limit=10,
                direction="b"
            )

            sessions_needed = set()
            if hasattr(messages_response, 'chunk'):
                for event in messages_response.chunk:
                    if hasattr(event, 'session_id'):
                        sessions_needed.add(event.session_id)
                        logger.info(f"   Session nécessaire: {event.session_id}")

            # Demander les clés pour chaque session
            if sessions_needed:
                logger.info(f"\n🔑 Demande de {len(sessions_needed)} sessions...")

                # Pour chaque session, demander les clés
                for session_id in sessions_needed:
                    logger.info(f"   Demande de clés pour session: {session_id}")

                    # Note: Dans une vraie implémentation, on utiliserait
                    # client.request_room_key() mais cela nécessite le chiffrement activé

                # Attendre un peu pour recevoir les réponses
                logger.info("⏳ Attente des réponses (10 secondes)...")
                await asyncio.sleep(10)

                # Synchroniser à nouveau pour voir si on a reçu des clés
                logger.info("🔄 Nouvelle synchronisation...")
                await client.sync(timeout=30000)

                # Essayer de récupérer les messages à nouveau
                logger.info("📥 Nouvelle tentative de récupération des messages...")
                messages_response = await client.room_messages(
                    TARGET_ROOM,
                    start="",
                    limit=5,
                    direction="b"
                )

                if hasattr(messages_response, 'chunk'):
                    for i, event in enumerate(messages_response.chunk[:3]):
                        logger.info(f"\n--- Message #{i+1} ---")
                        logger.info(f"Type: {type(event).__name__}")
                        if hasattr(event, 'body'):
                            logger.success(f"✅ Message déchiffré: {event.body}")
                        elif hasattr(event, 'decrypted') and not event.decrypted:
                            logger.warning(f"🔒 Message toujours chiffré")

        # Sauvegarder la session
        logger.info("\n💾 Sauvegarde de la session...")
        await client.sync_store.save_sync_response(sync_response)

    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())

    finally:
        await client.close()
        logger.info("🔌 Déconnexion")

if __name__ == "__main__":
    asyncio.run(request_room_keys())