import socket
import threading
import random

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

def GameLoopinit(clients):
    topicList = ["food", "cars", "anime", "movies", "school", "trains", "shervin", "IEEE", "the state of vancouver's economy in chinese", "clothing", "canada", "computer parts", "games", "art"]

    print("Game Has Started!!")
    # role and topic given to players
    innocentTopic = random.choice(topicList)
    innocent = "you're in the majority, you must figure out who the impostor is. The Topic is: " + innocentTopic
    impostor = "you're the impostor, don't get found out, the other innocents have a topic, you need to blend in"
    broadcast_except_random(innocent, impostor)
    
    



def broadcast(message, sender):
    for client in clients:
        if client != sender:
            try:
                client.send(message.encode())
            except:
                client.close()
                del clients[client]

def broadcast_except_random(message, impostMessage): # Used in game logic to determine impostor 
    if not clients:
        return  # no clients connected

    excluded_client = random.choice(list(clients))
    
    for client in clients:
        if client != excluded_client:
            try:
                client.send(message.encode())
            except:
                client.close()
                del clients[client]
        elif client == excluded_client:
            try:
                client.send(impostMessage.encode())
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
        # Each thread contains a client during server runtime
        threading.Thread(target=handle_client, args=(client, addr)).start()

if __name__ == "__main__":
    start_server()
