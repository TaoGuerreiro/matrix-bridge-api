#!/usr/bin/env python3
"""
Script de test pour récupérer les messages d'une room
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import sys
from loguru import logger

# Add src to path
sys.path.insert(0, 'src')

from etke_matrix_client_prod import ProductionMatrixClient

load_dotenv()

async def test_room_messages():
    """Test la récupération des messages d'une room"""
    logger.info("🔬 Starting room messages test...")

    # Créer le client
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

        # Room Instagram d'Antonin
        room_id = "!HBeUMtwsIJtzIlXljT:chalky.etke.host"
        logger.info(f"🔍 Fetching messages from room: {room_id}")

        # Récupérer les messages
        messages = await client.get_room_messages(room_id, limit=10)

        logger.info(f"📊 Found {len(messages)} messages")

        if messages:
            for msg in messages[:3]:  # Afficher les 3 premiers
                logger.info(f"  📩 From {msg['sender']}: {msg['content'][:50]}...")
        else:
            logger.warning("⚠️ No messages found in room")

            # Essayer de comprendre pourquoi
            if client.client and room_id in client.client.rooms:
                room = client.client.rooms[room_id]
                logger.info(f"  Room exists: {room.display_name}")
                logger.info(f"  Encrypted: {room.encrypted}")
                logger.info(f"  Members: {len(room.users)}")

                # Essayer une méthode alternative
                logger.info("🔄 Trying alternative method...")
                try:
                    from nio import MessageDirection
                    response = await client.client.room_messages(
                        room_id,
                        start="",
                        limit=10,
                        message_direction=MessageDirection.back
                    )

                    if response:
                        logger.info(f"  Response type: {type(response)}")
                        if hasattr(response, 'chunk'):
                            logger.info(f"  Chunk length: {len(response.chunk)}")
                            for event in response.chunk[:3]:
                                logger.info(f"    Event type: {type(event).__name__}")
                                if hasattr(event, 'body'):
                                    logger.info(f"    Content: {event.body[:50]}...")
                        else:
                            logger.warning("  No chunk in response")
                except Exception as e2:
                    logger.error(f"  Alternative method failed: {e2}")
            else:
                logger.error(f"  Room {room_id} not found in client rooms")

    except Exception as e:
        logger.error(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.stop()
        logger.info("👋 Test completed")

if __name__ == "__main__":
    asyncio.run(test_room_messages())