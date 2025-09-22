# 📚 Guide d'Intégration etke.cc

## 🎯 Vue d'ensemble

Cette nouvelle architecture utilise **etke.cc** comme service Matrix managé avec bridges Instagram/Messenger pré-configurés, simplifiant drastiquement l'infrastructure.

## 🏗️ Architecture Simplifiée

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Instagram API  │────▶│  etke.cc     │◀────│  Messenger  │
│   (Bridged)     │     │  Matrix      │     │  (Bridged)  │
└─────────────────┘     │  + Bridges   │     └─────────────┘
                        └──────┬───────┘
                               │
                        ┌──────▼───────┐
                        │  Votre API   │
                        │  (api_etke)  │
                        └──────┬───────┘
                               │
                        ┌──────▼───────┐
                        │ Votre Client │
                        └──────────────┘
```

## 🚀 Étapes de Configuration

### 1. Attendez la Confirmation etke.cc

Après votre commande, vous recevrez:
- URL de votre serveur Matrix (ex: `https://matrix.chalky.etke.host`)
- Identifiants de connexion
- Accès à l'interface d'administration

### 2. Configurez les Variables d'Environnement

Renommez et complétez le fichier `.env.etke`:

```bash
cp .env.etke .env
# Éditer .env avec vos identifiants etke.cc
```

### 3. Installez les Dépendances

```bash
pip install -r requirements.txt
```

### 4. Configuration des Bridges sur etke.cc

Via l'interface admin etke.cc:

1. **Instagram Bridge**:
   - Naviguez vers la section Bridges
   - Activez mautrix-meta pour Instagram
   - Connectez avec: `chalky_booking` / `&B!4tsoD&LLYjHbbXL`

2. **Messenger Bridge**:
   - Même processus pour Facebook Messenger
   - Utilisez vos identifiants Facebook

### 5. Démarrez l'API

```bash
# Mode développement
python src/api_etke.py

# Mode production
uvicorn src.api_etke:app --host 0.0.0.0 --port 8000
```

## 📡 Endpoints API Disponibles

### Health & Status
- `GET /api/v1/health` - État de l'API
- `GET /api/v1/version` - Version de l'API
- `GET /api/v1/test` - Test de connexion

### Messages
- `GET /api/v1/messages/instagram` - Messages Instagram
- `GET /api/v1/messages/messenger` - Messages Messenger
- `POST /api/v1/send` - Envoyer un message
- `GET /api/v1/sync` - Synchroniser nouveaux messages

### Conversations
- `GET /api/v1/rooms` - Liste des conversations
- `GET /api/v1/threads/{platform}` - Threads par plateforme
- `GET /api/v1/threads/{platform}/{room_id}/messages` - Messages d'un thread

### Webhook
- `POST /api/v1/webhook/setup` - Configurer écoute temps réel

## 🔧 Exemple d'Utilisation

### Récupérer les Messages Instagram

```python
import requests

# Récupérer les messages
response = requests.get("http://localhost:8000/api/v1/messages/instagram")
messages = response.json()

for msg in messages["messages"]:
    print(f"{msg['sender']}: {msg['content']}")
```

### Envoyer un Message

```python
# Envoyer vers Instagram
payload = {
    "room_id": "!abc123:matrix.chalky.etke.host",
    "message": "Bonjour depuis l'API!",
    "platform": "instagram"
}

response = requests.post(
    "http://localhost:8000/api/v1/send",
    json=payload
)
```

### Synchronisation Continue

```python
import asyncio
from etke_matrix_client import EtkeMatrixClient

async def sync_loop():
    client = EtkeMatrixClient()
    await client.connect()

    while True:
        result = await client.sync_new_messages()
        if result["success"]:
            # Traiter les nouveaux messages
            for msg in result["messages"]["instagram"]:
                print(f"Nouveau message Instagram: {msg['content']}")

        await asyncio.sleep(30)  # Sync toutes les 30 secondes

asyncio.run(sync_loop())
```

## ⚙️ Configuration Avancée

### Webhook pour Messages Temps Réel

1. Configurez votre URL ngrok:
```bash
ngrok http 8001  # Port pour votre webhook listener
```

2. Activez le webhook dans l'API:
```python
POST /api/v1/webhook/setup
```

3. Les messages seront automatiquement forwarded vers votre webhook.

### Filtrage des Messages

Le client Matrix peut filtrer par:
- Plateforme (Instagram/Messenger)
- Room ID spécifique
- Expéditeur
- Période temporelle

## 🔍 Debugging

### Logs Détaillés

```python
# Dans etke_matrix_client.py
from loguru import logger

logger.add("debug.log", level="DEBUG")
```

### Test de Connexion

```bash
curl http://localhost:8000/api/v1/test
```

### Vérifier les Rooms

```bash
curl http://localhost:8000/api/v1/rooms
```

## 🛡️ Sécurité

1. **Ne jamais committer** `.env` avec vos identifiants
2. **Utiliser HTTPS** en production
3. **Limiter les accès** API avec authentification
4. **Chiffrer** les tokens en base de données

## 📊 Avantages de cette Architecture

✅ **Infrastructure Simplifiée**
- Plus de Docker local
- Plus de configuration bridge complexe
- Maintenance automatique par etke.cc

✅ **Fiabilité Accrue**
- Serveurs Hetzner haute disponibilité
- Monitoring intégré
- Backups automatiques

✅ **Développement Rapide**
- Focus sur la logique métier
- API simple et claire
- Bridges pré-configurés

## 🆘 Support

- **etke.cc Support**: Via leur interface admin
- **Matrix Community**: #matrix:matrix.org
- **Votre Code**: Issues sur ce repo

## 🔄 Migration depuis l'Ancienne Architecture

Si vous migrez depuis l'architecture Docker locale:

1. Exportez vos données existantes
2. Désactivez les containers Docker
3. Pointez vers etke.cc
4. Importez vos données via l'API Matrix

---

**Note**: Une fois vos identifiants etke.cc reçus, mettez à jour `.env` et vous êtes prêt à démarrer!