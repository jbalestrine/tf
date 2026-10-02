import asyncio
import socket
import websockets
import json

# --- CONFIGURATION ---
IRC_SERVER = "irc.libera.chat"
IRC_PORT = 6667
IRC_CHANNEL = "#echo-test"
IRC_BOT_NICK = "PythonBridgeBot"

PYTHON_CHAT_WS_URL = "ws://masterchief:8080/echo-chat"  # Your python chat WebSocket URL
# ---------------------

async def handle_irc_to_python_chat(irc_socket, ws_client):
    """Listens for IRC messages and forwards them to the Python chat."""
    loop = asyncio.get_running_loop()
    buffer = ""
    
    while True:
        try:
            # Read data from IRC socket asynchronously
            data = await loop.run_in_executor(None, irc_socket.recv, 2048)
            if not data:
                break
                
            buffer += data.decode("utf-8", errors="ignore")
            lines = buffer.split("\r\n")
            buffer = lines.pop()

            for line in lines:
                # Respond to PING to keep IRC connection alive
                if line.startswith("PING"):
                    irc_socket.send(f"PONG {line.split()[1]}\r\n".encode())
                    continue

                # Parse standard IRC PRIVMSG (messages)
                if "PRIVMSG" in line and IRC_CHANNEL in line:
                    # Example format: :Username!user@host PRIVMSG #channel :Message text
                    user = line.split("!")[0][1:]
                    msg = line.split(f"PRIVMSG {IRC_CHANNEL} :")[1]

                    # Skip messages sent by the bot itself
                    if user == IRC_BOT_NICK:
                        continue

                    # Forward to your Python chat via WebSocket
                    payload = json.dumps({"sender": f"IRC-{user}", "message": msg})
                    await ws_client.send(payload)
                    print(f"[IRC -> Chat] {user}: {msg}")

        except Exception as e:
            print(f"Error in IRC listener: {e}")
            break

async def handle_python_chat_to_irc(irc_socket, ws_client):
    """Listens for Python chat messages and forwards them to IRC."""
    while True:
        try:
            # Receive message from your Python chat
            raw_data = await ws_client.recv()
            data = json.loads(raw_data)
            
            sender = data.get("sender", "Unknown")
            msg = data.get("message", "")

            # Prevent loopback loops
            if sender.startswith("IRC-") or sender == IRC_BOT_NICK:
                continue

            # Forward to IRC
            irc_message = f"PRIVMSG {IRC_CHANNEL} :[{sender}]: {msg}\r\n"
            irc_socket.send(irc_message.encode())
            print(f"[Chat -> IRC] {sender}: {msg}")

        except Exception as e:
            print(f"Error in Chat listener: {e}")
            break

async def main():
    # 1. Connect to IRC via standard TCP Socket
    print(f"Connecting to IRC: {IRC_SERVER}...")
    irc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    irc_socket.connect((IRC_SERVER, IRC_PORT))
    
    # Register the IRC bot
    irc_socket.send(f"NICK {IRC_BOT_NICK}\r\n".encode())
    irc_socket.send(f"USER {IRC_BOT_NICK} 0 * :Python Bridge\r\n".encode())
    irc_socket.send(f"JOIN {IRC_CHANNEL}\r\n".encode())

    # 2. Connect to Python Chat via WebSocket
    print(f"Connecting to Python Chat: {PYTHON_CHAT_WS_URL}...")
    async with websockets.connect(PYTHON_CHAT_WS_URL) as ws_client:
        print("Bridge successfully established!")
        
        # Run both listening directions concurrently
        await asyncio.gather(
            handle_irc_to_python_chat(irc_socket, ws_client),
            handle_python_chat_to_irc(irc_socket, ws_client)
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBridge stopped.")

im using echo_chat as the chat i want to bridge to. i want to use an irc client to connect to you.
