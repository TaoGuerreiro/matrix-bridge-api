#!/usr/bin/env python3
"""
Entry point for Clever Cloud deployment
Imports the complete Matrix Bridge API with all endpoints
"""

# Import the complete API with all endpoints
from src.api_etke_prod import app

# This makes the app available for uvicorn
# Usage: uvicorn app:app
if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))