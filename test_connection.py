#!/usr/bin/env python3
"""
Test de connexion simple à etke.cc Matrix
Sans dépendances FastAPI/Pydantic
"""
import asyncio
import os
from nio import AsyncClient, LoginError
from dotenv import load_dotenv

async def test_connection():
    # Charger les variables d'environnement
    load_dotenv()

    homeserver = os.getenv("ETKE_HOMESERVER", "https://matrix.chalky.etke.host")
    username = os.getenv("ETKE_USERNAME", "@florent:chalky.etke.host")
    password = os.getenv("ETKE_PASSWORD")

    if not password:
        print("❌ Mot de passe manquant dans .env")
        return False

    print(f"📡 Connexion à {homeserver}")
    print(f"👤 Utilisateur: {username}")

    client = AsyncClient(homeserver, username)

    try:
        # Tentative de connexion
        print("🔄 Connexion en cours...")
        response = await client.login(password)

        if isinstance(response, LoginError):
            print(f"❌ Erreur de connexion: {response.message}")
            return False

        print(f"✅ Connexion réussie!")
        print(f"🔑 Access token: {response.access_token[:20]}...")
        print(f"🆔 Device ID: {response.device_id}")

        # Récupérer les rooms
        await client.sync(timeout=10000)

        print(f"\n📊 Rooms trouvées: {len(client.rooms)}")

        # Lister les rooms
        for room_id, room in client.rooms.items():
            print(f"  • {room.display_name or 'Sans nom'} ({room_id})")

            # Identifier les bridges
            if "instagram" in room.display_name.lower() if room.display_name else False:
                print(f"    → Bridge Instagram détecté")
            elif "messenger" in room.display_name.lower() if room.display_name else False:
                print(f"    → Bridge Messenger détecté")

        # Déconnexion
        await client.logout()
        await client.close()

        return True

    except Exception as e:
        print(f"❌ Erreur: {e}")
        await client.close()
        return False

if __name__ == "__main__":
    print("=== Test de connexion etke.cc Matrix ===\n")
    result = asyncio.run(test_connection())

    if result:
        print("\n✅ Test réussi! L'API peut maintenant se connecter à etke.cc")
        print("\n📝 Prochaines étapes:")
        print("1. Configurer les bridges Instagram/Messenger via https://matrix.chalky.etke.host/admin")
        print("2. Se connecter avec les credentials Instagram dans le bridge")
        print("3. Lancer l'API avec: python3 src/api_etke.py")
    else:
        print("\n❌ Test échoué. Vérifiez les credentials dans .env")