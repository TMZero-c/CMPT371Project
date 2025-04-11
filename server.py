import socket
import threading
import json
import random
import math
import time

with open("message_protocol.json", "r") as f:
    MESSAGE_TYPES = json.load(f)

# Shared data structures
clients = {}           # socket -> player_name
ready_clients = set()  # set of sockets that are ready
clients_room_ids = {}  # socket -> current room identifier

lobby_clients = []     # list of sockets currently in the lobby
rooms = {}             # room_id (int) -> list of sockets

impostor_for_game = None
game_stage = 0
DISCUSSION_TIME = 30  # seconds
votes = {}  # player_name -> vote_target
round_active = False
game_running = False  # Tracks whether a game is currently running

# Use a re-entrant lock for nested locking
data_lock = threading.RLock()

topicList = [
    "food", "cars", "anime", "movies", "school", "trains", "shervin", "IEEE",
    "the state of vancouver's economy in chinese", "clothing", "canada", "computer parts", "games", "art"
]

def create_message(message_type, **kwargs):
    """Convert the message dictionary to JSON and append a newline delimiter."""
    message = {"type": message_type}
    for field in MESSAGE_TYPES[message_type]["fields"]:
        message[field] = kwargs.get(field)
    return (json.dumps(message) + "\n").encode()

def parse_message(data):
    try:
        return json.loads(data.decode())
    except Exception:
        return None

def send_with_retry(client, message, retries=3):
    """Send a message to a client with retry logic."""
    for attempt in range(retries):
        try:
            client.send(message)
            return True
        except Exception:
            if attempt < retries - 1:
                time.sleep(0.1)
            else:
                return False

def broadcast(message, exclude=None):
    with data_lock:
        client_snapshot = list(clients.keys())
    failed_clients = []
    for client in client_snapshot:
        if client != exclude and not send_with_retry(client, message):
            failed_clients.append(client)
    with data_lock:
        for client in failed_clients:
            try:
                client.close()
            except Exception:
                pass
            clients.pop(client, None)

def lobby_broadcast(message, exclude=None):
    with data_lock:
        lobby_snapshot = list(lobby_clients)
    failed_clients = []
    for client in lobby_snapshot:
        if client != exclude and not send_with_retry(client, message):
            failed_clients.append(client)
    with data_lock:
        for client in failed_clients:
            try:
                client.close()
            except Exception:
                pass
            if client in lobby_clients:
                lobby_clients.remove(client)

def room_broadcast(msg, room_id, sender):
    with data_lock:
        room_snapshot = list(rooms.get(room_id, []))
    failed_clients = []
    for client in room_snapshot:
        if client != sender and not send_with_retry(client, msg):
            failed_clients.append(client)
    with data_lock:
        for client in failed_clients:
            try:
                client.close()
            except Exception:
                pass
            if room_id in rooms and client in rooms[room_id]:
                rooms[room_id].remove(client)

def handle_client(conn, addr):
    global game_running
    player_name = None
    buffer = ""
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            buffer += data.decode()
            # Process each complete JSON message (newline-delimited)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue
                message = parse_message(line.encode())
                if not message:
                    continue

                msg_type = message["type"]
                if msg_type == "JOIN_ROOM":
                    with data_lock:
                        if conn not in clients:
                            player_name = message["player_name"]
                            clients[conn] = player_name
                            lobby_clients.append(conn)
                            clients_room_ids[conn] = "lobby"
                    send_with_retry(conn, create_message("LOBBY_JOINED",
                                                         message=f"Welcome to the lobby, {player_name}!"))
                    broadcast(create_message("INFO", message=f"{player_name} joined."), exclude=conn)

                elif msg_type == "JOIN_LOBBY":
                    with data_lock:
                        current_room = clients_room_ids.get(conn)
                        if isinstance(current_room, int) and current_room in rooms and conn in rooms[current_room]:
                            rooms[current_room].remove(conn)
                        if conn not in lobby_clients:
                            lobby_clients.append(conn)
                        clients_room_ids[conn] = "lobby"
                    send_with_retry(conn, create_message("LOBBY_JOINED", message="You have rejoined the lobby."))

                elif msg_type == "READY":
                    with data_lock:
                        if game_running:
                            send_with_retry(conn, create_message("INFO", message="The game is already running."))
                            continue
                        ready_clients.add(conn)
                    broadcast(create_message("INFO", message=f"{clients[conn]} is ready."))
                    with data_lock:
                        if len(ready_clients) == len(clients):
                            threading.Thread(target=start_game, daemon=True).start()

                elif msg_type == "JOIN":
                    room_id = message.get("room_id")
                    if not isinstance(room_id, int):
                        send_with_retry(conn, create_message("INFO", message="Invalid room number."))
                        continue
                    with data_lock:
                        if conn in lobby_clients:
                            lobby_clients.remove(conn)
                        if room_id not in rooms:
                            rooms[room_id] = []
                        if len(rooms[room_id]) >= 2:
                            send_with_retry(conn, create_message("INFO", message="Room is full. Choose another."))
                            continue
                        rooms[room_id].append(conn)
                        clients_room_ids[conn] = room_id
                    send_with_retry(conn, create_message("INFO", message=f"Joined room {room_id}"))

                elif msg_type == "CHAT":
                    with data_lock:
                        room_id = clients_room_ids.get(conn)
                    content = message.get("message")
                    sender = clients.get(conn, "Unknown")
                    if room_id == "lobby":
                        lobby_broadcast(create_message("INFO", message=f"{sender}: {content}"), exclude=conn)
                    elif isinstance(room_id, int):
                        room_broadcast(create_message("INFO", message=f"{sender}: {content}"), room_id, conn)
                    else:
                        send_with_retry(conn, create_message("INFO", message="You're not in a valid room."))

                elif msg_type == "PING":
                    send_with_retry(conn, create_message("PONG"))

                elif msg_type == "VOTE":
                    voter = clients.get(conn)
                    with data_lock:
                        if voter in votes:
                            send_with_retry(conn, create_message("INFO", message="You have already voted."))
                        else:
                            target = message.get("target")
                            if target in list(clients.values()):
                                votes[voter] = target
                                send_with_retry(conn, create_message("INFO", message=f"You voted for {target}."))
                            else:
                                send_with_retry(conn, create_message("INFO", message="Invalid vote target."))
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        with data_lock:
            if conn in clients:
                left_name = clients.pop(conn)
                ready_clients.discard(conn)
                if conn in lobby_clients:
                    lobby_clients.remove(conn)
                current_room = clients_room_ids.get(conn)
                if isinstance(current_room, int) and current_room in rooms and conn in rooms[current_room]:
                    rooms[current_room].remove(conn)
                broadcast(create_message("INFO", message=f"{left_name} has disconnected."), exclude=conn)
        try:
            conn.close()
        except Exception:
            pass

