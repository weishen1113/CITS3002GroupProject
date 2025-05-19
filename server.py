import socket
import threading
import time
import select
from battleship import Board, parse_coordinate
from protocol import encode_packet, decode_packet

HOST = '127.0.0.1'
PORT = 5000

clients = []
boards = []
spectators = []
waiting_queue = []
player_last_active = [time.time(), time.time()]
TIMEOUT = 30
lock = threading.Lock()
turn = 0  # Index of whose turn it is
replay_ready = [False, False]
num_players = 100
disconnected = [False, False]
disconnected_at = [0, 0]

def broadcast_to_spectators(message):
    to_remove = []
    for s in spectators:
        try:
            packet = encode_packet(0, 1, message)
            s.sendall(packet)
        except:
            to_remove.append(s)
    for s in to_remove:
        spectators.remove(s)
            
def broadcast_chat(sender_client, message):
    for client in clients:
        if client is not sender_client:
            try:
                send(client, message, packet_type=2)
            except:
                continue

def broadcast_to_all(message):
    for client in clients:
        try:
            send(client, message)
        except:
            continue  # Ignore any broken connections

def send(client, msg, packet_type=1):
    try:
        packet = encode_packet(0, packet_type, msg)
        client['conn'].sendall(packet)
        print(f"[DEBUG] Sent to {client['id']}: {msg}")
    except Exception as e:
        print(f"[ERROR] Failed to send to {client['id']}: {e}")

def send_board(client, board, broadcast=True):
    board_str = "GRID\n"
    board_str += "  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)) + '\n'
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.display_grid[r][c] for c in range(board.size))
        board_str += f"{row_label:2} {row_str}\n"
    board_str += '\n'

    send(client, board_str)
    if broadcast:
        broadcast_to_spectators(board_str)

    return board_str

def get_opponent_index(my_index):
    for i, c in enumerate(clients):
        if i != my_index and c.get('role') == 'player':
            return i
    return None

