#!/usr/bin/env python3
"""
Client Matrix Production avec PostgreSQL
Utilise PostgreSQL pour la persistance des clés de chiffrement
"""
import os
import asyncio
from typing import Optional, Dict, List, Any
from pathlib import Path

from nio import (
    AsyncClient,
    AsyncClientConfig,
    LoginResponse,
    RoomMessageText,
    MegolmEvent,
    MessageDirection
)
from loguru import logger
from dotenv import load_dotenv

try:
    from .postgres_matrix_store import PostgresMatrixStore
except ImportError:
    # Fallback for Clever Cloud deployment
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from postgres_matrix_store import PostgresMatrixStore

load_dotenv()


class ProductionMatrixClient:
    """Client Matrix production-ready avec persistance PostgreSQL"""

    def __init__(
        self,
        use_postgres: bool = True,
        pg_config: Dict[str, Any] = None
    ):
        """
        Initialise le client Matrix avec support PostgreSQL ou SQLite

        Args:
            use_postgres: Utiliser PostgreSQL (True) ou SQLite (False)
            pg_config: Configuration PostgreSQL
        """
        # Configuration Matrix
        self.homeserver = os.getenv("ETKE_HOMESERVER", "https://matrix.chalky.etke.host")
        self.username = os.getenv("ETKE_USERNAME", "@florent:chalky.etke.host")
        self.password = os.getenv("ETKE_PASSWORD")
        self.device_id = "BEEPER_API_CLIENT"

        # Configuration du store
        self.use_postgres = use_postgres and os.getenv("USE_POSTGRES_STORE", "false").lower() == "true"

        # Configuration PostgreSQL par défaut (Clever Cloud variables)
        self.pg_config = pg_config or {
            'database': os.getenv('POSTGRESQL_ADDON_DB', os.getenv('POSTGRES_DB', 'matrix_store')),
            'host': os.getenv('POSTGRESQL_ADDON_HOST', os.getenv('POSTGRES_HOST', 'localhost')),
            'port': int(os.getenv('POSTGRESQL_ADDON_PORT', os.getenv('POSTGRES_PORT', 5432))),
            'user': os.getenv('POSTGRESQL_ADDON_USER', os.getenv('POSTGRES_USER', 'matrix_user')),
            'password': os.getenv('POSTGRESQL_ADDON_PASSWORD', os.getenv('POSTGRES_PASSWORD')),
            'pool_size': int(os.getenv('POSTGRES_POOL_SIZE', 20))
        }

        self.client: Optional[AsyncClient] = None
        self.store = None
        self.user_id: Optional[str] = None
        self.access_token: Optional[str] = None

        # Rooms tracking
        self.instagram_rooms: Dict[str, str] = {}
        self.messenger_rooms: Dict[str, str] = {}
        self.message_callbacks = []
        self.sync_task = None
        self.webhook_url: Optional[str] = None

        logger.info(f"ProductionMatrixClient initialized (PostgreSQL: {self.use_postgres})")

    async def connect(self) -> bool:
        """Se connecter au serveur Matrix avec le bon store"""
        try:
            if self.use_postgres:
                logger.info("🐘 Using PostgreSQL store for production")
                await self._connect_with_postgres()
            else:
                logger.info("📁 Using SQLite store for development")
                await self._connect_with_sqlite()

            # Login
            response = await self.client.login(
                password=self.password,
                device_name=self.device_id
            )

            if isinstance(response, LoginResponse):
                self.user_id = response.user_id
                self.access_token = response.access_token
                logger.info(f"✅ Connected to etke.cc as {self.user_id}")

                # Load encryption store if available
                try:
                    await self._load_encryption_store()
                except Exception as e:
                    logger.warning(f"Could not load encryption store: {e}")

                # Synchronisation initiale
                await self._initial_sync()

                # Configuration du chiffrement
                try:
                    await self._setup_encryption()
                except Exception as e:
                    logger.warning(f"Could not setup encryption: {e}")

                return True
            else:
                logger.error(f"❌ Login failed: {response}")
                return False

        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False

    async def _connect_with_postgres(self):
        """Connexion avec SQLite temporaire + sauvegarde PostgreSQL"""
        # Créer le store PostgreSQL pour sauvegarder les données
        self.store = PostgresMatrixStore(
            user_id=self.username,
            device_id=self.device_id,
            pickle_key="encryption_key_for_etke",
            **self.pg_config
        )

        # Utiliser un dossier temporaire pour SQLite (matrix-nio a besoin d'un store path)
        store_path = Path("/tmp/matrix_store_temp")
        store_path.mkdir(exist_ok=True)

        # Configuration du client avec chiffrement
        config = AsyncClientConfig(
            store_sync_tokens=True,
            encryption_enabled=True,
            pickle_key="encryption_key_for_etke",
            store_name="temp_store.db"
        )

        # Créer le client avec SQLite temporaire
        self.client = AsyncClient(
            homeserver=self.homeserver,
            user=self.username,
            device_id=self.device_id,
            store_path=str(store_path),
            config=config
        )

        logger.info("PostgreSQL store configured with temp SQLite for nio compatibility")

    async def _connect_with_sqlite(self):
        """Connexion avec store SQLite (fallback)"""
        # Utiliser un répertoire approprié selon l'environnement
        # Sur Clever Cloud, /tmp est disponible
        # En local, utiliser un dossier local
        default_path = "/tmp/matrix_store" if os.path.exists("/tmp") else "./matrix_store"
        store_path = Path(os.environ.get("MATRIX_STORE_PATH", default_path))
        store_path.mkdir(parents=True, exist_ok=True)

        config = AsyncClientConfig(
            store_sync_tokens=True,
            encryption_enabled=True,
            pickle_key="encryption_key_for_etke",
            store_name="etke_store.db"
        )

        self.client = AsyncClient(
            homeserver=self.homeserver,
            user=self.username,
            device_id=self.device_id,
            store_path=str(store_path),
            config=config
        )

        logger.info("SQLite store configured successfully")

    async def _load_encryption_store(self):
        """Charge le store de chiffrement (PostgreSQL ou SQLite)"""
        try:
            if self.use_postgres:
                # Charger depuis PostgreSQL
                account = self.store.load_account()
                if account:
                    logger.info("🔐 Loaded Olm account from PostgreSQL")
                    # Restaurer l'account dans le client nio
                    if hasattr(self.client, 'olm') and self.client.olm:
                        self.client.olm.account = account

                # Charger les sessions Megolm
                sessions = self.store.load_inbound_group_sessions()
                logger.info(f"🔑 Loaded {len(sessions)} Megolm sessions from PostgreSQL")

                # Charger les device keys
                device_keys = self.store.load_device_keys()
                logger.info(f"📱 Loaded device keys for {len(device_keys)} users")

            else:
                # SQLite - utiliser la méthode nio standard
                self.client.load_store()
                logger.info("🔐 Encryption store loaded from SQLite")

            # Vérifier que les clés Olm sont chargées
            if hasattr(self.client, 'olm') and self.client.olm:
                logger.info("🔑 Olm encryption keys are available")
            else:
                logger.warning("⚠️ Olm encryption keys not loaded yet")

        except Exception as e:
            logger.error(f"❌ Failed to load encryption store: {e}")

    async def _initial_sync(self):
        """Synchronisation initiale pour récupérer l'état"""
        logger.info("🔄 Initial sync...")

        sync_response = await self.client.sync(timeout=30000, full_state=True)

        # Sauvegarder le token de sync
        if self.use_postgres and sync_response.next_batch:
            self.store.save_sync_token(sync_response.next_batch)

        # Parser les rooms Instagram/Messenger initiales
        # Les rooms etke.cc ont des membres comme @instagram_XXX ou @whatsapp_XXX
        for room_id, room in self.client.rooms.items():
            room_name = room.display_name or room_id

            # Chercher dans les membres de la room pour identifier le type
            room_members = list(room.users.keys()) if hasattr(room, 'users') else []
            room_info = f"{room_name} (members: {', '.join(room_members[:3])}...)" if room_members else room_name

            # Détecter Instagram par les membres ou le nom
            if any("instagram" in member.lower() for member in room_members) or "instagram" in room_name.lower():
                self.instagram_rooms[room_id] = room_name
                logger.info(f"📷 Found Instagram room: {room_info}")

            # Détecter Messenger/Facebook par les membres ou le nom
            elif any("messenger" in member.lower() or "facebook" in member.lower() for member in room_members) or "messenger" in room_name.lower() or "facebook" in room_name.lower():
                self.messenger_rooms[room_id] = room_name
                logger.info(f"💬 Found Messenger room: {room_info}")

            # Pour WhatsApp (au cas où)
            elif any("whatsapp" in member.lower() for member in room_members) or "whatsapp" in room_name.lower():
                # On pourrait créer une catégorie WhatsApp ou l'ignorer
                logger.info(f"📱 Found WhatsApp room (ignored): {room_info}")

        logger.info(f"🔗 Total found: {len(self.instagram_rooms)} Instagram, {len(self.messenger_rooms)} Messenger")

    async def _setup_encryption(self):
        """Configure le chiffrement et partage les clés"""
        logger.info("🔐 Setting up encryption...")

        # Télécharger les clés des autres devices
        await self.client.keys_query()

        # Partager les clés pour toutes les rooms chiffrées
        shared_count = 0
        for room_id in self.client.rooms:
            room = self.client.rooms[room_id]
            if room.encrypted:
                try:
                    await self.client.share_group_session(
                        room_id,
                        ignore_unverified_devices=True
                    )
                    shared_count += 1
                except Exception as e:
                    logger.warning(f"Could not share keys for {room_id}: {e}")

        logger.info(f"📊 Shared keys for {shared_count} encrypted rooms")

        # Marquer les devices des bridges comme trustés
        await self._trust_bridge_devices()

    async def _trust_bridge_devices(self):
        """Fait automatiquement confiance aux devices des bridges"""
        bridge_users = set()

        # Identifier les utilisateurs bridges
        for room_id in list(self.instagram_rooms.keys()) + list(self.messenger_rooms.keys()):
            room = self.client.rooms.get(room_id)
            if room:
                for user_id in room.users:
                    if any(bridge in user_id for bridge in ["instagram", "messenger", "instagrambot", "messengerbot"]):
                        bridge_users.add(user_id)

        logger.info(f"🌉 Found {len(bridge_users)} bridge users to trust")

        # Faire confiance à leurs devices
        for user_id in bridge_users:
            try:
                devices = self.client.device_store.active_user_devices(user_id)
                for device in devices.values():
                    if not device.verified:
                        self.client.verify_device(device)
                        logger.debug(f"✅ Trusted device {device.id} for {user_id}")

                        # Sauvegarder en PostgreSQL si activé
                        if self.use_postgres:
                            self.store.save_device_keys(
                                user_id,
                                device.id,
                                {'verified': True, 'keys': device.keys}
                            )
            except Exception as e:
                logger.debug(f"Could not verify devices for {user_id}: {e}")

    async def decrypt_event(self, event: MegolmEvent) -> Optional[Dict]:
        """
        Déchiffre un événement Megolm

        Args:
            event: L'événement chiffré

        Returns:
            Le contenu déchiffré ou None
        """
        try:
            if self.use_postgres:
                # Chercher la session dans PostgreSQL
                session = self.store.get_inbound_group_session(
                    event.room_id,
                    event.session_id,
                    event.sender_key
                )

                if session:
                    # Utiliser la session pour déchiffrer
                    decrypted = await self.client.decrypt_event(event)
                    return decrypted

            else:
                # Utiliser la méthode standard nio
                decrypted = await self.client.decrypt_event(event)
                return decrypted

        except Exception as e:
            logger.error(f"Failed to decrypt event: {e}")
            return None

    async def send_message(
        self,
        room_id: str,
        message: str,
        msgtype: str = "m.text"
    ) -> bool:
        """
        Envoie un message chiffré dans une room

        Args:
            room_id: ID de la room
            message: Message à envoyer
            msgtype: Type de message

        Returns:
            True si envoyé avec succès
        """
        try:
            room = self.client.rooms.get(room_id)
            if not room:
                logger.error(f"Room {room_id} not found")
                return False

            # Créer le contenu du message
            content = {
                "msgtype": msgtype,
                "body": message
            }

            # Envoyer (sera automatiquement chiffré si la room est chiffrée)
            response = await self.client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content
            )

            if response.event_id:
                logger.info(f"✅ Message sent to {room_id}: {response.event_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")

        return False

    async def listen_for_messages(self, callback=None):
        """
        Écoute les messages en temps réel avec déchiffrement automatique

        Args:
            callback: Fonction appelée pour chaque message
        """
        if callback:
            self.message_callbacks.append(callback)

        # Callback pour détecter de nouvelles rooms lors des syncs
        @self.client.event
        async def on_sync(response):
            """Callback appelé après chaque sync pour détecter les nouvelles rooms"""
            try:
                # Vérifier si de nouvelles rooms ont été ajoutées
                current_room_ids = set(self.client.rooms.keys())
                tracked_room_ids = set(self.instagram_rooms.keys()) | set(self.messenger_rooms.keys())

                new_rooms = current_room_ids - tracked_room_ids

                if new_rooms:
                    logger.info(f"🔍 Found {len(new_rooms)} new rooms during sync")

                    for room_id in new_rooms:
                        room = self.client.rooms.get(room_id)
                        if room:
                            room_name = room.display_name or ""

                            if "instagram" in room_name.lower() or "(ig)" in room_name.lower():
                                self.instagram_rooms[room_id] = room_name
                                logger.info(f"📷 New Instagram room: {room_name}")

                            elif "messenger" in room_name.lower() or "facebook" in room_name.lower():
                                self.messenger_rooms[room_id] = room_name
                                logger.info(f"💬 New Messenger room: {room_name}")

                    logger.info(f"🔗 Updated totals: {len(self.instagram_rooms)} Instagram, {len(self.messenger_rooms)} Messenger")

            except Exception as e:
                logger.error(f"Error in sync callback: {e}")

        # Callbacks pour les messages
        @self.client.event
        async def on_room_message(room, event):
            # Message texte normal
            if isinstance(event, RoomMessageText):
                logger.info(f"📨 Plain message from {event.sender}: {event.body}")
                for cb in self.message_callbacks:
                    await cb(room, event)

            # Message chiffré
            elif isinstance(event, MegolmEvent):
                logger.info(f"🔐 Encrypted message from {event.sender}")

                # Déchiffrer
                decrypted = await self.decrypt_event(event)
                if decrypted:
                    # Créer un pseudo-event avec le contenu déchiffré
                    event.body = decrypted.get('content', {}).get('body', '[Decrypted but no body]')
                    logger.info(f"✅ Decrypted: {event.body}")

                    for cb in self.message_callbacks:
                        await cb(room, event)
                else:
                    logger.warning(f"⚠️ Could not decrypt message from {event.sender}")

        # Démarrer la synchronisation
        self.sync_task = asyncio.create_task(
            self.client.sync_forever(timeout=30000, full_state=False)
        )

        logger.info("⚡ Message listener started with decryption support and room detection")

    async def close(self):
        """Ferme proprement le client et les connexions"""
        logger.info("🔌 Closing Matrix client...")

        # Arrêter la synchronisation
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass

        # Sauvegarder l'état final en PostgreSQL
        if self.use_postgres and self.store:
            if hasattr(self.client, 'olm') and self.client.olm:
                self.store.save_account(self.client.olm.account)
                logger.info("💾 Saved final Olm account state to PostgreSQL")

            # Fermer le pool de connexions
            self.store.close()

        # Fermer le client
        await self.client.close()
        logger.info("✅ Matrix client closed successfully")

    # Méthodes utilitaires pour les tests

    async def test_persistence(self) -> bool:
        """
        Teste que les clés sont bien persistées et récupérables

        Returns:
            True si la persistance fonctionne
        """
        if not self.use_postgres:
            logger.warning("Persistence test only works with PostgreSQL")
            return False

        try:
            # Sauvegarder l'état actuel
            if hasattr(self.client, 'olm') and self.client.olm:
                self.store.save_account(self.client.olm.account)

            # Simuler un redémarrage en rechargeant
            account = self.store.load_account()
            sessions = self.store.load_inbound_group_sessions()

            # Vérifier que les données sont présentes
            if account and len(sessions) > 0:
                logger.info(f"✅ Persistence test passed: {len(sessions)} sessions recovered")
                return True
            else:
                logger.error("❌ Persistence test failed: No data recovered")
                return False

        except Exception as e:
            logger.error(f"❌ Persistence test error: {e}")
            return False

    async def get_room_messages(
        self,
        room_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Récupère les derniers messages d'une room avec déchiffrement

        Args:
            room_id: ID de la room
            limit: Nombre de messages

        Returns:
            Liste des messages déchiffrés
        """
        messages = []

        try:
            response = await self.client.room_messages(
                room_id=room_id,
                start="",
                limit=limit,
                direction=MessageDirection.back
            )

            if hasattr(response, 'chunk'):
                for event in response.chunk:
                    if isinstance(event, RoomMessageText):
                        messages.append({
                            'sender': event.sender,
                            'body': event.body,
                            'timestamp': event.server_timestamp
                        })

                    elif isinstance(event, MegolmEvent):
                        decrypted = await self.decrypt_event(event)
                        if decrypted:
                            body = decrypted.get('content', {}).get('body', '[No body]')
                            messages.append({
                                'sender': event.sender,
                                'body': body,
                                'timestamp': event.server_timestamp,
                                'decrypted': True
                            })

        except Exception as e:
            logger.error(f"Failed to get room messages: {e}")

        return messages

    # Additional methods required by the API

    async def start(self):
        """Start the Matrix client and connect"""
        return await self.connect()

    async def stop(self):
        """Stop the Matrix client"""
        await self.close()

    async def setup_webhook(self, webhook_url: str):
        """Setup webhook URL for external notifications"""
        self.webhook_url = webhook_url
        logger.info(f"Webhook configured: {webhook_url}")

    async def get_platform_messages(self, platform: str, limit: int = 50) -> List[Dict]:
        """Get messages from a specific platform (Instagram/Messenger)"""
        messages = []

        if platform == "instagram":
            rooms = self.instagram_rooms
        elif platform == "messenger":
            rooms = self.messenger_rooms
        else:
            return messages

        for room_id in rooms.keys():
            try:
                room_messages = await self.get_room_messages(room_id, limit // len(rooms) if rooms else limit)
                for msg in room_messages:
                    msg['platform'] = platform
                    msg['room_id'] = room_id
                messages.extend(room_messages)
            except Exception as e:
                logger.error(f"Failed to get messages from {room_id}: {e}")

        # Sort by timestamp and limit
        messages.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        return messages[:limit]

    async def get_rooms_list(self) -> Dict[str, Any]:
        """Get list of all rooms with metadata"""
        # Si aucune room trackée, force une synchronisation pour détecter les rooms
        if not self.instagram_rooms and not self.messenger_rooms and self.client:
            logger.info("🔄 No rooms tracked, forcing sync to detect rooms...")
            try:
                await self.client.sync(timeout=10000, full_state=True)

                # Re-parse les rooms après sync
                for room_id, room in self.client.rooms.items():
                    room_name = room.display_name or ""

                    if "instagram" in room_name.lower() or "(ig)" in room_name.lower():
                        self.instagram_rooms[room_id] = room_name
                        logger.info(f"📷 Detected Instagram room: {room_name}")

                    elif "messenger" in room_name.lower() or "facebook" in room_name.lower():
                        self.messenger_rooms[room_id] = room_name
                        logger.info(f"💬 Detected Messenger room: {room_name}")

                logger.info(f"🔗 After sync: {len(self.instagram_rooms)} Instagram, {len(self.messenger_rooms)} Messenger")
            except Exception as e:
                logger.error(f"Failed to sync for room detection: {e}")

        rooms = []

        for room_id, room_name in self.instagram_rooms.items():
            room_obj = self.client.rooms.get(room_id) if self.client else None
            rooms.append({
                'room_id': room_id,
                'name': room_name,
                'platform': 'instagram',
                'encrypted': room_obj.encrypted if room_obj else False
            })

        for room_id, room_name in self.messenger_rooms.items():
            room_obj = self.client.rooms.get(room_id) if self.client else None
            rooms.append({
                'room_id': room_id,
                'name': room_name,
                'platform': 'messenger',
                'encrypted': room_obj.encrypted if room_obj else False
            })

        return {
            'total': len(rooms),
            'rooms': rooms
        }

    async def sync_once(self):
        """Perform a single sync operation"""
        if self.client:
            logger.info("🔄 Performing single sync...")
            try:
                sync_response = await self.client.sync(timeout=10000)
                logger.info(f"✅ Sync completed. Next batch: {sync_response.next_batch if hasattr(sync_response, 'next_batch') else 'N/A'}")

                # Update room tracking after sync
                current_rooms = len(self.client.rooms)
                tracked_rooms = len(self.instagram_rooms) + len(self.messenger_rooms)
                logger.info(f"📊 Rooms: {current_rooms} total, {tracked_rooms} tracked")

                return sync_response
            except Exception as e:
                logger.error(f"❌ Sync failed: {e}")
                raise

    async def get_encryption_status(self) -> Dict:
        """Get encryption status information"""
        if not self.client:
            return {'status': 'disconnected'}

        olm_available = hasattr(self.client, 'olm') and self.client.olm

        return {
            'status': 'connected' if self.client.logged_in else 'disconnected',
            'olm_available': olm_available,
            'device_id': self.device_id,
            'user_id': self.user_id,
            'postgres_store': self.use_postgres,
            'rooms_encrypted': sum(1 for room in self.client.rooms.values() if room.encrypted) if self.client else 0
        }

    async def fix_encryption(self):
        """Fix encryption issues in background"""
        logger.info("Starting encryption fix...")
        try:
            if self.client:
                # Re-setup encryption
                await self.client.keys_query()
                await self._setup_encryption()
                logger.info("Encryption fix completed")
        except Exception as e:
            logger.error(f"Encryption fix failed: {e}")

    async def get_room_messages(self, room_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Récupérer les messages d'une room spécifique"""
        if not self.client:
            logger.error("Client not initialized")
            return []

        messages = []
        try:
            # Récupérer l'historique des messages
            from nio import RoomMessagesResponse, RoomMessageText, MegolmEvent

            response = await self.client.room_messages(
                room_id,
                start="",
                limit=limit
            )

            if isinstance(response, RoomMessagesResponse) and response.chunk:
                for event in response.chunk:
                    message_data = None

                    # Messages texte non chiffrés
                    if isinstance(event, RoomMessageText):
                        message_data = {
                            'id': event.event_id,
                            'sender': event.sender,
                            'content': event.body,
                            'timestamp': datetime.fromtimestamp(event.server_timestamp / 1000).isoformat() if event.server_timestamp else "",
                            'room_id': room_id,
                            'type': 'text',
                            'decrypted': False
                        }

                    # Messages chiffrés
                    elif isinstance(event, MegolmEvent):
                        # Essayer de déchiffrer
                        try:
                            decrypted = await self.decrypt_event(event)
                            if decrypted and hasattr(decrypted, 'body'):
                                message_data = {
                                    'id': event.event_id,
                                    'sender': event.sender,
                                    'content': decrypted.body,
                                    'timestamp': datetime.fromtimestamp(event.server_timestamp / 1000).isoformat() if event.server_timestamp else "",
                                    'room_id': room_id,
                                    'type': 'text',
                                    'decrypted': True
                                }
                        except Exception as decrypt_error:
                            logger.debug(f"Could not decrypt message: {decrypt_error}")
                            # Ajouter quand même le message non déchiffré
                            message_data = {
                                'id': event.event_id,
                                'sender': event.sender,
                                'content': "[Message chiffré]",
                                'timestamp': datetime.fromtimestamp(event.server_timestamp / 1000).isoformat() if event.server_timestamp else "",
                                'room_id': room_id,
                                'type': 'encrypted',
                                'decrypted': False
                            }

                    # Ajouter le message s'il a été traité
                    if message_data:
                        messages.append(message_data)

                logger.info(f"📊 Retrieved {len(messages)} messages from room {room_id}")
            else:
                logger.warning(f"No messages found in room {room_id} (response type: {type(response)})")

        except Exception as e:
            logger.error(f"Error getting room messages: {e}")
            import traceback
            traceback.print_exc()

        return messages

