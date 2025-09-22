#!/usr/bin/env python3
"""
Emergency Debug Endpoint for Clever Cloud Deployment
Minimal FastAPI app to diagnose deployment issues
"""
import os
import sys
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Create minimal debug app
debug_app = FastAPI(title="Clever Cloud Debug API")

@debug_app.get("/")
async def debug_root():
    """Debug root endpoint"""
    return {
        "status": "debug_alive",
        "python_version": sys.version,
        "working_directory": os.getcwd(),
        "python_path": sys.path[:5],  # First 5 entries
        "port": os.getenv("PORT", "not_set")
    }

@debug_app.get("/env")
async def debug_environment():
    """Check critical environment variables"""
    env_vars = {}
    critical_vars = [
        "PORT", "DATABASE_URL", "ETKE_HOMESERVER",
        "ETKE_USERNAME", "ETKE_PASSWORD", "USE_POSTGRES_STORE"
    ]

    for var in critical_vars:
        value = os.getenv(var)
        env_vars[var] = "SET" if value else "MISSING"
        # Show partial value for debugging (security conscious)
        if value and var == "DATABASE_URL":
            env_vars[f"{var}_preview"] = value[:20] + "..." if len(value) > 20 else value
        elif value and "PASSWORD" in var:
            env_vars[f"{var}_length"] = len(value)

    return {
        "environment_status": env_vars,
        "all_env_count": len(os.environ)
    }

@debug_app.get("/imports")
async def debug_imports():
    """Test critical imports"""
    import_status = {}

    try:
        import fastapi
        import_status["fastapi"] = f"OK - {fastapi.__version__}"
    except Exception as e:
        import_status["fastapi"] = f"FAILED - {e}"

    try:
        import psycopg2
        import_status["psycopg2"] = "OK"
    except Exception as e:
        import_status["psycopg2"] = f"FAILED - {e}"

    try:
        from nio import AsyncClient
        import_status["matrix-nio"] = "OK"
    except Exception as e:
        import_status["matrix-nio"] = f"FAILED - {e}"

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from src.postgres_matrix_store import PostgresMatrixStore
        import_status["postgres_store"] = "OK"
    except Exception as e:
        import_status["postgres_store"] = f"FAILED - {e}"

    return {
        "import_status": import_status,
        "src_accessible": os.path.exists("src"),
        "files_in_current": os.listdir(".")[:10]
    }

@debug_app.get("/database")
async def debug_database():
    """Test database connection"""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        return {"database_status": "NO_DATABASE_URL"}

    try:
        import urllib.parse
        result = urllib.parse.urlparse(database_url)

        pg_config = {
            "host": result.hostname,
            "port": result.port or 5432,
            "database": result.path[1:],  # Remove leading slash
            "user": result.username,
            "has_password": bool(result.password)
        }

        # Test connection
        import psycopg2
        conn = psycopg2.connect(database_url)
        conn.close()

        return {
            "database_status": "CONNECTION_OK",
            "parsed_config": pg_config
        }

    except Exception as e:
        return {
            "database_status": f"CONNECTION_FAILED - {e}",
            "database_url_format": "Expected: postgresql://user:pass@host:port/db"
        }

# Export for uvicorn
app = debug_app

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    print(f"🔧 Starting debug server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)