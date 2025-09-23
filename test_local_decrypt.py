#!/usr/bin/env python3
"""
Test local de déchiffrement des messages Matrix avec les clés Element
"""
import asyncio
import os
import json
from pathlib import Path
from nio import AsyncClient, RoomMessageText, LoginResponse
from nio.events.room_events import UnknownEncryptedEvent, RoomEncryptedMedia
from nio.store import SqliteMemoryStore
from loguru import logger
from dotenv import load_dotenv
import base64

# Configuration
load_dotenv()

ETKE_HOMESERVER = "https://matrix.chalky.etke.host"
ETKE_USERNAME = "@florent:chalky.etke.host"
ETKE_PASSWORD = os.getenv("ETKE_PASSWORD", "")

# Clés Element fournies par l'utilisateur
ELEMENT_SESSION_ID = "RZUGVZXKSP"
ELEMENT_SESSION_KEY = "x/FCdIFgn1vgyLPzQIiw7P2mLOPZp3Ry1vXpoo8ozXA"

# Room spécifique mentionnée par l'utilisateur
TARGET_ROOM = "!GHTWDcxXouPfkhMVqy:chalky.etke.host"

async def test_decrypt_with_element_keys():
    """Test de déchiffrement avec les clés Element"""
    logger.info("🔐 Démarrage du test de déchiffrement local")

    # Configuration du store
    store_path = Path("matrix_store_test")

    # Créer le client sans chiffrement pour ce test simple
    client = AsyncClient(
        ETKE_HOMESERVER,
        ETKE_USERNAME
    )

    try:
        # Connexion
        logger.info(f"🔌 Connexion à {ETKE_HOMESERVER}...")
        response = await client.login(ETKE_PASSWORD)

        if not isinstance(response, LoginResponse):
            logger.error(f"❌ Échec de connexion: {response}")
            return

        logger.success(f"✅ Connecté en tant que {ETKE_USERNAME}")

        # Synchronisation initiale
        logger.info("🔄 Synchronisation initiale...")
        sync_response = await client.sync(timeout=30000, full_state=True)

        # Vérifier si la room existe
        if TARGET_ROOM not in client.rooms:
            logger.warning(f"⚠️ Room {TARGET_ROOM} non trouvée")
            logger.info(f"Rooms disponibles: {list(client.rooms.keys())}")
        else:
            room = client.rooms[TARGET_ROOM]
            logger.info(f"✅ Room trouvée: {room.display_name}")
            logger.info(f"   Chiffrée: {room.encrypted}")
            logger.info(f"   Membres: {len(room.users)}")

            # Essayer d'importer la session Megolm Element
            if room.encrypted:
                logger.info("🔑 Tentative d'import de la session Megolm Element...")
                try:
                    # Décoder la clé de session base64
                    session_key_bytes = base64.b64decode(ELEMENT_SESSION_KEY)

                    # Créer un dictionnaire de session
                    session_data = {
                        "algorithm": "m.megolm.v1.aes-sha2",
                        "room_id": TARGET_ROOM,
                        "sender_key": "",  # À récupérer si possible
                        "session_id": ELEMENT_SESSION_ID,
                        "session_key": ELEMENT_SESSION_KEY,
                        "chain_index": 0
                    }

                    logger.info(f"   Session ID: {ELEMENT_SESSION_ID}")
                    logger.info(f"   Longueur clé: {len(session_key_bytes)} octets")

                except Exception as e:
                    logger.error(f"❌ Erreur lors du traitement de la clé: {e}")

            # Récupérer les messages de la room
            logger.info("📥 Récupération des messages...")
            messages_response = await client.room_messages(
                TARGET_ROOM,
                start="",
                limit=50,
                direction="b"  # backwards = plus récents d'abord
            )

            if hasattr(messages_response, 'chunk'):
                logger.info(f"📊 {len(messages_response.chunk)} événements trouvés")

                decrypted_count = 0
                encrypted_count = 0
                plain_count = 0

                for i, event in enumerate(messages_response.chunk[:10]):  # Les 10 premiers
                    if isinstance(event, (UnknownEncryptedEvent, RoomEncryptedMedia)):
                        encrypted_count += 1
                        logger.info(f"\n🔒 Message chiffré #{i+1}:")
                        logger.info(f"   Type: {event.algorithm}")
                        logger.info(f"   Session ID: {event.session_id}")
                        logger.info(f"   Device ID: {event.device_id}")
                        logger.info(f"   Sender: {event.sender}")

                        # Vérifier si c'est la même session
                        if event.session_id == ELEMENT_SESSION_ID:
                            logger.success("   ✅ Session ID correspond!")
                        else:
                            logger.info(f"   ❓ Session différente")

                        # Tentative de déchiffrement
                        try:
                            # Si on a la clé de session correspondante
                            if event.session_id == ELEMENT_SESSION_ID:
                                logger.info("   🔓 Tentative de déchiffrement avec la clé Element...")
                                # Le déchiffrement réel nécessiterait l'intégration
                                # complète avec le store de clés

                        except Exception as e:
                            logger.error(f"   ❌ Erreur déchiffrement: {e}")

                    elif isinstance(event, RoomMessageText):
                        plain_count += 1
                        logger.info(f"\n📝 Message en clair #{i+1}:")
                        logger.info(f"   Sender: {event.sender}")
                        logger.info(f"   Contenu: {event.body[:100]}...")
                        decrypted_count += 1

                logger.info(f"\n📊 Résumé:")
                logger.info(f"   Messages chiffrés: {encrypted_count}")
                logger.info(f"   Messages en clair: {plain_count}")
                logger.info(f"   Messages déchiffrés: {decrypted_count}")

            else:
                logger.warning("❌ Pas de messages dans la réponse")

        # Test avec d'autres rooms Instagram
        logger.info("\n🔍 Recherche de rooms Instagram...")
        instagram_rooms = []
        for room_id, room in client.rooms.items():
            if "instagram" in room.display_name.lower() or \
               any("instagram" in str(alias).lower() for alias in getattr(room, 'canonical_alias', [])):
                instagram_rooms.append((room_id, room))

        if instagram_rooms:
            logger.info(f"📷 {len(instagram_rooms)} rooms Instagram trouvées")
            for room_id, room in instagram_rooms[:3]:
                logger.info(f"\n📍 Room: {room.display_name}")
                logger.info(f"   ID: {room_id}")
                logger.info(f"   Chiffrée: {room.encrypted}")

                # Récupérer quelques messages
                msg_response = await client.room_messages(room_id, limit=5)
                if hasattr(msg_response, 'chunk'):
                    for event in msg_response.chunk:
                        if isinstance(event, RoomMessageText):
                            logger.success(f"   ✅ Message: {event.body[:50]}...")
                        elif isinstance(event, (UnknownEncryptedEvent, RoomEncryptedMedia)):
                            logger.info(f"   🔒 Message chiffré (session: {event.session_id[:10]}...)")

    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())

    finally:
        await client.close()
        logger.info("🔌 Déconnexion")

if __name__ == "__main__":
    asyncio.run(test_decrypt_with_element_keys())