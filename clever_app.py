#!/usr/bin/env python3
"""
Clever Cloud Entry Point - Import Complete Production API
Connects to Matrix via etke.cc bridges
"""

# Import the complete production API with all endpoints
from src.api_etke_prod import app

# Re-export for uvicorn
__all__ = ['app']