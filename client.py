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
                print("Disconnected from server.")
                break
            msg = parse_message(data)
            if not msg:
                continue

            msg_type = msg["type"]

            if msg_type == "ROOM_JOINED":
                print(f"\n✅ Joined room {msg['room_id']}.")
            elif msg_type == "ASSIGN_ROLE":
                print(f"\n🎭 Your role is: {msg['role'].upper()}")
            elif msg_type == "GAME_STARTED":
                print("\n🚀 Game has started.")
            elif msg_type == "MAIN_ROOM":
                print("\n↩️ You are now in the main room. Voting is enabled.")
                in_main_room = True
            elif msg_type == "VOTE_RESULT":
                print(f"\n📣 {msg['eliminated']} was voted out!")
            elif msg_type == "END_GAME":
                print(f"\n🏁 Game Over! Winner: {msg['winner']}")
            elif msg_type == "PONG":
                print("✅ Server responded with PONG")
            elif msg_type == "INFO":
                print(f"\nℹ️  {msg['message']}")
        except Exception as e:
            print("Error receiving message:", e)
            break

def main():
    global in_main_room
    in_main_room = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', 5555))

    name = input("Enter your name: ")
    sock.send(create_message("JOIN_ROOM", player_name=name))

    threading.Thread(target=handle_server_messages, args=(sock,), daemon=True).start()

    while True:
        try:
            cmd = input("\nCommands: ready, chat <msg>, vote <name>, ping, exit\n> ").strip()
            if cmd == "ready":
                sock.send(create_message("READY"))
            elif cmd.startswith("chat "):
                msg = cmd[5:]
                sock.send(create_message("CHAT", message=msg, room_id="current"))
            elif cmd.startswith("vote "):
                if in_main_room:
                    target = cmd.split(" ")[1]
                    sock.send(create_message("VOTE", target=target))
                else:
                    print("❌ You can only vote in the main room!")
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
