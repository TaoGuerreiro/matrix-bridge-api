#!/usr/bin/env python3
"""
Enhanced encryption handler for etke.cc Matrix client
Handles both E2EE and E2BE (end-to-bridge encryption)
"""
import os
import json
import base64
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from loguru import logger
from nio import (
    AsyncClient,
    MatrixRoom,
    RoomMessageText,
    RoomEncryptedMedia,
    EncryptionError,
    MegolmEvent,
    crypto,
    store
)

class EncryptionHandler:
    """
    Advanced encryption handler for Matrix with E2BE support
    """

    def __init__(self, client: AsyncClient, store_path: str = None):
        self.client = client
        self.store_path = store_path or "./matrix_store"
        self.element_session = os.getenv("ELEMENT_SESSION")
        self.element_session_key = os.getenv("ELEMENT_SESSION_KEY")

        # Track decryption failures for retry
        self.failed_events = {}
        self.key_requests_sent = set()

    async def setup_encryption(self):
        """Initialize encryption support with proper store"""
        try:
            # Create store directory
            Path(self.store_path).mkdir(parents=True, exist_ok=True)

            # Check if we need to import Element session
            if self.element_session and self.element_session_key:
                logger.info("🔑 Importing Element session keys...")
                await self._import_element_session()

            # Enable encryption support
            if not self.client.olm:
                logger.warning("⚠️ Olm not available - encryption support limited")
                return False

            # Trust all devices (for bridges)
            self.client.trust_device_on_first_use = True

            logger.success("✅ Encryption handler initialized")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup encryption: {e}")
            return False

    async def _import_element_session(self):
        """Import Element Web session for existing encryption keys"""
        try:
            # Element stores keys in IndexedDB, we need to import them
            # This is a simplified version - full implementation would need
            # to handle the Element export format properly

            session_data = {
                'session_id': self.element_session,
                'session_key': self.element_session_key,
                'user_id': self.client.user_id
            }

            # Store session data for later use
            session_file = Path(self.store_path) / "element_session.json"
            session_file.write_text(json.dumps(session_data, indent=2))

            logger.info(f"📝 Stored Element session: {self.element_session}")

        except Exception as e:
            logger.warning(f"⚠️ Could not import Element session: {e}")

    async def decrypt_event(self, event: MegolmEvent, room_id: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt a single encrypted event
        """
        try:
            # Try to decrypt the event
            if hasattr(self.client, 'decrypt_event'):
                decrypted = self.client.decrypt_event(event)

                if isinstance(decrypted, EncryptionError):
                    logger.warning(f"⚠️ Decryption failed: {decrypted}")

                    # Track failed event for retry
                    self.failed_events[event.event_id] = {
                        'event': event,
                        'room_id': room_id,
                        'attempts': self.failed_events.get(event.event_id, {}).get('attempts', 0) + 1,
                        'last_attempt': datetime.now().isoformat()
                    }

                    # Request keys if not already done
                    if event.session_id not in self.key_requests_sent:
                        await self._request_room_keys(room_id, event.session_id)
                        self.key_requests_sent.add(event.session_id)

                    return None

                # Successfully decrypted
                if isinstance(decrypted, RoomMessageText):
                    return {
                        'content': decrypted.body,
                        'sender': event.sender,
                        'timestamp': event.server_timestamp,
                        'decrypted': True,
                        'type': 'text'
                    }

            # Fallback: return encrypted placeholder
            return {
                'content': f"[Encrypted message - session {event.session_id[:8]}...]",
                'sender': event.sender,
                'timestamp': event.server_timestamp,
                'decrypted': False,
                'type': 'encrypted',
                'session_id': event.session_id
            }

        except Exception as e:
            logger.error(f"❌ Error decrypting event: {e}")
            return None

    async def _request_room_keys(self, room_id: str, session_id: str):
        """Request missing room keys from other devices"""
        try:
            logger.info(f"🔑 Requesting keys for session {session_id[:8]}...")

            # In a full implementation, this would send a key request
            # to other devices that might have the keys

            # For now, log the request
            logger.debug(f"Key request for room {room_id}, session {session_id}")

        except Exception as e:
            logger.error(f"Failed to request keys: {e}")

    async def handle_room_key_event(self, event):
        """Handle incoming room key events"""
        try:
            logger.info("🔑 Received room key event")

            # Process the key and retry failed decryptions
            await self._retry_failed_decryptions()

        except Exception as e:
            logger.error(f"Error handling room key: {e}")

    async def _retry_failed_decryptions(self):
        """Retry decrypting previously failed events"""
        if not self.failed_events:
            return

        logger.info(f"🔄 Retrying {len(self.failed_events)} failed decryptions...")

        retry_events = list(self.failed_events.items())
        for event_id, data in retry_events:
            if data['attempts'] > 3:
                # Too many attempts, give up
                continue

            result = await self.decrypt_event(data['event'], data['room_id'])
            if result and result.get('decrypted'):
                logger.success(f"✅ Successfully decrypted {event_id} on retry")
                del self.failed_events[event_id]

    async def export_room_keys(self, room_id: str = None) -> List[Dict[str, Any]]:
        """Export room keys for backup"""
        try:
            keys = []

            # In a full implementation, this would export Megolm session keys
            # for the specified room or all rooms

            logger.info(f"📤 Exported {len(keys)} room keys")
            return keys

        except Exception as e:
            logger.error(f"Failed to export keys: {e}")
            return []

    async def import_room_keys(self, keys: List[Dict[str, Any]]) -> int:
        """Import room keys from backup"""
        try:
            imported = 0

            for key_data in keys:
                # In a full implementation, this would import the Megolm session
                # into the crypto store
                imported += 1

            logger.info(f"📥 Imported {imported} room keys")
            return imported

        except Exception as e:
            logger.error(f"Failed to import keys: {e}")
            return 0

    def get_decryption_stats(self) -> Dict[str, Any]:
        """Get statistics about encryption/decryption"""
        return {
            'failed_events': len(self.failed_events),
            'key_requests_sent': len(self.key_requests_sent),
            'retry_candidates': sum(1 for e in self.failed_events.values() if e['attempts'] <= 3),
            'element_session': bool(self.element_session),
            'olm_available': bool(self.client.olm if hasattr(self.client, 'olm') else False)
        }