# PostgreSQL Matrix Encryption Persistence Tests

This document describes the comprehensive test suite for validating PostgreSQL persistence of Matrix encryption keys.

## Overview

The `test_postgres_persistence.py` script validates that Matrix encryption keys are properly persisted in PostgreSQL and can survive server restarts. This is crucial for maintaining end-to-end encryption functionality in production environments.

## Test Coverage

### Unit Tests
- **Olm Account Persistence**: Tests saving/loading of the main Olm cryptographic account
- **Megolm Session Persistence**: Tests saving/loading of group chat encryption sessions
- **Device Keys Persistence**: Tests saving/loading of device identity keys
- **Sync Token Persistence**: Tests saving/loading of Matrix synchronization tokens

### Integration Tests
- **Client Integration**: Tests ProductionMatrixClient with PostgreSQL backend
- **Server Restart Simulation**: Simulates complete server restart and verifies key recovery
- **Encryption Key Recovery**: Tests complete workflow of saving and recovering all encryption data

### Performance Tests
- **Bulk Operations**: Tests performance with large numbers of encryption keys
- **Concurrent Access**: Tests data consistency with multiple simultaneous clients

### Error Handling Tests
- **Database Failures**: Tests graceful handling of database connection issues
- **Data Consistency**: Tests data integrity under concurrent access patterns

## Prerequisites

### 1. PostgreSQL Setup

Ensure PostgreSQL is running and accessible. The tests use environment variables for configuration:

```bash
# .env file
POSTGRES_DB=matrix_store_test
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=matrix_user
POSTGRES_PASSWORD=your_password
USE_POSTGRES_STORE=true
```

### 2. Install Dependencies

```bash
# Install test dependencies
pip install -r requirements.txt
```

### 3. Database Permissions

The test user needs permissions to:
- Create databases
- Create tables
- Insert/update/delete data
- Manage connections

```sql
-- Example PostgreSQL setup
CREATE USER matrix_user WITH PASSWORD 'your_password';
CREATE DATABASE matrix_store_test OWNER matrix_user;
GRANT ALL PRIVILEGES ON DATABASE matrix_store_test TO matrix_user;
```

## Running the Tests

### Quick Test Run

```bash
# Run all tests
python src/test_postgres_persistence.py
```

### Using pytest (Alternative)

```bash
# Run with pytest for more detailed output
pytest src/test_postgres_persistence.py -v -s
```

### Docker Environment (Recommended)

```bash
# Start PostgreSQL with Docker
docker run -d \
  --name postgres-test \
  -e POSTGRES_DB=matrix_store_test \
  -e POSTGRES_USER=matrix_user \
  -e POSTGRES_PASSWORD=test_password \
  -p 5432:5432 \
  postgres:15

# Run tests
POSTGRES_PASSWORD=test_password python src/test_postgres_persistence.py

# Cleanup
docker stop postgres-test && docker rm postgres-test
```

## Test Scenarios

### 1. Basic Persistence Test

```
1. Save encryption keys to PostgreSQL
2. Load keys from PostgreSQL
3. Verify data integrity
```

### 2. Server Restart Simulation

```
1. Create ProductionMatrixClient with PostgreSQL
2. Save encryption state (account + sessions)
3. Close client (simulate shutdown)
4. Create new client instance
5. Verify all encryption data is recovered
6. Test message decryption with recovered keys
```

### 3. Performance Validation

```
1. Save 50+ encryption sessions
2. Measure save/load performance
3. Verify performance meets thresholds:
   - Save: < 10 seconds for 50 sessions
   - Load: < 5 seconds for all sessions
```

### 4. Concurrent Access Test

```
1. Create multiple client instances
2. Perform simultaneous save operations
3. Verify data consistency
4. Test isolation between different users
```

## Expected Output

### Successful Test Run

