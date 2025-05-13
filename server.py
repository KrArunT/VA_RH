import asyncio
import pika
import threading
import websockets
import subprocess
import json

# RabbitMQ connection settings
RABBITMQ_HOST = '10.216.179.127'
RABBITMQ_USER = 'admin'
RABBITMQ_PASSWORD = 'Infobell@123'
QUEUE_NAMES = ['VA_AMD', '']

ws_queue = asyncio.Queue()
start_event = asyncio.Event()
connected_clients = set()

# WebSocket server handler
async def websocket_handler(websocket):
    print(f"Client connected: {websocket.remote_address}")
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Received from client: {message}")
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send("❌ Invalid JSON command")
                continue

            if data.get("start") == True:
                if not start_event.is_set():
                    start_event.set()
                    print("✅ START command received. Starting consumers and publishers...")
                    # Start RabbitMQ consumers in background threads
                    for queue_name in QUEUE_NAMES:
                        threading.Thread(target=rabbitmq_consumer, args=(asyncio.get_running_loop(), queue_name), daemon=True).start()
                    # Start publishers
                    subprocess.Popen(["python3", "pub_va.py"])
                    #subprocess.Popen(["python3", "pub2.py"])
                    await websocket.send("✅ Consumers and publishers started.")
                else:
                    await websocket.send("ℹ Already running.")
            else:
                await websocket.send("❌ Unknown command received")
    except websockets.exceptions.ConnectionClosed:
        print(f"Client disconnected: {websocket.remote_address}")
    finally:
        connected_clients.remove(websocket)

# RabbitMQ Consumer thread function
def rabbitmq_consumer(loop, queue_name):
    def on_message(channel, method_frame, header_frame, body):
        message = f"[{queue_name}] {body.decode()}"
        print(f"Received from RabbitMQ: {message}")
        asyncio.run_coroutine_threadsafe(ws_queue.put(message), loop)
        channel.basic_ack(delivery_tag=method_frame.delivery_tag)

    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    connection_params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)
    channel.basic_consume(queue=queue_name, on_message_callback=on_message)

    print(f"🔁 Starting RabbitMQ consumer for queue: {queue_name}")
    try:
        channel.start_consuming()
    except Exception as e:
        print(f"❌ Consumer for {queue_name} stopped: {e}")
    finally:
        connection.close()

# Broadcaster coroutine
async def ws_broadcaster():
    while True:
        message = await ws_queue.get()
        stale_clients = set()
        if connected_clients:
            print(f"📢 Broadcasting: {message}")
            for client in connected_clients:
                try:
                    await client.send(message)
                except websockets.exceptions.ConnectionClosed:
                    stale_clients.add(client)
            # Clean up disconnected clients
            connected_clients.difference_update(stale_clients)
        else:
            print("⚠ No clients connected. Message dropped.")

# Main loop
async def main():
    print("🚀 Starting WebSocket Server on ws://0.0.0.0:8765")
    ws_server = await websockets.serve(websocket_handler, '0.0.0.0', 8768)

    # Start broadcaster task
    asyncio.create_task(ws_broadcaster())

    print("⏳ Waiting for START command from any client...")
    await start_event.wait()

    print("✅ System is now active and listening...")

    # Keep server running
    await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())
