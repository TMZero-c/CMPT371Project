import socket
import threading

# Server configuration
HOST = '0.0.0.0'  # Bind to all available interfaces
PORT = 12345      # Port to listen on

# List to keep track of connected clients
clients = []

# Function to handle client communication
def handle_client(client_socket, addr):
    print(f"[NEW CONNECTION] {addr} connected.")
    clients.append(client_socket)
    try:
        while True:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break
            print(f"[{addr}] {message}")
            broadcast(message, client_socket)
    except ConnectionResetError:
        print(f"[DISCONNECTED] {addr} disconnected.")
    finally:
        clients.remove(client_socket)
        client_socket.close()

# Function to broadcast messages to all clients except the sender
def broadcast(message, sender_socket):
    for client in clients:
        if client != sender_socket:
            try:
                client.send(message.encode('utf-8'))
            except:
                clients.remove(client)

# Main server function
def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[LISTENING] Server is listening on {HOST}:{PORT}")
    try:
        while True:
            client_socket, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(client_socket, addr))
            thread.start()
            print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")
    except KeyboardInterrupt:
        print("\n[SHUTTING DOWN] Server is shutting down.")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()