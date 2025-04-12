import socket          # Provides access to the BSD socket interface for networking.
import threading       # Enables concurrent execution via threads.
import json            # Used for encoding and decoding JSON messages.
import random          # Used for random selections (e.g., choosing the impostor or a chat topic).
import math            # Used to perform mathematical operations (e.g., calculating the number of rooms).
import time            # Provides time-related functions (e.g., sleep for delays).

# Load the messaging protocol definition from a JSON file.
# This file contains message types and their expected fields.
with open("message_protocol.json", "r") as f:
    MESSAGE_TYPES = json.load(f)

# ------------------------- Shared Data Structures ------------------------- #
# Global data structures to keep track of clients, game state, and chat rooms.

clients = {}           # Dictionary mapping a socket to its associated player_name.
ready_clients = set()  # Set of sockets that have indicated they are ready to play.
clients_room_ids = {}  # Dictionary mapping a socket to its current room identifier 
                       # (could be "lobby" or an integer representing a specific room).

lobby_clients = []     # List of sockets that are currently in the lobby waiting for game start.
rooms = {}             # Dictionary mapping room_id (integer) to a list of sockets assigned to that room.

impostor_for_game = None  # Variable to store the socket chosen to be the impostor.
game_stage = 0            # Variable representing the current stage of the game.
DISCUSSION_TIME = 30      # Discussion time in seconds for each chat room phase.
votes = {}                # Dictionary mapping a voter (player_name) to the vote target (player_name).
round_active = False      # Boolean flag indicating if a discussion round is currently active.
game_running = False      # Boolean flag indicating if the game is currently running.

# A re-entrant lock is used for nested lock acquisitions in multi-threaded sections
data_lock = threading.RLock()

# List of possible discussion topics to assign to normal players.
topicList = [
    "food", "cars", "anime", "movies", "school", "trains", "shervin", "IEEE",
    "the state of vancouver's economy in chinese", "clothing", "canada", "computer parts", "games", "art"
]

# --------------------------- Message Helper Functions --------------------------- #
def create_message(message_type, **kwargs):
    """
    Creates a JSON message based on a message type and additional keyword arguments.
    The message dictionary is constructed by taking the predefined fields
    for a given type from the MESSAGE_TYPES dictionary, and filling them using kwargs.
    A newline delimiter is appended to help with message framing.
    """
    message = {"type": message_type}
    # Iterate over each field expected in the message type and populate it.
    for field in MESSAGE_TYPES[message_type]["fields"]:
        message[field] = kwargs.get(field)
    # Convert the dictionary into a JSON formatted string, append a newline, and encode to bytes.
    return (json.dumps(message) + "\n").encode()

def parse_message(data):
    """
    Attempts to decode a received data block (bytes) into a JSON object.
    Returns None if decoding fails.
    """
    try:
        return json.loads(data.decode())
    except Exception:
        return None

def send_with_retry(client, message, retries=3):
    """
    Attempts to send a message to the provided client socket.
    If the send fails, it retries up to 'retries' times with a small delay in between.
    Returns True on a successful send and False if all retries fail.
    """
    for attempt in range(retries):
        try:
            client.send(message)
            return True
        except Exception:
            # If not the last attempt, wait briefly before retrying.
            if attempt < retries - 1:
                time.sleep(0.1)
            else:
                return False

# --------------------------- Broadcasting Functions --------------------------- #
def broadcast(message, exclude=None):
    """
    Broadcasts a message to every client connected in the 'clients' dictionary, except the 'exclude' socket.
    If a client fails to receive the message, that client is removed from the list and its socket is closed.
    """
    with data_lock:
        client_snapshot = list(clients.keys())
    failed_clients = []
    # Attempt to send the message to each client not equal to 'exclude'
    for client in client_snapshot:
        if client != exclude and not send_with_retry(client, message):
            failed_clients.append(client)
    with data_lock:
        # Clean up any clients that failed to receive the message.
        for client in failed_clients:
            try:
                client.close()
            except Exception:
                pass
            clients.pop(client, None)

def lobby_broadcast(message, exclude=None):
    """
    Broadcasts a message to every client in the lobby (lobby_clients list), excluding the specified client if provided.
    If a client in the lobby fails to receive the message, it gets removed from the lobby list.
    """
    with data_lock:
        lobby_snapshot = list(lobby_clients)
    failed_clients = []
    for client in lobby_snapshot:
        if client != exclude and not send_with_retry(client, message):
            failed_clients.append(client)
    with data_lock:
        # Remove any clients that failed from the lobby_clients list.
        for client in failed_clients:
            try:
                client.close()
            except Exception:
                pass
            if client in lobby_clients:
                lobby_clients.remove(client)

