# merged_client.py
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
    global in_main_room
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                print("[DISCONNECTED] Server closed connection.")
                break
            msg = parse_message(data)
            if not msg:
                continue

            msg_type = msg.get("type")
            if msg_type == "INFO":
                print(msg.get("message", ""))
            elif msg_type == "ASSIGN_ROLE":
                print(f"\n[ROLE] You are the {msg['role']}. Topic: {msg['topic']}")
            elif msg_type == "ROOM_JOINED":
                print(f"[JOINED] Room: {msg['room_id']}, Players: {msg['players']}")
            elif msg_type == "GAME_STARTED":
                print("[GAME] Game started with players:", ", ".join(msg["players"]))
            elif msg_type == "VOTE_RESULT":
                print(f"\n[VOTE RESULT] {msg['ejected_player']} was ejected!")
            elif msg_type == "END_GAME":
                print(f"\n[GAME OVER] {msg['winner'].capitalize()} win!")
            elif msg_type == "PONG":
                print("✅ Pong received from server")
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

    name = input("Enter your display name: ")
    sock.send(create_message("JOIN_ROOM", player_name=name))

    threading.Thread(target=handle_server_messages, args=(sock,), daemon=True).start()

    while True:
        try:
            cmd = input("\n> ").strip()
            if cmd == "ready":
                sock.send(create_message("READY"))
            elif cmd.startswith("chat "):
                msg = cmd[5:]
                sock.send(create_message("CHAT", message=msg, room_id="ROOM1"))
            elif cmd.startswith("vote "):
                if in_main_room:
                    target = cmd.split(" ")[1]
                    sock.send(create_message("VOTE", target=target))
                else:
                    print("❌ You can only vote in the main room!")
            elif cmd == "ping":
                sock.send(create_message("PING"))
            elif cmd == "exit":
                print("Exiting game.")
                break
            else:
                print("Unknown command. Try: ready, chat <msg>, vote <name>, ping, exit")
        except KeyboardInterrupt:
            break

    sock.close()



if __name__ == "__main__":
    main()
