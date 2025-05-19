import random
from protocol import encode_packet, decode_packet

def flip_random_bit(packet: bytes) -> bytes:
    """Flip a random bit in the packet (excluding checksum byte at index 0)."""
    packet = bytearray(packet)
    index = random.randint(1, len(packet) - 1)
    bit = 1 << random.randint(0, 7)
    packet[index] ^= bit
    return bytes(packet)

def simulate_checksum_detection(trials=1000, error_rate=0.05):
    actual_injected = 0
    detected = 0
    undetected = 0

    for _ in range(trials):
        pkt = encode_packet(42, 1, "FIRE B5")
        corrupt = random.random() < error_rate

        if corrupt:
            pkt = flip_random_bit(pkt)
            actual_injected += 1

        try:
            decode_packet(pkt)
            if corrupt:
                undetected += 1
        except ValueError:
            if corrupt:
                detected += 1

    print(f"Total Packets         : {trials}")
    print(f"Injected Corruptions : {actual_injected}")
    print(f"Detected Corruptions : {detected}")
    print(f"Undetected Corruptions: {undetected}")
    print(f"Detection Rate        : {detected / max(1, actual_injected):.2%}")


if __name__ == "__main__":
    simulate_checksum_detection()
