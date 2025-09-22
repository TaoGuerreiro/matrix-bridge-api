#!/usr/bin/env python3
"""
Test script pour vérifier et déboguer le déchiffrement des messages
"""
import asyncio
import os
import json
from pathlib import Path
from nio import (
    AsyncClient,
    AsyncClientConfig,
    LoginResponse,
    RoomMessageText,
    MegolmEvent,
    EncryptionError,
    RoomKeyEvent,
    Event,
    MessageDirection
)
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

async def test_decryption():
    """Tester le déchiffrement des messages Instagram"""

    # Configuration
    homeserver = os.getenv("ETKE_HOMESERVER", "https://matrix.chalky.etke.host")
    username = os.getenv("ETKE_USERNAME", "@florent:chalky.etke.host")
    password = os.getenv("ETKE_PASSWORD")
    device_id = "BEEPER_API_CLIENT"

    # Créer le dossier pour le store
    store_path = Path("matrix_store")
    store_path.mkdir(exist_ok=True)

    logger.info(f"🔧 Connecting to {homeserver} as {username}")

    # Configuration avec encryption
    config = AsyncClientConfig(
        store_sync_tokens=True,
        encryption_enabled=True,
        pickle_key="encryption_key_for_etke",
        store_name="etke_store.db"
    )

    # Créer le client
    client = AsyncClient(
        homeserver=homeserver,
        user=username,
        device_id=device_id,
        store_path=str(store_path),
        config=config
    )

    # Connexion
    response = await client.login(password=password, device_name=device_id)

    if not isinstance(response, LoginResponse):
        logger.error(f"❌ Login failed: {response}")
        return

    logger.info(f"✅ Logged in as {response.user_id}")

    # Charger le store de chiffrement (load_store n'est pas async dans nio)
    client.load_store()
    logger.info("🔐 Encryption store loaded")

    # Vérifier si nous avons Olm
    if hasattr(client, 'olm') and client.olm:
        logger.info("✅ Olm account loaded successfully")
        logger.info(f"   Identity keys: {client.olm.account.identity_keys}")
    else:
        logger.error("❌ Olm account not loaded")

    # Faire une sync complète pour obtenir les clés
    logger.info("🔄 Performing initial sync...")
    sync_response = await client.sync(timeout=30000, full_state=True)
    logger.info("✅ Initial sync complete")

    # Télécharger les clés des utilisateurs
    logger.info("🔑 Querying encryption keys...")
    await client.keys_query()

    # Partager les clés de session pour les rooms chiffrées
    logger.info("🔐 Sharing group session keys...")
    for room_id in client.rooms:
        room = client.rooms[room_id]
        if room.encrypted:
            logger.info(f"   Sharing keys for encrypted room: {room_id}")
            try:
                await client.share_group_session(room_id, ignore_unverified_devices=True)
            except Exception as e:
                logger.warning(f"   Could not share keys for {room_id}: {e}")

    # Trouver les rooms Instagram
    instagram_rooms = {}
    for room_id, room in client.rooms.items():
        room_name = room.display_name or "Unknown"
        if "instagram" in room_name.lower() or "(ig)" in room_name.lower():
            instagram_rooms[room_id] = room_name
            logger.info(f"📷 Found Instagram room: {room_name} ({room_id})")
            logger.info(f"   Encrypted: {room.encrypted}")
            logger.info(f"   Members: {len(room.users)}")

    if not instagram_rooms:
        logger.warning("⚠️ No Instagram rooms found")
        await client.close()
        return

    # Tester le déchiffrement pour chaque room Instagram
    for room_id, room_name in instagram_rooms.items():
        logger.info(f"\n🔍 Testing room: {room_name}")

        # Récupérer les messages récents
        messages_response = await client.room_messages(
            room_id=room_id,
            start="",
            limit=10,
            direction=MessageDirection.back
        )

        if not hasattr(messages_response, 'chunk'):
            logger.error(f"❌ Could not get messages for {room_id}")
            continue

        logger.info(f"📨 Found {len(messages_response.chunk)} events")

        for event in messages_response.chunk:
            event_type = type(event).__name__

            if isinstance(event, RoomMessageText):
                logger.info(f"✅ Plain text message from {event.sender}: {event.body[:50]}...")

            elif isinstance(event, MegolmEvent):
                logger.info(f"🔐 Encrypted event ({event_type}) from {event.sender}")

                # Tenter de déchiffrer
                try:
                    # La méthode decrypt_event existe dans nio
                    if hasattr(client, 'decrypt_event'):
                        decrypted = await client.decrypt_event(event)

                        if decrypted:
                            logger.info(f"✅ DECRYPTED successfully!")

                            # Extraire le contenu du message
                            if isinstance(decrypted, dict):
                                content = decrypted.get('content', {})
                                body = content.get('body', '')
                                logger.info(f"   Message: {body[:100]}...")
                            elif hasattr(decrypted, 'body'):
                                logger.info(f"   Message: {decrypted.body[:100]}...")
                            else:
                                logger.info(f"   Decrypted type: {type(decrypted)}")
                                logger.info(f"   Decrypted content: {str(decrypted)[:200]}...")
                        else:
                            logger.warning("⚠️ decrypt_event returned None")
                    else:
                        logger.error("❌ Client doesn't have decrypt_event method")

                        # Essayer une méthode alternative
                        if hasattr(event, 'ciphertext') and hasattr(event, 'algorithm'):
                            logger.info(f"   Algorithm: {event.algorithm}")
                            logger.info(f"   Session ID: {getattr(event, 'session_id', 'N/A')}")
                            logger.info(f"   Device ID: {getattr(event, 'device_id', 'N/A')}")

                            # Vérifier si nous avons la clé de session
                            if hasattr(client, 'olm') and client.olm:
                                # Essayer de récupérer la clé de session depuis le store
                                try:
                                    from nio.store.database import SqliteStore
                                    store = SqliteStore(
                                        user_id=response.user_id,
                                        device_id=device_id,
                                        store_path=str(store_path),
                                        pickle_key="encryption_key_for_etke"
                                    )

                                    # Ouvrir le store
                                    store.open()

                                    # Récupérer la clé de groupe
                                    if hasattr(event, 'session_id'):
                                        group_session = store.load_inbound_group_session(
                                            room_id=room_id,
                                            sender_key=getattr(event, 'sender_key', ''),
                                            session_id=event.session_id
                                        )

                                        if group_session:
                                            logger.info("✅ Found group session in store!")
                                        else:
                                            logger.warning("⚠️ No group session found")

                                    store.close()

                                except Exception as store_error:
                                    logger.error(f"Store error: {store_error}")

                except EncryptionError as e:
                    logger.error(f"❌ Encryption error: {e}")
                except Exception as e:
                    logger.error(f"❌ Decryption failed: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

            else:
                logger.debug(f"⏭️ Other event type: {event_type}")

    # Test d'écoute en temps réel
    logger.info("\n🎯 Testing real-time message listening...")

    # Définir un callback pour les messages
    message_received = asyncio.Event()
    decrypted_message = None

    async def message_callback(room, event):
        nonlocal decrypted_message

        logger.info(f"📨 Real-time event received in {room.room_id}")
        logger.info(f"   Event type: {type(event).__name__}")
        logger.info(f"   Sender: {event.sender}")

        if isinstance(event, RoomMessageText):
            logger.info(f"✅ Plain message: {event.body}")
            decrypted_message = event.body
            message_received.set()

        elif isinstance(event, MegolmEvent):
            logger.info("🔐 Encrypted message received, attempting to decrypt...")

            try:
                decrypted = await client.decrypt_event(event)
                if decrypted:
                    if isinstance(decrypted, dict):
                        body = decrypted.get('content', {}).get('body', '')
                        logger.info(f"✅ DECRYPTED: {body}")
                        decrypted_message = body
                    elif hasattr(decrypted, 'body'):
                        logger.info(f"✅ DECRYPTED: {decrypted.body}")
                        decrypted_message = decrypted.body
                    message_received.set()
                else:
                    logger.warning("⚠️ Could not decrypt")
            except Exception as e:
                logger.error(f"❌ Decryption error: {e}")

    # Ajouter les callbacks
    client.add_event_callback(message_callback, RoomMessageText)
    client.add_event_callback(message_callback, MegolmEvent)

    logger.info("⏳ Waiting for messages (send a message on Instagram)...")

    # Sync en arrière-plan
    sync_task = asyncio.create_task(client.sync_forever(timeout=30000, full_state=False))

    try:
        # Attendre un message pendant 60 secondes
        await asyncio.wait_for(message_received.wait(), timeout=60)

        if decrypted_message:
            logger.info(f"🎉 Successfully received and decrypted: {decrypted_message}")
        else:
            logger.warning("⚠️ Message received but not decrypted")

    except asyncio.TimeoutError:
        logger.info("⏰ Timeout - no messages received in 60 seconds")

    # Nettoyer
    sync_task.cancel()
    await client.close()
    logger.info("🔌 Disconnected")

if __name__ == "__main__":
    asyncio.run(test_decryption())