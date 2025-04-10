import socket
import threading
import json

'''

Did you know that the critically acclaimed MMORPG Final Fantasy XIV has a free trial, and includes thee ntirety of A Realm Reborn AND the award-winning Heavensward and Stormblood expansions up to level 70 with no restrictions on playtime? Sign up, and enjoy Eorzea today!


'''

with open("message_protocol.json", "r") as f:
    MESSAGE_TYPES = json.load(f)

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

def handle_server_messages(sock):
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                print("Disconnected from server.")
                break
            msg = parse_message(data)
            if not msg:
                continue

            msg_type = msg["type"]

            if msg_type in ["LOBBY_JOINED", "ROOM_JOINED", "ASSIGN_ROLE", "GAME_STARTED",
                            "MAIN_ROOM", "VOTE_RESULT", "END_GAME", "INFO"]:
                print(msg.get("message") or msg)
            elif msg_type == "PONG":
                print("✅ Server responded with PONG")
        except Exception as e:
            print("Error receiving message:", e)
            break

def print_help():
    print("\nAvailable commands:")
    print("  ready              - Mark yourself as ready")
    print("  chat <message>     - Send a chat message to your current room/lobby")
    print("  vote <name/room>   - Vote for a player (during voting) or for a room (in lobby/game)")
    print("  join <room_num>    - Join a specific room (after game starts)")
    print("  lobby              - Return to the lobby")
    print("  ping               - Ping the server")
    print("  help               - Show this help message")
    print("  exit               - Disconnect and exit\n")

def main():
    ip_address = input("Enter server IP address: ")
    if not ip_address:
        print("No IP address provided. Exiting...")
        exit(69)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip_address, 5555))

    name = input("Enter your name: ")
    # Join the lobby automatically upon connection
    sock.send(create_message("JOIN_ROOM", player_name=name))

    threading.Thread(target=handle_server_messages, args=(sock,), daemon=True).start()

    while True:
        try:
            cmd = input("> ").strip()
            if cmd == "ready":
                sock.send(create_message("READY"))
            elif cmd.startswith("chat "):
                msg = cmd[5:]
                # “current” means whichever room or lobby the client is in.
                sock.send(create_message("CHAT", message=msg, room_id="current"))
            elif cmd.startswith("join"):
                # join <room_num> command used during the game to select a specific numeric room
                value = cmd.split(" ", 1)[1]
                if value.isdigit():
                    sock.send(create_message("JOIN_SPECIFIC_ROOM", room_id=int(value)))
                else:
                    sock.send(create_message("VOTE", target=value))
            elif cmd == "lobby":
                sock.send(create_message("JOIN_LOBBY"))
            elif cmd == "ping":
                sock.send(create_message("PING"))
            elif cmd == "help":
                print_help()
            elif cmd == "exit":
                print("Exiting...")
                break
            else:
                print("Unknown command. Type 'help' for options.")
        except KeyboardInterrupt:
            break

    sock.close()

if __name__ == "__main__":
    main()