def broadcast_except_one(common_msg, impostor):
    with data_lock:
        impostor_name = clients.get(impostor)
        client_snapshot = list(clients.items())
    if not impostor_name:
        print("[ERROR] Impostor not found in clients.")
        return
    for client, player_name in client_snapshot:
        if client == impostor:
            send_with_retry(client, create_message("ASSIGN_ROLE", role="impostor", topic="(none)"))
            print(f"[ROLE ASSIGNMENT] {player_name} is the impostor.")
        else:
            send_with_retry(client, create_message("ASSIGN_ROLE", role="crewmate", topic=common_msg))
            print(f"[ROLE ASSIGNMENT] {player_name} is a crewmate.")

def start_game():
    global impostor_for_game, game_stage, game_running, round_active
    with data_lock:
        current_clients = list(clients.keys())
        if not current_clients:
            return
        if not game_running:
            impostor_for_game = random.choice(current_clients)
        game_stage = 1
        game_running = True
        topic = random.choice(topicList)
    broadcast_except_one(topic, impostor_for_game)
    with data_lock:
        player_names = list(clients.values())
    broadcast(create_message("GAME_STARTED", players=player_names))
    max_rooms = math.ceil(len(current_clients) / 2)
    for conn in current_clients:
        send_with_retry(conn, create_message("INFO", message=f"Choose a room number (1 to {max_rooms}) with command: join <room_number>"))
    with data_lock:
        round_active = True
    broadcast(create_message("INFO", message=f"Room discussion time: {DISCUSSION_TIME} seconds..."))
    time.sleep(DISCUSSION_TIME)
    end_room_phase()

def end_room_phase():
    global rooms, clients_room_ids, round_active
    broadcast(create_message("INFO", message="Discussion time over. Returning to the lobby."))
    with data_lock:
        rooms.clear()
        clients_room_ids.clear()
        client_snapshot = list(clients.keys())
        lobby_clients.clear()
        for conn in client_snapshot:
            lobby_clients.append(conn)
            clients_room_ids[conn] = "lobby"
        round_active = False
    for conn in client_snapshot:
        send_with_retry(conn, create_message("JOIN_LOBBY"))
    collect_votes()

def collect_votes():
    global votes
    with data_lock:
        votes = {}
    broadcast(create_message("INFO", message="Please vote for who you think is the impostor. Use the command: vote <player_name>"))
    start_time = time.time()
    VOTING_DURATION = 20  # seconds
    while time.time() - start_time < VOTING_DURATION:
        time.sleep(1)
    with data_lock:
        vote_counts = {}
        for target in votes.values():
            vote_counts[target] = vote_counts.get(target, 0) + 1
    print("[DEBUG] Votes received:")
    with data_lock:
        for voter, target in votes.items():
            print(f"  {voter} voted for {target}")
    if not vote_counts:
        broadcast(create_message("INFO", message="No votes cast. Nobody is eliminated."))
        print("[DEBUG] No votes were cast.")
        check_game_end(None)
    else:
        eliminated = max(vote_counts.items(), key=lambda x: x[1])[0]
        broadcast(create_message("VOTE_RESULT", voted_out=eliminated))
        print(f"[DEBUG] {eliminated} has been voted out.")
        check_game_end(eliminated)
    with data_lock:
        votes.clear()

def check_game_end(eliminated_name):
    global impostor_for_game, game_running
    if eliminated_name:
        eliminated_conn = None
        with data_lock:
            for conn, name in clients.items():
                if name == eliminated_name:
                    eliminated_conn = conn
                    break
            if eliminated_conn:
                clients.pop(eliminated_conn, None)
                try:
                    eliminated_conn.close()
                except Exception:
                    pass
    with data_lock:
        impostor_still_alive = (impostor_for_game in clients)
        num_players = len(clients)
    if eliminated_name and not impostor_still_alive:
        broadcast(create_message("END_GAME", winner="crewmates"))
        with data_lock:
            game_running = False
    elif num_players <= 2:
        broadcast(create_message("END_GAME", winner="impostor"))
        with data_lock:
            game_running = False
    else:
        time.sleep(2)
        start_game()

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
