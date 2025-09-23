#!/usr/bin/env python3
"""
Test script pour débugger le problème de synchronisation Matrix
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import sys

# Add src to path
sys.path.insert(0, 'src')

from etke_matrix_client_prod import ProductionMatrixClient
from loguru import logger

load_dotenv()

async def test_sync():
    """Test la synchronisation et affiche les rooms trouvées"""
    logger.info("🔬 Starting sync test...")

    # Créer le client sans PostgreSQL pour simplifier
    client = ProductionMatrixClient(
        use_postgres=False,
        pg_config=None
    )

    try:
        # Démarrer le client
        logger.info("📡 Connecting to Matrix...")
        await client.start()

        # Attendre un peu pour la connexion
        await asyncio.sleep(2)

        # Vérifier l'état
        logger.info(f"✅ Logged in: {client.client.logged_in if client.client else False}")
        logger.info(f"🔑 User ID: {client.client.user_id if client.client else 'None'}")
        logger.info(f"📱 Device ID: {client.client.device_id if client.client else 'None'}")

        # Forcer une sync complète
        logger.info("🔄 Forcing full sync...")
        if client.client:
            response = await client.client.sync(timeout=30000, full_state=True)
            logger.info(f"📦 Sync response rooms: {len(response.rooms.join) if response and response.rooms else 0}")

            # Afficher les rooms
            if response and response.rooms and response.rooms.join:
                for room_id in response.rooms.join:
                    logger.info(f"  📍 Room: {room_id}")

        # Obtenir la liste des rooms via notre méthode
        logger.info("📋 Getting rooms list via API method...")
        rooms = await client.get_rooms_list()
        logger.info(f"📊 Total rooms found: {rooms['total']}")

        if rooms['total'] > 0:
            logger.success("✅ Rooms detected successfully!")
            for room in rooms['rooms']:
                logger.info(f"  🏠 {room['name']} ({room['room_id']}) - {room['platform']}")
        else:
            logger.warning("⚠️ No rooms found! Check if bridges are configured.")

            # Vérifier si le client a des rooms
            if client.client and hasattr(client.client, 'rooms'):
                logger.info(f"🔍 Client rooms object: {client.client.rooms}")
                logger.info(f"🔍 Number of rooms in client: {len(client.client.rooms) if client.client.rooms else 0}")

        # Tester la synchronisation continue
        logger.info("🔁 Starting continuous sync for 10 seconds...")

        # Créer une tâche de sync
        sync_task = asyncio.create_task(client.listen_for_messages())

        # Attendre 10 secondes
        await asyncio.sleep(10)

        # Vérifier à nouveau
        rooms_after = await client.get_rooms_list()
        logger.info(f"📊 Rooms after continuous sync: {rooms_after['total']}")

        # Annuler la tâche de sync
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass

    except Exception as e:
        logger.error(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.stop()
        logger.info("👋 Test completed")

if __name__ == "__main__":
    asyncio.run(test_sync())