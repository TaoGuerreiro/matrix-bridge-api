#!/usr/bin/env python3
"""
Serveur de test simple pour recevoir et afficher les webhooks
"""
from fastapi import FastAPI, Request
from datetime import datetime
import uvicorn
import json

app = FastAPI(title="Webhook Test Server")

# Stockage des webhooks reçus
received_webhooks = []

@app.post("/webhooks/instagram")
async def receive_instagram_webhook(request: Request):
    """Recevoir les webhooks Instagram"""
    try:
        # Récupérer le body JSON
        body = await request.json()

        # Ajouter timestamp de réception
        webhook_data = {
            "received_at": datetime.now().isoformat(),
            "headers": dict(request.headers),
            "body": body
        }

        received_webhooks.append(webhook_data)

        # Afficher dans la console
        print(f"\n🔔 WEBHOOK REÇU à {webhook_data['received_at']}")
        print(f"📱 Platform: {body.get('platform', 'unknown')}")
        print(f"👤 Sender: {body.get('sender', 'unknown')}")
        print(f"💬 Message: {body.get('message', 'no message')}")
        print(f"🏠 Room: {body.get('room_name', 'unknown')}")
        print(f"📄 Full data: {json.dumps(body, indent=2)}")
        print("-" * 50)

        return {"status": "received", "timestamp": webhook_data['received_at']}

    except Exception as e:
        print(f"❌ Erreur webhook: {e}")
        return {"error": str(e)}, 500

@app.get("/webhooks/history")
async def get_webhook_history():
    """Voir l'historique des webhooks reçus"""
    return {
        "total": len(received_webhooks),
        "webhooks": received_webhooks[-10:]  # Derniers 10
    }

@app.get("/webhooks/count")
async def get_webhook_count():
    """Compter les webhooks reçus"""
    return {
        "total_received": len(received_webhooks),
        "last_received": received_webhooks[-1]["received_at"] if received_webhooks else None
    }

@app.delete("/webhooks/clear")
async def clear_webhook_history():
    """Vider l'historique"""
    global received_webhooks
    count = len(received_webhooks)
    received_webhooks = []
    return {"cleared": count}

if __name__ == "__main__":
    print("🚀 Démarrage du serveur de test webhook...")
    print("📡 URL de test: http://localhost:8001/webhooks/instagram")
    print("📊 Historique: http://localhost:8001/webhooks/history")
    print("🔢 Compteur: http://localhost:8001/webhooks/count")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")