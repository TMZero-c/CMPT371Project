# server.py
import socket
import threading
import json
import random
import time

with open("message_protocol.json", "r") as f:
    MESSAGE_TYPES = json.load(f)

TOPICS = [
    "Pizza toppings",
    "Favorite animals",
    "Dream vacation",
    "Best movie of all time",
    "Go-to karaoke song"
]

def create_message(message_type, **kwargs):
    if message_type not in MESSAGE_TYPES:
        raise ValueError("Unknown message type.")
    message = {"type": message_type}
    for field in MESSAGE_TYPES[message_type]["fields"]:
        message[field] = kwargs.get(field)
    return json.dumps(message).encode()

def parse_message(data):
    try:
        return json.loads(data.decode())
    except:
        return None

class GameServer:
    def __init__(self, host='', port=5555, max_players=3):
        self.host = host
        self.port = port
        self.max_players = max_players
        self.players = []
        self.sockets = []
        self.roles = {}
        self.topics = {}
        self.ready_players = set()
        self.votes = {}
        self.lock = threading.Lock()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        self.socket_to_player = {}  # conn -> player_name
        self.player_to_socket = {}  # player_name -> conn

    def broadcast(self, message, exclude=None):
        for sock in self.sockets:
            if sock != exclude:
                try:
                    sock.send(message)
                except:
                    pass

    def handle_client(self, conn, addr):
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
                    with self.lock:
                        if len(self.players) >= self.max_players:
                            conn.send(create_message("END_GAME", winner="Room Full"))
                            return
                        player_name = message["player_name"]
                        self.players.append(player_name)
                        self.sockets.append(conn)
                        self.socket_to_player[conn] = player_name
                        self.player_to_socket[player_name] = conn
                        print(f"{player_name} joined. Players: {self.players}")
                        conn.send(create_message("ROOM_JOINED", room_id="ROOM123", players=self.players))
                        self.broadcast(create_message("INFO", message=f"{player_name} has joined."), exclude=conn)

                elif msg_type == "READY":
                    with self.lock:
                        self.ready_players.add(player_name)
                        self.broadcast(create_message("INFO", message=f"{player_name} is ready."))
                        if len(self.ready_players) == self.max_players:
                            threading.Thread(target=self.start_game, daemon=True).start()

                elif msg_type == "VOTE":
                    # TODO: handle vote tallying logic
                    self.broadcast(create_message("INFO", message=f"{player_name} voted."))
                    # TODO: Send raw vote message to handle game flow

                elif msg_type == "CHAT":
                    msg = message["message"]
                    self.broadcast(create_message("INFO", message=f"{player_name}: {msg}"))

                elif msg_type == "PING":
                    conn.send(create_message("PONG"))

        except Exception as e:
            print(f"Error with player {player_name}: {e}")
        finally:
            if player_name:
                with self.lock:
                    if player_name in self.players:
                        self.players.remove(player_name)
                    if conn in self.sockets:
                        self.sockets.remove(conn)
                    self.socket_to_player.pop(conn, None)
                    self.player_to_socket.pop(player_name, None)
            conn.close()

    def start_game(self):
        print("Game starting!")
        topic = random.choice(TOPICS)
        impostor = random.choice(self.players)
        for i, name in enumerate(self.players):
            sock = self.sockets[i]
            role = "impostor" if name == impostor else "crewmate"
            self.roles[name] = role
            assigned_topic = topic if role == "crewmate" else "(none)"
            self.topics[name] = assigned_topic
            sock.send(create_message("ASSIGN_ROLE", role=role, topic=assigned_topic))

        self.broadcast(create_message("GAME_STARTED", players=self.players))
        # TODO: Start chatroom and voting flow here

    def run(self):
        print("clients use this to join: " + socket.gethostbyname(socket.gethostname()))

        print(f"Server listening on {self.host}:{self.port}")
        try:
            while True:
                conn, addr = self.server_socket.accept()
                print(f"Connection from {addr}")
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("Server shutting down...")
        finally:
            self.server_socket.close()

if __name__ == "__main__":
    GameServer().run()
