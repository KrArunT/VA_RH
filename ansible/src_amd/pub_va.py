import os
import requests
import random
import time
import json
import concurrent.futures
import re
from pathlib import Path
import pika

# RabbitMQ connection configuration
RABBITMQ_HOST = '10.216.179.127'
RABBITMQ_USER = 'admin'
RABBITMQ_PASSWORD = 'Infobell@123'
QUEUE_NAME = 'VA_AMD_test'

# RabbitMQ setup
CREDENTIALS = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
CONNECTION_PARAMS = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=CREDENTIALS)
connection = pika.BlockingConnection(CONNECTION_PARAMS)
channel = connection.channel()
channel.queue_declare(queue=QUEUE_NAME, durable=True)

VIDEO_DIR = "./videos"
TRANSCRIPT_DIR = "./transcripts"
SUMMARY_DIR = "./summaries"
NUM_CONTAINERS = 12
BASE_PORT = 8080
SUMMARY_ENDPOINT = "http://10.216.172.152:8000/v1/chat/completions"

os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)

# Global tracking
video_counter = 0
processed_times = []
results_log = []

def send_to_container(video_file, container_id):
    port = BASE_PORT + container_id
    url = f"http://10.216.172.152:{port}/transcribe"

    with open(video_file, "rb") as f:
        files = {"file": (os.path.basename(video_file), f, "video/mp4")}
        try:
            start = time.time()
            response = requests.post(url, files=files, timeout=300)
            response.raise_for_status()
            transcript = response.json().get("transcript", "")
            time1 = time.time() - start
            return transcript, time1, None
        except Exception as e:
            return f"[ERROR] {e}", 0.0, str(e)

def summarize_text(transcript, name):
    prompt = f"""
    You are an intelligent assistant designed to summarize spoken transcripts concisely and accurately.

    Below is the transcript of an audio file:

    --- Transcript Start ---
    {transcript}
    --- Transcript End ---

    Your task:
    1. Summarize the entire transcript in **no more than 128 words**.
    2. Summary should be in **English Language only**.
    3. Capture the main ideas clearly and concisely, avoiding repetition or filler content.
    4. Provide **5 to 6 relevant keywords** that best represent the core topics or themes discussed.

    Return your output in the following format:

    Summary:
    <your 128-word summary here>

    Keywords:
    <comma-separated list of 5-6 keywords>
    """

    payload = {
        "model": "/model",
        "messages": [{"role": "system", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 512
    }

    headers = {"Content-Type": "application/json"}

    try:
        start = time.time()
        response = requests.post(SUMMARY_ENDPOINT, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        summary = response.json()["choices"][0]["message"]["content"].strip()
        match = re.search(r"</think>(.*)", summary, re.DOTALL)
        parsed = match.group(1).strip() if match else summary
        time2 = time.time() - start
        return parsed, time2, None
    except Exception as e:
        return f"[ERROR] {e}", 0.0, str(e)

def process_video(video_file, container_id, counter):
    global processed_times

    name = Path(video_file).stem
    print(f"Processing [{name}]...")

    # Transcription
    transcript, time1, error1 = send_to_container(video_file, container_id)
    if error1:
        print(f"[{name}] Transcription failed: {error1}")
        return

    with open(os.path.join(TRANSCRIPT_DIR, f"{name}.txt"), "w", encoding="utf-8") as f:
        f.write(transcript)

    # Summarization
    summary, time2, error2 = summarize_text(transcript, name)
    if error2:
        print(f"[{name}] Summarization failed: {error2}")
        return

    total_time = time1 + time2
    processed_times.append(total_time)

    # Save summary with counter
    summary_filename = os.path.join(SUMMARY_DIR, f"summary_{name}_{counter}.txt")
    with open(summary_filename, "w", encoding="utf-8") as f:
        f.write(summary)

    avg_latency = sum(processed_times) / len(processed_times)
    throughput = len(processed_times) / sum(processed_times)

    result = {
        "avg_latency": round(avg_latency, 2),
        "throughput": round(throughput, 2),
        "total_video_processed": counter,
        "pending": 100 - counter,
        "summary": summary
    }

    results_log.append(result)
    with open("pipeline_stats.json", "w") as f:
        json.dump(results_log, f, indent=2)

    # ✅ Publish Done message to RabbitMQ
    done_message = {"name": name, "status": "Done"}
    channel.basic_publish(
        exchange='',
        routing_key=QUEUE_NAME,
        body=json.dumps(done_message),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    print(f"[{name}] Done. Total time: {total_time:.2f}s | Avg Latency: {avg_latency:.2f}s | Throughput: {throughput:.2f} vids/s")

def main():
    global video_counter

    video_files = sorted([
        os.path.join(VIDEO_DIR, f)
        for f in os.listdir(VIDEO_DIR)
        if f.endswith(".mp4")
    ])

    # Repeat to get 100 total samples
    all_videos = [random.choice(video_files) for _ in range(100)]

    for i in range(0, len(all_videos), NUM_CONTAINERS):
        batch = all_videos[i:i+NUM_CONTAINERS]
        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_CONTAINERS) as executor:
            futures = []
            for idx, video_file in enumerate(batch):
                video_counter += 1
                futures.append(executor.submit(process_video, video_file, idx % NUM_CONTAINERS, video_counter))
            for future in concurrent.futures.as_completed(futures):
                future.result()  # wait for completion

if __name__ == "__main__":
    try:
        main()
    finally:
        # Ensure connection closes on exit
        connection.close()
        print("✅ All tasks completed and connection closed.")
