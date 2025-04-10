import socket
import threading
import json

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
    except:
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

            if msg_type in ["ROOM_JOINED", "ASSIGN_ROLE", "GAME_STARTED",
                            "MAIN_ROOM", "VOTE_RESULT", "END_GAME", "INFO"]:
                print(msg.get("message") or msg)
            elif msg_type == "PONG":
                print("✅ Server responded with PONG")
        except Exception as e:
            print("Error receiving message:", e)
            break

def main():
    ip_address = input("Enter server IP address: ")
    if not ip_address:
        print("No IP address provided. Exiting...")
        exit(69)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip_address, 5555))

    name = input("Enter your name: ")
    sock.send(create_message("JOIN_ROOM", player_name=name))

    threading.Thread(target=handle_server_messages, args=(sock,), daemon=True).start()

    while True:
        try:
            cmd = input("> ").strip()
            if cmd == "ready":
                sock.send(create_message("READY"))
            elif cmd.startswith("chat "):
                msg = cmd[5:]
                sock.send(create_message("CHAT", message=msg, room_id="current"))
            elif cmd.startswith("vote "):
                target = cmd.split(" ", 1)[1]
                sock.send(create_message("VOTE", target=target))
            elif cmd == "ping":
                sock.send(create_message("PING"))
            elif cmd == "exit":
                print("Exiting...")
                break
            else:
                print("Unknown command.")
        except KeyboardInterrupt:
            break

    sock.close()

if __name__ == "__main__":
    main()
