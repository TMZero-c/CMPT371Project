import socket
import threading

clients = {}

def handle_client(client, addr):
    global clients
    print(f"[NEW CONNECTION] {addr} connected.")

    # Ask for a display name
    client.send("Enter your display name: ".encode())
    display_name = client.recv(1024).decode().strip()
    clients[client] = display_name

    welcome_message = f"[SERVER] {display_name} has joined the chat.\n"
    broadcast(welcome_message, client)

    while True:
        try:
            message = client.recv(1024)
            if not message:
                break
            formatted_message = f"{display_name}: {message.decode()}\n"
            print(f"[MESSAGE] {addr}: {formatted_message.strip()}")
            broadcast(formatted_message, client)
        except:
            break

    print(f"[DISCONNECTED] {addr} ({display_name}) disconnected.")
    client.close()
    del clients[client]
    broadcast(f"[SERVER] {display_name} has left the chat.\n", None)

def broadcast(message, sender):
    for client in clients:
        if client != sender:
            try:
                client.send(message.encode())
            except:
                client.close()
                del clients[client]

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", 5555))
    server.listen()
    print("[SERVER STARTED] Listening on port 5555...")

    while True:
        client, addr = server.accept()
        threading.Thread(target=handle_client, args=(client, addr)).start()

if __name__ == "__main__":
    start_server()
