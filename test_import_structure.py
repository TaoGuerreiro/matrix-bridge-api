#!/usr/bin/env python3
"""
Test script to verify import structure without dependencies
"""
import sys
import os
import ast

def test_import_structure():
    """Test if the import structure is syntactically correct"""
    print("Testing import structure (syntax only)...")

    # Test files to check
    files_to_test = [
        'app.py',
        'src/main.py',
        'src/api_etke_prod.py',
        'src/etke_matrix_client_prod.py',
        'src/postgres_matrix_store.py',
        'src/__init__.py'
    ]

    for file_path in files_to_test:
        full_path = os.path.join(os.getcwd(), file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r') as f:
                    source = f.read()

                # Parse the Python AST to check syntax
                ast.parse(source)
                print(f"✅ {file_path}: Syntax OK")

                # Check for problematic import patterns
                if 'from .' in source and 'except ImportError' in source:
                    print(f"✅ {file_path}: Has fallback imports")
                elif file_path.endswith('app.py') or file_path.endswith('main.py'):
                    print(f"✅ {file_path}: Entry point file")
                else:
                    print(f"⚠️  {file_path}: No import fallbacks")

            except SyntaxError as e:
                print(f"❌ {file_path}: Syntax Error - {e}")
            except Exception as e:
                print(f"❌ {file_path}: Error - {e}")
        else:
            print(f"❌ {file_path}: File not found")

    # Test CC_RUN_COMMAND
    if os.path.exists('CC_RUN_COMMAND'):
        with open('CC_RUN_COMMAND', 'r') as f:
            cmd = f.read().strip()
        print(f"✅ CC_RUN_COMMAND: {cmd}")
    else:
        print("❌ CC_RUN_COMMAND: Not found")

if __name__ == "__main__":
    test_import_structure()