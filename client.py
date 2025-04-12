import sys                      # Provides access to some variables used or maintained by the interpreter.
import socket                   # Provides a low-level network interface for communication between processes.
import threading                # Allows the program to run multiple threads concurrently.
import json                     # Enables encoding and decoding of JSON data for message exchange.
from PyQt5.QtWidgets import (   # Importing various PyQt5 widgets for GUI creation.
    QApplication,              # Manages the GUI application's control flow and main settings.
    QWidget,                   # Base class for all user interface objects.
    QTextEdit,                 # Provides a multi-line text editing area (used to display chat messages).
    QLineEdit,                 # Provides a single-line text editor (used for user input).
    QPushButton,               # Creates clickable buttons.
    QVBoxLayout,               # Lays out widgets vertically.
    QLabel,                    # Displays text or images.
    QHBoxLayout,               # Lays out widgets horizontally.
    QMessageBox,               # Displays modal dialog boxes for messages or errors.
    QInputDialog               # Provides dialog boxes to prompt user input.
)
from PyQt5.QtCore import pyqtSignal, QObject   # Importing core components; pyqtSignal is used for custom signals and QObject is the base class of all Qt objects.

# Load the message protocol from a JSON file.
# This file defines the structure and required fields for each message type used in the game.
with open("message_protocol.json", "r") as f:
    MESSAGE_TYPES = json.load(f)

def create_message(message_type, **kwargs):
    """
    Creates a JSON message for the specified message type.
    It uses the MESSAGE_TYPES to know the expected fields, fills them
    using keyword arguments, converts the dictionary to a JSON string,
    and appends a newline as a delimiter for framing.
    """
    message = {"type": message_type}  # Initialize message with its type.
    # Populate each expected field with the provided keyword values.
    for field in MESSAGE_TYPES[message_type]["fields"]:
        message[field] = kwargs.get(field)
    # Convert the message dict to a JSON string, add a newline, and encode to bytes.
    return (json.dumps(message) + "\n").encode()

def parse_message(data):
    """
    Decodes a received bytes object to a JSON object.
    Returns the parsed JSON, or None if decoding fails.
    """
    try:
        return json.loads(data.decode())
    except Exception:
        return None

class Communicator(QObject):
    # Define a custom signal to handle incoming messages (as strings) from the server.
    message_received = pyqtSignal(str)

