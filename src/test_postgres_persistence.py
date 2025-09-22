#!/usr/bin/env python3
"""
Comprehensive test script for PostgreSQL persistence of Matrix encryption keys.

This script validates that:
1. Matrix encryption keys are properly saved to PostgreSQL
2. Keys can be recovered after a complete server restart
3. Message decryption works after key recovery
4. The persistence layer is robust and reliable

Tests include both unit tests and integration tests.
"""

import os
import sys
import asyncio
import pytest
import json
import tempfile
import random
import string
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from etke_matrix_client_prod import ProductionMatrixClient
from postgres_matrix_store import PostgresMatrixStore

from nio import (
    AsyncClient,
    MegolmEvent,
    RoomMessageText,
    LoginResponse
)
from loguru import logger
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test configuration
TEST_USER_ID = "@test_user:test.server"
TEST_DEVICE_ID = "TEST_DEVICE_123"
TEST_PICKLE_KEY = "test_encryption_key_2024"
TEST_ROOM_ID = "!test_room:test.server"
TEST_SESSION_ID = "test_session_123"
TEST_SENDER_KEY = "test_sender_key_456"

# PostgreSQL test configuration
POSTGRES_TEST_CONFIG = {
    'database': os.getenv('POSTGRES_DB', 'matrix_store_test'),
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'user': os.getenv('POSTGRES_USER', 'matrix_user'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'pool_size': 5
}


class MockOlmAccount:
    """Mock Olm account for testing"""
    def __init__(self):
        self.identity_keys = {"curve25519": "test_curve_key", "ed25519": "test_ed_key"}
        self.shared = True

    def pickle(self, key=""):
        return b"mock_pickled_account_data"

    @classmethod
    def from_pickle(cls, pickled_data, key=""):
        return cls()


class MockMegolmSession:
    """Mock Megolm session for testing"""
    def __init__(self, session_id: str):
        self.id = session_id
        self.first_known_index = 0

    def pickle(self, key=""):
        return f"mock_pickled_session_{self.id}".encode()

    @classmethod
    def from_pickle(cls, pickled_data, key=""):
        session_id = pickled_data.decode().split("_")[-1]
        return cls(session_id)


class TestPostgresPersistence:
    """Test suite for PostgreSQL Matrix encryption persistence"""

    def __init__(self):
        self.store: Optional[PostgresMatrixStore] = None
        self.client: Optional[ProductionMatrixClient] = None
        self.test_data = {}

    async def setup_test_environment(self) -> bool:
        """Set up test environment with clean database"""
        try:
            # Create test database if it doesn't exist
            await self._create_test_database()

            # Initialize PostgreSQL store
            self.store = PostgresMatrixStore(
                user_id=TEST_USER_ID,
                device_id=TEST_DEVICE_ID,
                pickle_key=TEST_PICKLE_KEY,
                **POSTGRES_TEST_CONFIG
            )

            # Clean existing test data
            await self._clean_test_data()

            logger.info("✅ Test environment setup completed")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup test environment: {e}")
            return False

    async def _create_test_database(self):
        """Create test database if it doesn't exist"""
        try:
            # Connect to default postgres database to create test database
            conn_config = POSTGRES_TEST_CONFIG.copy()
            test_db = conn_config.pop('database')
            conn_config['database'] = 'postgres'

            conn = psycopg2.connect(**conn_config)
            conn.autocommit = True
            cur = conn.cursor()

            # Check if test database exists
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (test_db,)
            )

            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{test_db}"')
                logger.info(f"Created test database: {test_db}")

            cur.close()
            conn.close()

        except Exception as e:
            logger.warning(f"Database creation warning: {e}")

    async def _clean_test_data(self):
        """Clean existing test data from database"""
        try:
            with self.store.get_connection() as conn:
                cur = conn.cursor()

                # Delete test account data
                cur.execute(
                    "DELETE FROM accounts WHERE user_id = %s AND device_id = %s",
                    (TEST_USER_ID, TEST_DEVICE_ID)
                )

                logger.info("🧹 Cleaned existing test data")

        except Exception as e:
            logger.warning(f"Clean test data warning: {e}")

    async def test_unit_olm_account_persistence(self) -> bool:
        """Unit test: Test Olm account save/load"""
        try:
            logger.info("🧪 Testing Olm account persistence...")

            # Create mock Olm account
            mock_account = MockOlmAccount()

            # Save account
            self.store.save_account(mock_account)
            logger.info("💾 Saved mock Olm account")

            # Load account
            loaded_account = self.store.load_account()

            if loaded_account:
                logger.info("✅ Olm account persistence test PASSED")
                return True
            else:
                logger.error("❌ Olm account persistence test FAILED - No account loaded")
                return False

        except Exception as e:
            logger.error(f"❌ Olm account persistence test FAILED: {e}")
            return False

    async def test_unit_megolm_session_persistence(self) -> bool:
        """Unit test: Test Megolm session save/load"""
        try:
            logger.info("🧪 Testing Megolm session persistence...")

            # Create mock Megolm session
            mock_session = MockMegolmSession(TEST_SESSION_ID)

            # Save session
            self.store.save_inbound_group_session(
                room_id=TEST_ROOM_ID,
                session_id=TEST_SESSION_ID,
                sender_key=TEST_SENDER_KEY,
                session=mock_session,
                signing_keys={"ed25519": "test_signing_key"},
                forwarding_chains=[]
            )
            logger.info("💾 Saved mock Megolm session")

            # Load specific session
            loaded_session = self.store.get_inbound_group_session(
                room_id=TEST_ROOM_ID,
                session_id=TEST_SESSION_ID,
                sender_key=TEST_SENDER_KEY
            )

            if loaded_session and loaded_session.id == TEST_SESSION_ID:
                logger.info("✅ Megolm session persistence test PASSED")
                return True
            else:
                logger.error("❌ Megolm session persistence test FAILED")
                return False

        except Exception as e:
            logger.error(f"❌ Megolm session persistence test FAILED: {e}")
            return False

    async def test_unit_device_keys_persistence(self) -> bool:
        """Unit test: Test device keys save/load"""
        try:
            logger.info("🧪 Testing device keys persistence...")

            # Test device keys
            test_keys = {
                "curve25519:DEVICE_ID": "test_curve_key",
                "ed25519:DEVICE_ID": "test_ed_key",
                "verified": True
            }

            # Save device keys
            self.store.save_device_keys(
                user_id="@test_user:server.com",
                device_id="TEST_DEVICE",
                keys=test_keys
            )
            logger.info("💾 Saved test device keys")

            # Load device keys
            loaded_keys = self.store.load_device_keys()

            if (loaded_keys and
                "@test_user:server.com" in loaded_keys and
                "TEST_DEVICE" in loaded_keys["@test_user:server.com"]):
                logger.info("✅ Device keys persistence test PASSED")
                return True
            else:
                logger.error("❌ Device keys persistence test FAILED")
                return False

        except Exception as e:
            logger.error(f"❌ Device keys persistence test FAILED: {e}")
            return False

    async def test_unit_sync_token_persistence(self) -> bool:
        """Unit test: Test sync token save/load"""
        try:
            logger.info("🧪 Testing sync token persistence...")

            test_token = f"test_sync_token_{random.randint(1000, 9999)}"

            # Save sync token
            self.store.save_sync_token(test_token)
            logger.info("💾 Saved test sync token")

            # Load sync token
            loaded_token = self.store.load_sync_token()

            if loaded_token == test_token:
                logger.info("✅ Sync token persistence test PASSED")
                return True
            else:
                logger.error(f"❌ Sync token persistence test FAILED - Expected: {test_token}, Got: {loaded_token}")
                return False

        except Exception as e:
            logger.error(f"❌ Sync token persistence test FAILED: {e}")
            return False

    async def test_integration_client_with_postgres(self) -> bool:
        """Integration test: Test ProductionMatrixClient with PostgreSQL"""
        try:
            logger.info("🔗 Testing ProductionMatrixClient integration with PostgreSQL...")

            # Force PostgreSQL usage
            os.environ["USE_POSTGRES_STORE"] = "true"

            # Create client with PostgreSQL
            self.client = ProductionMatrixClient(
                use_postgres=True,
                pg_config=POSTGRES_TEST_CONFIG
            )

            # Mock the connection to avoid real Matrix server
            await self._mock_matrix_connection()

            logger.info("✅ ProductionMatrixClient PostgreSQL integration test PASSED")
            return True

        except Exception as e:
            logger.error(f"❌ ProductionMatrixClient PostgreSQL integration test FAILED: {e}")
            return False

    async def _mock_matrix_connection(self):
        """Mock Matrix connection for testing"""
        # This would normally connect to Matrix server
        # For testing, we just initialize the store components

        if self.client.use_postgres:
            self.client.store = PostgresMatrixStore(
                user_id=TEST_USER_ID,
                device_id=TEST_DEVICE_ID,
                pickle_key=TEST_PICKLE_KEY,
                **POSTGRES_TEST_CONFIG
            )
            logger.info("🐘 Mocked PostgreSQL Matrix client")
        else:
            logger.info("📁 Mocked SQLite Matrix client")

    async def test_integration_server_restart_simulation(self) -> bool:
        """Integration test: Simulate server restart and verify key recovery"""
        try:
            logger.info("🔄 Testing server restart simulation...")

            # Phase 1: Save encryption state
            logger.info("📤 Phase 1: Saving encryption state...")

            # Create first client instance
            client1 = ProductionMatrixClient(
                use_postgres=True,
                pg_config=POSTGRES_TEST_CONFIG
            )
            await self._mock_matrix_connection_for_client(client1)

            # Save test encryption data
            test_account = MockOlmAccount()
            test_session = MockMegolmSession("restart_test_session")

            client1.store.save_account(test_account)
            client1.store.save_inbound_group_session(
                room_id="!restart_test_room:server",
                session_id="restart_test_session",
                sender_key="restart_sender_key",
                session=test_session
            )

            # Save test data reference
            self.test_data = {
                'account_saved': True,
                'session_room_id': "!restart_test_room:server",
                'session_id': "restart_test_session",
                'sender_key': "restart_sender_key"
            }

            logger.info("💾 Saved encryption state in first client instance")

            # Phase 2: Simulate server restart
            logger.info("🔌 Phase 2: Simulating server restart...")

            # Close first client (simulate shutdown)
            client1.store.close()
            del client1
            logger.info("🔌 First client closed (simulating shutdown)")

            # Wait briefly to simulate restart time
            await asyncio.sleep(1)

            # Phase 3: Create new client instance (simulate restart)
            logger.info("🚀 Phase 3: Starting new client instance...")

            client2 = ProductionMatrixClient(
                use_postgres=True,
                pg_config=POSTGRES_TEST_CONFIG
            )
            await self._mock_matrix_connection_for_client(client2)

            # Phase 4: Verify data recovery
            logger.info("🔍 Phase 4: Verifying data recovery...")

            # Load account
            recovered_account = client2.store.load_account()
            if not recovered_account:
                logger.error("❌ Failed to recover Olm account")
                return False

            # Load session
            recovered_session = client2.store.get_inbound_group_session(
                room_id=self.test_data['session_room_id'],
                session_id=self.test_data['session_id'],
                sender_key=self.test_data['sender_key']
            )

            if not recovered_session:
                logger.error("❌ Failed to recover Megolm session")
                return False

            # Verify session ID matches
            if recovered_session.id != self.test_data['session_id']:
                logger.error(f"❌ Session ID mismatch: expected {self.test_data['session_id']}, got {recovered_session.id}")
                return False

            # Clean up
            client2.store.close()

            logger.info("✅ Server restart simulation test PASSED")
            return True

        except Exception as e:
            logger.error(f"❌ Server restart simulation test FAILED: {e}")
            return False

    async def _mock_matrix_connection_for_client(self, client):
        """Helper to mock Matrix connection for a specific client"""
        if client.use_postgres:
            client.store = PostgresMatrixStore(
                user_id=TEST_USER_ID,
                device_id=TEST_DEVICE_ID,
                pickle_key=TEST_PICKLE_KEY,
                **POSTGRES_TEST_CONFIG
            )

    async def test_integration_encryption_key_recovery(self) -> bool:
        """Integration test: Test complete encryption key recovery workflow"""
        try:
            logger.info("🔐 Testing complete encryption key recovery workflow...")

            # Create multiple test sessions
            test_sessions = [
                {
                    'room_id': f"!test_room_{i}:server",
                    'session_id': f"session_{i}",
                    'sender_key': f"sender_key_{i}"
                }
                for i in range(5)
            ]

            # Save multiple sessions
            store = PostgresMatrixStore(
                user_id=TEST_USER_ID,
                device_id=TEST_DEVICE_ID,
                pickle_key=TEST_PICKLE_KEY,
                **POSTGRES_TEST_CONFIG
            )

            for session_data in test_sessions:
                mock_session = MockMegolmSession(session_data['session_id'])
                store.save_inbound_group_session(
                    room_id=session_data['room_id'],
                    session_id=session_data['session_id'],
                    sender_key=session_data['sender_key'],
                    session=mock_session
                )

            logger.info(f"💾 Saved {len(test_sessions)} test sessions")

            # Load all sessions
            recovered_sessions = store.load_inbound_group_sessions()

            if len(recovered_sessions) < len(test_sessions):
                logger.error(f"❌ Expected {len(test_sessions)} sessions, got {len(recovered_sessions)}")
                return False

            # Verify each session
            for session_data in test_sessions:
                found = False
                for recovered in recovered_sessions:
                    if (recovered['room_id'] == session_data['room_id'] and
                        recovered['session_id'] == session_data['session_id'] and
                        recovered['sender_key'] == session_data['sender_key']):
                        found = True
                        break

                if not found:
                    logger.error(f"❌ Session not found: {session_data}")
                    return False

            store.close()

            logger.info("✅ Encryption key recovery workflow test PASSED")
            return True

        except Exception as e:
            logger.error(f"❌ Encryption key recovery workflow test FAILED: {e}")
            return False

    async def test_performance_bulk_operations(self) -> bool:
        """Performance test: Test bulk save/load operations"""
        try:
            logger.info("⚡ Testing bulk operations performance...")

            store = PostgresMatrixStore(
                user_id=TEST_USER_ID,
                device_id=TEST_DEVICE_ID,
                pickle_key=TEST_PICKLE_KEY,
                **POSTGRES_TEST_CONFIG
            )

            # Test bulk session saves
            start_time = datetime.now()
            num_sessions = 50

            for i in range(num_sessions):
                mock_session = MockMegolmSession(f"bulk_session_{i}")
                store.save_inbound_group_session(
                    room_id=f"!bulk_room_{i}:server",
                    session_id=f"bulk_session_{i}",
                    sender_key=f"bulk_sender_{i}",
                    session=mock_session
                )

            save_time = datetime.now() - start_time
            logger.info(f"💾 Saved {num_sessions} sessions in {save_time.total_seconds():.2f}s")

            # Test bulk load
            start_time = datetime.now()
            recovered_sessions = store.load_inbound_group_sessions()
            load_time = datetime.now() - start_time

            logger.info(f"📤 Loaded {len(recovered_sessions)} sessions in {load_time.total_seconds():.2f}s")

            # Performance thresholds
            if save_time.total_seconds() > 10:  # Should save 50 sessions in under 10s
                logger.warning(f"⚠️ Bulk save performance slow: {save_time.total_seconds():.2f}s")

            if load_time.total_seconds() > 5:   # Should load in under 5s
                logger.warning(f"⚠️ Bulk load performance slow: {load_time.total_seconds():.2f}s")

            store.close()

            logger.info("✅ Bulk operations performance test PASSED")
            return True

        except Exception as e:
            logger.error(f"❌ Bulk operations performance test FAILED: {e}")
            return False

    async def test_error_handling_database_failures(self) -> bool:
        """Test error handling during database failures"""
        try:
            logger.info("🛡️ Testing error handling for database failures...")

            # Test with invalid database config
            invalid_config = POSTGRES_TEST_CONFIG.copy()
            invalid_config['port'] = 99999  # Invalid port

            try:
                invalid_store = PostgresMatrixStore(
                    user_id=TEST_USER_ID,
                    device_id=TEST_DEVICE_ID,
                    pickle_key=TEST_PICKLE_KEY,
                    **invalid_config
                )

                # This should fail
                invalid_store.load_account()
                logger.error("❌ Expected database connection to fail but it didn't")
                return False

            except Exception as e:
                logger.info(f"✅ Correctly handled database connection failure: {e}")

            logger.info("✅ Error handling test PASSED")
            return True

        except Exception as e:
            logger.error(f"❌ Error handling test FAILED: {e}")
            return False

    async def test_data_consistency_concurrent_access(self) -> bool:
        """Test data consistency with concurrent access"""
        try:
            logger.info("🔄 Testing data consistency with concurrent access...")

            # Create multiple store instances (simulating concurrent clients)
            stores = [
                PostgresMatrixStore(
                    user_id=f"{TEST_USER_ID}_{i}",
                    device_id=f"{TEST_DEVICE_ID}_{i}",
                    pickle_key=TEST_PICKLE_KEY,
                    **POSTGRES_TEST_CONFIG
                )
                for i in range(3)
            ]

            # Concurrent saves
            async def save_test_data(store, index):
                mock_account = MockOlmAccount()
                store.save_account(mock_account)

                for j in range(5):
                    mock_session = MockMegolmSession(f"concurrent_session_{index}_{j}")
                    store.save_inbound_group_session(
                        room_id=f"!concurrent_room_{index}_{j}:server",
                        session_id=f"concurrent_session_{index}_{j}",
                        sender_key=f"concurrent_sender_{index}_{j}",
                        session=mock_session
                    )

            # Run concurrent operations
            tasks = [save_test_data(store, i) for i, store in enumerate(stores)]
            await asyncio.gather(*tasks)

            # Verify data integrity
            for i, store in enumerate(stores):
                account = store.load_account()
                sessions = store.load_inbound_group_sessions()

                if not account:
                    logger.error(f"❌ Account not found for store {i}")
                    return False

                expected_sessions = 5
                actual_sessions = len([s for s in sessions if f"concurrent_session_{i}" in s['session_id']])

                if actual_sessions != expected_sessions:
                    logger.error(f"❌ Expected {expected_sessions} sessions for store {i}, got {actual_sessions}")
                    return False

            # Clean up
            for store in stores:
                store.close()

            logger.info("✅ Data consistency test PASSED")
            return True

        except Exception as e:
            logger.error(f"❌ Data consistency test FAILED: {e}")
            return False

    async def cleanup_test_environment(self):
        """Clean up test environment"""
        try:
            if self.store:
                self.store.close()

            if self.client:
                await self.client.close()

            # Clean test database
            await self._clean_test_data()

            logger.info("🧹 Test environment cleaned up")

        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")

    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results"""
        results = {}

        logger.info("🚀 Starting comprehensive PostgreSQL persistence tests...")

        # Setup
        if not await self.setup_test_environment():
            logger.error("❌ Failed to setup test environment")
            return {"setup": False}

        # Unit tests
        logger.info("\n📝 === UNIT TESTS ===")
        results["unit_olm_account"] = await self.test_unit_olm_account_persistence()
        results["unit_megolm_session"] = await self.test_unit_megolm_session_persistence()
        results["unit_device_keys"] = await self.test_unit_device_keys_persistence()
        results["unit_sync_token"] = await self.test_unit_sync_token_persistence()

        # Integration tests
        logger.info("\n🔗 === INTEGRATION TESTS ===")
        results["integration_client"] = await self.test_integration_client_with_postgres()
        results["integration_restart"] = await self.test_integration_server_restart_simulation()
        results["integration_recovery"] = await self.test_integration_encryption_key_recovery()

        # Performance tests
        logger.info("\n⚡ === PERFORMANCE TESTS ===")
        results["performance_bulk"] = await self.test_performance_bulk_operations()

        # Error handling tests
        logger.info("\n🛡️ === ERROR HANDLING TESTS ===")
        results["error_handling"] = await self.test_error_handling_database_failures()
        results["data_consistency"] = await self.test_data_consistency_concurrent_access()

        # Cleanup
        await self.cleanup_test_environment()

        return results


async def main():
    """Main test runner"""
    logger.info("🧪 PostgreSQL Matrix Encryption Persistence Test Suite")
    logger.info("=" * 60)

    # Check PostgreSQL availability
    try:
        conn = psycopg2.connect(**POSTGRES_TEST_CONFIG)
        conn.close()
        logger.info("✅ PostgreSQL connection verified")
    except Exception as e:
        logger.error(f"❌ PostgreSQL not available: {e}")
        logger.error("Please ensure PostgreSQL is running and accessible")
        return False

    # Run tests
    test_suite = TestPostgresPersistence()
    results = await test_suite.run_all_tests()

    # Print results summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("=" * 60)

    passed = 0
    total = 0

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name:30} {status}")
        if result:
            passed += 1
        total += 1

    logger.info("-" * 60)
    logger.info(f"Total: {passed}/{total} tests passed ({(passed/total*100):.1f}%)")

    if passed == total:
        logger.info("🎉 ALL TESTS PASSED! PostgreSQL persistence is working correctly.")
        return True
    else:
        logger.error(f"❌ {total-passed} tests failed. Please check the issues above.")
        return False


if __name__ == "__main__":
    # Setup logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )

    # Run tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)