#!/bin/bash

# Script de test complet pour l'API etke.cc
# Usage: ./test_api.sh [commande]

API_BASE="http://localhost:8000/api/v1"

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Fonction pour afficher les titres
print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Fonction pour afficher les commandes
print_command() {
    echo -e "${YELLOW}➤ $1${NC}"
}

# Fonction pour faire un curl avec formattage
api_call() {
    local method=${1:-GET}
    local endpoint=$2
    local data=$3

    if [ "$method" = "POST" ] && [ -n "$data" ]; then
        curl -s -X POST "$API_BASE$endpoint" \
             -H "Content-Type: application/json" \
             -d "$data" | python3 -m json.tool
    else
        curl -s "$API_BASE$endpoint" | python3 -m json.tool
    fi
}

# Test complet de l'API
test_all() {
    print_section "🔍 DIAGNOSTIC API"

    print_command "Health Check"
    api_call GET "/health"

    print_command "Version"
    api_call GET "/version"

    print_command "Test connexion"
    api_call GET "/test"

    print_section "📋 ROOMS & CONVERSATIONS"

    print_command "Toutes les rooms"
    api_call GET "/rooms"

    print_command "Threads Instagram"
    api_call GET "/threads/instagram"

    print_command "Threads Messenger"
    api_call GET "/threads/messenger"

    print_section "📨 MESSAGES"

    print_command "Messages Instagram (limit 10)"
    api_call GET "/messages/instagram?limit=10"

    print_command "Messages Messenger (limit 10)"
    api_call GET "/messages/messenger?limit=10"

    print_section "📤 TEST ENVOI"

    print_command "Envoi message Instagram (Flo Chalky)"
    local test_message="Test API $(date '+%H:%M:%S') 🤖"
    api_call POST "/send" '{
        "room_id": "!GHTWDcxXouPfkhMVqy:chalky.etke.host",
        "content": "'"$test_message"'",
        "message_type": "m.text"
    }'

    print_section "🔄 SYNCHRONISATION"

    print_command "Sync nouveaux messages"
    api_call GET "/sync"
}

# Test messages d'une room spécifique
test_room_messages() {
    local platform=$1
    local room_id=$2
    local limit=${3:-20}

    if [ -z "$platform" ] || [ -z "$room_id" ]; then
        echo -e "${RED}Usage: $0 room <platform> <room_id> [limit]${NC}"
        echo "Exemple: $0 room instagram '!GHTWDcxXouPfkhMVqy:chalky.etke.host'"
        return 1
    fi

    print_section "📨 MESSAGES DE LA ROOM"
    echo -e "Platform: ${CYAN}$platform${NC}"
    echo -e "Room ID: ${CYAN}$room_id${NC}"
    echo -e "Limit: ${CYAN}$limit${NC}"

    api_call GET "/threads/$platform/$room_id/messages?limit=$limit"
}

# Envoyer un message
send_message() {
    local platform=$1
    local room_id=$2
    local message=$3

    if [ -z "$platform" ] || [ -z "$room_id" ] || [ -z "$message" ]; then
        echo -e "${RED}Usage: $0 send <platform> <room_id> '<message>'${NC}"
        echo "Exemple: $0 send instagram '!GHTWDcxXouPfkhMVqy:chalky.etke.host' 'Hello!'"
        return 1
    fi

    print_section "📤 ENVOI MESSAGE"
    echo -e "Platform: ${CYAN}$platform${NC}"
    echo -e "Room ID: ${CYAN}$room_id${NC}"
    echo -e "Message: ${CYAN}$message${NC}"

    api_call POST "/send" '{
        "room_id": "'"$room_id"'",
        "content": "'"$message"'",
        "message_type": "m.text"
    }'
}

# Lister les rooms avec IDs
list_rooms() {
    print_section "📋 LISTE DES ROOMS AVEC IDs"

    echo -e "${PURPLE}🔍 Récupération des rooms...${NC}"
    local rooms_data=$(curl -s "$API_BASE/rooms")

    echo -e "\n${GREEN}📷 ROOMS INSTAGRAM:${NC}"
    echo "$rooms_data" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for i, room in enumerate(data['rooms']['instagram'], 1):
    print(f'{i}. {room[\"name\"]}')
    print(f'   ID: {room[\"room_id\"]}')
    print()
"

    echo -e "${GREEN}💬 ROOMS MESSENGER:${NC}"
    echo "$rooms_data" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for i, room in enumerate(data['rooms']['messenger'], 1):
    print(f'{i}. {room[\"name\"]}')
    print(f'   ID: {room[\"room_id\"]}')
    print()
"
}

# Raccourcis pour les rooms principales
flo_messages() {
    local limit=${1:-20}
    print_section "📨 MESSAGES FLO CHALKY (Instagram)"
    test_room_messages "instagram" "!GHTWDcxXouPfkhMVqy:chalky.etke.host" "$limit"
}

