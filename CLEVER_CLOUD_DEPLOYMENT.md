# 🚀 Déploiement Clever Cloud - Organisation Chalky

## Architecture sur Clever Cloud

```
┌─────────────────────────────────────────────────────────────┐
│                     Organisation: Chalky                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────┐    ┌──────────────────────┐       │
│  │   App: matrix-api    │    │  Addon: PostgreSQL   │       │
│  │                      │◄───┤                      │       │
│  │  • Python 3.11       │    │  • Plan S            │       │
│  │  • FastAPI/Uvicorn   │    │  • 256MB RAM         │       │
│  │  • 2 Workers         │    │  • Auto-backup       │       │
│  └──────────────────────┘    └──────────────────────┘       │
│           ▲                                                  │
│           │                                                  │
│  ┌────────┴──────────┐                                      │
│  │   etke.cc Matrix  │                                      │
│  │  Bridges Instagram│                                      │
│  └───────────────────┘                                      │
└─────────────────────────────────────────────────────────────┘
```

## Fichiers de Configuration Créés

### 1. `/clevercloud/python.json`
Configuration Python pour Clever Cloud avec:
- Python 3.11
- Hook post-deploy pour initialiser les clés
- 3 déploiements gardés en historique

### 2. `/src/api_etke_prod.py`
API FastAPI optimisée pour Clever Cloud:
- Parse automatique de `DATABASE_URL`
- Support du port dynamique via `PORT`
- Health check endpoint pour monitoring
- Lifespan management pour PostgreSQL

### 3. `/run.sh`
Script de démarrage avec:
- Détection automatique PostgreSQL
- Initialisation des clés si nécessaire
- Configuration uvicorn avec workers

### 4. `/.clever.json`
Configuration du projet Clever Cloud (à mettre à jour avec l'app_id réel)

## Variables d'Environnement Requises

### Variables etke.cc Matrix (Obligatoires)
```bash
ETKE_HOMESERVER=https://matrix.chalky.etke.host
ETKE_USERNAME=@florent:chalky.etke.host
ETKE_PASSWORD=<password_etke>
```

### Variables PostgreSQL (Automatiques)
```bash
DATABASE_URL=postgresql://user:pass@host:port/db  # Injecté par Clever Cloud
USE_POSTGRES_STORE=true
```

### Variables Application
```bash
WEBHOOK_URL=https://bicicouriers.eu.ngrok.io/webhooks/instagram
CC_PYTHON_BACKEND=uvicorn
CC_PYTHON_MODULE=src.api_etke_prod:app
CC_PYTHON_VERSION=3.11
CC_HEALTH_CHECK_PATH=/api/v1/health
PORT=8080  # Géré par Clever Cloud
```

### Variables Performance
```bash
CC_WORKERS=2
CC_WORKER_RESTART=3600
```

## Commandes de Déploiement

### Installation Clever CLI
```bash
npm install -g clever-tools
```

### Déploiement Initial
```bash
# 1. Se connecter
clever login

# 2. Créer l'app dans l'organisation Chalky
clever create --type python --org "Chalky" matrix-bridge-api

# 3. Créer PostgreSQL
clever addon create postgresql-addon --plan s --org "Chalky" matrix-postgres

# 4. Lier PostgreSQL
clever service link-addon matrix-postgres

# 5. Configurer les variables
clever env set ETKE_PASSWORD "votre_password"
clever env set WEBHOOK_URL "https://bicicouriers.eu.ngrok.io/webhooks/instagram"
# ... autres variables

# 6. Déployer
git add .
git commit -m "Configure for Clever Cloud deployment"
git push clever master

# 7. Suivre les logs
clever logs -f

# 8. Initialiser les clés (une seule fois)
clever ssh
python src/fix_encryption_postgres.py
exit
```

### Mises à Jour
```bash
# Déployer une mise à jour
git push clever master

# Redémarrer l'application
clever restart

# Voir le statut
clever status
```

## URLs de Production

- **API**: `https://matrix-bridge-api-chalky.cleverapps.io`
- **Health Check**: `https://matrix-bridge-api-chalky.cleverapps.io/api/v1/health`
- **Documentation**: `https://matrix-bridge-api-chalky.cleverapps.io/docs`

## Monitoring et Logs

### Consulter les Logs
```bash
# Logs en temps réel
clever logs -f

# Derniers 100 logs
clever logs --before 100

# Logs d'une date spécifique
clever logs --since "2024-01-01"
```

### Métriques PostgreSQL
```bash
# Se connecter à PostgreSQL
clever addon env matrix-postgres

# Utiliser psql avec les credentials
psql $DATABASE_URL

# Vérifier les sessions Matrix
SELECT COUNT(*) FROM megolm_inbound_sessions;
```

## Scaling

### Augmenter les Workers
```bash
clever env set CC_WORKERS 4
clever restart
```

### Changer le Plan PostgreSQL
```bash
# Passer au plan M (512MB)
clever addon update matrix-postgres --plan m
```

### Ajouter Plus de RAM à l'App
```bash
clever scale --flavor M
```

## Backup et Restauration

### Backup Manuel PostgreSQL
```bash
# Se connecter en SSH
clever ssh

# Exporter la base
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Télécharger le backup
scp backup_*.sql local/
```

### Restauration
```bash
# Se connecter en SSH
clever ssh

# Restaurer depuis un backup
psql $DATABASE_URL < backup_20240101.sql
```

## Troubleshooting

### L'API ne démarre pas
1. Vérifier les logs: `clever logs`
2. Vérifier les variables: `clever env`
3. Tester localement avec les mêmes variables

### PostgreSQL non accessible
1. Vérifier l'addon: `clever addon`
2. Vérifier DATABASE_URL: `clever env | grep DATABASE`
3. Tester la connexion: `clever ssh` puis `psql $DATABASE_URL`

### Messages non déchiffrés
1. Se connecter: `clever ssh`
2. Réinitialiser: `python src/fix_encryption_postgres.py`
3. Vérifier: `python src/test_postgres_persistence.py`

## Sécurité

### Bonnes Pratiques
- ✅ Utiliser des variables d'environnement pour les secrets
- ✅ Activer HTTPS (automatique sur Clever Cloud)
- ✅ Configurer les CORS dans l'API
- ✅ Utiliser PostgreSQL avec SSL
- ✅ Backups automatiques quotidiens

### Rotation des Secrets
```bash
# Changer le password etke
clever env set ETKE_PASSWORD "nouveau_password"
clever restart
```

## Support Clever Cloud

- **Documentation**: https://www.clever.cloud/doc/
- **Status**: https://www.cleverstatus.com/
- **Support**: support@clever-cloud.com
- **Console**: https://console.clever-cloud.com/

## Checklist de Déploiement

- [ ] Compte Clever Cloud créé
- [ ] Accès à l'organisation Chalky
- [ ] Clever CLI installé
- [ ] Variables d'environnement configurées
- [ ] PostgreSQL addon créé et lié
- [ ] Application déployée
- [ ] Clés de chiffrement initialisées
- [ ] Health check fonctionnel
- [ ] Webhook configuré
- [ ] Tests de déchiffrement passés
- [ ] Monitoring activé

---

**Status**: ✅ Prêt pour le déploiement sur Clever Cloud dans l'organisation Chalky