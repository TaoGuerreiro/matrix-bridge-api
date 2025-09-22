#!/usr/bin/env python3
"""
Alternative entry point for Clever Cloud deployment with fixed app
"""
import sys
import os

# Add parent directory to path to access clever_app_fixed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the working fixed app
from clever_app_fixed import app

# Export app for uvicorn: uvicorn src.main:app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))