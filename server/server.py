import os
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_sqlalchemy import SQLAlchemy
import yaml



def load_config():
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # Construct the full path to the server_config.yaml file
    config_path = os.path.join(script_dir, 'server_config.yaml')

    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)

    return config


users = {}
config = load_config()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{config['database_path']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")



class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(80), nullable=False)
    recipient = db.Column(db.String(80), nullable=False)
    content = db.Column(db.String(500), nullable=False)

# Database models
# Database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    nickname = db.Column(db.String(80), nullable=False)
    online = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<User {self.username}>'


def create_tables():
    with app.app_context():
        db.create_all()
# When client connects, automatically add them to a room with their username
@socketio.on('connect')
def handle_connect():
    username = request.args.get('username')
    if username:
        users[request.sid] = username
        join_room(username)
        print(f"[DEBUG] User {username} connected and joined room: {username}")
        emit('message', {'data': 'Connected to server!'})
    else:
        print("[DEBUG] Username not provided in connection parameters!")
        disconnect()

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in users:
        username = users[request.sid]
        print(f"[DEBUG] User {username} disconnected")
        # Fetch user from DB and update online status
        user = User.query.filter_by(username=username).first()
        if user:
            user.online = False
            db.session.commit()
            print(f"[DEBUG] User {username} set to offline in the database.")
        del users[request.sid]


@socketio.on('send_message')
def handle_send_message(data):
    recipient = data['recipient']
    message = data['message']
    sender_sid = request.sid
    sender_username = users.get(sender_sid, "Unknown User")
    print(f"[DEBUG] Sending message from {sender_username} to {recipient}: {message}")
    #emit('receive_message', {'message': message, 'from': sender_username}, room=recipient)
    if recipient == "all":
        # Broadcast the message to all connected clients
        emit('receive_message', {'from': sender_username, 'message': message}, broadcast=True)
    else:
        # Send the message to the specific recipient
        emit('receive_message', {'from': sender_username, 'message': message}, room=recipient)
    # Save the message to the database
    new_message = Message(sender=sender_username, recipient=recipient, content=message)
    db.session.add(new_message)
    db.session.commit()



@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    key = data.get('key')
    nickname = data.get('nickname')

    # Check permission key
    if key != config['user_key']:
        return jsonify({'message': 'Invalid permission key'}), 403

    user = User.query.filter_by(username=username).first()
    if user:
        # User exists, check password
        if user.password == password:
            user.online = True
            db.session.commit()
            return jsonify({'message': 'User logged in', 'id': user.id}), 200
        else:
            return jsonify({'message': 'Invalid password'}), 401
    else:
        # Create new user
        new_user = User(username=username, password=password, nickname=nickname, online=True)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User registered', 'id': new_user.id}), 201

# Handle user logout
@app.route('/logout', methods=['POST'])
def logout():
    user_id = request.get_json().get('user_id')
    user = User.query.get(user_id)
    if user:
        user.online = False
        db.session.commit()
        return jsonify({'message': 'User logged out'}), 200
    return jsonify({'message': 'User not found'}), 404

@app.route('/users', methods=['GET'])
def list_users():
    users = User.query.all()
    users_list = [{'username': user.username, 'nickname': user.nickname, 'online': user.online} for user in users]
    return jsonify(users_list)

@socketio.on('message')
def handle_message(data):
    recipient = data['recipient']
    message = data['message']
    # Example of sending a message; in practice, you'd filter for the recipient's session
    emit('receive_message', {'message': message, 'from': request.sid}, room=recipient)

# Routes and socket events will be added here

if __name__ == '__main__':
    create_tables()
    socketio.run(app, host=config['ip_address'], port=config['port'])
