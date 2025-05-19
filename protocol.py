# protocol.py
import struct
from crypto_utils import encrypt, decrypt

def encode_packet(seq, packet_type, payload):
    raw = f"{packet_type}:{payload}".encode()
    encrypted = encrypt(raw, seq)
    checksum = (sum(encrypted) + seq) % 256
    return struct.pack("!BB", checksum, seq) + encrypted  # checksum + seq + ciphertext

def decode_packet(data):
    if len(data) < 2:
        raise ValueError("Incomplete packet")

    recv_checksum, seq = struct.unpack("!BB", data[:2])
    encrypted = data[2:]
    if (sum(encrypted) + seq) % 256 != recv_checksum:
        raise ValueError("Checksum mismatch")

    raw = decrypt(encrypted, seq)
    parts = raw.decode().split(":", 1)
    if len(parts) != 2:
        raise ValueError("Malformed decrypted content")

    packet_type = int(parts[0])
    payload = parts[1]
    return seq, packet_type, payload
