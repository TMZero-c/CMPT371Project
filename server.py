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

lock = threading.Lock()

topicList = [
    "food", "cars", "anime", "movies", "school", "trains", "shervin", "IEEE",
    "the state of vancouver's economy in chinese", "clothing", "canada", "computer parts", "games", "art"
]

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

def send_with_retry(client, message, retries=3):
    """Send a message to a client with retry logic."""
    for attempt in range(retries):
        try:
            client.send(message)
            return True
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.1)  # Small delay before retrying
            else:
                return False

def broadcast(message, exclude=None):
    with lock:
        client_snapshot = list(clients.keys())
    failed_clients = []
    for client in client_snapshot:
        if client != exclude and not send_with_retry(client, message):
            failed_clients.append(client)
    with lock:
        for client in failed_clients:
            client.close()
            clients.pop(client, None)

def lobby_broadcast(message, exclude=None):
    with lock:
        lobby_snapshot = list(lobby_clients)
    failed_clients = []
    for client in lobby_snapshot:
        if client != exclude and not send_with_retry(client, message):
            failed_clients.append(client)
    with lock:
        for client in failed_clients:
            client.close()
            if client in lobby_clients:
                lobby_clients.remove(client)

def room_broadcast(msg, room_id, sender):
    with lock:
        if room_id in rooms:
            room_snapshot = list(rooms[room_id])
        else:
            room_snapshot = []
    failed_clients = []
    for client in room_snapshot:
        if client != sender:
            if not send_with_retry(client, msg):
                failed_clients.append(client)
    with lock:
        if room_id in rooms:
            for client in failed_clients:
                client.close()
                if client in rooms[room_id]:
                    rooms[room_id].remove(client)

def handle_client(conn, addr):
    global game_running
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
                        lobby_clients.append(conn)
                        clients_room_ids[conn] = "lobby"
                send_with_retry(conn, create_message("LOBBY_JOINED",
                                                     message=f"Welcome to the lobby, {player_name}!"))
                broadcast(create_message("INFO", message=f"{player_name} joined."), exclude=conn)

            elif msg_type == "JOIN_LOBBY":
                with lock:
                    current_room = clients_room_ids.get(conn)
                    if isinstance(current_room, int) and current_room in rooms:
                        if conn in rooms[current_room]:
                            rooms[current_room].remove(conn)
                    if conn not in lobby_clients:
                        lobby_clients.append(conn)
                    clients_room_ids[conn] = "lobby"
                send_with_retry(conn, create_message("LOBBY_JOINED", message="You have rejoined the lobby."))

            elif msg_type == "READY":
                with lock:
                    if game_running:
                        send_with_retry(conn, create_message("INFO", message="The game is already running."))
                        continue
                    ready_clients.add(conn)
                broadcast(create_message("INFO", message=f"{clients[conn]} is ready."))

                with lock:
                    if len(ready_clients) == len(clients):
                        threading.Thread(target=start_game, daemon=True).start()

            elif msg_type == "JOIN":
                room_id = message.get("room_id")
                if not isinstance(room_id, int):
                    send_with_retry(conn, create_message("INFO", message="Invalid room number."))
                    continue
                with lock:
                    if conn in lobby_clients:
                        lobby_clients.remove(conn)
                    if room_id not in rooms:
                        rooms[room_id] = []
                    if len(rooms[room_id]) >= 2:
                        send_with_retry(conn, create_message("INFO", message="Room is full. Choose another."))
                        continue
                    else:
                        rooms[room_id].append(conn)
                        clients_room_ids[conn] = room_id
                send_with_retry(conn, create_message("INFO", message=f"Joined room {room_id}"))

            elif msg_type == "CHAT":
                with lock:
                    room_id = clients_room_ids.get(conn)
                content = message.get("message")
                sender = clients.get(conn, "Unknown")
                if room_id == "lobby":
                    lobby_broadcast(create_message("INFO", message=f"{sender}: {content}"), conn)
                elif isinstance(room_id, int):
                    room_broadcast(create_message("INFO", message=f"{sender}: {content}"), room_id, conn)
                else:
                    send_with_retry(conn, create_message("INFO", message="You're not in a valid room."))

            elif msg_type == "PING":
                send_with_retry(conn, create_message("PONG"))

            elif msg_type == "VOTE":
                voter = clients.get(conn)
                with lock:
                    if voter in votes:
                        send_with_retry(conn, create_message("INFO", message="You have already voted."))
                    else:
                        target = message.get("target")
                        if target in clients.values():
                            votes[voter] = target
                            send_with_retry(conn, create_message("INFO", message=f"You voted for {target}."))
                        else:
                            send_with_retry(conn, create_message("INFO", message="Invalid vote target."))

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        with lock:
            if conn in clients:
                left_name = clients.pop(conn)
                ready_clients.discard(conn)
                if conn in lobby_clients:
                    lobby_clients.remove(conn)
                current_room = clients_room_ids.get(conn)
                if isinstance(current_room, int) and current_room in rooms and conn in rooms[current_room]:
                    rooms[current_room].remove(conn)
                broadcast(create_message("INFO", message=f"{left_name} has disconnected."), exclude=conn)
        conn.close()

