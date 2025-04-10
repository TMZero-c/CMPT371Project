# PyQt-based GUI client for the social deduction game
import sys # ehehehehheh
import socket
import threading
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextEdit, QLineEdit, QPushButton, QVBoxLayout, QLabel, QHBoxLayout, QMessageBox,
    QInputDialog
)
from PyQt5.QtCore import pyqtSignal, QObject

'''

Did you know that the critically acclaimed MMORPG Final Fantasy XIV has a free trial, and includes thee ntirety of A Realm Reborn AND the award-winning Heavensward and Stormblood expansions up to level 70 with no restrictions on playtime? Sign up, and enjoy Eorzea today!


'''

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
    except Exception as e:
        return None

class Communicator(QObject):
    message_received = pyqtSignal(str)

class GameClient(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: Consolas;
                font-size: 14px;
            }
            QPushButton {
                background-color: #333;
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QLineEdit, QTextEdit {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)
        self.setWindowTitle("Blend In")

        self.sock = None
        self.comm = Communicator()
        self.comm.message_received.connect(self.display_message)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        self.input_line = QLineEdit()
        self.input_line.returnPressed.connect(self.send_input)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_input)

        self.ready_button = QPushButton("Ready")
        self.ready_button.clicked.connect(lambda: self.send_command("READY"))

        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self.show_help)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Game Chat"))
        layout.addWidget(self.chat_display)
        layout.addWidget(QLabel("Your Input"))
        layout.addWidget(self.input_line)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.send_button)
        btn_layout.addWidget(self.ready_button)
        btn_layout.addWidget(self.help_button)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.init_connection()

    def init_connection(self):
        ip_address, ok = QInputDialog.getText(self, "Connect to Server", "Enter server IP:")
        if not ok or not ip_address:
            QMessageBox.critical(self, "Connection Error", "No IP provided.")
            sys.exit(1)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((ip_address, 5555))

        name, ok = QInputDialog.getText(self, "Enter Name", "Your name:")
        if not ok or not name:
            QMessageBox.critical(self, "Name Error", "No name provided.")
            sys.exit(1)

        self.sock.send(create_message("JOIN_ROOM", player_name=name))
        threading.Thread(target=self.handle_server_messages, daemon=True).start()

    def handle_server_messages(self):
        while True:
            try:
                data = self.sock.recv(1024)
                if not data:
                    self.comm.message_received.emit("[Disconnected from server]")
                    break
                msg = parse_message(data)
                if msg:
                    display_text = msg.get("message") or json.dumps(msg)
                    self.comm.message_received.emit(display_text)
            except:
                break

    def send_input(self):
        text = self.input_line.text().strip()
        if not text:
            return

        if text.startswith("chat "):
            self.sock.send(create_message("CHAT", message=text[5:], room_id="current"))
        elif text.startswith("vote "):
            value = text.split(" ", 1)[1]
            if value.isdigit():
                self.sock.send(create_message("JOIN_SPECIFIC_ROOM", room_id=int(value)))
            else:
                self.sock.send(create_message("VOTE", target=value))
        elif text == "ping":
            self.sock.send(create_message("PING"))
        elif text == "exit":
            self.sock.close()
            self.close()
        else:
            self.display_message("Unknown command. Type 'help' for options.")

        self.input_line.clear()

    def send_command(self, cmd):
        if cmd == "READY":
            self.sock.send(create_message("READY"))

    def show_help(self):
        help_text = (
            "Available commands:\n"
            "  chat <message>     - Send a chat message to your room\n"
            "  vote <name>        - Vote for a player (during voting)\n"
            "  vote <room_num>    - Join a specific room (after game starts)\n"
            "  ping               - Ping the server\n"
            "  exit               - Disconnect and exit\n"
        )
        QMessageBox.information(self, "Help", help_text)

    def display_message(self, text):
        self.chat_display.append(text)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GameClient()
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec_())