class GameClient(QWidget):
    def __init__(self):
        """Constructor for the GameClient GUI. Initializes and arranges the UI components, 
        sets up connections, and starts the initial connection to the server."""
        super().__init__()
        
        # Apply a custom dark style to the widget.
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
        
        self.setWindowTitle("Blend In")  # Set the window title.

        self.sock = None  # This will hold the client's socket connection.
        self.comm = Communicator()  # Create a Communicator object for handling signals.
        self.comm.message_received.connect(self.display_message)  # Connect the signal to the display_message method.

        # Set up the main chat display area and input field.
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)  # Users cannot edit this area; it's for displaying messages.

        self.input_line = QLineEdit()
        self.input_line.returnPressed.connect(self.send_input)  # Send input when the user presses Enter.

        # Set up buttons for sending messages, marking ready, and getting help.
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_input)
        
        self.ready_button = QPushButton("Ready")
        self.ready_button.clicked.connect(lambda: self.send_command("READY"))
        
        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self.show_help)

        # Layout configuration: Create a vertical layout for overall arrangement.
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Game Chat"))  # Label for chat section.
        layout.addWidget(self.chat_display)      # Add the chat display.
        layout.addWidget(QLabel("Your Input"))   # Label for the input section.
        layout.addWidget(self.input_line)          # Add the input field.

        # Create a horizontal layout for the buttons.
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.send_button)
        btn_layout.addWidget(self.ready_button)
        btn_layout.addWidget(self.help_button)
        layout.addLayout(btn_layout)  # Add the button layout to the main layout.

        self.setLayout(layout)  # Set the final layout for the widget.

        # Initialize the connection to the server.
        self.init_connection()

    def init_connection(self):
        """
        Asks the user to enter the server IP address and their name, then initializes a socket connection.
        Sends a JOIN_ROOM message to register the client on the server and starts a thread to handle incoming messages.
        """
        ip_address, ok = QInputDialog.getText(self, "Connect to Server", "Enter server IP:")
        if not ok or not ip_address:
            QMessageBox.critical(self, "Connection Error", "No IP provided.")
            sys.exit(1)
        
        # Create a TCP socket.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Connect to the server using the provided IP and fixed port 5555.
        self.sock.connect((ip_address, 5555))

        # Ask for the player's name.
        name, ok = QInputDialog.getText(self, "Enter Name", "Your name:")
        if not ok or not name:
            QMessageBox.critical(self, "Name Error", "No name provided.")
            sys.exit(1)

        # Send a JOIN_ROOM message with the player's name to the server.
        self.sock.send(create_message("JOIN_ROOM", player_name=name))
        # Start a background thread to listen for server messages.
        threading.Thread(target=self.handle_server_messages, daemon=True).start()

    def handle_server_messages(self):
        """
        Continuously listens for messages from the server.
        Processes data by splitting it on newline delimiters (as defined by our message framing), 
        decodes the JSON messages, and acts on the message type accordingly.
        """
        buffer = ""
        while True:
            try:
                data = self.sock.recv(1024)  # Receive data from the server.
                if not data:
                    self.comm.message_received.emit("[Disconnected from server]")
                    break
                buffer += data.decode()  # Append received data to the buffer.

                # Process each complete JSON message in the buffer.
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        msg = parse_message(line.encode())  # Convert message from JSON.
                        if msg:
                            msg_type = msg.get("type")  # Determine the type of message.
                            # Process ASSIGN_ROLE messages to update the player's role.
                            if msg_type == "ASSIGN_ROLE":
                                role = msg.get("role")
                                topic = msg.get("topic")
                                if role == "impostor":
                                    self.comm.message_received.emit("You are the impostor!")
                                elif role == "crewmate":
                                    self.comm.message_received.emit(f"You are a crewmate. Topic: {topic}")
                            # Process VOTE_RESULT messages to display elimination details.
                            elif msg_type == "VOTE_RESULT":
                                voted_out = msg.get("voted_out")
                                self.comm.message_received.emit(f"{voted_out} has been eliminated.")
                            # Process JOIN_LOBBY messages to notify the client.
                            elif msg_type == "JOIN_LOBBY":
                                self.comm.message_received.emit("You have been moved back to the lobby.")
                            # For other message types, display the 'message' field or entire message.
                            else:
                                display_text = msg.get("message") or json.dumps(msg)
                                self.comm.message_received.emit(display_text)
            except Exception as e:
                self.comm.message_received.emit(f"[Error receiving message: {e}]")
                break

    def send_input(self):
        """
        Reads the text input from the QLineEdit, determines the command type (chat, join, vote, etc.),
        sends the appropriate message to the server, and clears the input field.
        """
        text = self.input_line.text().strip()
        if not text:
            return

        # Command for sending chat messages.
        if text.startswith("chat "):
            self.sock.send(create_message("CHAT", message=text[5:], room_id="current"))
        # Command for joining a specific room.
        elif text.startswith("join "):
            value = text.split(" ", 1)[1]
            if value.isdigit():
                self.sock.send(create_message("JOIN", room_id=int(value)))
            else:
                self.display_message("Invalid room number. Use: join <room_number>")
        # Command for voting.
        elif text.startswith("vote "):
            target = text.split(" ", 1)[1]
            self.sock.send(create_message("VOTE", target=target))
        # Ping command for checking connectivity.
        elif text == "ping":
            self.sock.send(create_message("PING"))
        # Exit command to disconnect and close the application.
        elif text == "exit":
            self.sock.close()
            self.close()
        else:
            # If the command is unrecognized, show help text in the chat display.
            self.display_message("Unknown command. Type 'help' for options.")
        
        self.input_line.clear()  # Clear the input field after processing the command.

    def send_command(self, cmd):
        """
        Sends a predefined command to the server. Currently supports marking the client as READY.
        """
        if cmd == "READY":
            self.sock.send(create_message("READY"))
            self.display_message("You are now marked as ready.")

    def show_help(self):
        """
        Displays a help dialog with a list of available commands and their formats.
        """
        help_text = (
            "Available commands:\n"
            "  chat <message>     - Send a chat message to your room\n"
            "  join <room_num>    - Join a specific room\n"
            "  vote <player_name> - Vote for a player\n"
            "  ready              - Mark yourself as ready\n"
            "  ping               - Ping the server\n"
            "  exit               - Disconnect and exit\n"
        )
        QMessageBox.information(self, "Help", help_text)

    def display_message(self, text):
        """
        Appends a new message or status update to the chat display area.
        """
        self.chat_display.append(text)

# ------------------------------ Main Application Entry Point ------------------------------ #
if __name__ == "__main__":
    app = QApplication(sys.argv)  # Create the main QApplication object.
    window = GameClient()           # Instantiate the GameClient GUI.
    window.resize(600, 400)         # Set the initial window size.
    window.show()                   # Display the GUI window.
    sys.exit(app.exec_())           # Start the Qt event loop and exit cleanly when done.
