# CLAUDE.md - API Bridge Matrix via etke.cc

## Objectif Principal
API simplifiée pour connecter Instagram et Messenger via le service managé etke.cc et ses bridges pré-configurés, sans utiliser les API officielles Instagram/Meta.

## Architecture avec etke.cc

### Service Matrix Managé
- **Type** : etke.cc avec bridges mautrix-meta pré-configurés
- **Hébergement** : Cloud managé etke.cc (Hetzner)
- **Statut** : ✅ Actif et opérationnel
- **URL** : https://matrix.chalky.etke.host
- **Admin Panel** : https://matrix.chalky.etke.host/admin
- **Element Web** : https://element.chalky.etke.host

### Credentials Matrix
- **Matrix ID** : @florent:chalky.etke.host
- **Username** : florent
- **Password** : Configuré dans .env

### Bridges Disponibles
#### Instagram Bridge
- **Bot** : @instagrambot:chalky.etke.host
- **Handle** : chalky_booking
- **Password** : &B!4tsoD&LLYjHbbXL

#### Messenger Bridge
- **Bot** : @messengerbot:chalky.etke.host

#### WhatsApp Bridge
- **Bot** : @whatsappbot:chalky.etke.host

### Contraintes
- ❌ **INTERDIT** : API Instagram/Meta directes
- ✅ **OBLIGATOIRE** : Utiliser etke.cc bridges
- ✅ **OBLIGATOIRE** : Matrix Client-Server API

### Development
- **Webhook URL** : https://bicicouriers.eu.ngrok.io

## Spécifications API

### Endpoints Principaux
#### Messaging
- `POST /api/v1/send` - Envoi de message
- `GET /api/v1/sync` - Synchronisation des messages
- `GET /api/v1/messages/instagram` - Messages Instagram
- `GET /api/v1/messages/messenger` - Messages Messenger

#### Conversations
- `GET /api/v1/rooms` - Liste des conversations
- `GET /api/v1/threads/{platform}` - Threads par plateforme
- `GET /api/v1/threads/{platform}/{room_id}/messages` - Messages d'un thread

#### System
- `GET /api/v1/health` - Health check
- `GET /api/v1/version` - Version API
- `GET /api/v1/test` - Test connexion

### Format des Données
- **Input/Output** : JSON
- **Authentification** : Via etke.cc Matrix
- **Erreurs** : Format JSON standardisé

## Stack Technique

### Technologies
- **Runtime** : Python 3.8+
- **Framework** : FastAPI
- **Matrix SDK** : matrix-nio
- **Service** : etke.cc (bridges managés)

### Architecture Simplifiée
```
Instagram/Messenger → etke.cc Bridges → Matrix Server → API Python → Client
```

### Fichiers Essentiels
- `src/etke_matrix_client.py` - Client Matrix pour etke.cc
- `src/api_etke.py` - API REST FastAPI
- `.env.etke` - Configuration (à renommer en .env)
- `ETKE_INTEGRATION.md` - Documentation

## Démarrage Rapide

1. **Configurer .env** avec identifiants etke.cc (✅ Fait)
2. **Installer dépendances** : `pip install -r requirements.txt`
3. **Installer dépendances** : `pip install fastapi uvicorn matrix-nio loguru python-dotenv`
4. **Lancer API** : `python src/api_etke.py`
5. **Configurer bridges** via interface admin etke.cc

## Notes
- Bridges gérés par etke.cc (pas de configuration locale)
- Toutes les interactions via Matrix Client-Server API
- Respect ToS Instagram/Messenger via bridges officiels