def start_game(index, client):
    global turn
    print(f"[DEBUG] Entered start_game(): index={index}, turn={turn}, id={clients[index]['id']}")
    print(f"[DEBUG] Player {index + 1} entering game loop...")
    
    opponent_index = 1 - index
    if opponent_index < 0 or opponent_index >= len(clients):
        send(client, "[ERROR] Opponent not found.")
        return False

    # Ensure board mapping is correct regardless of client index
    board = boards[1] if index == 0 else boards[0]

    while True:
        # print(f"[DEBUG] Checking turn: current={turn}, my_index={index}")
        if turn != index:
            time.sleep(0.05)  # Let other threads breathe
            continue

        print(f"[DEBUG] It's my turn: index={index}")
        send(client, "Your turn. Enter coordinate to fire at (e.g. B5):")

        # Timeout logic
        start_time = time.time()
        sock = client['conn']
        sock.setblocking(0)

        buffer = b''

        while True:
            elapsed = time.time() - start_time
            if elapsed > TIMEOUT:
                send(client, "[TIMEOUT] You took too long. You forfeit.")
                send(clients[opponent_index], "[INFO] Opponent timed out. You win!")

                # Demote BOTH players and re-add to spectators
                clients[index]['role'] = 'waiting'
                clients[index]['has_played'] = True
                spectators.append(clients[index]['conn'])  # Add to spectators

                clients[opponent_index]['role'] = 'waiting'
                clients[opponent_index]['has_played'] = True
                spectators.append(clients[opponent_index]['conn'])  # Add to spectators

                promote_next_players()
                return False

            ready, _, _ = select.select([sock], [], [], 0.5)
            if ready:
                try:
                    chunk = sock.recv(1024)
                    if not chunk:
                        raise ConnectionResetError
                    buffer += chunk
                    print(f"[DEBUG] Received raw chunk from {client['id']}: {chunk}")

                    try:
                        seq, packet_type, payload = decode_packet(buffer)
                        print(f"[DEBUG] Decoded packet from {client['id']}: seq={seq}, type={packet_type}, payload='{payload}'")
                        buffer = b''

                        # Replay protection check — must happen before anything else
                        last_seq = client.get('last_seq', -1)
                        print(f"[DEBUG] Last accepted seq for {client['id']}: {last_seq}")
                        if seq <= last_seq:
                            print(f"[SECURITY] Replayed or out-of-order packet from {client['id']} (seq={seq} <= {last_seq})")
                            send(client, "[SECURITY] Replayed or out-of-order packet ignored.")
                            continue

                        # Accept and store latest seq
                        client['last_seq'] = seq
                        print(f"[DEBUG] Updated last_seq for {client['id']} to {seq}")
                        # input: CHAT <your message>
                        if packet_type == 2:
                            chat_message = f"[CHAT] {client['id']}: {payload}"
                            broadcast_chat(client, chat_message)
                            send(client, f"[CHAT SENT] {payload}")
                            continue

                        elif packet_type != 1:
                            send(client, "[ERROR] Unknown packet type.")
                            continue

                        guess = payload.strip()
                        player_last_active[index] = time.time()
                        break

                    except ValueError:
                        send(client, "[ERROR] Packet corrupted. Ignoring...")
                        buffer = b''
                        continue  # jump to the next loop iteration

                except Exception:
                    disconnected[index] = True
                    disconnected_at[index] = time.time()
                    send(clients[opponent_index], "[INFO] Opponent disconnected. Waiting 60 seconds for reconnection...")

                    reconnect_deadline = time.time() + 60
                    while time.time() < reconnect_deadline:
                        if not disconnected[index]:
                            # Player reconnected
                            client = clients[index]
                            sock = client['conn']
                            sock.setblocking(0)
                            send(client, "[INFO] Reconnected successfully.")
                            send_board(client, board, broadcast=False)
                            send(client, "Welcome back. Enter coordinate to fire at (e.g. B5):")
                            break
                        time.sleep(1)
                    else:
                        # Timeout expired, end game safely
                        if board.all_ships_sunk():  # opponent might have already won
                            return True

                        send(clients[opponent_index], "[INFO] Opponent failed to reconnect. You win!")
                        clients[index]['role'] = 'waiting'
                        clients[index]['has_played'] = True
                        spectators.append(clients[index]['conn'])

                        clients[opponent_index]['role'] = 'waiting'
                        clients[opponent_index]['has_played'] = True
                        spectators.append(clients[opponent_index]['conn'])

                        promote_next_players()
                        return False

            time.sleep(0.1)

        if guess.lower() == 'quit!':
            send(client, "You have quit the game immediately.")
            send(clients[opponent_index], "[INFO] Opponent quit the game. You win!")

            # Demote both players
            clients[index]['role'] = 'waiting'
            clients[index]['has_played'] = True
            spectators.append(clients[index]['conn'])

            clients[opponent_index]['role'] = 'waiting'
            clients[opponent_index]['has_played'] = True
            spectators.append(clients[opponent_index]['conn'])

            promote_next_players()
            return False

        elif guess.lower() == 'quit':
            send(client, "You quit the game. Waiting 60 seconds in case you reconnect.")
            disconnected[index] = True
            disconnected_at[index] = time.time()
            send(clients[opponent_index], "[INFO] Opponent disconnected. Waiting 60 seconds for reconnection...")

            reconnect_deadline = time.time() + 60
            while time.time() < reconnect_deadline:
                if not disconnected[index]:
                    client = clients[index]
                    sock = client['conn']
                    sock.setblocking(0)
                    send(client, "[INFO] Reconnected successfully.")
                    send_board(client, board, broadcast=False)
                    send(client, "Welcome back. Enter coordinate to fire at (e.g. B5):")
                    break
                time.sleep(1)
            else:
                if board.all_ships_sunk():
                    return True

                send(clients[opponent_index], "[INFO] Opponent failed to reconnect. You win!")

                clients[index]['role'] = 'waiting'
                clients[index]['has_played'] = True
                spectators.append(clients[index]['conn'])

                clients[opponent_index]['role'] = 'waiting'
                clients[opponent_index]['has_played'] = True
                spectators.append(clients[opponent_index]['conn'])

                promote_next_players()
                return False

            continue

        try:
            row, col = parse_coordinate(guess)
            if not (0 <= row < 10 and 0 <= col < 10):
                raise ValueError("Out of bounds.")
        except ValueError as e:
            send(client, f"Invalid coordinate: {e}")
            continue

        result, sunk_name = board.fire_at(row, col)
        send_board(client, board)  # attacker sees the updated board, spectators get one copy

        if result == 'hit':
            msg = "HIT!"
            if sunk_name:
                msg += f" You sank the {sunk_name}!"
            send(client, msg)
            send(clients[opponent_index], f"Your ship was hit at {guess}!")
            broadcast_to_spectators(f"[Spectator] {guess}: HIT!{' Sank ' + sunk_name if sunk_name else ''}")

            if board.all_ships_sunk():
                send(client, "You win!")
                send(clients[opponent_index], "You lose!")
                broadcast_to_spectators(f"[Spectator] Player {index + 1} wins!")
                if index == 0:
                    promote_next_players()
                return True  # End game

        elif result == 'miss':
            send(client, "MISS!")
            send(clients[opponent_index], f"Opponent fired at {guess} and missed.")
            broadcast_to_spectators(f"[Spectator] {guess}: MISS!")

        elif result == 'already_shot':
            send(client, "Already fired there. Try again.")
            continue

        turn = opponent_index  # Switch turn

