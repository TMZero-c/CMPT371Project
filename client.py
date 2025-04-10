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

def discover_server(port=5555):
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp.settimeout(5)

    try:
        udp.sendto(b"DISCOVER_SERVER", ('<broadcast>', port))
        print("[DISCOVERY] Sent broadcast to discover server...")

        response, server_address = udp.recvfrom(1024)
        if response.decode() == "SERVER_HERE":
            print(f"[DISCOVERY] Server found at {server_address[0]}")
            return server_address[0]
    except socket.timeout:
        print("[ERROR] Server discovery timed out.")
    finally:
        udp.close()
    return None


def start_client():
    server_ip = discover_server()
    if not server_ip:
        return

    # Now connect using TCP
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((server_ip, 5555))
    except Exception as e:
        print(f"[ERROR] Could not connect to server: {e}")
        return

    threading.Thread(target=receive_messages, args=(client,), daemon=True).start()

    print("[CONNECTED] Type messages below to chat.")
    while True:
        message = input()
        if message.lower() == "exit":
            break
        client.send(message.encode())

    client.close()
    print("[DISCONNECTED]")

if __name__ == "__main__":
    start_client()