antonin_messages() {
    local limit=${1:-20}
    print_section "📨 MESSAGES ANTONIN (Instagram)"
    test_room_messages "instagram" "!HBeUMtwsIJtzIlXljT:chalky.etke.host" "$limit"
}

send_to_flo() {
    local message=$1
    if [ -z "$message" ]; then
        echo -e "${RED}Usage: $0 flo '<message>'${NC}"
        return 1
    fi
    send_message "instagram" "!GHTWDcxXouPfkhMVqy:chalky.etke.host" "$message"
}

# Affichage de l'aide
show_help() {
    echo -e "${GREEN}🚀 Script de test API etke.cc${NC}"
    echo
    echo -e "${YELLOW}USAGE:${NC}"
    echo "  $0 [commande] [arguments]"
    echo
    echo -e "${YELLOW}COMMANDES:${NC}"
    echo -e "  ${CYAN}test${NC}                     - Test complet de l'API"
    echo -e "  ${CYAN}rooms${NC}                    - Lister toutes les rooms avec IDs"
    echo -e "  ${CYAN}room <platform> <room_id> [limit]${NC} - Messages d'une room spécifique"
    echo -e "  ${CYAN}send <platform> <room_id> '<message>'${NC} - Envoyer un message"
    echo
    echo -e "${YELLOW}RACCOURCIS:${NC}"
    echo -e "  ${CYAN}flo [limit]${NC}              - Messages de Flo Chalky (Instagram)"
    echo -e "  ${CYAN}antonin [limit]${NC}          - Messages d'Antonin (Instagram)"
    echo -e "  ${CYAN}flo '<message>'${NC}          - Envoyer message à Flo"
    echo
    echo -e "${YELLOW}ENDPOINTS DIRECTS:${NC}"
    echo -e "  ${CYAN}health${NC}                   - Health check"
    echo -e "  ${CYAN}version${NC}                  - Version API"
    echo -e "  ${CYAN}sync${NC}                     - Synchroniser messages"
    echo -e "  ${CYAN}stream${NC}                   - Stream temps réel (SSE)"
    echo -e "  ${CYAN}webhook setup <url>${NC}     - Configurer webhook"
    echo -e "  ${CYAN}webhook status${NC}           - Statut du webhook"
    echo -e "  ${CYAN}webhook disable${NC}          - Désactiver webhook"
    echo
    echo -e "${YELLOW}EXEMPLES:${NC}"
    echo "  $0 test                          # Test complet"
    echo "  $0 rooms                         # Lister rooms"
    echo "  $0 flo 10                        # 10 derniers messages Flo"
    echo "  $0 flo 'Salut!'                  # Envoyer à Flo"
    echo "  $0 room instagram '!GHT...' 15   # 15 messages d'une room"
    echo "  $0 webhook setup https://yourapp.com/webhook  # Configurer webhook"
}

# Router principal
case ${1:-help} in
    "test"|"all")
        test_all
        ;;
    "rooms"|"list")
        list_rooms
        ;;
    "room"|"messages")
        test_room_messages "$2" "$3" "$4"
        ;;
    "send")
        send_message "$2" "$3" "$4"
        ;;
    "flo")
        if [[ "$2" =~ ^[0-9]+$ ]]; then
            flo_messages "$2"
        else
            send_to_flo "$2"
        fi
        ;;
    "health")
        api_call GET "/health"
        ;;
    "version")
        api_call GET "/version"
        ;;
    "sync")
        api_call GET "/sync"
        ;;
    "stream")
        print_section "🔥 STREAMING TEMPS RÉEL"
        echo -e "${YELLOW}➤ Connexion au stream (Ctrl+C pour arrêter)${NC}"
        curl -N "$API_BASE/stream"
        ;;
    "webhook")
        action=$2
        url=$3
        case $action in
            "setup")
                if [ -z "$url" ]; then
                    echo -e "${RED}Usage: $0 webhook setup <url>${NC}"
                    echo "Exemple: $0 webhook setup https://yourapp.com/webhook"
                    return 1
                fi
                print_section "🪝 CONFIGURATION WEBHOOK"
                echo -e "URL: ${CYAN}$url${NC}"
                api_call POST "/webhook/setup" '{
                    "webhook_url": "'"$url"'",
                    "platforms": ["instagram", "messenger"],
                    "enabled": true
                }'
                ;;
            "status")
                print_section "🔍 STATUT WEBHOOK"
                api_call GET "/webhook/status"
                ;;
            "disable")
                print_section "❌ DÉSACTIVER WEBHOOK"
                curl -s -X DELETE "$API_BASE/webhook" | python3 -m json.tool
                ;;
            *)
                echo -e "${RED}Usage: $0 webhook <setup|status|disable> [url]${NC}"
                echo "Exemples:"
                echo "  $0 webhook setup https://yourapp.com/webhook"
                echo "  $0 webhook status"
                echo "  $0 webhook disable"
                ;;
        esac
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        echo -e "${RED}Commande inconnue: $1${NC}"
        show_help
        exit 1
        ;;
esac
