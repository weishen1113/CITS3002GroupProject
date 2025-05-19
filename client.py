import socket
import threading
from protocol import decode_packet, encode_packet

HOST = '127.0.0.1'
PORT = 5000
running = True

def main():
    global running
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        seq = 0
        s.connect((HOST, PORT))

        # Username negotiation loop
        while True:
            data = s.recv(1024)
            try:
                _, packet_type, payload = decode_packet(data)
                print(payload)

                if "Enter your username" in payload or "already taken" in payload:
                    username = input(">> ")
                    s.sendall(encode_packet(seq, 1, username))
                    seq += 1
                elif "Type 'quit'" in payload or "Enter coordinate" in payload or "connected as a spectator" in payload:
                    break  # Game has started, stop prompting for username
            except Exception as e:
                print(f"[ERROR] Username negotiation failed: {e}")
                return

        # Start receiving thread
        recv_thread = threading.Thread(target=receive_messages, args=(s,))
        recv_thread.daemon = True
        recv_thread.start()

        try:
            while running:
                user_input = input()

                if user_input.lower() == "quit":
                    s.sendall(encode_packet(seq, 1, "quit"))
                    print("You exited the game.")
                    running = False
                    break

                if user_input.startswith("CHAT "):
                    msg = user_input[5:]
                    s.sendall(encode_packet(seq, 2, msg))
                else:
                    s.sendall(encode_packet(seq, 1, user_input))

                seq += 1

        except KeyboardInterrupt:
            print("\n[INFO] Client interrupted. Exiting...")
            running = False

def receive_messages(sock):
    buffer = b''
    while running:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buffer += chunk

            while len(buffer) >= 1:
                checksum = buffer[0]
                # Try to decrypt the rest and validate checksum
                try:
                    # Minimum valid length: 1 checksum + 8 nonce + something encrypted
                    _, _, payload = decode_packet(buffer)
                    print(f"\n{payload}")
                    print(">> ", end="", flush=True)
                    buffer = b''  # Clear after successful decode
                    break
                except ValueError:
                    # wait for more data to form a full packet
                    break
        except Exception as e:
            print("[ERROR]", e)
            break

if __name__ == "__main__":
    main()
