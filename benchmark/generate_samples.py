import os
from gtts import gTTS
from pydub import AudioSegment

OUTPUT_DIR = "benchmark/audio_samples"
os.makedirs(OUTPUT_DIR, exist_ok=True)

prompts = [
    {
        "filename": "01_greeting.ogg",
        "text": "Hello, do you have a table for two people?",
    },
    {
        "filename": "02_order_complex.ogg",
        "text": "I would like the spicy chicken burger, but without onions, and a large coke.",
    },
    {
        "filename": "03_bill.ogg",
        "text": "Can I get the bill please? We are paying by card.",
    },
]

print(f"Generating {len(prompts)} audio samples in '{OUTPUT_DIR}'...")

for p in prompts:
    print(f" -> Generating: {p['filename']}...")
    # 1. Generate MP3 with Google TTS
    mp3_path = os.path.join(OUTPUT_DIR, "temp.mp3")
    tts = gTTS(p["text"], lang="en")
    tts.save(mp3_path)

    # 2. Convert to OGG (48kHz, Mono, Opus) - LiveKit Compatible
    sound = AudioSegment.from_mp3(mp3_path)
    # Opus usually likes 48kHz.
    sound = sound.set_frame_rate(48000).set_channels(1)

    out_path = os.path.join(OUTPUT_DIR, p["filename"])
    # Export as OGG with libopus codec
    sound.export(out_path, format="ogg", codec="libopus")

    # Cleanup
    if os.path.exists(mp3_path):
        os.remove(mp3_path)

print("Done! Ready for benchmarking.")
