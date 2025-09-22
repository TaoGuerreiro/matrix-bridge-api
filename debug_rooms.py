#!/usr/bin/env python3
"""
Script de diagnostic pour vérifier les rooms Matrix et les bridges
"""
import asyncio
import os
from nio import AsyncClient, RoomMessage, Event
from dotenv import load_dotenv

async def debug_matrix_rooms():
    load_dotenv()

    homeserver = os.getenv("ETKE_HOMESERVER")
    username = os.getenv("ETKE_USERNAME")
    password = os.getenv("ETKE_PASSWORD")

    print(f"🔍 Diagnostic Matrix pour {username}")
    print(f"🏠 Serveur: {homeserver}\n")

    client = AsyncClient(homeserver, username)

    try:
        # Connexion
        response = await client.login(password)
        print(f"✅ Connexion réussie")

        # Synchronisation initiale
        print("🔄 Synchronisation initiale...")
        await client.sync(timeout=30000)

        print(f"\n📊 Analyse des rooms:")
        print(f"   Total rooms: {len(client.rooms)}")

        if len(client.rooms) == 0:
            print("❌ Aucune room trouvée")
            print("\n🔍 Vérifications à faire:")
            print("1. Les bridges Instagram/Messenger sont-ils correctement configurés?")
            print("2. Avez-vous envoyé des messages depuis Instagram/Messenger?")
            print("3. Les bridges ont-ils créé des rooms automatiquement?")
            print("\n💡 Solutions:")
            print("- Allez sur https://matrix.chalky.etke.host/admin")
            print("- Vérifiez l'état des bridges dans l'interface admin")
            print("- Envoyez un message test depuis Instagram/Messenger")
            print("- Rejoignez manuellement les rooms des bridges:")
            print("  • Tapez: !instagram dans un DM avec @instagrambot:chalky.etke.host")
            print("  • Tapez: !messenger dans un DM avec @messengerbot:chalky.etke.host")
            return

        # Analyser chaque room
        for room_id, room in client.rooms.items():
            print(f"\n🏠 Room: {room_id}")
            print(f"   Nom: {room.display_name or 'Sans nom'}")
            print(f"   Topic: {room.topic or 'Pas de topic'}")
            print(f"   Membres: {len(room.users) if hasattr(room, 'users') else 'Inconnu'}")
            print(f"   Canonical alias: {room.canonical_alias or 'Aucun'}")

            # Identifier les bridges
            bridge_type = "inconnu"
            if any(keyword in (room.display_name or "").lower()
                   for keyword in ["instagram", "ig"]):
                bridge_type = "instagram"
            elif any(keyword in (room.display_name or "").lower()
                     for keyword in ["messenger", "facebook", "fb"]):
                bridge_type = "messenger"
            elif "@instagrambot:" in str(room.users):
                bridge_type = "instagram (bot détecté)"
            elif "@messengerbot:" in str(room.users):
                bridge_type = "messenger (bot détecté)"

            print(f"   Type détecté: {bridge_type}")

            # Récupérer quelques messages récents
            try:
                # Limiter à 5 messages pour le diagnostic
                response = await client.room_messages(room_id, start="", limit=5)
                if hasattr(response, 'chunk'):
                    print(f"   Messages récents: {len(response.chunk)}")
                    for event in response.chunk[:3]:  # Afficher max 3 messages
                        if hasattr(event, 'body') and hasattr(event, 'sender'):
                            print(f"     • {event.sender}: {event.body[:50]}...")
                else:
                    print(f"   Messages: Impossible de récupérer")
            except Exception as e:
                print(f"   Messages: Erreur - {e}")

        print(f"\n📝 Résumé:")
        instagram_rooms = [r for r in client.rooms.values()
                          if "instagram" in (r.display_name or "").lower()]
        messenger_rooms = [r for r in client.rooms.values()
                          if "messenger" in (r.display_name or "").lower()]

        print(f"   Rooms Instagram détectées: {len(instagram_rooms)}")
        print(f"   Rooms Messenger détectées: {len(messenger_rooms)}")

        # Instructions pour activer les bridges
        if len(instagram_rooms) == 0 and len(messenger_rooms) == 0:
            print("\n🚀 Pour activer les bridges:")
            print("1. Allez sur https://matrix.chalky.etke.host/admin")
            print("2. Vérifiez que les bridges sont 'Running'")
            print("3. Créez des conversations avec les bots:")
            print("   - Démarrez un chat avec @instagrambot:chalky.etke.host")
            print("   - Envoyez: login")
            print("   - Suivez les instructions")

    except Exception as e:
        print(f"❌ Erreur: {e}")
    finally:
        await client.logout()
        await client.close()

if __name__ == "__main__":
    asyncio.run(debug_matrix_rooms())