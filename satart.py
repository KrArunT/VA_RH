import asyncio
import websockets
import json

async def start_and_listen():
    uri = "ws://localhost:8768"  # Change to your server's IP if needed
    async with websockets.connect(uri) as websocket:
        start_command = {"start": True}
        await websocket.send(json.dumps(start_command))
        print("✅ Sent START command to server.")

        try:
            while True:
                message = await websocket.recv()
                print(f"📩 Received message from server: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Connection closed by server.")

if __name__ == "__main__":
    asyncio.run(start_and_listen())
