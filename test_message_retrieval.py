#!/usr/bin/env python3
"""
Test script to properly retrieve and decrypt messages from encrypted Matrix rooms
"""
import os
import asyncio
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from nio import (
    AsyncClient,
    AsyncClientConfig,
    LoginResponse,
    RoomMessageText,
    MegolmEvent,
    RoomEncryptedMedia,
    MessageDirection,
    EncryptionError
)
from loguru import logger

load_dotenv()

async def test_message_retrieval():
    """Test retrieving messages from encrypted rooms"""

    # Setup client with encryption
    homeserver = os.getenv("ETKE_HOMESERVER", "https://matrix.chalky.etke.host")
    username = os.getenv("ETKE_USERNAME", "@florent:chalky.etke.host")
    password = os.getenv("ETKE_PASSWORD")

    # Create store path for encryption keys
    store_path = Path("./test_store")
    store_path.mkdir(exist_ok=True)

    # Configure client with encryption support
    config = AsyncClientConfig(
        store_sync_tokens=True,
        encryption_enabled=True,
        pickle_key="test_encryption_key"
    )

    # Create client
    client = AsyncClient(
        homeserver=homeserver,
        user=username,
        device_id="TEST_DEVICE",
        store_path=str(store_path),
        config=config
    )

    try:
        # Login
        logger.info(f"🔐 Logging in as {username}...")
        response = await client.login(password)

        if isinstance(response, LoginResponse):
            logger.success(f"✅ Logged in successfully")

            # Do a full sync to get encryption keys
            logger.info("🔄 Performing full sync to get encryption keys...")
            sync_response = await client.sync(timeout=30000, full_state=True)
            logger.info(f"✅ Sync completed, next batch: {sync_response.next_batch[:20]}...")

            # Test room: Flo Chalky Instagram
            room_id = "!GHTWDcxXouPfkhMVqy:chalky.etke.host"
            logger.info(f"📥 Fetching messages from room {room_id}")

            # Get messages with higher limit to include older history
            messages_response = await client.room_messages(
                room_id=room_id,
                start="",  # Start from the most recent
                limit=100,  # Get more messages
                direction=MessageDirection.back  # Go backwards in time
            )

            messages = []
            encrypted_count = 0
            decrypted_count = 0
            plain_count = 0

            if hasattr(messages_response, 'chunk'):
                logger.info(f"📊 Got {len(messages_response.chunk)} events from room")

                for event in messages_response.chunk:
                    # Handle plain text messages
                    if isinstance(event, RoomMessageText):
                        plain_count += 1
                        messages.append({
                            'type': 'plain',
                            'sender': event.sender,
                            'content': event.body,
                            'timestamp': datetime.fromtimestamp(event.server_timestamp / 1000).isoformat() if event.server_timestamp else "unknown"
                        })
                        logger.info(f"📝 Plain message from {event.sender[:20]}...")

                    # Handle encrypted messages
                    elif isinstance(event, MegolmEvent):
                        encrypted_count += 1

                        # Try to decrypt
                        try:
                            decrypted = client.decrypt_event(event)

                            if isinstance(decrypted, EncryptionError):
                                logger.warning(f"⚠️ Failed to decrypt: {decrypted}")
                                messages.append({
                                    'type': 'encrypted_failed',
                                    'sender': event.sender,
                                    'content': f"[Encrypted - {decrypted}]",
                                    'timestamp': datetime.fromtimestamp(event.server_timestamp / 1000).isoformat() if event.server_timestamp else "unknown",
                                    'session_id': event.session_id
                                })
                            elif isinstance(decrypted, RoomMessageText):
                                decrypted_count += 1
                                messages.append({
                                    'type': 'decrypted',
                                    'sender': event.sender,
                                    'content': decrypted.body,
                                    'timestamp': datetime.fromtimestamp(event.server_timestamp / 1000).isoformat() if event.server_timestamp else "unknown"
                                })
                                logger.success(f"🔓 Decrypted message from {event.sender[:20]}...")
                            else:
                                logger.warning(f"❓ Unknown decrypted type: {type(decrypted)}")

                        except Exception as e:
                            logger.error(f"❌ Decryption error: {e}")
                            messages.append({
                                'type': 'encrypted_error',
                                'sender': event.sender,
                                'content': f"[Encrypted - Error: {str(e)}]",
                                'timestamp': datetime.fromtimestamp(event.server_timestamp / 1000).isoformat() if event.server_timestamp else "unknown"
                            })

            # Print summary
            logger.info(f"""
📊 Message Statistics:
- Total events: {len(messages_response.chunk) if hasattr(messages_response, 'chunk') else 0}
- Plain messages: {plain_count}
- Encrypted messages: {encrypted_count}
- Successfully decrypted: {decrypted_count}
- Failed to decrypt: {encrypted_count - decrypted_count}
""")

            # Print recent messages
            logger.info("\n📨 Recent Messages (newest first):")
            for i, msg in enumerate(messages[:20]):  # Show first 20 messages
                sender_short = msg['sender'].split(':')[0] if ':' in msg['sender'] else msg['sender']

                if msg['type'] == 'plain':
                    logger.info(f"{i+1}. [PLAIN] {sender_short}: {msg['content'][:100]}...")
                elif msg['type'] == 'decrypted':
                    logger.success(f"{i+1}. [DECRYPTED] {sender_short}: {msg['content'][:100]}...")
                elif msg['type'] == 'encrypted_failed':
                    logger.warning(f"{i+1}. [ENCRYPTED] {sender_short}: Failed to decrypt (session: {msg.get('session_id', 'unknown')[:8]}...)")
                else:
                    logger.error(f"{i+1}. [ERROR] {sender_short}: {msg['content'][:100]}...")

            # Check if we have encryption keys
            if hasattr(client, 'olm') and client.olm:
                logger.info("✅ Olm encryption is available")

                # Check if we have the account
                if hasattr(client.olm, 'account') and client.olm.account:
                    logger.info("✅ Olm account is loaded")
                else:
                    logger.warning("⚠️ No Olm account loaded")
            else:
                logger.warning("⚠️ Olm encryption not available")

        else:
            logger.error(f"❌ Login failed: {response}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()
        logger.info("🔌 Client closed")

if __name__ == "__main__":
    asyncio.run(test_message_retrieval())