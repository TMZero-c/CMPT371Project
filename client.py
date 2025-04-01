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

    # getting the hostname by socket.gethostname() method
    hostname = socket.gethostname()

    # getting the IP address using socket.gethostbyname() method
    ip_address = socket.gethostbyname(hostname)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((str(ip_address), 5555))

    threading.Thread(target=receive_messages, args=(client,), daemon=True).start()

    print("[CONNECTED] Type messages below to chat.")
    while True:
        message = input("input: ")
        if message.lower() == "exit":
            break
        client.send(message.encode())

    client.close()
    print("[DISCONNECTED]")

if __name__ == "__main__":
    start_client()