def room_broadcast(msg, room_id, sender):
    """
    Broadcasts a message to all clients in a specified room (rooms[room_id]), excluding the sender.
    If sending fails for any client, that client is closed and removed from the room.
    """
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

# --------------------------- Client Handler Function --------------------------- #
def handle_client(conn, addr):
    """
    Function to handle all communication with a connected client.
    This continuously receives data, processes complete newline-delimited JSON messages,
    and performs actions based on the message type (e.g., JOIN_ROOM, CHAT, VOTE).
    """
    global game_running
    player_name = None
    buffer = ""
    try:
        while True:
            # Receive a data chunk from the client.
            data = conn.recv(1024)
            # If no data is received, the client has disconnected.
            if not data:
                break
            # Append received data to the buffer (may contain partial messages).
            buffer += data.decode()
            # Process each complete JSON message (messages are newline-delimited).
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue
                message = parse_message(line.encode())
                if not message:
                    continue

                # Identify the type of the message.
                msg_type = message["type"]

                # Handle JOIN_ROOM messages: Register a new client in the lobby.
                if msg_type == "JOIN_ROOM":
                    with data_lock:
                        if conn not in clients:
                            player_name = message["player_name"]
                            clients[conn] = player_name  # Associate connection with player name.
                            lobby_clients.append(conn)   # Add client to lobby.
                            clients_room_ids[conn] = "lobby"  # Set client's current room as lobby.
                    # Send a welcome message to the client.
                    send_with_retry(conn, create_message("LOBBY_JOINED",
                                                         message=f"Welcome to the lobby, {player_name}!"))
                    # Notify all other clients that a new player has joined.
                    broadcast(create_message("INFO", message=f"{player_name} joined."), exclude=conn)

                # Handle messages to rejoin the lobby.
                elif msg_type == "JOIN_LOBBY":
                    with data_lock:
                        current_room = clients_room_ids.get(conn)
                        # If the client was in a room, remove them from that room.
                        if isinstance(current_room, int) and current_room in rooms and conn in rooms[current_room]:
                            rooms[current_room].remove(conn)
                        # Ensure client is in the lobby list.
                        if conn not in lobby_clients:
                            lobby_clients.append(conn)
                        clients_room_ids[conn] = "lobby"  # Mark client's room as lobby.
                    send_with_retry(conn, create_message("LOBBY_JOINED", message="You have rejoined the lobby."))

                # Handle READY messages: Mark clients as ready to start the game.
                elif msg_type == "READY":
                    with data_lock:
                        if game_running:
                            send_with_retry(conn, create_message("INFO", message="The game is already running."))
                            continue
                        ready_clients.add(conn)  # Mark this client as ready.
                    # Inform all clients that this player is ready.
                    broadcast(create_message("INFO", message=f"{clients[conn]} is ready."))
                    with data_lock:
                        # If all clients are ready, start the game in a new thread.
                        if len(ready_clients) == len(clients):
                            threading.Thread(target=start_game, daemon=True).start()

                # Handle JOIN messages for joining a specific room.
                elif msg_type == "JOIN":
                    room_id = message.get("room_id")
                    # Validate that room_id is an integer.
                    if not isinstance(room_id, int):
                        send_with_retry(conn, create_message("INFO", message="Invalid room number."))
                        continue
                    with data_lock:
                        if conn in lobby_clients:
                            lobby_clients.remove(conn)  # Remove client from lobby if present.
                        if room_id not in rooms:
                            rooms[room_id] = []  # Initialize the room if it does not exist.
                        # Check if room is already full (max 2 players per room).
                        if len(rooms[room_id]) >= 2:
                            send_with_retry(conn, create_message("INFO", message="Room is full. Choose another."))
                            continue
                        rooms[room_id].append(conn)          # Add client to the room.
                        clients_room_ids[conn] = room_id       # Update client's current room identifier.
                    send_with_retry(conn, create_message("INFO", message=f"Joined room {room_id}"))

                # Handle CHAT messages: Send the chat to the appropriate room or lobby.
                elif msg_type == "CHAT":
                    with data_lock:
                        room_id = clients_room_ids.get(conn)
                    content = message.get("message")
                    sender = clients.get(conn, "Unknown")
                    if room_id == "lobby":
                        # Broadcast to everyone in the lobby except the sender.
                        lobby_broadcast(create_message("INFO", message=f"{sender}: {content}"), exclude=conn)
                    elif isinstance(room_id, int):
                        # Broadcast to all members of the room except the sender.
                        room_broadcast(create_message("INFO", message=f"{sender}: {content}"), room_id, conn)
                    else:
                        # Inform client if they are in an invalid room.
                        send_with_retry(conn, create_message("INFO", message="You're not in a valid room."))

                # Handle PING messages: Respond with a PONG.
                elif msg_type == "PING":
                    send_with_retry(conn, create_message("PONG"))

                # Handle VOTE messages: Process a client's vote for a player.
                elif msg_type == "VOTE":
                    voter = clients.get(conn)
                    with data_lock:
                        # Check if the client has already voted.
                        if voter in votes:
                            send_with_retry(conn, create_message("INFO", message="You have already voted."))
                        else:
                            target = message.get("target")
                            # Verify if the target is a valid player by checking the clients dictionary.
                            if target in list(clients.values()):
                                votes[voter] = target  # Record the vote.
                                send_with_retry(conn, create_message("INFO", message=f"You voted for {target}."))
                            else:
                                send_with_retry(conn, create_message("INFO", message="Invalid vote target."))
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        # Cleanup on client disconnection.
        with data_lock:
            if conn in clients:
                left_name = clients.pop(conn)
                ready_clients.discard(conn)
                if conn in lobby_clients:
                    lobby_clients.remove(conn)
                current_room = clients_room_ids.get(conn)
                # Remove client from any room they belong to.
                if isinstance(current_room, int) and current_room in rooms and conn in rooms[current_room]:
                    rooms[current_room].remove(conn)
                # Notify all clients that a player has disconnected.
                broadcast(create_message("INFO", message=f"{left_name} has disconnected."), exclude=conn)
        try:
            conn.close()  # Close the socket connection.
        except Exception:
            pass

