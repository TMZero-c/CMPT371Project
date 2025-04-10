import sys
import socket
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextEdit, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject


class Communicator(QObject):
    new_message = pyqtSignal(str)


class GameClient(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Social Deduction Game")
        self.setGeometry(300, 200, 600, 400)

        # Socket setup
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.communicator = Communicator()
        self.communicator.new_message.connect(self.append_message)

        # UI components
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
        self.leave_button.clicked.connect(self.leave_room)

        # Layouts
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

        threading.Thread(target=self.connect_to_server, daemon=True).start()

    def connect_to_server(self):
        try:
            host = "192.168.1.42"  # <-- Replace with your server's IP
            port = 5555
            self.client.connect((host, port))
            threading.Thread(target=self.receive_messages, daemon=True).start()
            self.communicator.new_message.emit("[CONNECTED] Connected to server.\n")
        except Exception as e:
            self.communicator.new_message.emit(f"[ERROR] Connection failed: {e}\n")

    def receive_messages(self):
        while True:
            try:
                msg = self.client.recv(1024)
                if not msg:
                    break
                self.communicator.new_message.emit(msg.decode())
            except:
                self.communicator.new_message.emit("[ERROR] Connection lost.\n")
                break

    def send_message(self):
        msg = self.msg_input.text().strip()
        if msg:
            try:
                self.client.send(msg.encode())
                self.msg_input.clear()
            except:
                self.communicator.new_message.emit("[ERROR] Failed to send message.\n")

    def mark_ready(self):
        try:
            self.client.send("ready".encode())
        except:
            self.communicator.new_message.emit("[ERROR] Could not mark ready.\n")

    def leave_room(self):
        try:
            self.client.send("leave".encode())
        except:
            self.communicator.new_message.emit("[ERROR] Could not leave room.\n")

    def vote(self):
        name, ok = QInputDialog.getText(self, "Vote", "Enter name to vote for:")
        if ok and name:
            try:
                self.client.send(name.encode())
            except:
                self.communicator.new_message.emit("[ERROR] Vote failed.\n")

    def append_message(self, msg):
        self.chat_display.append(msg.strip())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    client_window = GameClient()
    client_window.show()
    sys.exit(app.exec_())
