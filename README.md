# 🌉 Matrix Bridge API - Instagram/Messenger via etke.cc

API de pont entre Instagram/Messenger et Matrix via le service managé etke.cc, avec persistence PostgreSQL des clés de chiffrement.

## 🚀 Fonctionnalités

- ✅ **Connexion Instagram/Messenger** via bridges Matrix etke.cc
- ✅ **Déchiffrement automatique** des messages MegolmEvent
- ✅ **Persistence PostgreSQL** des clés de chiffrement
- ✅ **API REST FastAPI** avec documentation Swagger
- ✅ **Webhook configurable** pour recevoir les messages déchiffrés
- ✅ **Déployable sur Clever Cloud** avec scaling automatique

## 🏗️ Architecture

```
Instagram/Messenger
        ↓
   etke.cc Matrix
   (Messages chiffrés)
        ↓
ProductionMatrixClient
    PostgreSQL Store
        ↓
    Webhook/API
  (Messages déchiffrés)
```

## 📋 Prérequis

- Python 3.11+
- PostgreSQL 15+ (ou addon Clever Cloud)
- Compte etke.cc avec bridges Instagram/Messenger configurés
- ngrok pour les webhooks locaux (développement)

## 🔧 Installation

### Développement Local

```bash
# Cloner le repository
git clone https://github.com/chalky-fr/matrix-bridge-api.git
cd matrix-bridge-api

# Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.etke .env
# Éditer .env avec vos credentials etke.cc

# Lancer l'API
python src/api_etke.py
```

### Docker

```bash
# Démarrer avec Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# Initialiser les clés de chiffrement
docker-compose -f docker-compose.prod.yml run --rm api python src/fix_encryption_postgres.py

# Vérifier le statut
curl http://localhost:8000/api/v1/health
```

## ☁️ Déploiement sur Clever Cloud

### Déploiement Rapide (5 minutes)

```bash
# 1. Installer Clever CLI
npm install -g clever-tools

# 2. Se connecter et créer l'app
clever login
clever create --type python --org "Chalky" matrix-bridge-api

# 3. Créer PostgreSQL addon
clever addon create postgresql-addon --plan s --org "Chalky" matrix-postgres
clever service link-addon matrix-postgres

# 4. Configurer les variables
clever env set ETKE_PASSWORD "votre_password"
clever env set WEBHOOK_URL "https://votre-webhook.com"

# 5. Déployer
git push clever master
```

Voir [CLEVER_CLOUD_DEPLOYMENT.md](CLEVER_CLOUD_DEPLOYMENT.md) pour le guide complet.

## 🔑 Variables d'Environnement

| Variable | Description | Requis |
|----------|-------------|---------|
| `ETKE_HOMESERVER` | URL du serveur Matrix etke.cc | ✅ |
| `ETKE_USERNAME` | Username Matrix (@user:domain) | ✅ |
| `ETKE_PASSWORD` | Mot de passe Matrix | ✅ |
| `DATABASE_URL` | URL PostgreSQL (auto sur Clever Cloud) | ✅ |
| `WEBHOOK_URL` | URL pour recevoir les messages | ❌ |
| `USE_POSTGRES_STORE` | Activer PostgreSQL (true/false) | ❌ |

## 📚 API Endpoints

### Messaging
- `GET /api/v1/health` - Health check
- `GET /api/v1/messages/{platform}` - Récupérer les messages (instagram/messenger)
- `POST /api/v1/send` - Envoyer un message
- `GET /api/v1/sync` - Synchroniser les messages

### Conversations
- `GET /api/v1/rooms` - Liste des conversations
- `GET /api/v1/threads/{platform}` - Threads par plateforme

### Configuration
- `POST /api/v1/webhook/setup` - Configurer le webhook
- `GET /api/v1/webhook/status` - Statut du webhook
- `GET /api/v1/encryption/status` - Statut du chiffrement

Documentation Swagger disponible sur `/docs`

## 🧪 Tests

```bash
# Lancer les tests de persistence PostgreSQL
./run_postgres_tests.sh --docker

# Test manuel de déchiffrement
python src/test_postgres_persistence.py
```

## 🔐 Sécurité

- **Chiffrement E2E** : Messages chiffrés via Matrix Megolm
- **Persistence sécurisée** : Clés stockées avec pickle_key
- **HTTPS** : Automatique sur Clever Cloud
- **Variables d'environnement** : Secrets jamais dans le code

## 📖 Documentation

- [PRODUCTION_QUICKSTART.md](PRODUCTION_QUICKSTART.md) - Guide de démarrage rapide
- [CLEVER_CLOUD_DEPLOYMENT.md](CLEVER_CLOUD_DEPLOYMENT.md) - Déploiement Clever Cloud
- [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) - Guide production complet
- [POSTGRES_TEST_SUMMARY.md](POSTGRES_TEST_SUMMARY.md) - Tests PostgreSQL

## 🤝 Contribution

Les contributions sont bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## 📄 Licence

MIT

## 👥 Équipe

Développé par [Chalky](https://chalky.fr)

---

**Status**: ✅ Production Ready | PostgreSQL Persistence | Clever Cloud Compatible