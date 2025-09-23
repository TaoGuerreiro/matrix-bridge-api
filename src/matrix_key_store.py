#!/usr/bin/env python3
"""
PostgreSQL Key Store pour Matrix
Gère la persistance des clés de chiffrement E2E dans PostgreSQL
"""
import json
import base64
import pickle
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncpg
from loguru import logger
from pathlib import Path


class PostgreSQLKeyStore:
    """
    Stockage persistant des clés Matrix dans PostgreSQL
    """

    def __init__(self, pg_config: Dict[str, Any]):
        self.pg_config = pg_config
        self.connection_pool = None

    async def init(self):
        """Initialise la connexion et crée les tables si nécessaire"""
        try:
            # Extraire pool_size du config et l'utiliser pour min_size/max_size
            pool_size = self.pg_config.pop('pool_size', 5)

            self.connection_pool = await asyncpg.create_pool(
                **self.pg_config,
                min_size=1,
                max_size=pool_size
            )

            await self._create_tables()
            logger.info("✅ PostgreSQL Key Store initialized")
            return True
        except Exception as e:
            logger.warning(f"PostgreSQL Key Store unavailable: {e}")
            logger.info("💡 Running in development mode without key persistence")
            self.connection_pool = None
            return False

    async def _create_tables(self):
        """Crée les tables nécessaires pour stocker les clés"""
        if not self.connection_pool:
            return

        async with self.connection_pool.acquire() as conn:
            # Table pour les informations du device
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS matrix_device_keys (
                    user_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    ed25519_key TEXT,
                    curve25519_key TEXT,
                    device_display_name TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Table pour les sessions Megolm (déchiffrement des messages)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS matrix_megolm_sessions (
                    session_id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    sender_key TEXT NOT NULL,
                    session_data TEXT NOT NULL,
                    first_known_index INTEGER DEFAULT 0,
                    forwarded_count INTEGER DEFAULT 0,
                    is_imported BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Créer un index pour les recherches par room
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_megolm_room
                ON matrix_megolm_sessions(room_id)
            """)

            # Table pour les sessions Olm (échange de clés)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS matrix_olm_sessions (
                    session_id TEXT PRIMARY KEY,
                    sender_key TEXT NOT NULL,
                    session_pickle TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Table pour l'account Olm (clés du compte)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS matrix_olm_account (
                    user_id TEXT PRIMARY KEY,
                    account_pickle TEXT NOT NULL,
                    shared BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Table pour les clés de rooms exportées
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS matrix_exported_keys (
                    export_id SERIAL PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    session_key TEXT NOT NULL,
                    algorithm TEXT DEFAULT 'm.megolm.v1.aes-sha2',
                    sender_key TEXT NOT NULL,
                    sender_claimed_keys TEXT,
                    forwarding_curve25519_key_chain TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(room_id, session_id)
                )
            """)

    async def save_device_keys(self, user_id: str, device_id: str, keys: Dict[str, str]):
        """Sauvegarde les clés du device"""
        if not self.connection_pool:
            logger.debug("PostgreSQL unavailable - skipping device keys save")
            return

        async with self.connection_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO matrix_device_keys (user_id, device_id, ed25519_key, curve25519_key)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    device_id = $2,
                    ed25519_key = $3,
                    curve25519_key = $4,
                    updated_at = NOW()
            """, user_id, device_id, keys.get('ed25519'), keys.get('curve25519'))

    async def get_device_keys(self, user_id: str) -> Optional[Dict[str, str]]:
        """Récupère les clés du device"""
        if not self.connection_pool:
            logger.debug("PostgreSQL unavailable - no device keys available")
            return None

        async with self.connection_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT device_id, ed25519_key, curve25519_key
                FROM matrix_device_keys
                WHERE user_id = $1
            """, user_id)

            if row:
                return {
                    'device_id': row['device_id'],
                    'ed25519': row['ed25519_key'],
                    'curve25519': row['curve25519_key']
                }
            return None

    async def save_megolm_session(self, room_id: str, session_id: str,
                                 sender_key: str, session_data: Any,
                                 first_known_index: int = 0):
        """Sauvegarde une session Megolm"""
        if not self.connection_pool:
            logger.debug("PostgreSQL unavailable - skipping Megolm session save")
            return

        try:
            # Sérialiser la session (peut être un objet ou un dict)
            if hasattr(session_data, 'to_json'):
                session_json = session_data.to_json()
            elif isinstance(session_data, dict):
                session_json = json.dumps(session_data)
            else:
                # Fallback avec pickle pour les objets complexes
                session_json = base64.b64encode(pickle.dumps(session_data)).decode('utf-8')

            async with self.connection_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO matrix_megolm_sessions
                    (session_id, room_id, sender_key, session_data, first_known_index)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (session_id)
                    DO UPDATE SET
                        session_data = $4,
                        first_known_index = LEAST(matrix_megolm_sessions.first_known_index, $5),
                        updated_at = NOW()
                """, session_id, room_id, sender_key, session_json, first_known_index)

                logger.debug(f"Saved Megolm session {session_id} for room {room_id}")
        except Exception as e:
            logger.error(f"Failed to save Megolm session: {e}")

    async def get_megolm_sessions(self, room_id: str) -> List[Dict[str, Any]]:
        """Récupère toutes les sessions Megolm d'une room"""
        if not self.connection_pool:
            logger.debug("PostgreSQL unavailable - no Megolm sessions available")
            return []

        async with self.connection_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT session_id, sender_key, session_data, first_known_index
                FROM matrix_megolm_sessions
                WHERE room_id = $1
                ORDER BY created_at DESC
            """, room_id)

            sessions = []
            for row in rows:
                try:
                    # Essayer de désérialiser
                    session_data = row['session_data']
                    try:
                        # D'abord essayer JSON
                        data = json.loads(session_data)
                    except:
                        # Sinon essayer pickle
                        data = pickle.loads(base64.b64decode(session_data))

                    sessions.append({
                        'session_id': row['session_id'],
                        'sender_key': row['sender_key'],
                        'session_data': data,
                        'first_known_index': row['first_known_index']
                    })
                except Exception as e:
                    logger.warning(f"Failed to deserialize session: {e}")

            return sessions

    async def save_olm_session(self, session_id: str, sender_key: str, session_pickle: str):
        """Sauvegarde une session Olm"""
        if not self.connection_pool:
            logger.debug("PostgreSQL unavailable - skipping Olm session save")
            return

        async with self.connection_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO matrix_olm_sessions (session_id, sender_key, session_pickle)
                VALUES ($1, $2, $3)
                ON CONFLICT (session_id)
                DO UPDATE SET
                    session_pickle = $3,
                    updated_at = NOW()
            """, session_id, sender_key, session_pickle)

    async def get_olm_sessions(self, sender_key: str) -> List[Dict[str, str]]:
        """Récupère les sessions Olm pour une sender_key"""
        if not self.connection_pool:
            logger.debug("PostgreSQL unavailable - no Olm sessions available")
            return []

        async with self.connection_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT session_id, session_pickle
                FROM matrix_olm_sessions
                WHERE sender_key = $1
                ORDER BY created_at DESC
            """, sender_key)

            return [{'session_id': row['session_id'],
                    'session_pickle': row['session_pickle']} for row in rows]

    async def save_olm_account(self, user_id: str, account_pickle: str):
        """Sauvegarde l'account Olm"""
        if not self.connection_pool:
            logger.debug("PostgreSQL unavailable - skipping Olm account save")
            return

        async with self.connection_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO matrix_olm_account (user_id, account_pickle, shared)
                VALUES ($1, $2, TRUE)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    account_pickle = $2,
                    shared = TRUE,
                    updated_at = NOW()
            """, user_id, account_pickle)

    async def get_olm_account(self, user_id: str) -> Optional[str]:
        """Récupère l'account Olm"""
        if not self.connection_pool:
            logger.debug("PostgreSQL unavailable - no Olm account available")
            return None

        async with self.connection_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT account_pickle
                FROM matrix_olm_account
                WHERE user_id = $1
            """, user_id)

            return row['account_pickle'] if row else None

    async def export_room_keys(self, room_id: str) -> List[Dict[str, Any]]:
        """Exporte les clés d'une room au format Element"""
        if not self.connection_pool:
            logger.debug("PostgreSQL unavailable - no room keys to export")
            return []

        async with self.connection_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT session_id, session_key, algorithm, sender_key,
                       sender_claimed_keys, forwarding_curve25519_key_chain
                FROM matrix_exported_keys
                WHERE room_id = $1
            """, room_id)

            keys = []
            for row in rows:
                key_data = {
                    'room_id': room_id,
                    'session_id': row['session_id'],
                    'session_key': row['session_key'],
                    'algorithm': row['algorithm'],
                    'sender_key': row['sender_key']
                }

                if row['sender_claimed_keys']:
                    key_data['sender_claimed_keys'] = json.loads(row['sender_claimed_keys'])
                if row['forwarding_curve25519_key_chain']:
                    key_data['forwarding_curve25519_key_chain'] = json.loads(row['forwarding_curve25519_key_chain'])

                keys.append(key_data)

            return keys

    async def import_room_keys(self, keys: List[Dict[str, Any]]):
        """Importe des clés au format Element"""
        if not self.connection_pool:
            logger.debug("PostgreSQL unavailable - skipping room keys import")
            return

        async with self.connection_pool.acquire() as conn:
            for key in keys:
                await conn.execute("""
                    INSERT INTO matrix_exported_keys
                    (room_id, session_id, session_key, algorithm, sender_key,
                     sender_claimed_keys, forwarding_curve25519_key_chain)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (room_id, session_id) DO NOTHING
                """,
                key.get('room_id'),
                key.get('session_id'),
                key.get('session_key'),
                key.get('algorithm', 'm.megolm.v1.aes-sha2'),
                key.get('sender_key'),
                json.dumps(key.get('sender_claimed_keys')) if key.get('sender_claimed_keys') else None,
                json.dumps(key.get('forwarding_curve25519_key_chain')) if key.get('forwarding_curve25519_key_chain') else None
                )

    async def clear_all_keys(self):
        """Efface toutes les clés (DANGER!)"""
        if not self.connection_pool:
            logger.warning("PostgreSQL unavailable - no keys to clear")
            return

        async with self.connection_pool.acquire() as conn:
            await conn.execute("TRUNCATE matrix_device_keys, matrix_megolm_sessions, matrix_olm_sessions, matrix_olm_account, matrix_exported_keys")
            logger.warning("⚠️ All encryption keys have been cleared!")

    async def get_stats(self) -> Dict[str, int]:
        """Statistiques sur les clés stockées"""
        if not self.connection_pool:
            return {
                'device_keys': 0,
                'megolm_sessions': 0,
                'olm_sessions': 0,
                'olm_accounts': 0,
                'exported_keys': 0,
                'status': 'postgresql_unavailable'
            }

        async with self.connection_pool.acquire() as conn:
            stats = {}

            stats['device_keys'] = await conn.fetchval("SELECT COUNT(*) FROM matrix_device_keys")
            stats['megolm_sessions'] = await conn.fetchval("SELECT COUNT(*) FROM matrix_megolm_sessions")
            stats['olm_sessions'] = await conn.fetchval("SELECT COUNT(*) FROM matrix_olm_sessions")
            stats['olm_accounts'] = await conn.fetchval("SELECT COUNT(*) FROM matrix_olm_account")
            stats['exported_keys'] = await conn.fetchval("SELECT COUNT(*) FROM matrix_exported_keys")
            stats['status'] = 'postgresql_connected'

            return stats

    async def close(self):
        """Ferme le pool de connexions"""
        if self.connection_pool:
            await self.connection_pool.close()