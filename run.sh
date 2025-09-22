#!/bin/bash
# Script de démarrage pour Clever Cloud
# Ce script est exécuté automatiquement au démarrage de l'application

set -e

echo "🚀 Starting Matrix Bridge API on Clever Cloud"

# Vérifier si PostgreSQL est configuré
if [ -n "$DATABASE_URL" ]; then
    echo "✅ PostgreSQL configured via DATABASE_URL"
    export USE_POSTGRES_STORE=true
else
    echo "⚠️ No PostgreSQL detected, using SQLite"
    export USE_POSTGRES_STORE=false
fi

# Initialiser les clés de chiffrement si nécessaire
if [ "$INIT_ENCRYPTION" = "true" ]; then
    echo "🔐 Initializing encryption keys..."
    python src/fix_encryption_postgres.py || echo "⚠️ Encryption initialization failed or already done"
fi

# Lancer l'application avec uvicorn
echo "🎯 Starting API server on port ${PORT:-8080}"
exec uvicorn src.api_etke_prod:app \
    --host 0.0.0.0 \
    --port ${PORT:-8080} \
    --workers ${CC_WORKERS:-2} \
    --log-level info