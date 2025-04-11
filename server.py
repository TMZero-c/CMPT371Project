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
DISCUSSION_TIME = 30  # seconds
votes = {}  # player_name -> vote_target
round_active = False
game_running = False  # Tracks whether a game is currently running

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
                    # Remove the client from any room they are in
                    current_room = clients_room_ids.get(conn)
                    if isinstance(current_room, int) and current_room in rooms:
                        if conn in rooms[current_room]:
                            rooms[current_room].remove(conn)
                    # Add the client back to the lobby
                    if conn not in lobby_clients:
                        lobby_clients.append(conn)
                    clients_room_ids[conn] = "lobby"
                    conn.send(create_message("LOBBY_JOINED", message="You have rejoined the lobby."))

            elif msg_type == "READY":
                global game_running
                with ready_lock:
                    if game_running:  # If a game is already running, ignore the READY action
                        conn.send(create_message("INFO", message="The game is already running."))
                        return

                    ready_clients.add(conn)
                    broadcast(create_message("INFO", message=f"{clients[conn]} is ready."))

                    # Start the game if all clients are ready
                    if len(ready_clients) == len(clients):
                        threading.Thread(target=start_game, daemon=True).start()
                        

            elif msg_type == "JOIN":
                # Handle joining a specific room
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
    global impostor_for_game, game_stage, game_running
    game_stage = 1
    print("[GAME] Starting")

    # Select a random topic and impostor
    topic = random.choice(topicList)
    if game_running == True:
        pass  # Game is already running, do not change impostor
    elif game_running == False:
        impostor_for_game = random.choice(list(clients.keys()))
        game_running = True  # Set the flag to indicate the game is running

    # Assign roles to all players
    broadcast_except_one(topic, impostor_for_game)

    # Notify all players that the game has started
    broadcast(create_message("GAME_STARTED", players=list(clients.values())))

    # Ask each player to choose a room number
    max_rooms = math.ceil(len(clients) / 2)
    for conn in clients:
        conn.send(create_message("INFO", message=f"Choose a room number (1 to {max_rooms}) with command: join <room_number>"))

    global round_active
    round_active = True
    broadcast(create_message("INFO", message=f"Room discussion time: {DISCUSSION_TIME} seconds..."))
    time.sleep(DISCUSSION_TIME)
    end_room_phase()

def check_game_end(eliminated_name):
    global impostor_for_game, game_running

    if eliminated_name:
        # Remove eliminated player
        eliminated_conn = None
        for conn, name in clients.items():
            if name == eliminated_name:
                eliminated_conn = conn
                break
        if eliminated_conn:
            clients.pop(eliminated_conn, None)
            eliminated_conn.close()

    if eliminated_name and clients.get(impostor_for_game) == eliminated_name:
        broadcast(create_message("END_GAME", winner="crewmates"))
        game_running = False  # Reset the flag when the game ends
    elif len(clients) <= 2:
        broadcast(create_message("END_GAME", winner="impostor"))
        game_running = False  # Reset the flag when the game ends
    else:
        time.sleep(2)
        start_game()  # Start new round

def end_room_phase():
    global rooms, clients_room_ids, round_active
    broadcast(create_message("INFO", message="Discussion time over. Returning to the lobby."))
    
    # Clear all rooms and reset client room assignments
    rooms.clear()
    clients_room_ids.clear()

    # Broadcast JOIN_LOBBY to all clients
    for conn in clients:
        conn.send(create_message("JOIN_LOBBY"))

    # Add all clients back to the lobby
    with lock:
        lobby_clients.extend(clients.keys())
        for conn in clients:
            clients_room_ids[conn] = "lobby"

    round_active = False
    collect_votes()


def collect_votes():
    global votes
    votes = {}
    broadcast(create_message("INFO", message="Please vote for who you think is the impostor."))
    
    # Wait 20 seconds for votes
    time.sleep(20)

    vote_counts = {}
    for target in votes.values():
        vote_counts[target] = vote_counts.get(target, 0) + 1

    if not vote_counts:
        broadcast(create_message("INFO", message="No votes cast. Nobody is eliminated."))
        check_game_end(None)
        return

    eliminated = max(vote_counts.items(), key=lambda x: x[1])[0]
    broadcast(create_message("VOTE_RESULT", voted_out=eliminated))
    check_game_end(eliminated)

def broadcast_except_one(common_msg, impostor):
    impostor_name = clients.get(impostor)  # Get the impostor's name
    if not impostor_name:
        print("[ERROR] Impostor not found in clients.")
        return

    print(f"[DEBUG] Clients: {clients}")
    print(f"[DEBUG] Impostor: {impostor}, Impostor Name: {impostor_name}")

    for client, player_name in list(clients.items()):
        try:
            if client == impostor:  # Compare by socket object
                client.send(create_message("ASSIGN_ROLE", role="impostor", topic="(none)"))
                print(f"[ROLE ASSIGNMENT] {player_name} is the impostor.")
            else:
                client.send(create_message("ASSIGN_ROLE", role="crewmate", topic=common_msg))
                print(f"[ROLE ASSIGNMENT] {player_name} is a crewmate.")
        except Exception as e:
            print(f"[ERROR] Failed to send role to {player_name}: {e}")
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
