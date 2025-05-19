# Battleship

---

## Overview

This is a secure, multiplayer Battleship game built with Python. It supports real-time encrypted gameplay between two players, spectator chat, match transitions, reconnections, and basic anti-replay protection. The game uses AES-CTR encryption, replay detection using sequence numbers, and includes a test harness to simulate replay and corruption attacks.

---

## Setup Instructions

1. **The required packages are listed in requirements.txt. To install:**

   ```bash
   pip install -r requirements.txt

   ```

2. **Start the Server**

   ```bash
   python server.py # The server will start listening on 127.0.0.1:5000 and handle multiple players and spectators.

   ```

3. **Start Four Clients**

   **In four separate terminals (or devices), run:**

   ```bash
   python client.py

   ```

   Enter a unique username per client (e.g., p1, p2, p3, p4).

- The first two users will be assigned as Player 1 and Player 2.

- The rest will join as spectators, waiting to be promoted into the next match.

4. **Gameplay Instructions**

   Once assigned as a player:

   You will see:

```bash
 Game started!
 - Type 'quit' for temporary disconnection (you can reconnect within 60s).
 - Type 'quit!' for immediate forfeit and transition to next match.

```

5. **Chat Functionality**

   Players can also chat, but only the player whose turn it is can send messages.

```bash
 CHAT Ready to sink your fleet!

```

Spectators can chat at any time using similar format:

```bash
 CHAT Hello!

```

6. **Reconnection & Quit Notes**

   Typing "quit" will simulate a temporary disconnect. You have 60 seconds to reconnect using the same username.

```bash
 quit

```

Typing quit! ends the game immediately and promotes the next two players.

```bash
 quit!

```

If disconnected unexpectedly (e.g., socket failure), reconnect with the same username to resume your role.

7. **Match Rotation**

   After a game ends:

   - Both players are demoted to spectators.

   - The next two eligible clients from the waiting list are promoted.

   - This continues seamlessly until all clients have played.

   **Note: When a new match begins (e.g., Player 3 vs Player 4), players may need to:**

   - Press ENTER once (without typing anything), then enter your coordinate on the next prompt
   - This is required only for the first input due to how sockets buffer the prompt.

8. **Testing Replay Protection**

   To simulate a replay attack and verify protection:

   ```bash
   python exploit_test.py # Ensure that your server is running.

   ```

   The script sends a valid packet, then attempts to replay it. If protection works, you'll see:

   ```bash
   [✓] Replay attack was detected and dropped (no response).

   ```

9. **Checksum Corruption Test**

   To evaluate the checksum defense against corrupted packets:

   ```bash
   python checksum_test.py

   ```

   This will flip random bits in packets and print detection statistics.

---

## Features

- **battleship.py**: Implements core game logic, including board setup, ship placement, attack handling, and grid display.
- **server.py**: Main server logic and game coordination
- **client.py**: Simple terminal-based client
- **protocol.py**: Packet encoding/decoding with encryption and checksumming
- **crypto_utils.py**: AES-CTR encryption helpers
- **exploit_test.py**: Simulated replay attack test
- **checksum_test.py**: Corruption detection test

---

## Team Members

<table>
  <tr>
    <th>No.</th>
    <th>UWA ID</th>
    <th>Name</th>
  </tr>
  <tr>
    <td>1</td>
    <td>23808128</td>
    <td>Ziye Xie</td>
  </tr>
  <tr>
    <td>2</td>
    <td>24250666</td>
    <td>Wei Shen Hong</td>
  </tr>
</table>
