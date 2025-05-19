# crypto_utils.py
from Crypto.Cipher import AES
import struct

SHARED_KEY = b'supersecretkey12'  # 16 bytes

def get_nonce(seq: int) -> bytes:
    return struct.pack(">Q", seq)  # 8-byte nonce from sequence number

def encrypt(plaintext: bytes, seq: int) -> bytes:
    nonce = get_nonce(seq)
    cipher = AES.new(SHARED_KEY, AES.MODE_CTR, nonce=nonce)
    return cipher.encrypt(plaintext)

def decrypt(ciphertext: bytes, seq: int) -> bytes:
    nonce = get_nonce(seq)
    cipher = AES.new(SHARED_KEY, AES.MODE_CTR, nonce=nonce)
    return cipher.decrypt(ciphertext)
