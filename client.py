import socket
import threading

def receive_messages(client):
    while True:
        try:
            message = client.recv(1024)
            if not message:
                break
            print("\n[Peer]: " + message.decode())
        except:
            print("\n[ERROR] Connection lost.")
            break

def start_client():

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_port = 5555
        # Discover the server's IP address automatically using broadcast
        client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        client.sendto(b"DISCOVER_SERVER", ('<broadcast>', server_port))
        print("[DISCOVERY] Sent broadcast to discover server.")

        # Wait for server response
        client.settimeout(5)
        try:
            response, server_address = client.recvfrom(1024)
            if response.decode() == "SERVER_HERE":
                server_ip = server_address[0]
                print(f"[DISCOVERY] Server found at {server_ip}.")
                client.connect((server_ip, server_port))

                print("[CONNECTED] Type messages below to chat.")
                while True:
                    message = input()
                    if message.lower() == "exit":
                        break
                    client.send(message.encode())

                client.close()
                print("[DISCONNECTED]")


            else:
                print("[ERROR] Unexpected response during discovery.")
            return
        except socket.timeout:
            print("[ERROR] Server discovery timed out.")
            return
    except ConnectionRefusedError:
        print("[ERROR] Connection refused. Ensure the server is running and listening on the specified port.")
        return

    threading.Thread(target=receive_messages, args=(client,), daemon=True).start()


if __name__ == "__main__":
    start_client()
