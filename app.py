#!/usr/bin/env python3
"""
Entry point for Clever Cloud deployment
Resolves import issues by using the fixed application
"""

# Import the working fixed app
from clever_app_fixed import app

# This makes the app available for uvicorn
# Usage: uvicorn app:app
if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))