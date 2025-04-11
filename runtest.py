import subprocess
import threading
import sys

# Start the server process
server_process = subprocess.Popen(["python", "server.py"])

# Start three client processes
client_processes = [
    subprocess.Popen(["python", "client.py"]) for _ in range(3)
]
def monitor_input():
    while True:
        user_input = input()
        if user_input.strip().lower() == 'stop':
            for client_process in client_processes:
                client_process.terminate()
            server_process.terminate()
            sys.exit()

# Start a thread to monitor user input
input_thread = threading.Thread(target=monitor_input, daemon=True)
input_thread.start()


# Wait for all client processes to complete
for client_process in client_processes:
    client_process.wait()

# Terminate the server process
server_process.terminate()
server_process.wait()