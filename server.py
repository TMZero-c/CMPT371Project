import socket
import threading
import json
import random
import math
import time

with open("message_protocol.json", "r") as f:
    MESSAGE_TYPES = json.load(f)

clients = {}           # socket -> player_name
ready_clients = set()  # set of sockets that are ready
clients_room_ids = {}  # socket -> current room identifier

# New: separate lobby list; game rooms will be stored in "rooms"
lobby_clients = []     # list of sockets currently in the lobby
rooms = {}             # room_id (int) -> list of sockets

impostor_for_game = None
game_stage = 0

lock = threading.Lock()
ready_lock = threading.Lock()

topicList = ["food", "cars", "anime", "movies", "school", "trains", "shervin", "IEEE", 
             "the state of vancouver's economy in chinese", "clothing", "canada", "computer parts", "games", "art"]

def create_message(message_type, **kwargs):
    message = {"type": message_type}
    for field in MESSAGE_TYPES[message_type]["fields"]:
        message[field] = kwargs.get(field)
    return json.dumps(message).encode()

def parse_message(data):
    try:
        return json.loads(data.decode())
    except Exception as e:
        return None

def broadcast(message, exclude=None):
    for client in list(clients):
        if client != exclude:
            try:
                client.send(message)
            except:
                client.close()
                clients.pop(client, None)

def lobby_broadcast(message, exclude=None):
    for client in list(lobby_clients):
        if client != exclude:
            try:
                client.send(message)
            except:
                client.close()
                if client in lobby_clients:
                    lobby_clients.remove(client)

def room_broadcast(msg, room_id, sender):
    if room_id in rooms:
        for c in rooms[room_id]:
            if c != sender:
                try:
                    c.send(msg)
                except:
                    c.close()
                    rooms[room_id].remove(c)

def handle_client(conn, addr):
    global impostor_for_game
    player_name = None
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            message = parse_message(data)
            if not message:
                continue

            msg_type = message["type"]
            if msg_type == "JOIN_ROOM":
                with lock:
                    if conn not in clients:
                        player_name = message["player_name"]
                        clients[conn] = player_name
                        # Automatically add to lobby on join
                        lobby_clients.append(conn)
                        clients_room_ids[conn] = "lobby"
                        conn.send(create_message("LOBBY_JOINED", 
                                                  message=f"Welcome to the lobby, {player_name}!"))
                        broadcast(create_message("INFO", message=f"{player_name} joined."), exclude=conn)

            elif msg_type == "JOIN_LOBBY":
                with lock:
                    # If the client is in a game room, remove them from that room
                    current_room = clients_room_ids.get(conn)
                    if isinstance(current_room, int):  
                        if current_room in rooms and conn in rooms[current_room]:
                            rooms[current_room].remove(conn)
                    # Add them to lobby if not already there
                    if conn not in lobby_clients:
                        lobby_clients.append(conn)
                    clients_room_ids[conn] = "lobby"
                    conn.send(create_message("LOBBY_JOINED", message="You have rejoined the lobby."))

            elif msg_type == "READY":
                with ready_lock:
                    ready_clients.add(conn)
                    broadcast(create_message("INFO", message=f"{clients[conn]} is ready."))
                    if len(ready_clients) == len(clients):
                        threading.Thread(target=start_game, daemon=True).start()

            elif msg_type == "JOIN_SPECIFIC_ROOM":
                room_id = message.get("room_id")
                if not isinstance(room_id, int):
                    conn.send(create_message("INFO", message="Invalid room number."))
                    continue
                with lock:
                    # Remove from lobby if in it
                    if conn in lobby_clients:
                        lobby_clients.remove(conn)
                    # Place the client in the requested game room
                    if room_id not in rooms:
                        rooms[room_id] = []
                    if len(rooms[room_id]) >= 2:
                        conn.send(create_message("INFO", message="Room is full. Choose another."))
                    else:
                        rooms[room_id].append(conn)
                        clients_room_ids[conn] = room_id
                        conn.send(create_message("INFO", message=f"Joined room {room_id}"))

            elif msg_type == "CHAT":
                # Determine where to broadcast based on the client's room setting.
                room_id = clients_room_ids.get(conn)
                content = message.get("message")
                sender = clients.get(conn, "Unknown")
                if room_id == "lobby":
                    lobby_broadcast(create_message("INFO", message=f"{sender}: {content}"), conn)
                elif isinstance(room_id, int):
                    room_broadcast(create_message("INFO", message=f"{sender}: {content}"), room_id, conn)
                else:
                    conn.send(create_message("INFO", message="You're not in a valid room."))

            elif msg_type == "VOTE":
                sender = clients.get(conn, "Unknown")
                broadcast(create_message("INFO", message=f"{sender} voted."))

            elif msg_type == "PING":
                conn.send(create_message("PONG"))

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        with lock:
            if conn in clients:
                left_name = clients.pop(conn)
                ready_clients.discard(conn)
                # Remove from lobby if present
                if conn in lobby_clients:
                    lobby_clients.remove(conn)
                # Also, if part of a game room, remove from that room
                current_room = clients_room_ids.get(conn)
                if isinstance(current_room, int) and current_room in rooms and conn in rooms[current_room]:
                    rooms[current_room].remove(conn)
                broadcast(create_message("INFO", message=f"{left_name} has disconnected."), exclude=conn)
        conn.close()

def start_game():
    global impostor_for_game, game_stage
    game_stage = 1
    print("[GAME] Starting")
    topic = random.choice(topicList)
    impostor_for_game = random.choice(list(clients.keys()))

    broadcast_except_one(topic, impostor_for_game)
    broadcast(create_message("GAME_STARTED", players=list(clients.values())))

    # Ask each player to choose a room number
    max_rooms = math.ceil(len(clients) / 2)
    for conn in clients:
        conn.send(create_message("INFO", message=f"Choose a room number (1 to {max_rooms}) with command: vote <room_number>"))

def broadcast_except_one(common_msg, impostor):
    for client in list(clients):
        try:
            if client == impostor:
                client.send(create_message("ASSIGN_ROLE", role="impostor", topic="(none)"))
            else:
                client.send(create_message("ASSIGN_ROLE", role="crewmate", topic=common_msg))
        except:
            client.close()
            clients.pop(client, None)

def run_server():
    print("Clients use this to join:", socket.gethostbyname(socket.gethostname()))
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("", 5555))
    server.listen()
    print("[SERVER STARTED] Listening on port 5555")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    run_server()