```
🧪 PostgreSQL Matrix Encryption Persistence Test Suite
============================================================
✅ PostgreSQL connection verified

📝 === UNIT TESTS ===
🧪 Testing Olm account persistence...
💾 Saved mock Olm account
✅ Olm account persistence test PASSED

🧪 Testing Megolm session persistence...
💾 Saved mock Megolm session
✅ Megolm session persistence test PASSED

🔗 === INTEGRATION TESTS ===
🔄 Testing server restart simulation...
📤 Phase 1: Saving encryption state...
💾 Saved encryption state in first client instance
🔌 Phase 2: Simulating server restart...
🔌 First client closed (simulating shutdown)
🚀 Phase 3: Starting new client instance...
🔍 Phase 4: Verifying data recovery...
✅ Server restart simulation test PASSED

📊 TEST RESULTS SUMMARY
============================================================
unit_olm_account              ✅ PASS
unit_megolm_session          ✅ PASS
unit_device_keys             ✅ PASS
unit_sync_token              ✅ PASS
integration_client           ✅ PASS
integration_restart          ✅ PASS
integration_recovery         ✅ PASS
performance_bulk             ✅ PASS
error_handling               ✅ PASS
data_consistency             ✅ PASS
------------------------------------------------------------
Total: 10/10 tests passed (100.0%)
🎉 ALL TESTS PASSED! PostgreSQL persistence is working correctly.
```

## Troubleshooting

### Common Issues

#### 1. PostgreSQL Connection Failed

```
❌ PostgreSQL not available: connection to server at "localhost" failed
```

**Solution**: Verify PostgreSQL is running and connection details are correct:

```bash
# Test connection manually
psql -h localhost -U matrix_user -d matrix_store_test
```

#### 2. Permission Denied

```
❌ Database error: permission denied for table accounts
```

**Solution**: Grant proper permissions:

```sql
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO matrix_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO matrix_user;
```

#### 3. Database Not Found

```
❌ Database "matrix_store_test" does not exist
```

**Solution**: Create the test database:

```sql
CREATE DATABASE matrix_store_test;
```

#### 4. Import Errors

```
❌ ModuleNotFoundError: No module named 'psycopg2'
```

**Solution**: Install missing dependencies:

```bash
pip install psycopg2-binary pytest pytest-asyncio
```

### Performance Issues

If bulk operations are slow:
1. Check PostgreSQL configuration
2. Verify adequate memory allocation
3. Consider connection pool settings
4. Check for concurrent database operations

### Data Integrity Issues

If tests fail with data inconsistency:
1. Check for conflicting test runs
2. Verify database isolation
3. Review transaction handling
4. Check for race conditions

## Production Considerations

### 1. Security

- Use strong, unique PostgreSQL passwords
- Enable SSL/TLS for database connections
- Implement proper access controls
- Consider encryption at rest

### 2. Performance

- Configure appropriate connection pools
- Monitor database performance
- Implement proper indexing
- Consider read replicas for scaling

### 3. Backup & Recovery

- Implement regular database backups
- Test backup restoration procedures
- Consider point-in-time recovery
- Document recovery procedures

### 4. Monitoring

- Monitor database health
- Track encryption key operations
- Alert on persistence failures
- Log security events

## Integration with Production

After tests pass, the PostgreSQL persistence layer can be safely used in production:

```python
# Production usage
client = ProductionMatrixClient(
    use_postgres=True,
    pg_config={
        'database': 'matrix_production',
        'host': 'db.example.com',
        'port': 5432,
        'user': 'matrix_user',
        'password': os.getenv('POSTGRES_PASSWORD'),
        'pool_size': 20
    }
)

# Enable PostgreSQL in environment
export USE_POSTGRES_STORE=true
```

## Additional Resources

- [Matrix Encryption Documentation](https://spec.matrix.org/v1.8/client-server-api/#end-to-end-encryption)
- [PostgreSQL Connection Pooling](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [matrix-nio Documentation](https://matrix-nio.readthedocs.io/)
- [Olm/Megolm Cryptographic Specification](https://spec.matrix.org/v1.8/appendices/#cryptographic-algorithms)