def promote_next_players():
    global clients, boards, turn

    # Reset has_played flags if all waiting players have played
    if all(c.get('has_played') for c in clients if c.get('role') == 'waiting'):
        for c in clients:
            if c.get('role') == 'waiting':
                c['has_played'] = False

    # Skip if game already running
    if len([c for c in clients if c.get('role') == 'player']) >= 2:
        print("[DEBUG] Skipping promotion: match already in progress.")
        return

    # Pick next eligible players
    eligible = [c for c in clients if c.get('role') == 'waiting' and not c.get('has_played')]
    if len(eligible) >= 2:
        players = [eligible[0], eligible[1]]
        players[0]['role'] = 'player'
        players[1]['role'] = 'player'
        players[0]['has_played'] = True
        players[1]['has_played'] = True

        # Remove from spectator list if promoted
        if players[0]['conn'] in spectators:
            spectators.remove(players[0]['conn'])
        if players[1]['conn'] in spectators:
            spectators.remove(players[1]['conn'])

        # Reset boards
        boards.clear()
        for _ in range(2):
            board = Board()
            board.place_ships_randomly()
            boards.append(board)

        turn = 0

        # Notify everyone
        broadcast_to_all("🔁 New match starting!")
        broadcast_to_all(f"[INFO] Next match: {players[0]['id']} vs {players[1]['id']}")
        time.sleep(1)
        send(players[0], "Welcome Player 1! Game will start now.")
        send(players[1], "Welcome Player 2! Game will start now.")
        time.sleep(0.2)
        instructions = (
            "Game started!\n"
            "- Type 'quit' for temporary disconnection (you can reconnect within 60s).\n"
            "- Type 'quit!' for immediate forfeit and transition to next match."
        )
        send(players[0], instructions)
        send(players[1], instructions)

        # Reset sequence tracking
        players[0]['last_seq'] = -1
        players[1]['last_seq'] = -1

        print(f"[DEBUG] Launching threads for: {players[0]['id']} (index 0), {players[1]['id']} (index 1)")
        threading.Thread(target=handle_client, args=(0, players[0]), daemon=True).start()
        threading.Thread(target=handle_client, args=(1, players[1]), daemon=True).start()

        
