"""
Client Matrix simplifié pour intégration avec etke.cc
Gère la connexion et les interactions avec les bridges Instagram/Messenger
"""
import os
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from nio import (
    AsyncClient,
    AsyncClientConfig,
    LoginResponse,
    RoomMessageText,
    MegolmEvent,
    SyncResponse,
    RoomMessagesResponse,
    MessageDirection,
    Event
)
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class EtkeMatrixClient:
    """Client Matrix optimisé pour etke.cc avec bridges Instagram/Messenger"""

    def __init__(self):
        # Configuration sera mise à jour avec vos détails etke.cc
        self.homeserver = os.getenv("ETKE_HOMESERVER", "https://matrix.chalky.etke.host")  # Sera votre domaine
        self.username = os.getenv("ETKE_USERNAME", "chalky_mood")
        self.password = os.getenv("ETKE_PASSWORD")  # À définir après réception
        self.device_id = "BEEPER_API_CLIENT"

        self.client: Optional[AsyncClient] = None
        self.user_id: Optional[str] = None
        self.access_token: Optional[str] = None

        # Rooms pour les différentes plateformes
        self.instagram_rooms: Dict[str, str] = {}  # thread_id -> room_id
        self.messenger_rooms: Dict[str, str] = {}  # thread_id -> room_id

    async def connect(self) -> bool:
        """Se connecter au serveur Matrix etke.cc avec support de chiffrement complet"""
        try:
            # Créer un dossier pour stocker les clés de chiffrement
            store_path = os.path.join(os.getcwd(), "matrix_store")
            os.makedirs(store_path, exist_ok=True)

            # Configuration pour activer l'encryption (même config que fix_encryption.py)
            config = AsyncClientConfig(
                store_sync_tokens=True,
                encryption_enabled=True,
                pickle_key="encryption_key_for_etke",  # Clé pour chiffrer le store local
                store_name="etke_store.db"
            )

            # AsyncClient avec store_path et configuration d'encryption
            self.client = AsyncClient(
                homeserver=self.homeserver,
                user=self.username,
                device_id=self.device_id,
                store_path=store_path,
                config=config
            )

            # Connexion avec username/password
            response = await self.client.login(
                password=self.password,
                device_name=self.device_id
            )

            if isinstance(response, LoginResponse):
                self.user_id = response.user_id
                self.access_token = response.access_token
                logger.info(f"✅ Connected to etke.cc as {self.user_id}")

                # Charger le store de chiffrement et les clés Olm (load_store n'est pas async)
                try:
                    self.client.load_store()
                    logger.info("🔐 Encryption store loaded successfully")

                    # Vérifier que les clés Olm sont chargées
                    if hasattr(self.client, 'olm') and self.client.olm:
                        logger.info("🔑 Olm encryption keys are available")
                    else:
                        logger.warning("⚠️ Olm encryption keys not loaded yet")

                except Exception as store_error:
                    logger.error(f"❌ Encryption store setup failed: {store_error}")

                # Démarrer la synchronisation initiale
                await self._initial_sync()
                return True
            else:
                logger.error(f"❌ Login failed: {response}")
                return False

        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False

    async def _initial_sync(self):
        """Synchronisation initiale pour découvrir les rooms bridgées"""
        try:
            # Synchronisation initiale
            await self.client.sync(timeout=30000, full_state=True)

            # Analyser les rooms après la sync
            for room_id, room in self.client.rooms.items():
                room_name = room.display_name or "Unknown"

                # Identifier les rooms Instagram (incluant conversations + bot)
                if ("instagram" in room_name.lower() or
                    "(ig)" in room_name.lower() or
                    "ig)" in room_name.lower() or
                    "instagram bridge bot" in room_name.lower()):
                    logger.info(f"📷 Found Instagram room: {room_name} ({room_id})")
                    self.instagram_rooms[room_id] = room_name

                # Identifier les rooms Messenger (incluant conversations + bot)
                elif ("messenger" in room_name.lower() or
                      "facebook" in room_name.lower() or
                      "messenger bridge bot" in room_name.lower()):
                    logger.info(f"💬 Found Messenger room: {room_name} ({room_id})")
                    self.messenger_rooms[room_id] = room_name

            logger.info(f"🔗 Total found: {len(self.instagram_rooms)} Instagram, {len(self.messenger_rooms)} Messenger")

            # Configurer le chiffrement après la sync initiale
            await self._setup_encryption()

        except Exception as e:
            logger.error(f"Initial sync failed: {e}")

    async def _setup_encryption(self):
        """Configurer le chiffrement et la confiance des appareils"""
        try:
            # Télécharger les clés d'autres appareils
            await self.client.keys_query()
            logger.info("🔑 Device keys queried")

            # Partager les clés de session pour les rooms chiffrées
            for room_id in self.client.rooms:
                room = self.client.rooms[room_id]
                if room.encrypted:
                    logger.debug(f"   Sharing keys for encrypted room: {room_id}")
                    try:
                        await self.client.share_group_session(room_id, ignore_unverified_devices=True)
                    except Exception as e:
                        logger.debug(f"   Could not share keys for {room_id}: {e}")

            logger.info("🔐 Encryption setup completed")

        except Exception as e:
            logger.warning(f"Encryption setup issue: {e}")

    async def get_instagram_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Récupérer les messages Instagram bridgés"""
        messages = []

        try:
            for room_id in self.instagram_rooms.keys():
                # Récupérer l'historique des messages
                response = await self.client.room_messages(
                    room_id=room_id,
                    start="",
                    limit=limit,
                    direction=MessageDirection.back
                )

                if isinstance(response, RoomMessagesResponse):
                    for event in response.chunk:
                        if isinstance(event, RoomMessageText):
                            messages.append({
                                "platform": "instagram",
                                "room_id": room_id,
                                "sender": event.sender,
                                "content": event.body,
                                "timestamp": event.server_timestamp,
                                "event_id": event.event_id,
                                "thread_name": self.instagram_rooms.get(room_id, "Unknown")
                            })

            logger.info(f"📷 Retrieved {len(messages)} Instagram messages")
            return messages

        except Exception as e:
            logger.error(f"Failed to get Instagram messages: {e}")
            return []

    async def get_messenger_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Récupérer les messages Messenger bridgés"""
        messages = []

        try:
            for room_id in self.messenger_rooms.keys():
                response = await self.client.room_messages(
                    room_id=room_id,
                    start="",
                    limit=limit,
                    direction=MessageDirection.back
                )

                if isinstance(response, RoomMessagesResponse):
                    for event in response.chunk:
                        if isinstance(event, RoomMessageText):
                            messages.append({
                                "platform": "messenger",
                                "room_id": room_id,
                                "sender": event.sender,
                                "content": event.body,
                                "timestamp": event.server_timestamp,
                                "event_id": event.event_id,
                                "thread_name": self.messenger_rooms.get(room_id, "Unknown")
                            })

            logger.info(f"💬 Retrieved {len(messages)} Messenger messages")
            return messages

        except Exception as e:
            logger.error(f"Failed to get Messenger messages: {e}")
            return []

    async def send_to_instagram(self, room_id: str, message: str) -> Dict[str, Any]:
        """Envoyer un message vers Instagram via le bridge"""
        try:
            if room_id not in self.instagram_rooms:
                return {
                    "success": False,
                    "error": "Room not found or not an Instagram room"
                }

            response = await self.client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": message
                }
            )

            logger.info(f"📷 Sent message to Instagram room {room_id}")
            return {
                "success": True,
                "event_id": response.event_id,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to send Instagram message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_to_messenger(self, room_id: str, message: str) -> Dict[str, Any]:
        """Envoyer un message vers Messenger via le bridge"""
        try:
            if room_id not in self.messenger_rooms:
                return {
                    "success": False,
                    "error": "Room not found or not a Messenger room"
                }

            response = await self.client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": message
                }
            )

            logger.info(f"💬 Sent message to Messenger room {room_id}")
            return {
                "success": True,
                "event_id": response.event_id,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to send Messenger message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def sync_new_messages(self, since_token: Optional[str] = None) -> Dict[str, Any]:
        """Synchroniser les nouveaux messages depuis la dernière sync"""
        try:
            sync_response = await self.client.sync(
                timeout=30000,
                since=since_token,
                full_state=False
            )

            new_messages = {
                "instagram": [],
                "messenger": [],
                "other": []
            }

            for room_id, room_data in sync_response.rooms.join.items():
                for event in room_data.timeline.events:
                    if isinstance(event, RoomMessageText):
                        message_data = {
                            "room_id": room_id,
                            "sender": event.sender,
                            "content": event.body,
                            "timestamp": event.server_timestamp,
                            "event_id": event.event_id
                        }

                        # Classifier par plateforme
                        if room_id in self.instagram_rooms:
                            message_data["platform"] = "instagram"
                            new_messages["instagram"].append(message_data)
                        elif room_id in self.messenger_rooms:
                            message_data["platform"] = "messenger"
                            new_messages["messenger"].append(message_data)
                        else:
                            new_messages["other"].append(message_data)

            total_messages = len(new_messages["instagram"]) + len(new_messages["messenger"])
            logger.info(f"📨 Synced {total_messages} new messages")

            return {
                "success": True,
                "messages": new_messages,
                "next_batch": sync_response.next_batch,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "messages": {"instagram": [], "messenger": [], "other": []}
            }

    async def get_room_list(self) -> Dict[str, List[Dict[str, str]]]:
        """Lister toutes les rooms par plateforme"""
        # Actualiser la liste si nécessaire
        if not self.instagram_rooms and not self.messenger_rooms:
            await self._refresh_room_list()

        return {
            "instagram": [
                {"room_id": rid, "name": name}
                for rid, name in self.instagram_rooms.items()
            ],
            "messenger": [
                {"room_id": rid, "name": name}
                for rid, name in self.messenger_rooms.items()
            ]
        }

    async def _refresh_room_list(self):
        """Actualiser la liste des rooms"""
        for room_id, room in self.client.rooms.items():
            room_name = room.display_name or "Unknown"

            # Identifier les rooms Instagram
            if ("instagram" in room_name.lower() or
                "(ig)" in room_name.lower() or
                "ig)" in room_name.lower() or
                "instagram bridge bot" in room_name.lower()):
                if room_id not in self.instagram_rooms:
                    logger.info(f"📷 New Instagram room: {room_name}")
                    self.instagram_rooms[room_id] = room_name

            # Identifier les rooms Messenger
            elif ("messenger" in room_name.lower() or
                  "facebook" in room_name.lower() or
                  "messenger bridge bot" in room_name.lower()):
                if room_id not in self.messenger_rooms:
                    logger.info(f"💬 New Messenger room: {room_name}")
                    self.messenger_rooms[room_id] = room_name

    async def listen_for_messages(self, callback):
        """Écouter les messages en temps réel (pour webhooks) - Non bloquant"""
        try:
            # Créer un wrapper pour gérer les deux types de messages
            async def message_wrapper(room, event):
                try:
                    if isinstance(event, RoomMessageText):
                        # Message non chiffré - traitement direct
                        logger.info(f"🔍 Plain message callback triggered - Room: {room.room_id}, Sender: {event.sender}, Message: {event.body[:50]}...")
                        await callback(room, event)
                    elif isinstance(event, MegolmEvent):
                        # Message chiffré Instagram - traitement spécial
                        logger.info(f"🔐 Encrypted message callback triggered - Room: {room.room_id}, Sender: {event.sender}")

                        # Vérifier si c'est un message Instagram/Messenger
                        if ("instagram" in event.sender.lower() or
                            room.room_id in self.instagram_rooms or
                            room.room_id in self.messenger_rooms):

                            # Tenter de décrypter le message
                            try:
                                logger.info(f"🔓 Attempting to decrypt MegolmEvent...")

                                # Charger le store avant de décrypter
                                if hasattr(self.client, 'load_store'):
                                    self.client.load_store()

                                # Vérifier si le client a les capacités de déchiffrement
                                if hasattr(self.client, 'decrypt_event'):
                                    # Essayer de décrypter l'événement
                                    decrypted_event = await self.client.decrypt_event(event)

                                    if decrypted_event:
                                        logger.info(f"✅ Message decrypted successfully")

                                        # Créer un événement avec le contenu décrypté
                                        class DecryptedEvent:
                                            def __init__(self, original_event, decrypted):
                                                self.sender = original_event.sender
                                                if isinstance(decrypted, dict):
                                                    self.body = decrypted.get('content', {}).get('body', '[Message sans contenu]')
                                                elif hasattr(decrypted, 'body'):
                                                    self.body = decrypted.body
                                                else:
                                                    self.body = str(decrypted)
                                                self.server_timestamp = original_event.server_timestamp
                                                self.event_id = original_event.event_id

                                        decrypted_msg = DecryptedEvent(event, decrypted_event)
                                        logger.info(f"📝 Decrypted message: {decrypted_msg.body[:50]}...")
                                        await callback(room, decrypted_msg)
                                        return
                                    else:
                                        logger.warning("⚠️ Decryption returned None")
                                else:
                                    logger.error("❌ Client doesn't have decrypt_event method")

                            except Exception as decrypt_error:
                                logger.warning(f"🔒 Decryption failed: {decrypt_error}")

                                # Tentative alternative : récupération depuis l'historique
                                try:
                                    logger.info(f"🔍 Trying to retrieve from room history...")

                                    # Faire une sync forcée pour récupérer les derniers messages
                                    sync_response = await self.client.sync(timeout=5000, full_state=False)

                                    # Chercher dans les événements de la room
                                    if hasattr(sync_response, 'rooms') and hasattr(sync_response.rooms, 'join'):
                                        room_data = sync_response.rooms.join.get(room.room_id)
                                        if room_data and hasattr(room_data, 'timeline'):
                                            for timeline_event in room_data.timeline.events:
                                                # Chercher un message texte correspondant
                                                if (hasattr(timeline_event, 'event_id') and
                                                    timeline_event.event_id == event.event_id and
                                                    hasattr(timeline_event, 'body')):
                                                    logger.info(f"✅ Found corresponding message in timeline")
                                                    await callback(room, timeline_event)
                                                    return

                                except Exception as sync_error:
                                    logger.warning(f"Sync retrieval failed: {sync_error}")

                            # Fallback si aucune méthode ne fonctionne
                            logger.warning(f"Unable to decrypt or retrieve message {event.event_id}")
                            class FallbackEvent:
                                def __init__(self):
                                    self.sender = event.sender
                                    self.body = "[Nouveau message Instagram reçu]"
                                    self.server_timestamp = event.server_timestamp
                                    self.event_id = event.event_id

                            await callback(room, FallbackEvent())
                        else:
                            logger.debug(f"🔐 Encrypted message from {event.sender} not from Instagram/Messenger, ignoring")
                except Exception as e:
                    logger.error(f"Error in message wrapper: {e}")

            # Définir les callbacks pour les deux types de messages
            self.client.add_event_callback(message_wrapper, RoomMessageText)
            self.client.add_event_callback(message_wrapper, MegolmEvent)
            logger.info("⚡ Message listener started (non-blocking) - Supporting both plain and encrypted messages")

            # Démarrer une tâche de synchronisation en arrière-plan
            self._sync_task = asyncio.create_task(self._background_sync())
            logger.info("🔄 Background sync task created")

        except Exception as e:
            logger.error(f"Message listener error: {e}")

    async def _background_sync(self):
        """Synchronisation en arrière-plan pour écouter les messages"""
        logger.info("🔄 Starting background sync for real-time messages")

        # Assurer qu'on a le token de sync initial
        if not hasattr(self.client, 'next_batch') or not self.client.next_batch:
            logger.info("🔄 Getting initial sync token...")
            try:
                initial_response = await self.client.sync(timeout=10000, full_state=False)
                logger.info(f"📥 Initial sync completed, next_batch: {initial_response.next_batch[:20]}...")
            except Exception as e:
                logger.error(f"Initial sync for background failed: {e}")
                return

        while True:
            try:
                # Synchronisation continue pour capturer les nouveaux messages
                response = await self.client.sync(timeout=30000, full_state=False)

                if response and hasattr(response, 'rooms') and response.rooms:
                    # Log le nombre d'événements reçus avec plus de détails
                    total_events = 0
                    for room_id, room_data in response.rooms.join.items():
                        if hasattr(room_data, 'timeline') and room_data.timeline.events:
                            event_count = len(room_data.timeline.events)
                            if event_count > 0:
                                total_events += event_count
                                logger.info(f"📨 Room {room_id}: {event_count} new events")

                                # Log détaillé de chaque événement
                                for event in room_data.timeline.events:
                                    event_type = type(event).__name__
                                    sender = getattr(event, 'sender', 'unknown')
                                    logger.info(f"   📨 Event: {event_type} from {sender}")

                                    # Si c'est un message texte, log le contenu
                                    if hasattr(event, 'body'):
                                        logger.info(f"   💬 Message: {event.body[:100]}...")

                    if total_events > 0:
                        logger.info(f"📨 Background sync: {total_events} new events processed")
                    else:
                        logger.debug("📭 No new events in this sync")

                await asyncio.sleep(2)  # Petite pause entre les syncs

            except Exception as e:
                logger.error(f"Background sync error: {e}")
                await asyncio.sleep(10)  # Plus long délai en cas d'erreur

    async def stop_listening(self):
        """Arrêter l'écoute des messages"""
        if hasattr(self, '_sync_task') and self._sync_task:
            self._sync_task.cancel()
            logger.info("🛑 Background sync task cancelled")

    async def disconnect(self):
        """Déconnexion propre"""
        # Arrêter la synchronisation en arrière-plan
        await self.stop_listening()

        if self.client:
            await self.client.close()
            logger.info("🔌 Disconnected from etke.cc")


# Exemple d'utilisation
async def main():
    client = EtkeMatrixClient()

    # Se connecter
    if await client.connect():
        # Récupérer les messages
        instagram_msgs = await client.get_instagram_messages()
        messenger_msgs = await client.get_messenger_messages()

        print(f"Instagram: {len(instagram_msgs)} messages")
        print(f"Messenger: {len(messenger_msgs)} messages")

        # Lister les rooms
        rooms = await client.get_room_list()
        print(f"Rooms: {rooms}")

        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())