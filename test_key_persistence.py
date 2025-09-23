#!/usr/bin/env python3
"""
Test de persistance des clés Matrix dans PostgreSQL
Vérifie que les clés sont correctement sauvegardées et restaurées
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
from matrix_key_store import PostgreSQLKeyStore

load_dotenv()

async def test_key_persistence():
    """Test la persistance des clés dans PostgreSQL"""
    logger.info("🔬 Starting key persistence test...")

    # Configuration PostgreSQL
    pg_config = {
        'database': os.getenv('POSTGRESQL_ADDON_DB', os.getenv('POSTGRES_DB', 'matrix_store')),
        'host': os.getenv('POSTGRESQL_ADDON_HOST', os.getenv('POSTGRES_HOST', 'localhost')),
        'port': int(os.getenv('POSTGRESQL_ADDON_PORT', os.getenv('POSTGRES_PORT', 5432))),
        'user': os.getenv('POSTGRESQL_ADDON_USER', os.getenv('POSTGRES_USER', 'matrix_user')),
        'password': os.getenv('POSTGRESQL_ADDON_PASSWORD', os.getenv('POSTGRES_PASSWORD'))
    }

    # Créer le key store directement
    key_store = PostgreSQLKeyStore(pg_config)
    await key_store.init()

    # Afficher les stats initiales
    stats = await key_store.get_stats()
    logger.info(f"📊 Initial stats: {stats}")

    # Créer le client avec PostgreSQL activé
    client = ProductionMatrixClient(
        use_postgres=True,
        pg_config=pg_config
    )

    try:
        # Phase 1: Connexion et sauvegarde
        logger.info("📡 Phase 1: Connecting and saving keys...")
        await client.start()
        await asyncio.sleep(3)

        # Vérifier si on a des rooms chiffrées
        encrypted_rooms = []
        if client.client:
            for room_id, room in client.client.rooms.items():
                if room.encrypted:
                    encrypted_rooms.append(room_id)
                    logger.info(f"  🔐 Encrypted room: {room_id} - {room.display_name}")

        logger.info(f"📊 Found {len(encrypted_rooms)} encrypted rooms")

        # Forcer la sauvegarde des clés
        if client.key_store:
            await client._save_keys_to_postgres()
            stats_after_save = await key_store.get_stats()
            logger.info(f"💾 Keys saved! New stats: {stats_after_save}")

        # Test de récupération d'un message
        if encrypted_rooms:
            test_room = encrypted_rooms[0]
            logger.info(f"🔍 Testing message retrieval for room {test_room}...")
            messages = await client.get_room_messages(test_room, limit=5)
            logger.info(f"  📩 Retrieved {len(messages)} messages")
            for msg in messages[:2]:
                logger.info(f"    - {msg.get('sender', 'Unknown')}: {msg.get('content', 'N/A')[:50]}...")

        # Arrêter le client
        await client.stop()
        logger.info("🛑 Client stopped")

        # Phase 2: Reconnexion et restauration
        logger.info("\n📡 Phase 2: Reconnecting with new client...")
        await asyncio.sleep(2)

        # Créer un nouveau client (simule un redémarrage)
        client2 = ProductionMatrixClient(
            use_postgres=True,
            pg_config=pg_config
        )

        await client2.start()
        await asyncio.sleep(3)

        # Les clés devraient être restaurées depuis PostgreSQL
        if client2.key_store:
            await client2._restore_keys_from_postgres()
            stats_after_restore = await key_store.get_stats()
            logger.info(f"🔄 Keys restored! Stats: {stats_after_restore}")

        # Tester à nouveau la récupération de messages
        if encrypted_rooms:
            test_room = encrypted_rooms[0]
            logger.info(f"🔍 Testing message retrieval after restore for room {test_room}...")
            messages2 = await client2.get_room_messages(test_room, limit=5)
            logger.info(f"  📩 Retrieved {len(messages2)} messages after restore")

            # Comparer avec les messages d'avant
            if len(messages2) > 0:
                logger.success("✅ Messages still accessible after key restore!")
                for msg in messages2[:2]:
                    logger.info(f"    - {msg.get('sender', 'Unknown')}: {msg.get('content', 'N/A')[:50]}...")
            else:
                logger.warning("⚠️ No messages retrieved after restore")

        await client2.stop()
        logger.info("🛑 Second client stopped")

        # Afficher les stats finales
        final_stats = await key_store.get_stats()
        logger.info(f"\n📊 Final statistics:")
        logger.info(f"  - Device keys: {final_stats.get('device_keys', 0)}")
        logger.info(f"  - Megolm sessions: {final_stats.get('megolm_sessions', 0)}")
        logger.info(f"  - Olm sessions: {final_stats.get('olm_sessions', 0)}")
        logger.info(f"  - Olm accounts: {final_stats.get('olm_accounts', 0)}")
        logger.info(f"  - Exported keys: {final_stats.get('exported_keys', 0)}")

        if final_stats.get('megolm_sessions', 0) > 0:
            logger.success("🎉 Key persistence test SUCCESSFUL! Keys are stored in PostgreSQL.")
        else:
            logger.warning("⚠️ No Megolm sessions found in PostgreSQL. Keys might not be persisting correctly.")

    except Exception as e:
        logger.error(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await key_store.close()
        logger.info("👋 Test completed")

if __name__ == "__main__":
    asyncio.run(test_key_persistence())