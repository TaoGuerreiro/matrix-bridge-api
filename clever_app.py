#!/usr/bin/env python3
"""
Clever Cloud Entry Point - Direct Import to Fixed App
Maximum reliability with zero dependency fallbacks
"""

# Import the working fixed app directly
from clever_app_fixed import app

# Re-export for uvicorn
__all__ = ['app']