# --------------------------- Game Functions --------------------------- #
def broadcast_except_one(common_msg, impostor):
    """
    Sends the ASSIGN_ROLE messages to all clients.
    The impostor receives a different message (with no topic) than other players (who get a common topic).
    """
    with data_lock:
        impostor_name = clients.get(impostor)
        client_snapshot = list(clients.items())
    if not impostor_name:
        print("[ERROR] Impostor not found in clients.")
        return
    for client, player_name in client_snapshot:
        if client == impostor:
            # Notify the impostor of their role.
            send_with_retry(client, create_message("ASSIGN_ROLE", role="impostor", topic="(none)"))
            print(f"[ROLE ASSIGNMENT] {player_name} is the impostor.")
        else:
            # Notify normal players of their role and assign the discussion topic.
            send_with_retry(client, create_message("ASSIGN_ROLE", role="crewmate", topic=common_msg))
            print(f"[ROLE ASSIGNMENT] {player_name} is a crewmate.")

def start_game():
    """
    Initiates the game once all players are ready.
    It randomly selects an impostor, chooses a discussion topic, assigns roles, and begins the discussion phase.
    """
    global impostor_for_game, game_stage, game_running, round_active
    with data_lock:
        current_clients = list(clients.keys())
        if not current_clients:
            return
        # Select an impostor randomly if a game is not already in progress.
        if not game_running:
            impostor_for_game = random.choice(current_clients)
        game_stage = 1  # Set the game stage to the beginning.
        game_running = True  # Mark the game as running.
        topic = random.choice(topicList)  # Choose a random discussion topic.
    broadcast_except_one(topic, impostor_for_game)
    with data_lock:
        player_names = list(clients.values())
    # Notify all clients that the game has started and list the players.
    broadcast(create_message("GAME_STARTED", players=player_names))
    max_rooms = math.ceil(len(current_clients) / 2)  # Calculate maximum available rooms.
    for conn in current_clients:
        # Inform players about how to join a discussion room.
        send_with_retry(conn, create_message("INFO", message=f"Choose a room number (1 to {max_rooms}) with command: join <room_number>"))
    with data_lock:
        round_active = True  # Mark the discussion round as active.
    # Inform clients of the discussion phase and how long it lasts.
    broadcast(create_message("INFO", message=f"Room discussion time: {DISCUSSION_TIME} seconds..."))
    time.sleep(DISCUSSION_TIME)  # Wait for the discussion phase to complete.
    end_room_phase()  # End the discussion phase and transition to voting.

