import socketio
import typer
import requests
from InquirerPy import inquirer
import yaml
import os
import logging
import random

# Define a list of available colors
colors = ["green", "yellow", "blue", "magenta", "cyan", "white"]

# Define a dictionary to store sender-color pairs
sender_colors = {}

app = typer.Typer()# Configure logging
logging.basicConfig(level=logging.ERROR)  # Set higher logging level to suppress INFO and DEBUG messages

app = typer.Typer()
sio = socketio.Client(logger=False, engineio_logger=False)  # Now logging is filtered by the global logging level
def load_config():
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # Construct the full path to the server_config.yaml file
    config_path = os.path.join(script_dir, 'client_config.yaml')

    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)

    return config


config = load_config()

# Server URL for HTTP requests
SERVER_URL = f"http://{config['server_ip']}:{config['server_port']}"


@sio.event
def connect():
    print("Connection established")
    sio.emit('after_connect', {'data': 'Client connected'})



@sio.event
def receive_message(data):
    sender = data['from']
    message = data['message']

    # If the sender is not in the dictionary, assign a random color to it
    if sender not in sender_colors:
        sender_colors[sender] = random.choice(colors)

    # Use typer to print the message with color
    colored_message = typer.style(f"\n{sender}: {message}", fg=sender_colors[sender])
    typer.echo(colored_message)

@sio.event
def disconnect():
    print("Disconnected from server")

def get_users():
    users_response = requests.get(f"{SERVER_URL}/users")
    users = users_response.json()
    # typer.echo("Current users:")
    online_users = {user['username']: user for user in users if user['online']}
    usernames = list(online_users.keys())
    for user in users:
        status = 'online' if user['online'] else 'offline'
        typer.echo(f"{user['username']} ({user['nickname']}): {status}")
    return users, usernames

def print_commands():
    """Prints the available commands."""
    typer.echo(typer.style(f"Welcome! Available commands:", fg="red"))
    typer.echo(typer.style(f"/chg: Change the recipient of the message", fg="red"))

@app.command()
def start():
    """Start the client and handle user interaction."""
    print_commands()
    connect_url = f"http://{config['server_ip']}:{config['server_port']}?username={config['username']}"
    sio.connect(connect_url)
    print(f"[DEBUG] Attempting to connect to {connect_url}")

    if not register():
        typer.echo("Cannot proceed without registration or login.")
        raise typer.Exit()

    current_recipient = None
    try:
        while True:

            #users, usernames = get_users()

            # If no recipient is selected yet, select one
            if not current_recipient:
                users, usernames = get_users()
                current_recipient = inquirer.select(
                    message="Choose the username of the recipient",
                    choices=usernames,
                ).execute()

            message = typer.prompt("Enter your message")

            # Check if the message is a command to change the recipient
            if message == "/chg":
                users, usernames = get_users()
                current_recipient = inquirer.select(
                    message="Choose the username of the recipient",
                    choices=usernames,
                ).execute()
                message = typer.prompt("Enter your message")


            print(f"[DEBUG] Sending message to {current_recipient}: {message}")
            sio.emit('send_message', {'recipient': current_recipient, 'message': message})

    except KeyboardInterrupt:
        sio.disconnect()
        typer.echo("Disconnected.")


def register():
    """Attempt to register or log in the user."""
    response = requests.post(f"{SERVER_URL}/register", json={
        'username': config['username'],
        'password': config['password'],
        'key': config['key'],
        'nickname': config['nickname']
    })
    if response.status_code in [200, 201]:
        typer.echo(f"Registration/Login successful: {response.json()}")
        return True
    else:
        typer.echo(f"Failed to register/login: {response.json()['message']}")
        return False


if __name__ == "__main__":
    app()