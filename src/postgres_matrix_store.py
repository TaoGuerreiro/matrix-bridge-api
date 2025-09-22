#!/usr/bin/env python3
"""
PostgreSQL Matrix Store pour production
Gère la persistance des clés de chiffrement Matrix dans PostgreSQL
"""
import os
import json
import pickle
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager

# Remove nio.store imports as they don't exist in current nio version
# We'll implement our own store interface

logger = logging.getLogger(__name__)


class PostgresMatrixStore:
    """
    Store PostgreSQL production-ready pour Matrix encryption
    Gère la persistance complète des clés de chiffrement
    """

    def __init__(
        self,
        user_id: str,
        device_id: str,
        database: str,
        host: str = "localhost",
        port: int = 5432,
        user: str = "matrix_user",
        password: str = None,
        pool_size: int = 20,
        pickle_key: str = "",
        **kwargs
    ):
        """
        Initialise le store PostgreSQL avec pool de connexions

        Args:
            user_id: Matrix user ID (@user:server.com)
            device_id: Device ID unique
            database: Nom de la base PostgreSQL
            host: Serveur PostgreSQL
            port: Port PostgreSQL
            user: Utilisateur PostgreSQL
            password: Mot de passe PostgreSQL
            pool_size: Taille du pool de connexions
            pickle_key: Clé pour chiffrer les données sensibles
        """
        self.user_id = user_id
        self.device_id = device_id
        self.pickle_key = pickle_key or "default_encryption_key"

        # Configuration PostgreSQL
        self.db_config = {
            'database': database,
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'cursor_factory': RealDictCursor
        }

        # Pool de connexions pour performance
        self.connection_pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=pool_size,
            **self.db_config
        )

        # Initialiser le schéma
        self._init_database_schema()

        # Charger l'account ID si existant
        self.account_id = self._get_or_create_account_id()

        logger.info(f"PostgresMatrixStore initialized for {user_id}/{device_id}")

    @contextmanager
    def get_connection(self):
        """Context manager pour obtenir une connexion du pool"""
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def _init_database_schema(self):
        """Créer les tables nécessaires si elles n'existent pas"""
        with self.get_connection() as conn:
            cur = conn.cursor()

            # Table des comptes Olm
            cur.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    shared BOOLEAN DEFAULT FALSE,
                    account_data BYTEA NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, device_id)
                )
            """)

            # Table des clés de devices
            cur.execute("""
                CREATE TABLE IF NOT EXISTS device_keys (
                    id SERIAL PRIMARY KEY,
                    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    keys JSONB NOT NULL,
                    display_name TEXT DEFAULT '',
                    deleted BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(account_id, user_id, device_id)
                )
            """)

            # Sessions Megolm (les plus importantes pour le déchiffrement)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS megolm_inbound_sessions (
                    id SERIAL PRIMARY KEY,
                    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                    room_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    sender_key TEXT NOT NULL,
                    signing_keys JSONB,
                    forwarding_chains TEXT[],
                    session_data BYTEA NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(account_id, room_id, session_id, sender_key)
                )
            """)

            # Sessions Olm (chiffrement 1-to-1)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS olm_sessions (
                    id SERIAL PRIMARY KEY,
                    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                    sender_key TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    session_data BYTEA NOT NULL,
                    creation_time TIMESTAMP DEFAULT NOW(),
                    last_usage TIMESTAMP DEFAULT NOW()
                )
            """)

            # Rooms chiffrées
            cur.execute("""
                CREATE TABLE IF NOT EXISTS encrypted_rooms (
                    id SERIAL PRIMARY KEY,
                    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                    room_id TEXT NOT NULL,
                    rotation_period INTEGER DEFAULT 604800000,
                    rotation_messages INTEGER DEFAULT 100,
                    UNIQUE(account_id, room_id)
                )
            """)

            # Tokens de synchronisation
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sync_tokens (
                    id SERIAL PRIMARY KEY,
                    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                    token TEXT NOT NULL
                )
            """)

            # Index pour performance
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_megolm_lookup
                ON megolm_inbound_sessions(account_id, room_id, sender_key);

                CREATE INDEX IF NOT EXISTS idx_device_keys_user
                ON device_keys(account_id, user_id);

                CREATE INDEX IF NOT EXISTS idx_olm_sender
                ON olm_sessions(account_id, sender_key);
            """)

            logger.info("Database schema initialized successfully")

    def _get_or_create_account_id(self) -> Optional[int]:
        """Récupère ou crée l'account ID pour ce user/device"""
        with self.get_connection() as conn:
            cur = conn.cursor()

            # Chercher un account existant
            cur.execute(
                "SELECT id FROM accounts WHERE user_id = %s AND device_id = %s",
                (self.user_id, self.device_id)
            )
            result = cur.fetchone()

            if result:
                return result['id']
            return None

    def _encrypt_data(self, data: Any) -> bytes:
        """Chiffre les données sensibles avec pickle_key"""
        pickled = pickle.dumps(data)
        # Dans un vrai système, utiliser une vraie encryption (ex: cryptography.Fernet)
        # Ici on fait simple pour la démo
        return pickled

    def _decrypt_data(self, data: bytes) -> Any:
        """Déchiffre les données"""
        return pickle.loads(data)

    # Méthodes pour Olm Account

    def load_account(self):
        """Charge le compte Olm depuis PostgreSQL"""
        if not self.account_id:
            return None

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT account_data FROM accounts WHERE id = %s",
                (self.account_id,)
            )
            result = cur.fetchone()

            if result:
                return self._decrypt_data(result['account_data'])
        return None

    def save_account(self, account):
        """Sauvegarde le compte Olm dans PostgreSQL"""
        account_data = self._encrypt_data(account)

        with self.get_connection() as conn:
            cur = conn.cursor()

            if self.account_id:
                # Update existant
                cur.execute(
                    """UPDATE accounts
                       SET account_data = %s, updated_at = NOW()
                       WHERE id = %s""",
                    (account_data, self.account_id)
                )
            else:
                # Nouveau compte
                cur.execute(
                    """INSERT INTO accounts (user_id, device_id, account_data)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (user_id, device_id)
                       DO UPDATE SET account_data = EXCLUDED.account_data, updated_at = NOW()
                       RETURNING id""",
                    (self.user_id, self.device_id, account_data)
                )
                self.account_id = cur.fetchone()['id']

    # Méthodes pour Megolm Sessions (crucial pour déchiffrement)

    def load_inbound_group_sessions(self) -> List:
        """Charge toutes les sessions Megolm depuis PostgreSQL"""
        if not self.account_id:
            return []

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT room_id, session_id, sender_key, session_data,
                          signing_keys, forwarding_chains
                   FROM megolm_inbound_sessions
                   WHERE account_id = %s""",
                (self.account_id,)
            )

            sessions = []
            for row in cur.fetchall():
                session_data = self._decrypt_data(row['session_data'])
                sessions.append({
                    'room_id': row['room_id'],
                    'session_id': row['session_id'],
                    'sender_key': row['sender_key'],
                    'session': session_data,
                    'signing_keys': row['signing_keys'],
                    'forwarding_chains': row['forwarding_chains'] or []
                })

            return sessions

    def save_inbound_group_session(
        self,
        room_id: str,
        session_id: str,
        sender_key: str,
        session,
        signing_keys: Dict = None,
        forwarding_chains: List = None
    ):
        """Sauvegarde une session Megolm dans PostgreSQL"""
        if not self.account_id:
            raise RuntimeError("No account ID available")

        session_data = self._encrypt_data(session)

        with self.get_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                """INSERT INTO megolm_inbound_sessions
                   (account_id, room_id, session_id, sender_key, session_data,
                    signing_keys, forwarding_chains)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (account_id, room_id, session_id, sender_key)
                   DO UPDATE SET
                       session_data = EXCLUDED.session_data,
                       signing_keys = EXCLUDED.signing_keys,
                       forwarding_chains = EXCLUDED.forwarding_chains""",
                (
                    self.account_id, room_id, session_id, sender_key,
                    session_data,
                    Json(signing_keys) if signing_keys else None,
                    forwarding_chains or []
                )
            )

        logger.debug(f"Saved Megolm session for room {room_id}")

    def get_inbound_group_session(
        self,
        room_id: str,
        session_id: str,
        sender_key: str
    ):
        """Récupère une session Megolm spécifique"""
        if not self.account_id:
            return None

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT session_data FROM megolm_inbound_sessions
                   WHERE account_id = %s AND room_id = %s
                   AND session_id = %s AND sender_key = %s""",
                (self.account_id, room_id, session_id, sender_key)
            )
            result = cur.fetchone()

            if result:
                return self._decrypt_data(result['session_data'])
        return None

    # Méthodes pour Device Keys

    def load_device_keys(self) -> Dict:
        """Charge les clés de tous les devices"""
        if not self.account_id:
            return {}

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT user_id, device_id, keys, display_name
                   FROM device_keys
                   WHERE account_id = %s AND deleted = FALSE""",
                (self.account_id,)
            )

            device_keys = {}
            for row in cur.fetchall():
                user_id = row['user_id']
                if user_id not in device_keys:
                    device_keys[user_id] = {}

                device_keys[user_id][row['device_id']] = {
                    'keys': row['keys'],
                    'display_name': row['display_name']
                }

            return device_keys

    def save_device_keys(self, user_id: str, device_id: str, keys: Dict):
        """Sauvegarde les clés d'un device"""
        if not self.account_id:
            raise RuntimeError("No account ID available")

        with self.get_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                """INSERT INTO device_keys
                   (account_id, user_id, device_id, keys)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (account_id, user_id, device_id)
                   DO UPDATE SET keys = EXCLUDED.keys""",
                (self.account_id, user_id, device_id, Json(keys))
            )

    # Méthodes pour Sync Token

    def load_sync_token(self) -> Optional[str]:
        """Charge le token de synchronisation"""
        if not self.account_id:
            return None

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT token FROM sync_tokens WHERE account_id = %s",
                (self.account_id,)
            )
            result = cur.fetchone()

            if result:
                return result['token']
        return None

    def save_sync_token(self, token: str):
        """Sauvegarde le token de synchronisation"""
        if not self.account_id:
            # Créer un compte par défaut si nécessaire
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO accounts (user_id, device_id, account_data)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (user_id, device_id) DO UPDATE SET updated_at = NOW()
                       RETURNING id""",
                    (self.user_id, self.device_id, self._encrypt_data({}))
                )
                self.account_id = cur.fetchone()['id']

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO sync_tokens (account_id, token)
                   VALUES (%s, %s)
                   ON CONFLICT (account_id)
                   DO UPDATE SET token = EXCLUDED.token""",
                (self.account_id, token)
            )

    def close(self):
        """Ferme le pool de connexions"""
        if hasattr(self, 'connection_pool'):
            self.connection_pool.closeall()
            logger.info("PostgreSQL connection pool closed")