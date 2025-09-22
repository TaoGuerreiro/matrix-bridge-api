#!/usr/bin/env python3
"""
Script pour établir une session de chiffrement persistante et auto-gérer les clés
"""
import asyncio
import os
from pathlib import Path
from nio import (
    AsyncClient,
    AsyncClientConfig,
    LoginResponse,
    RoomKeyRequestResponse,
    ToDeviceError,
    LocalProtocolError
)
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

async def setup_persistent_encryption():
    """Configurer une session de chiffrement persistante qui partage automatiquement les clés"""

    homeserver = os.getenv("ETKE_HOMESERVER", "https://matrix.chalky.etke.host")
    username = os.getenv("ETKE_USERNAME", "@florent:chalky.etke.host")
    password = os.getenv("ETKE_PASSWORD")
    device_id = "BEEPER_API_CLIENT"

    # Créer un dossier pour le store persistant
    store_path = Path("matrix_store")
    store_path.mkdir(exist_ok=True)

    logger.info(f"🔧 Setting up persistent encryption for {username}")

    # Configuration avec chiffrement et stockage persistant
    config = AsyncClientConfig(
        store_sync_tokens=True,
        encryption_enabled=True,
        pickle_key="encryption_key_for_etke",
        store_name="etke_store.db"
    )

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
        return None

    logger.info(f"✅ Logged in as {response.user_id}")

    # Charger le store
    client.load_store()
    logger.info("🔐 Store loaded")

    # Synchronisation complète pour récupérer toutes les rooms
    logger.info("🔄 Initial sync...")
    sync_response = await client.sync(timeout=30000, full_state=True)
    logger.info(f"✅ Synced {len(client.rooms)} rooms")

    # Télécharger toutes les clés des utilisateurs
    logger.info("🔑 Downloading all user keys...")
    await client.keys_query()

    # Partager automatiquement les clés pour toutes les rooms chiffrées
    logger.info("🔐 Sharing keys for encrypted rooms...")
    shared_count = 0
    failed_count = 0

    for room_id in client.rooms:
        room = client.rooms[room_id]
        if room.encrypted:
            try:
                # Partager les clés de session avec tous les membres de la room
                await client.share_group_session(room_id, ignore_unverified_devices=True)
                shared_count += 1
                logger.debug(f"   ✅ Shared keys for {room_id}")
            except Exception as e:
                failed_count += 1
                logger.warning(f"   ⚠️ Could not share keys for {room_id}: {e}")

    logger.info(f"📊 Key sharing complete: {shared_count} succeeded, {failed_count} failed")

    # Demander les clés manquantes pour les messages qu'on ne peut pas déchiffrer
    logger.info("🔄 Requesting missing keys...")

    # Pour chaque room Instagram/Messenger
    instagram_rooms = [rid for rid, room in client.rooms.items()
                       if "instagram" in (room.display_name or "").lower()]
    messenger_rooms = [rid for rid, room in client.rooms.items()
                       if "messenger" in (room.display_name or "").lower()]

    logger.info(f"📷 Found {len(instagram_rooms)} Instagram rooms")
    logger.info(f"💬 Found {len(messenger_rooms)} Messenger rooms")

    # Configurer la confiance automatique pour les bridges
    logger.info("🤝 Setting up trust for bridge devices...")

    bridge_users = set()
    for room_id in instagram_rooms + messenger_rooms:
        room = client.rooms.get(room_id)
        if room:
            for user_id in room.users:
                if "instagram" in user_id or "messenger" in user_id:
                    bridge_users.add(user_id)

    logger.info(f"🌉 Found {len(bridge_users)} bridge users")

    # Vérifier automatiquement les dispositifs des bridges
    for user_id in bridge_users:
        try:
            # Récupérer les dispositifs de cet utilisateur
            devices = client.device_store.active_user_devices(user_id)
            for device in devices.values():
                if not device.verified:
                    # Marquer comme vérifié (faire confiance)
                    client.verify_device(device)
                    logger.info(f"   ✅ Trusted device {device.id} for {user_id}")
        except Exception as e:
            logger.debug(f"   Could not verify devices for {user_id}: {e}")

    # Sauvegarder l'état
    logger.info("💾 Saving encryption state...")
    await client.close()

    logger.info("✅ Encryption setup complete!")
    logger.info("🔄 The API should now be able to decrypt Instagram/Messenger messages")

    return True

async def test_decryption_after_setup():
    """Tester si on peut maintenant déchiffrer les messages"""

    homeserver = os.getenv("ETKE_HOMESERVER", "https://matrix.chalky.etke.host")
    username = os.getenv("ETKE_USERNAME", "@florent:chalky.etke.host")
    password = os.getenv("ETKE_PASSWORD")
    device_id = "BEEPER_API_CLIENT"

    store_path = Path("matrix_store")

    config = AsyncClientConfig(
        store_sync_tokens=True,
        encryption_enabled=True,
        pickle_key="encryption_key_for_etke",
        store_name="etke_store.db"
    )

    client = AsyncClient(
        homeserver=homeserver,
        user=username,
        device_id=device_id,
        store_path=str(store_path),
        config=config
    )

    response = await client.login(password=password, device_name=device_id)

    if not isinstance(response, LoginResponse):
        logger.error(f"❌ Login failed: {response}")
        return

    client.load_store()

    logger.info("🔍 Testing decryption capability...")

    # Sync pour obtenir les derniers messages
    await client.sync(timeout=10000)

    # Chercher une room Instagram avec des messages
    for room_id, room in client.rooms.items():
        if "instagram" in (room.display_name or "").lower():
            logger.info(f"📷 Testing room: {room.display_name}")

            # Essayer de récupérer des messages récents
            from nio import MessageDirection
            response = await client.room_messages(
                room_id=room_id,
                start="",
                limit=5,
                direction=MessageDirection.back
            )

            if hasattr(response, 'chunk'):
                for event in response.chunk:
                    event_type = type(event).__name__

                    if event_type == "RoomMessageText":
                        logger.info(f"   ✅ Plain text message: {event.body[:50]}...")
                    elif event_type == "MegolmEvent":
                        # Essayer de déchiffrer
                        try:
                            decrypted = await client.decrypt_event(event)
                            if decrypted:
                                logger.info(f"   ✅ SUCCESSFULLY DECRYPTED: {str(decrypted)[:100]}...")
                            else:
                                logger.warning(f"   ⚠️ Could not decrypt")
                        except Exception as e:
                            logger.error(f"   ❌ Decryption error: {e}")

            break  # Tester juste une room

    await client.close()
    logger.info("🔌 Test complete")

if __name__ == "__main__":
    # D'abord configurer le chiffrement
    asyncio.run(setup_persistent_encryption())

    # Puis tester
    logger.info("\n" + "="*50)
    logger.info("Now testing decryption...")
    logger.info("="*50 + "\n")

    asyncio.run(test_decryption_after_setup())