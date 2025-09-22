#!/usr/bin/env python3
"""
Clever Cloud Entry Point - Production Matrix API
Intelligent fallback system for maximum deployment reliability
"""
import os
import sys
import logging

# Setup logging early
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add src to path for imports
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

logger.info(f"🚀 Clever Cloud Matrix Bridge API Starting")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"PORT env: {os.getenv('PORT', 'NOT_SET')}")
logger.info(f"Python version: {sys.version}")

# Application selection with intelligent fallback
app = None
app_type = "unknown"

# Try 1: New robust production API
try:
    logger.info("📦 Loading robust production API...")
    from api_clever_prod import app
    app_type = "robust_production"
    logger.info("✅ Robust production API loaded successfully")

except Exception as e:
    logger.warning(f"⚠️ Robust production API failed: {e}")

    # Try 2: Original production API
    try:
        logger.info("📦 Loading original production API...")
        from api_etke_prod import app
        app_type = "original_production"
        logger.info("✅ Original production API loaded successfully")

    except Exception as e2:
        logger.warning(f"⚠️ Original production API failed: {e2}")

        # Try 3: Debug app
        try:
            logger.info("🔧 Loading debug app as fallback...")
            from debug_clever import debug_app as app
            app_type = "debug_fallback"
            logger.info("✅ Debug app loaded as emergency fallback")

        except Exception as e3:
            logger.error(f"❌ All app loading strategies failed!")
            logger.error(f"  - Robust production: {e}")
            logger.error(f"  - Original production: {e2}")
            logger.error(f"  - Debug fallback: {e3}")

            # Create minimal emergency app
            from fastapi import FastAPI
            app = FastAPI(title="Emergency API")

            @app.get("/")
            async def emergency_root():
                return {
                    "status": "emergency_mode",
                    "message": "All primary applications failed to load",
                    "errors": {
                        "robust_production": str(e),
                        "original_production": str(e2),
                        "debug_fallback": str(e3)
                    },
                    "working_directory": os.getcwd(),
                    "python_path": sys.path[:3],
                    "environment_vars": {
                        "PORT": os.getenv("PORT", "NOT_SET"),
                        "DATABASE_URL": "SET" if os.getenv("DATABASE_URL") else "NOT_SET",
                        "ETKE_PASSWORD": "SET" if os.getenv("ETKE_PASSWORD") else "NOT_SET"
                    }
                }

            @app.get("/health")
            async def emergency_health():
                return {"status": "emergency", "app_type": "minimal_emergency"}

            app_type = "emergency"
            logger.error("💀 Emergency minimal app created")

# Log final app type
logger.info(f"🎯 Final app type: {app_type}")

# Environment validation
critical_vars = ["PORT", "DATABASE_URL", "ETKE_HOMESERVER", "ETKE_USERNAME", "ETKE_PASSWORD"]
missing_vars = [var for var in critical_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"❌ Missing critical environment variables: {missing_vars}")
else:
    logger.info("✅ All critical environment variables present")

# Export app for uvicorn
# Usage: uvicorn clever_app:app --host 0.0.0.0 --port $PORT
__all__ = ['app']

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"🚀 Starting {app_type} app on port {port}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )