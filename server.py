import socket
import threading
import random
import math
import time

clients = {} # key: socket obj, value: display name (string)
rooms = {}  # key: room_id (int), value: list of clients

ready_clients = set()  # stores sockets of ready clients
ready_lock = threading.Lock()  # so we can safely modify from multiple threads

clients_room_ids = {}  # socket -> room_id (assigned after game starts)
impostor_for_game = None

game_stage = 0
topicList = ["food", "cars", "anime", "movies", "school", "trains", "shervin", "IEEE", "the state of vancouver's economy in chinese", "clothing", "canada", "computer parts", "games", "art"]

def handle_client(client, addr):
    global clients
    print(f"[NEW CONNECTION] {addr} connected.")

    # Ask for a display name
    client.send("Enter your display name: ".encode())  
    display_name = client.recv(1024).decode().strip()
    # room_id = handle_room_joining(client)
    clients[client] = display_name

    welcome_message = f"[SERVER] {display_name} has joined the chat.\n"
    broadcast(welcome_message, client)

    client.send("Enter \"ready\" when ready!, when all players are ready, the game will start\n".encode())

    while True:
        try:
            message = client.recv(1024)
            if not message:
                break

            decoded_message = message.decode().strip().lower()

            if decoded_message == "ready":
                with ready_lock:
                    if client not in ready_clients:
                        ready_clients.add(client)
                        print(f"[READY] {display_name} is ready.")
                        client.send("You are marked as ready.\n".encode())

                    if len(ready_clients) == len(clients):
                        GameLoopinit(clients)

                        # Now let each client join a room
                        for c in list(clients.keys()):
                            room_id = handle_room_joining(c)
                            clients_room_ids[c] = room_id
                continue

            formatted_message = f"{display_name}: {message.decode()}\n"
            print(f"[MESSAGE] {addr}: {formatted_message.strip()}")

            # Only broadcast to same room after rooms are assigned
            if client in clients_room_ids:
                room_id = clients_room_ids[client]
                room_broadcast(formatted_message, room_id, client)
            else:
                client.send("Game hasn't started yet or you're not in a room.\n".encode())

        except:
            break

    print(f"[DISCONNECTED] {addr} ({display_name}) disconnected.")
    client.close()
    del clients[client] 
    with ready_lock:
        if client in ready_clients:
            ready_clients.remove(client)
    clients_room_ids.pop(client, None)
    
    broadcast(f"[SERVER] {display_name} has left the chat.\n", None)



def GameLoopinit(clients): # i dont remeber why i added clients param but hwtaever

    print("Game Has Started!!")
    broadcast("GAME IS STARTING!\n", None)
    # role and topic given to players
    innocentTopic = random.choice(topicList)
    innocent = "you're in the majority, you must figure out who the impostor is. The Topic is: " + innocentTopic + "\n"
    impostor = "you're the impostor, don't get found out, the other innocents have a topic, you need to blend in \n"
    broadcast_except_random(innocent, impostor)

    '''
    # start a timer or something, once its over start voting phase
    # then use forcestage to bypass timer
    if game_stage == 1:
        # start voting and do a kick
        to_be_kicked = start_voting_sequence()
        eject_client(to_be_kicked, "you were voted out ig lol")
        # then check if impostor is dead or not
        if impostor_for_game == None:
            print("innocent wins!")
            end_game()
            # end game and reset everything
    elif game_stage > 1:
        # recursively call second_round_and_up
        second_round_and_up(clients)
        pass

    # then repeat a modified GameLoopinit in which the impostor is already exists maybe
    # broadcast_except_select_one(innocent, impostor, impostor_for_game)
    '''

def game_state_listener():
    global game_stage

    print("[GAME STATE LISTENER] Started monitoring game_stage.")
    previous_stage = game_stage  # Keep track of the last known game stage

    while True:
        if game_stage != previous_stage:  # Check if game_stage has changed
            print(f"[GAME STATE] Detected change in game_stage: {game_stage}")

            if game_stage == 1:
                # Start voting and eject a player
                to_be_kicked = start_voting_sequence()
                if to_be_kicked:
                    eject_client(to_be_kicked, "You were voted out!")
                # Check if the impostor is dead
                if impostor_for_game is None:
                    print("Innocents win!")
                    end_game()
                else:
                    print("Game continues to the next round.")

            elif game_stage > 1:
                # Handle subsequent rounds
                print(f"its round {game_stage}!!")
                print("wahoo!!!!")

                
                innocent2 = "you're still in the majority, you must figure out who the impostor is. The Topic is: " + innocentTopic + "\n"
                impostor2 = "you're still the impostor! don't get found out, the other innocents have a topic, you need to blend in. Good luck \n"
                if game_stage % 2 == 0: # even stage, talking round
                    innocentTopic = random.choice(topicList)
                    print("continuing game, round: " + str(game_stage))
                    broadcast_except_select_one(innocent2, impostor2, impostor_for_game)

                if game_stage % 2 is not 0: # odd stage, voting round

                    # Start voting and eject a player
                    to_be_kicked = start_voting_sequence()
                    if to_be_kicked:
                        eject_client(to_be_kicked, "You were voted out!")


                    if len(clients) == 2 and impostor_for_game is not None: # amount of players is 2, and impostor still alive
                        # impostor wins and end game
                        print("impostor wins!")
                        end_game()
                    elif impostor_for_game == None: #impostor is dead
                        # innocent wins and end game
                        print("innocent wins!")
                        end_game()
                    else:
                        #continue game let players go back into rooms.
                        # then start voting seqence again until other conditions are met.
                        broadcast("the impostor still lies among us...\n", None)
                        game_stage += 1 # increment game stage to continue the game

                        
                        

            # Update the previous stage
            previous_stage = game_stage

        # Add a small delay to avoid busy-waiting
        time.sleep(0.1)



def end_game():
    global game_stage, impostor_for_game, clients_room_ids, rooms, ready_clients

    print("[GAME END] Ending the game and resetting the server state.")

    # Reset game stage
    game_stage = 0

    # Clear impostor and room-related data
    impostor_for_game = None
    clients_room_ids.clear()
    rooms.clear()

    # Reset ready clients
    with ready_lock:
        ready_clients.clear()

    # Notify all clients that the game has ended
    for client in list(clients.keys()):
        try:
            client.send("[SERVER] The game has ended. Waiting for all players to be ready again.\n".encode())
        except:
            client.close()
            del clients[client]

    # Restart the ready check
    for client in list(clients.keys()):
        try:
            client.send("Enter \"ready\" when ready to start a new game.\n".encode())
        except:
            client.close()
            del clients[client]

    print("[GAME RESET] Game state has been reset. Waiting for players to be ready.")

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
        print("something is very wrong..")
        return  # no clients connected

    excluded_client = random.choice(list(clients.keys())) #if theres only one player, they will always be the
    # impostor LOL
    impostor_for_game = excluded_client
    
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
    return impostor_for_game

def broadcast_except_select_one(message, impostMessage, impostClient): # Used in game logic to determine impostor 
    if not clients:
        print("something is very wrong..")
        return  # no clients connected

    excluded_client = impostClient
    # this should be round 2+ stuff
    
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

def eject_client(client, reason=None):
    display_name = clients.get(client, "The Game")

    try:
        if reason:
            client.send(f"You have been ejected: {reason}\n".encode())
        else:
            client.send("You have been ejected from the server.\n".encode())
    except:
        pass  # It's okay if sending fails

    print(f"[EJECTED] {display_name} has been ejected from the server.")

    # Remove from room
    for room_id, members in list(rooms.items()):
        if client in members:
            members.remove(client)
            if len(members) == 0:
                del rooms[room_id]

    # if they are impostor, clean impostor
    if client == impostor_for_game:
        impostor_for_game = None
        print("[IMPOSTOR EJECTED] The impostor has been ejected.")

    # Clean up tracking structures
    with ready_lock:
        ready_clients.discard(client)
    clients_room_ids.pop(client, None)
    if client in clients:
        del clients[client]

    try:
        client.close()
    except:
        pass

def start_voting_sequence():
    print("[VOTING] Voting sequence has started.")
    
    # 1. Remove all clients from rooms
    for client in clients:
        clients_room_ids.pop(client, None)
    rooms.clear()

    # 2. Notify players
    for client in clients:
        try:
            client.send("\n[VOTING] Discussion is over. Time to vote!\n".encode())
            client.send("Type the display name of the person you think is the impostor:\n".encode())
        except:
            continue

    # 3. Collect votes
    votes = {}
    vote_lock = threading.Lock()
    vote_event = threading.Event()

    def collect_vote(client):
        try:
            vote = client.recv(1024).decode().strip()
            with vote_lock:
                votes[vote] = votes.get(vote, 0) + 1
            client.send(f"[VOTING] You voted for: {vote}\n".encode())
        except:
            pass
        finally:
            vote_event.set()

    threads = []
    for client in list(clients.keys()):
        t = threading.Thread(target=collect_vote, args=(client,))
        t.start()
        threads.append(t)

    # 4. Wait for all votes to come in or timeout (e.g., 30 seconds)
    timeout = 30
    for t in threads:
        t.join(timeout=timeout)

    # 5. Tally votes
    if not votes:
        print("[VOTING] No votes were cast.")
        return None

    max_votes = max(votes.values())
    top_voted = [name for name, count in votes.items() if count == max_votes]

    if len(top_voted) > 1:
        # start tie sequence, this is temporary
        chosen_name = random.choice(top_voted)
        pass
    else:
        chosen_name = top_voted[0] 
    

    # Find the client corresponding to the chosen name
    chosen_client = None
    for client, name in clients.items():
        if name == chosen_name:
            chosen_client = client
            break

    print(f"[VOTING RESULT] Chosen by vote: {chosen_client}")
    broadcast(f"\n[VOTING RESULT] The group voted for: {chosen_client}\n", None)
        
    return chosen_client  # returns client obj


def server_command_listener():
    while True:
        cmd = input(">> ").strip().lower()

        if cmd == "list":
            print(f"[SERVER] Connected clients: {len(clients)}")
            for client, name in clients.items():
                print(f"- {name}")
        
        elif cmd.startswith("eject "):
            name_to_kick = cmd.split(" ", 1)[1]
            found = False
            for client, name in list(clients.items()):
                if name.lower() == name_to_kick.lower():
                    eject_client(client, "You were kicked by the server.")
                    found = True
                    break
            if not found:
                print(f"[SERVER] No client with name '{name_to_kick}' found.")
        
        elif cmd == "rooms":
            print("[SERVER] Current rooms and occupants:")
            for room_id, members in rooms.items():
                names = [clients.get(c, "Unknown") for c in members]
                print(f"Room {room_id}: {', '.join(names)}")
        
        elif cmd == "help":
            print("Available commands:")
            print("  list           - Show connected clients")
            print("  eject [name]   - Kick client by display name")
            print("  rooms          - Show room status")
            print("  help           - Show this help message")

        elif cmd == "forcestage":
            with ready_lock:  # Use a lock to ensure thread safety
                game_stage += 1
            print(f"[SERVER] Forcing game stage! New game_stage: {game_stage}")


        else:
            print("[SERVER] Unknown command. Type 'help' for options.")

def start_discovery_responder(port=5555):
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind(('', port))
    print("[DISCOVERY] Ready to respond to broadcast...")

    while True:
        msg, addr = udp.recvfrom(1024)
        if msg == b"DISCOVER_SERVER":
            print(f"[DISCOVERY] Ping from {addr}, responding...")
            udp.sendto(b"SERVER_HERE", addr)


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', 5555))
    server.listen()
    print("[SERVER STARTED] Listening on port 5555...")
    
    # fucky wucky
    threading.Thread(target=start_discovery_responder, daemon=True).start()

    # Start the game state listener in a separate thread
    threading.Thread(target=game_state_listener, daemon=True).start()

    # Start the server command listener in a separate thread
    threading.Thread(target=server_command_listener, daemon=True).start()

    while True:
        client, addr = server.accept()
        # Each thread contains a client during server runtime
        threading.Thread(target=handle_client, args=(client, addr)).start()



if __name__ == "__main__":
    start_server()
