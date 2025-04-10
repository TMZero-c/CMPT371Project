# merged_client_gui.py (PyQt JSON-integrated version)
import sys
import socket
import threading
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextEdit, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

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

class Communicator(QObject):
    new_message = pyqtSignal(str)

class GameClient(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Blend In")
        self.setGeometry(300, 200, 600, 400)

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.communicator = Communicator()
        self.communicator.new_message.connect(self.append_message)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Type your message here...")
        self.msg_input.returnPressed.connect(self.send_message)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)

        self.ready_button = QPushButton("✔️ Ready")
        self.ready_button.clicked.connect(self.mark_ready)

        self.vote_button = QPushButton("🗳️ Vote")
        self.vote_button.clicked.connect(self.vote)

        self.leave_button = QPushButton("🚪 Leave")
        self.leave_button.clicked.connect(self.leave_game)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.msg_input)
        input_layout.addWidget(self.send_button)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ready_button)
        button_layout.addWidget(self.vote_button)
        button_layout.addWidget(self.leave_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.chat_display)
        main_layout.addLayout(input_layout)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        threading.Thread(target=self.connect_and_listen, daemon=True).start()

    def connect_and_listen(self):
        try:
            host = socket.gethostbyname(socket.gethostname())
            port = 5555
            self.client.connect((host, port))

            name, ok = QInputDialog.getText(self, "Name", "Enter your display name:")
            if ok and name:
                self.client.send(create_message("JOIN_ROOM", player_name=name))

            self.communicator.new_message.emit("[CONNECTED] Connected to server.\n")
            self.receive_messages()
        except Exception as e:
            self.communicator.new_message.emit(f"[ERROR] Connection failed: {e}\n")

    def receive_messages(self):
        while True:
            try:
                msg = self.client.recv(1024)
                if not msg:
                    break
                parsed = parse_message(msg)
                if not parsed:
                    continue

                msg_type = parsed.get("type")
                if msg_type == "INFO":
                    self.communicator.new_message.emit(parsed.get("message", ""))
                elif msg_type == "ASSIGN_ROLE":
                    self.communicator.new_message.emit(f"[ROLE] You are the {parsed['role']}. Topic: {parsed['topic']}")
                elif msg_type == "ROOM_JOINED":
                    self.communicator.new_message.emit(f"[JOINED] Room: {parsed['room_id']}, Players: {parsed['players']}")
                elif msg_type == "GAME_STARTED":
                    self.communicator.new_message.emit("[GAME] Game started with players: " + ", ".join(parsed['players']))
                elif msg_type == "VOTE_RESULT":
                    self.communicator.new_message.emit(f"[VOTE RESULT] {parsed['eliminated']} was ejected!")
                elif msg_type == "END_GAME":
                    self.communicator.new_message.emit(f"[GAME OVER] {parsed['winner']} win!")
                elif msg_type == "PONG":
                    self.communicator.new_message.emit("✅ Pong received from server")
            except:
                self.communicator.new_message.emit("[ERROR] Connection lost.\n")
                break

    def send_message(self):
        msg = self.msg_input.text().strip()
        if msg:
            try:
                self.client.send(create_message("CHAT", message=msg, room_id="ROOM123"))
                self.msg_input.clear()
            except:
                self.communicator.new_message.emit("[ERROR] Failed to send message.\n")

    def mark_ready(self):
        try:
            self.client.send(create_message("READY"))
        except:
            self.communicator.new_message.emit("[ERROR] Could not mark ready.\n")

    def vote(self):
        name, ok = QInputDialog.getText(self, "Vote", "Enter name to vote for:")
        if ok and name:
            try:
                self.client.send(create_message("VOTE", target=name))
            except:
                self.communicator.new_message.emit("[ERROR] Vote failed.\n")

    def leave_game(self):
        try:
            self.client.close()
            self.communicator.new_message.emit("[INFO] You disconnected from the game.\n")
        except:
            self.communicator.new_message.emit("[ERROR] Could not disconnect.\n")

    def append_message(self, msg):
        self.chat_display.append(msg.strip())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    client_window = GameClient()
    client_window.show()
    sys.exit(app.exec_())
