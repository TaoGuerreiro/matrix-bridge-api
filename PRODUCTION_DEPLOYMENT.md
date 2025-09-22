# Guide de Déploiement Production - Matrix Encryption avec PostgreSQL

## 🎯 Objectif
Assurer la persistance complète des clés de chiffrement Matrix pour que les messages Instagram/Messenger restent déchiffrables même après un redémarrage du serveur.

## 📋 Prérequis

- PostgreSQL 15+
- Python 3.8+
- Docker & Docker Compose (optionnel mais recommandé)
- Compte etke.cc avec bridges Instagram/Messenger configurés

## 🏗️ Architecture Implémentée

```
┌─────────────────────────────────┐
│        Instagram/Messenger       │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│     etke.cc Matrix Server       │
│    (Bridges mautrix-meta)       │
└────────────┬────────────────────┘
             │ Messages chiffrés (MegolmEvent)
┌────────────▼────────────────────┐
│    ProductionMatrixClient       │
│  ┌───────────────────────────┐  │
│  │  PostgreSQL Store         │  │
│  │  - Olm Account Keys       │  │
│  │  - Megolm Session Keys    │  │
│  │  - Device Trust Keys      │  │
│  │  - Sync Tokens            │  │
│  └───────────────────────────┘  │
└────────────┬────────────────────┘
             │ Messages déchiffrés
┌────────────▼────────────────────┐
│         Webhook API             │
│   (https://ngrok.io/...)        │
└─────────────────────────────────┘
```

## 📦 Fichiers Créés

### Core Components
- **`src/postgres_matrix_store.py`** - Store PostgreSQL personnalisé pour nio
- **`src/etke_matrix_client_prod.py`** - Client Matrix production-ready
- **`src/test_postgres_persistence.py`** - Tests de validation complète
- **`src/migrate_to_postgres.py`** - Migration SQLite → PostgreSQL
- **`docker-compose.prod.yml`** - Stack production Docker

### Configuration Files
- **`.env.production`** - Variables d'environnement production
- **`Dockerfile.prod`** - Image Docker optimisée
- **`init-db.sql`** - Script d'initialisation PostgreSQL

## 🚀 Déploiement Production

### 1. Configuration Environnement

Créer `.env.production`:
```bash
# Matrix/etke.cc
ETKE_HOMESERVER=https://matrix.chalky.etke.host
ETKE_USERNAME=@florent:chalky.etke.host
ETKE_PASSWORD=your_password_here

# PostgreSQL
USE_POSTGRES_STORE=true
POSTGRES_HOST=postgres
POSTGRES_DB=matrix_store
POSTGRES_USER=matrix_user
POSTGRES_PASSWORD=strong_password_here
POSTGRES_PORT=5432
POSTGRES_POOL_SIZE=20

# API
API_HOST=0.0.0.0
API_PORT=8000

# Webhook
WEBHOOK_URL=https://your-ngrok-url.ngrok.io/webhooks/instagram
```

### 2. Démarrage avec Docker Compose

```bash
# Démarrer PostgreSQL
docker-compose -f docker-compose.prod.yml up -d postgres

# Attendre que PostgreSQL soit prêt
docker-compose -f docker-compose.prod.yml exec postgres pg_isready

# Migrer les données existantes (si applicable)
docker-compose -f docker-compose.prod.yml run --rm api python src/migrate_to_postgres.py

# Initialiser les clés de chiffrement
docker-compose -f docker-compose.prod.yml run --rm api python src/fix_encryption_postgres.py

# Démarrer l'API
docker-compose -f docker-compose.prod.yml up -d api

# Vérifier les logs
docker-compose -f docker-compose.prod.yml logs -f api
```

### 3. Test de Persistence

```bash
# Tester la persistence après redémarrage
docker-compose -f docker-compose.prod.yml run --rm api python src/test_postgres_persistence.py

# Redémarrer l'API pour vérifier la récupération
docker-compose -f docker-compose.prod.yml restart api

# Vérifier que les messages sont toujours déchiffrables
curl -X GET http://localhost:8000/api/v1/messages/instagram
```

## 🔐 Fonctionnement du Chiffrement

