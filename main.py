import os
import sys
import whisper
import subprocess
import requests
import time

# Create output folders if not exist
os.makedirs("audios", exist_ok=True)
os.makedirs("transcripts", exist_ok=True)
os.makedirs("summarize", exist_ok=True)

VLLM_API_URL = "http://localhost:16000/generate"

def convert_mp4_to_mp3(input_file, output_file):
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "192k",
        output_file
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def transcribe_audio(audio_file):
    model = whisper.load_model("small")
    result = model.transcribe(audio_file)
    return result["text"]

def summarize_text(text):
    prompt = f"Summarize the following text:\n\n{text}\n\nSummary:"
    payload = {
        "prompt": prompt,
        "max_tokens": 512,
        "temperature": 0.3
    }
    response = requests.post(VLLM_API_URL, json=payload)
    if response.status_code == 200:
        result = response.json()
        return result.get("text", "No summary returned.")
    else:
        return f"Error: {response.status_code} {response.text}"

def main(input_file):
    total_start = time.time()

    # Step 1: Convert MP4 to MP3
    mp3_file = os.path.join("audios", os.path.splitext(os.path.basename(input_file))[0] + ".mp3")
    start = time.time()
    convert_mp4_to_mp3(input_file, mp3_file)
    mp4_to_mp3_latency = time.time() - start
    print(f"MP4 to MP3 conversion latency: {mp4_to_mp3_latency:.2f} seconds")

    # Step 2: Transcribe MP3
    start = time.time()
    transcript = transcribe_audio(mp3_file)
    mp3_to_transcript_latency = time.time() - start
    print(f"MP3 to Transcript latency: {mp3_to_transcript_latency:.2f} seconds")

    # Save transcript
    transcript_file = os.path.join("transcripts", os.path.splitext(os.path.basename(mp3_file))[0] + ".txt")
    with open(transcript_file, "w", encoding="utf-8") as f:
        f.write(transcript)

    # Step 3: Summarize transcript
    start = time.time()
    summary = summarize_text(transcript)
    summarization_latency = time.time() - start
    print(f"Summarization latency: {summarization_latency:.2f} seconds")

    # Save summary
    summary_file = os.path.join("summarize", os.path.splitext(os.path.basename(mp3_file))[0] + "_summary.txt")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary)

    # Total latency
    total_latency = time.time() - total_start
    print(f"Total process latency: {total_latency:.2f} seconds")

    # Log all latencies
    print("\n--- Latency Report ---")
    print(f"MP4 to MP3 conversion: {mp4_to_mp3_latency:.2f} s")
    print(f"MP3 to Transcript: {mp3_to_transcript_latency:.2f} s")
    print(f"Summarization: {summarization_latency:.2f} s")
    print(f"Total: {total_latency:.2f} s")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <video_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    main(input_file)
