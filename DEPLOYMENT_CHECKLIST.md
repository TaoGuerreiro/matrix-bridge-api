# 🚀 Clever Cloud Deployment Checklist

## Critical Environment Variables (Must be set in Clever Cloud)

### ✅ Matrix Configuration
- `ETKE_HOMESERVER=https://matrix.chalky.etke.host`
- `ETKE_USERNAME=@florent:chalky.etke.host`
- `ETKE_PASSWORD=E3oVNfK0SlRL8NaCroXBiQ0dPfSQYmV9ktS01O5pMr7nGOpGFq7ZXoELVomNSRrT`

### ✅ Database Configuration (PostgreSQL Addon)
- `DATABASE_URL` (automatically set by PostgreSQL addon)
- `USE_POSTGRES_STORE=true`

### ✅ Optional Configuration
- `WEBHOOK_URL=https://bicicouriers.eu.ngrok.io`
- `API_HOST=0.0.0.0`

## Deployment Strategy

### Entry Point Options (in order of preference)
1. **Primary**: `uvicorn clever_app:app` (intelligent fallback system)
2. **Debug**: `uvicorn debug_clever:app` (minimal diagnostic)
3. **Emergency**: `uvicorn clever_app:app` (will create emergency mode if all fail)

### Application Layers
1. **Robust Production** (`api_clever_prod.py`) - Full features with config validation
2. **Original Production** (`api_etke_prod.py`) - Original working version
3. **Debug Mode** (`debug_clever.py`) - Diagnostic endpoints only
4. **Emergency Mode** - Minimal FastAPI with error reporting

## Testing URLs (after deployment)

### Health Checks
- `GET /` - Root status with app type
- `GET /api/v1/health` - Comprehensive health check
- `GET /api/v1/config` - Configuration validation status
- `GET /api/v1/debug/environment` - Environment variable status

### Diagnostic Endpoints
- `GET /api/v1/version` - Version information
- `GET /env` (debug mode only) - Environment variables
- `GET /imports` (debug mode only) - Import status
- `GET /database` (debug mode only) - Database connection test

## Expected URL
https://matrix-bridge-api-chalky.cleverapps.io/api/v1/health

## Troubleshooting

### If 404 Error
1. Check entry point in Clever Cloud configuration
2. Verify `PORT` environment variable is available
3. Check application logs for startup errors
4. Try debug endpoint: `/api/v1/debug/environment`

### If 503 Error
1. Check Matrix credentials are correctly set
2. Verify PostgreSQL addon is properly configured
3. Check `DATABASE_URL` format
4. Review logs for Matrix connection errors

### If Configuration Errors
1. Visit `/api/v1/config` to see validation results
2. Check environment variables in Clever Cloud console
3. Ensure all critical variables are set
4. Verify `DATABASE_URL` format: `postgresql://user:pass@host:port/db`

## Deployment Commands

```bash
# Test locally first
uvicorn clever_app:app --host 0.0.0.0 --port 8000

# Deploy to Clever Cloud
git add .
git commit -m "feat: robust production deployment with intelligent fallback"
git push clever master
```

## Success Criteria

✅ Application starts without 404 errors
✅ Health check returns 200 status
✅ Configuration validation passes
✅ Matrix client connects successfully
✅ PostgreSQL connection established
✅ All critical endpoints accessible

## Rollback Plan

If deployment fails:
1. Revert to previous working commit
2. Use debug mode entry point: `uvicorn debug_clever:app`
3. Check environment variables one by one
4. Fix issues and redeploy incrementally