def handle_client(player_index, client):
    global turn

    print(f"[DEBUG] Starting handle_client thread for: {client['id']}")

    while len(boards) < 2:
        time.sleep(0.1)

    try:
        start_game(player_index, client)
    except Exception as e:
        print(f"[ERROR] start_game crashed for {client['id']}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            send(client, "Game over! Thanks for playing.")
        except:
            pass
        try:
            client['conn'].close()
        except:
            pass

def handle_spectator(client):
    conn = client['conn']
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
            try:
                seq, packet_type, payload = decode_packet(data)

                # Replay protection
                if seq <= client.get('last_seq', -1):
                    send(client, "[SECURITY] Replayed chat packet ignored.")
                    continue
                client['last_seq'] = seq

                if packet_type == 2:  # Chat packet
                    chat_message = f"[CHAT] {client['id']}: {payload}"
                    broadcast_chat(client, chat_message)
                    send(client, f"[CHAT SENT] {payload}")

                # Ignore other packet types silently
            except Exception:
                continue
        except:
            break

def main():
    print(f"[INFO] Server running on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(10)  # Allow many queued connections

        while True:
            conn, addr = s.accept()
            print(f"[INFO] Connection from {addr}")

            username = None
            found_reconnect = False
            while True:
                conn.sendall(encode_packet(0, 1, "[SERVER] Enter your username:"))
                try:
                    data = conn.recv(1024)
                    _, packet_type, candidate = decode_packet(data)

                    if packet_type != 1:
                        conn.sendall(encode_packet(0, 1, "[SERVER] Invalid packet for username."))
                        continue

                    # Reconnect BEFORE duplicate check
                    for i, client in enumerate(clients):
                        if client.get('id') == candidate and disconnected[i]:
                            print(f"[INFO] Reconnecting player {candidate}")
                            client['conn'] = conn
                            client['wfile'] = conn.makefile('w')
                            player_last_active[i] = time.time()
                            disconnected[i] = False
                            client['last_seq'] = -1
                            found_reconnect = True
                            break

                    if found_reconnect:
                        break  # Skip rest; do not add new client object

                    # Check for duplicate usernames (non-disconnected)
                    if any(c['id'] == candidate for c in clients):
                        conn.sendall(encode_packet(0, 1, "Username already exists. Please try again."))
                        continue

                    username = candidate
                    break  # <- correctly escapes prompt loop

                except Exception as e:
                    print(f"[ERROR] Username processing failed: {e}")
                    conn.sendall(encode_packet(0, 1, "Invalid input. Please try again."))

            # If user was a reconnect, do NOT create new client_obj
            if found_reconnect:
                continue

            # New client setup
            client_obj = {
                'conn': conn,
                'role': None,  # will be set to 'player' or 'waiting' below
                'id': username,
                'has_played': False,
                'wfile': conn.makefile('w'),
                'last_seq': -1  # Initialize with -1 (no packets received yet)
            }
            clients.append(client_obj)
            disconnected.append(False)
            disconnected_at.append(0)
            player_last_active.append(time.time())

            # Count current players
            current_players = [c for c in clients if c['role'] == 'player']

            if len(current_players) < 2:
                # Assign as player
                board = Board()
                board.place_ships_randomly()
                boards.append(board)

                client_obj['role'] = 'player'
                client_obj['has_played'] = True

                current_players = [c for c in clients if c['role'] == 'player']
                if len(current_players) == 2:
                    for i, client in enumerate(current_players):
                        send(client, f"Welcome Player {i + 1}! Game will start now.")
                    time.sleep(0.1)
                    instructions = (
                        "Game started!\n"
                        "- Type 'quit' for temporary disconnection (you can reconnect within 60s).\n"
                        "- Type 'quit!' for immediate forfeit and transition to next match."
                    )
                    for i, client in enumerate(current_players):
                        send(client, instructions)
                        threading.Thread(target=handle_client, args=(clients.index(client), client), daemon=True).start()
            else:
                # assign as waiting spectator
                client_obj['role'] = 'waiting'
                spectators.append(conn)
                try:
                    packet = encode_packet(0, 1, "[SERVER] You are connected as a spectator.")
                    conn.sendall(packet)
                except:
                    pass

                # Start spectator thread
                threading.Thread(target=handle_spectator, args=(client_obj,), daemon=True).start()

    # Keep the main thread alive while game threads run
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()