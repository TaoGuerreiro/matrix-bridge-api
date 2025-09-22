#!/usr/bin/env python3
"""
Entry point for Clever Cloud deployment
Resolves import issues by adding the src directory to Python path
"""
import sys
import os

# Add src directory to Python path for Clever Cloud
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import the app from the production module
from api_etke_prod import app

# This makes the app available for uvicorn
# Usage: uvicorn app:app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))