def start_game():
    global impostor_for_game, game_stage, game_running, round_active
    # Make a snapshot of the current clients for iteration
    current_clients = list(clients.keys())
    
    with lock:
        if game_running:
            pass
        else:
            impostor_for_game = random.choice(current_clients)
        game_stage = 1
        game_running = True

        # Select a random topic and impostor
        topic = random.choice(topicList)
        

    # Assign roles using the snapshot of clients
    broadcast_except_one(topic, impostor_for_game)

    # Notify all players that the game has started
    with lock:
        player_names = list(clients.values())
    broadcast(create_message("GAME_STARTED", players=player_names))

    # Ask each player to choose a room number
    max_rooms = math.ceil(len(current_clients) / 2)
    for conn in current_clients:
        send_with_retry(conn, create_message("INFO", message=f"Choose a room number (1 to {max_rooms}) with command: join <room_number>"))
    
    with lock:
        round_active = True
    broadcast(create_message("INFO", message=f"Room discussion time: {DISCUSSION_TIME} seconds..."))
    
    time.sleep(DISCUSSION_TIME)
    end_room_phase()

def check_game_end(eliminated_name):
    global impostor_for_game, game_running
    if eliminated_name:
        # Remove eliminated player
        eliminated_conn = None
        with lock:
            for conn, name in clients.items():
                if name == eliminated_name:
                    eliminated_conn = conn
                    break
            if eliminated_conn:
                clients.pop(eliminated_conn, None)
                eliminated_conn.close()

    with lock:
        # Check win conditions
        impostor_still_alive = any(name == clients.get(impostor_for_game) for name in clients.values())
        num_players = len(clients)

    if eliminated_name and not impostor_still_alive:
        broadcast(create_message("END_GAME", winner="crewmates"))
        with lock:
            game_running = False
    elif num_players <= 2:
        broadcast(create_message("END_GAME", winner="impostor"))
        with lock:
            game_running = False
    else:
        time.sleep(2)
        # with lock:
            # game_running = False  # Reset flag so that a new round can start
        start_game()  # Start new round

def end_room_phase():
    global rooms, clients_room_ids, round_active
    broadcast(create_message("INFO", message="Discussion time over. Returning to the lobby."))

    with lock:
        rooms.clear()
        clients_room_ids.clear()
        client_snapshot = list(clients.keys())
    # Broadcast JOIN_LOBBY to all clients
    for conn in client_snapshot:
        send_with_retry(conn, create_message("JOIN_LOBBY"))
    with lock:
        lobby_clients[:] = client_snapshot  # Reset lobby clients
        for conn in client_snapshot:
            clients_room_ids[conn] = "lobby"
    with lock:
        round_active = False
    collect_votes()

def collect_votes():
    global votes
    with lock:
        votes = {}  # Reset votes at the start of the round
    broadcast(create_message("INFO", message="Please vote for who you think is the impostor. Use the command: vote <player_name>"))
    
    start_time = time.time()
    VOTING_DURATION = 20  # seconds
    while time.time() - start_time < VOTING_DURATION:
        time.sleep(1)  # Check periodically for votes

    with lock:
        vote_counts = {}
        for target in votes.values():
            vote_counts[target] = vote_counts.get(target, 0) + 1

    print("[DEBUG] Votes received:")
    with lock:
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

    with lock:
        votes.clear()

def broadcast_except_one(common_msg, impostor):
    with lock:
        impostor_name = clients.get(impostor)
        client_snapshot = list(clients.items())
    
    if not impostor_name:
        print("[ERROR] Impostor not found in clients.")
        return

    for client, player_name in client_snapshot:
        try:
            if client == impostor:
                client.send(create_message("ASSIGN_ROLE", role="impostor", topic="(none)"))
                print(f"[ROLE ASSIGNMENT] {player_name} is the impostor.")
            else:
                client.send(create_message("ASSIGN_ROLE", role="crewmate", topic=common_msg))
                print(f"[ROLE ASSIGNMENT] {player_name} is a crewmate.")
        except Exception as e:
            print(f"[ERROR] Failed to send role to {player_name}: {e}")
            with lock:
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
