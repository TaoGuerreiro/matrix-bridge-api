#!/usr/bin/env python3
"""
Test script to verify all imports work correctly
"""
import sys
import os

print("Testing Matrix Bridge API imports...")
print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path[:3]}...")

# Test 1: Direct app import
print("\n=== Test 1: Direct app import ===")
try:
    from app import app
    print("✅ app.py import successful")
except ImportError as e:
    print(f"❌ app.py import failed: {e}")

# Test 2: Via src.main
print("\n=== Test 2: src.main import ===")
try:
    from src.main import app as app_main
    print("✅ src.main import successful")
except ImportError as e:
    print(f"❌ src.main import failed: {e}")

# Test 3: Adding src to path manually
print("\n=== Test 3: Manual src path ===")
try:
    src_path = os.path.join(os.getcwd(), 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from api_etke_prod import app as app_direct
    print("✅ Direct api_etke_prod import successful")
except ImportError as e:
    print(f"❌ Direct api_etke_prod import failed: {e}")

# Test 4: Test individual modules
print("\n=== Test 4: Individual modules ===")
try:
    from etke_matrix_client_prod import ProductionMatrixClient
    print("✅ ProductionMatrixClient import successful")
except ImportError as e:
    print(f"❌ ProductionMatrixClient import failed: {e}")

try:
    from postgres_matrix_store import PostgresMatrixStore
    print("✅ PostgresMatrixStore import successful")
except ImportError as e:
    print(f"❌ PostgresMatrixStore import failed: {e}")

print("\n=== Import test completed ===")