def end_room_phase():
    """
    Ends the discussion phase by moving all players back to the lobby.
    Clears current room assignments and notifies clients to rejoin the lobby,
    then proceeds to collect votes.
    """
    global rooms, clients_room_ids, round_active
    broadcast(create_message("INFO", message="Discussion time over. Returning to the lobby."))
    with data_lock:
        # Clear all room assignments.
        rooms.clear()
        clients_room_ids.clear()
        client_snapshot = list(clients.keys())
        lobby_clients.clear()
        # Move all clients to the lobby.
        for conn in client_snapshot:
            lobby_clients.append(conn)
            clients_room_ids[conn] = "lobby"
        round_active = False  # Mark round as inactive.
    # Notify clients that they have rejoined the lobby.
    for conn in client_snapshot:
        send_with_retry(conn, create_message("JOIN_LOBBY"))
    collect_votes()  # Begin the voting phase.

def collect_votes():
    """
    Initiates the voting phase after discussion.
    Notifies clients to vote, waits for a fixed duration, tallies votes,
    and then determines which player is eliminated.
    """
    global votes
    with data_lock:
        votes = {}  # Reset votes for the new voting round.
    broadcast(create_message("INFO", message="Please vote for who you think is the impostor. Use the command: vote <player_name>"))
    start_time = time.time()
    VOTING_DURATION = 20  # Voting phase duration in seconds.
    while time.time() - start_time < VOTING_DURATION:
        time.sleep(1)
    with data_lock:
        vote_counts = {}
        # Count the votes received for each target.
        for target in votes.values():
            vote_counts[target] = vote_counts.get(target, 0) + 1
    print("[DEBUG] Votes received:")
    with data_lock:
        # Output voting details for debugging purposes.
        for voter, target in votes.items():
            print(f"  {voter} voted for {target}")
    if not vote_counts:
        # If no votes were cast, notify all clients that no one is eliminated.
        broadcast(create_message("INFO", message="No votes cast. Nobody is eliminated."))
        print("[DEBUG] No votes were cast.")
        check_game_end(None)
    else:
        # Determine the player with the highest vote count.
        eliminated = max(vote_counts.items(), key=lambda x: x[1])[0]
        broadcast(create_message("VOTE_RESULT", voted_out=eliminated))
        print(f"[DEBUG] {eliminated} has been voted out.")
        check_game_end(eliminated)
    with data_lock:
        votes.clear()  # Clear votes for next round.

def check_game_end(eliminated_name):
    """
    Checks if the game should end based on the eliminated player or the number of remaining players.
    If the impostor is eliminated or if only two players remain, the game ends.
    Otherwise, the game continues with another round.
    """
    global impostor_for_game, game_running
    if eliminated_name:
        eliminated_conn = None
        with data_lock:
            # Find the connection associated with the eliminated player.
            for conn, name in clients.items():
                if name == eliminated_name:
                    eliminated_conn = conn
                    break
            if eliminated_conn:
                clients.pop(eliminated_conn, None)  # Remove the eliminated client.
                try:
                    eliminated_conn.close()  # Close the client's connection.
                except Exception:
                    pass
    with data_lock:
        # Check if the impostor is still connected.
        impostor_still_alive = (impostor_for_game in clients)
        num_players = len(clients)
    if eliminated_name and not impostor_still_alive:
        # If the impostor is eliminated, declare crewmates as winners.
        broadcast(create_message("END_GAME", winner="crewmates"))
        with data_lock:
            game_running = False
    elif num_players <= 2:
        # If only two players remain, declare the impostor as the winner.
        broadcast(create_message("END_GAME", winner="impostor"))
        with data_lock:
            game_running = False
    else:
        # Otherwise, wait briefly and start a new round.
        time.sleep(2)
        start_game()

def run_server():
    """
    Sets up and starts the server.
    Binds to a specified port, listens for incoming connections, and spawns a new thread for each client.
    """
    print("Clients use this to join:", socket.gethostbyname(socket.gethostname()))
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("", 5555))  # Bind the server socket to all available interfaces on port 5555.
    server.listen()         # Start listening for incoming connections.
    print("[SERVER STARTED] Listening on port 5555")
    while True:
        conn, addr = server.accept()  # Accept new incoming connection.
        # Spawn a new thread to handle the client communication.
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

# --------------------------- Main Execution --------------------------- #
if __name__ == "__main__":
    run_server()
