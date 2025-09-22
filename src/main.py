#!/usr/bin/env python3
"""
Alternative entry point for Clever Cloud deployment with absolute imports
"""
import sys
import os

# Ensure current directory is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import the app with absolute import
from api_etke_prod import app

# Export app for uvicorn: uvicorn src.main:app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))