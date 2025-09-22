#!/usr/bin/env python3
"""
Migration du store SQLite vers PostgreSQL pour la production
"""
import os
import asyncio
import pickle
import psycopg2
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

async def migrate_to_postgres():
    """Migrer le store SQLite existant vers PostgreSQL"""

    # Configuration PostgreSQL
    pg_config = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "database": os.getenv("POSTGRES_DB", "matrix_store"),
        "user": os.getenv("POSTGRES_USER", "matrix_user"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "port": int(os.getenv("POSTGRES_PORT", 5432))
    }

    logger.info(f"🔄 Migration vers PostgreSQL: {pg_config['host']}:{pg_config['port']}")

    # Connexion PostgreSQL
    conn = psycopg2.connect(**pg_config)
    cur = conn.cursor()

    # Créer les tables nécessaires
    logger.info("📊 Création des tables Matrix...")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS device_keys (
            user_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            keys JSONB,
            trust_state TEXT DEFAULT 'unverified',
            PRIMARY KEY (user_id, device_id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS inbound_group_sessions (
            room_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            sender_key TEXT NOT NULL,
            session_data BYTEA NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (room_id, session_id, sender_key)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS outbound_group_sessions (
            room_id TEXT PRIMARY KEY,
            session_data BYTEA NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS olm_sessions (
            sender_key TEXT NOT NULL,
            session_id TEXT NOT NULL,
            session_data BYTEA NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (sender_key, session_id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sync_tokens (
            user_id TEXT PRIMARY KEY,
            token TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS account_data (
            user_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            account_data BYTEA NOT NULL,
            PRIMARY KEY (user_id, device_id)
        );
    """)

    conn.commit()
    logger.info("✅ Tables créées avec succès")

    # Charger les données depuis SQLite si elles existent
    sqlite_path = Path("matrix_store/etke_store.db")
    if sqlite_path.exists():
        logger.info("📦 Migration des données SQLite existantes...")

        import sqlite3
        sqlite_conn = sqlite3.connect(str(sqlite_path))
        sqlite_cur = sqlite_conn.cursor()

        # Migrer les sessions de groupe (les plus importantes)
        try:
            sqlite_cur.execute("SELECT * FROM inbound_group_sessions")
            sessions = sqlite_cur.fetchall()

            for session in sessions:
                cur.execute("""
                    INSERT INTO inbound_group_sessions
                    (room_id, session_id, sender_key, session_data)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (session[0], session[1], session[2], session[3]))

            logger.info(f"   ✅ Migré {len(sessions)} sessions de groupe")
        except Exception as e:
            logger.warning(f"   ⚠️ Pas de sessions à migrer: {e}")

        conn.commit()
        sqlite_conn.close()

    # Créer des index pour les performances
    logger.info("🚀 Création des index...")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_room ON inbound_group_sessions(room_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_sender ON inbound_group_sessions(sender_key);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_device_user ON device_keys(user_id);")

    conn.commit()
    cur.close()
    conn.close()

    logger.info("✅ Migration terminée avec succès!")
    logger.info("📝 Ajouter ces variables d'environnement pour l'API:")
    logger.info(f"   POSTGRES_HOST={pg_config['host']}")
    logger.info(f"   POSTGRES_DB={pg_config['database']}")
    logger.info(f"   POSTGRES_USER={pg_config['user']}")
    logger.info("   POSTGRES_PASSWORD=***")

if __name__ == "__main__":
    asyncio.run(migrate_to_postgres())