### Phase 1: Initialisation
1. **Connexion** au serveur Matrix avec un `device_id` fixe
2. **Création/Chargement** du compte Olm (clés d'identité cryptographique)
3. **Synchronisation** pour découvrir les rooms chiffrées
4. **Partage des clés** Megolm avec toutes les rooms
5. **Trust automatique** des devices des bridges Instagram/Messenger
6. **Sauvegarde PostgreSQL** de toutes les clés

### Phase 2: Réception de Messages
1. Message Instagram arrive chiffré (MegolmEvent)
2. Récupération de la session Megolm depuis PostgreSQL
3. Déchiffrement avec la clé de session
4. Transmission au webhook en clair

### Phase 3: Après Redémarrage
1. **Chargement** du compte Olm depuis PostgreSQL
2. **Restauration** de toutes les sessions Megolm
3. **Récupération** des device keys et trust states
4. **Reprise** du token de synchronisation
5. **Déchiffrement** immédiat des nouveaux messages

## 📊 Tables PostgreSQL

```sql
-- Compte Olm (identité cryptographique)
accounts (
    id, user_id, device_id, account_data, shared, created_at, updated_at
)

-- Sessions Megolm (clés de déchiffrement des rooms)
megolm_inbound_sessions (
    id, account_id, room_id, session_id, sender_key,
    session_data, signing_keys, forwarding_chains, created_at
)

-- Clés des devices (trust relationships)
device_keys (
    id, account_id, user_id, device_id, keys,
    display_name, deleted, created_at
)

-- Sessions Olm (chiffrement 1-to-1)
olm_sessions (
    id, account_id, sender_key, session_id,
    session_data, creation_time, last_usage
)

-- Rooms chiffrées
encrypted_rooms (
    id, account_id, room_id, rotation_period, rotation_messages
)

-- Token de synchronisation
sync_tokens (
    id, account_id, token
)
```

## 🔄 Backup & Recovery

### Backup Automatique
Le docker-compose inclut un service de backup quotidien:
```bash
# Backup manuel
docker-compose -f docker-compose.prod.yml exec postgres \
    pg_dump -U matrix_user matrix_store > backup_$(date +%Y%m%d).sql

# Restauration
docker-compose -f docker-compose.prod.yml exec -T postgres \
    psql -U matrix_user matrix_store < backup_20240101.sql
```

### Points Critiques
- **JAMAIS** perdre la base PostgreSQL = perte définitive des clés
- **JAMAIS** changer le `device_id` = nouvelle session, nouvelles clés
- **TOUJOURS** faire des backups chiffrés des clés

## 🧪 Validation

### Tests Automatisés
```bash
# Suite complète
python src/test_postgres_persistence.py

# Tests unitaires
python -m pytest src/test_postgres_persistence.py::TestPostgresPersistence

# Tests d'intégration
python -m pytest src/test_postgres_persistence.py::TestIntegration
```

### Checklist Production
- [ ] PostgreSQL avec SSL/TLS activé
- [ ] Backups automatiques configurés
- [ ] Monitoring des métriques PostgreSQL
- [ ] Alerting sur les erreurs de déchiffrement
- [ ] Logs centralisés
- [ ] Health checks configurés
- [ ] Rate limiting sur l'API
- [ ] Authentification sur les endpoints sensibles

## 🐛 Troubleshooting

### Problème: Messages non déchiffrés
```bash
# Vérifier les clés en base
docker-compose exec postgres psql -U matrix_user matrix_store \
    -c "SELECT COUNT(*) FROM megolm_inbound_sessions;"

# Recharger les clés
docker-compose run --rm api python src/fix_encryption_postgres.py
```

### Problème: Connection PostgreSQL échoue
```bash
# Vérifier la connectivité
docker-compose exec api nc -zv postgres 5432

# Vérifier les credentials
docker-compose exec postgres psql -U matrix_user -d matrix_store
```

### Problème: Performance dégradée
```bash
# Analyser les requêtes lentes
docker-compose exec postgres psql -U matrix_user matrix_store \
    -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Reconstruire les index
docker-compose exec postgres psql -U matrix_user matrix_store \
    -c "REINDEX DATABASE matrix_store;"
```

## 📈 Monitoring

### Métriques Clés
- **Nombre de sessions Megolm** : Doit augmenter avec les nouvelles conversations
- **Taux de déchiffrement réussi** : Doit être > 99%
- **Temps de déchiffrement** : < 100ms par message
- **Taille base PostgreSQL** : ~1MB par 100 rooms chiffrées

### Requêtes de Monitoring
```sql
-- Sessions actives
SELECT COUNT(*) as total_sessions,
       COUNT(DISTINCT room_id) as rooms_with_keys
FROM megolm_inbound_sessions;

-- Activité récente
SELECT DATE(created_at) as day,
       COUNT(*) as new_sessions
FROM megolm_inbound_sessions
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY day DESC;

-- Santé du pool de connexions
SELECT state, COUNT(*)
FROM pg_stat_activity
WHERE datname = 'matrix_store'
GROUP BY state;
```

## 🚧 Limitations Connues

1. **Une seule instance API** par `device_id` (sinon conflits de sessions)
2. **Pas de rotation automatique** des clés Megolm (feature Matrix)
3. **Backup des clés** non chiffré par défaut (ajouter pgcrypto pour production)

## 📚 Ressources

- [Matrix Encryption Spec](https://spec.matrix.org/v1.2/client-server-api/#end-to-end-encryption)
- [nio Documentation](https://matrix-nio.readthedocs.io/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/encryption-options.html)

## ✅ Conclusion

Avec cette implémentation:
- ✅ Les clés de chiffrement survivent aux redémarrages
- ✅ Les messages Instagram/Messenger sont déchiffrables en permanence
- ✅ Le système est scalable et production-ready
- ✅ Les backups garantissent la récupération en cas de problème

La persistance PostgreSQL assure que votre API peut être redémarrée, mise à jour, ou migrée sans jamais perdre la capacité de déchiffrer les messages.