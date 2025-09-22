-- Initialize test database for Matrix encryption persistence tests
-- This script is automatically run when the PostgreSQL container starts

-- Create additional test database if needed
CREATE DATABASE matrix_store_test_backup;

-- Grant all privileges to test user
GRANT ALL PRIVILEGES ON DATABASE matrix_store_test TO matrix_user;
GRANT ALL PRIVILEGES ON DATABASE matrix_store_test_backup TO matrix_user;

-- Connect to test database and set up initial schema
\c matrix_store_test;

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO matrix_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO matrix_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO matrix_user;

-- Create extension for better JSON support if available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log successful initialization
INSERT INTO pg_stat_statements_info (dealloc) VALUES (0) ON CONFLICT DO NOTHING;

-- Create a test verification table
CREATE TABLE test_init_verification (
    id SERIAL PRIMARY KEY,
    initialized_at TIMESTAMP DEFAULT NOW(),
    test_ready BOOLEAN DEFAULT TRUE
);

INSERT INTO test_init_verification (test_ready) VALUES (TRUE);

-- Grant permissions on test table
GRANT ALL PRIVILEGES ON TABLE test_init_verification TO matrix_user;
GRANT ALL PRIVILEGES ON SEQUENCE test_init_verification_id_seq TO matrix_user;