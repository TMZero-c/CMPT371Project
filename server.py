import socket
import threading
import random
import math

clients = {} # key: socket obj, value: display name (string)
rooms = {}  # key: room_id (int), value: list of clients

def handle_client(client, addr):
    global clients
    print(f"[NEW CONNECTION] {addr} connected.")

    # Ask for a display name
    client.send("Enter your display name: ".encode())
    display_name = client.recv(1024).decode().strip()
    room_id = handle_room_joining(client)
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
            room_broadcast(formatted_message, room_id, client)
        except:
            break

    print(f"[DISCONNECTED] {addr} ({display_name}) disconnected.")
    client.close()
    del clients[client]
    broadcast(f"[SERVER] {display_name} has left the chat.\n", None)

def GameLoopinit(clients): # we need to make it call gameloopinit when all players are 'ready'
    topicList = ["food", "cars", "anime", "movies", "school", "trains", "shervin", "IEEE", "the state of vancouver's economy in chinese", "clothing", "canada", "computer parts", "games", "art"]

    print("Game Has Started!!")
    broadcast("GAME IS STARTING", None)
    # role and topic given to players
    innocentTopic = random.choice(topicList)
    innocent = "you're in the majority, you must figure out who the impostor is. The Topic is: " + innocentTopic
    impostor = "you're the impostor, don't get found out, the other innocents have a topic, you need to blend in"
    broadcast_except_random(innocent, impostor)
    

def handle_room_joining(client):
    while True:
        try:
            # Calculate how many rooms are allowed based on current clients
            num_players = len(clients) + 1  # +1 for the player who's joining
            max_rooms = math.ceil(num_players / 2)

            client.send(f"Enter a room number to join (1 to {max_rooms}): ".encode())
            room_choice = client.recv(1024).decode().strip()

            if not room_choice.isdigit():
                client.send("Invalid input. Please enter a number.\n".encode())
                continue

            room_id = int(room_choice)
            if room_id < 1 or room_id > max_rooms:
                client.send(f"Room number must be between 1 and {max_rooms}.\n".encode())
                continue

            if room_id not in rooms:
                rooms[room_id] = []

            if len(rooms[room_id]) < 2:
                rooms[room_id].append(client)
                client.send(f"Joined room {room_id}.\n".encode())
                return room_id
            else:
                client.send("Room is full. Try another room.\n".encode())

        except:
            continue

def leave_room(client):
    for room_id, members in list(rooms.items()):
        if client in members:
            members.remove(client)
            client.send(f"You have left room {room_id}.\n".encode())
            print(f"[ROOM UPDATE] Client {clients.get(client, 'Unknown')} left room {room_id}.")
            if len(members) == 0:
                del rooms[room_id]  # delete empty room
            return True
    client.send("You're not in a room.\n".encode())
    return False

def kick_client_from_room(client):
    was_in_room = leave_room(client)
    if was_in_room:
        try:
            client.send("You have been kicked from your room.\n".encode())
        except:
            client.close()



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

def room_broadcast(message, room_id, sender):
    if room_id in rooms:
        for client in rooms[room_id]:
            if client != sender:
                try:
                    client.send(message.encode())
                except:
                    client.close()
                    rooms[room_id].remove(client)



def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", 5555))
    server.listen()
    print("[SERVER STARTED] Listening on port 5555...")
    GameLoopinit(clients) # this should work..

    while True:
        client, addr = server.accept()
        # Each thread contains a client during server runtime
        threading.Thread(target=handle_client, args=(client, addr)).start()

if __name__ == "__main__":
    start_server()
