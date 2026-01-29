import asyncio
import os
import time
import wave
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from livekit import api, rtc

# Load env variables
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY")
API_SECRET = os.getenv("LIVEKIT_API_SECRET")

SAMPLE_RATE = 48000
NUM_CHANNELS = 1


async def get_token(room_name="benchmark-room", identity="bench_driver"):
    token = (
        api.AccessToken(API_KEY, API_SECRET)
        .with_identity(identity)
        .with_name("Benchmark Driver")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
    )
    return token.to_jwt()


async def play_audio_file(source: rtc.AudioSource, filepath: str):
    """
    Reads a WAV file, converts it to 10ms AudioFrames, and publishes
    them to the LiveKit room at real-time speed.
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return

    with wave.open(filepath, "rb") as wf:
        # Verify format (Must be 48k/1ch/16bit for this simple script)
        if wf.getframerate() != SAMPLE_RATE or wf.getnchannels() != NUM_CHANNELS:
            print(f"Warning: {filepath} is {wf.getframerate()}Hz. Resampling recommended for best results.")

        # Calculate chunk size for 10ms (standard WebRTC frame duration)
        # 48000 Hz / 100 = 480 samples per 10ms
        samples_per_frame = int(SAMPLE_RATE / 100)

        print(f" -> Playing {filepath}...")

        while True:
            # Read raw bytes
            data = wf.readframes(samples_per_frame)
            if len(data) == 0:
                break

            # Convert raw bytes to Int16 Numpy Array
            # This is crucial: LiveKit expects an array of int16 samples
            pcm_data = np.frombuffer(data, dtype=np.int16)

            # Create the AudioFrame
            frame = rtc.AudioFrame.create(
                sample_rate=SAMPLE_RATE,
                num_channels=NUM_CHANNELS,
                samples_per_channel=samples_per_frame,
            )

            # Load data into the frame (LiveKit SDK specific)
            # We must verify the data length matches what the frame expects
            if len(pcm_data) < samples_per_frame * NUM_CHANNELS:
                # Pad with silence if we are at the very end and have a partial frame
                padding = (samples_per_frame * NUM_CHANNELS) - len(pcm_data)
                pcm_data = np.pad(pcm_data, (0, padding), "constant")

            # Push to WebRTC Source
            # Note: The usage depends on exact SDK version, but usually:
            # frame.data[:] = pcm_data   <-- (If memory view is exposed)
            # or we construct it differently.
            # For current LiveKit Python SDK, AudioFrame accepts the buffer in constructor or via specific method.
            # Let's use the safest 'create' + 'capture' flow for raw buffers:

            await source.capture_frame(frame)

            # BUT WAIT: The frame needs DATA.
            # The current SDK requires creating a frame from the bytes.
            # Correct approach for LiveKit Python > 0.4.x:

            # (Re-creating frame with data for clarity)
            # We actually create the frame FROM the buffer directly usually.
            # Let's use the memoryview approach if 'create' creates an empty buffer.
            # Accessing the underlying C-buffer:
            input_audio_buffer = frame.data
            # We need to cast our numpy array to bytes and copy it in
            # This 'ctypes' style copy is sometimes tricky in pure python

            # SIMPLER ALTERNATIVE FOR BENCHMARKING:
            # If the SDK supports `capture_frame` with a numpy array directly (some versions do), use that.
            # If not, we use the buffer copy:
            # We cast the memoryview to bytes ('B') so we can copy raw bytes into it regardless of the underlying type (int16)
            input_audio_buffer.cast("B")[:] = pcm_data.tobytes()

            await source.capture_frame(frame)

            # Sleep to maintain real-time playback (10ms)
            await asyncio.sleep(0.01)

    print(" -> Playback finished.")


async def run_benchmark(audio_file):
    print(f"\n--- Testing: {os.path.basename(audio_file)} ---")
    token = await get_token()
    room = rtc.Room()

    # 1. Connect
    try:
        await room.connect(LIVEKIT_URL, token)
        print("Driver connected.")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # 2. Setup Mic
    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
    track = rtc.LocalAudioTrack.create_audio_track("bench_mic", source)
    await room.local_participant.publish_track(track)

    # 3. Setup Listener
    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO and participant.identity.startswith("agent"):
            print(" -> Agent Audio Track Detected!")

    # 4. Wait for agent to join
    print(" -> Waiting for agent to join...")
    while len(room.remote_participants) == 0:
        await asyncio.sleep(0.5)
    print(f" -> Agent joined: {list(room.remote_participants.values())[0].identity}")

    # Wait a bit more for subscription/tracks
    await asyncio.sleep(2)

    # 5. Inject Audio
    _t_start = time.time()
    await play_audio_file(source, audio_file)
    _t_audio_end = time.time()

    print(" -> Waiting for response...")
    await asyncio.sleep(10)  # Listen for reply
    await room.disconnect()


if __name__ == "__main__":
    # Ensure you ran 'benchmark/generate_samples.py' first!
    target_file = "benchmark/audio_samples/01_greeting.wav"

    if os.path.exists(target_file):
        asyncio.run(run_benchmark(target_file))
    else:
        print("Error: Audio file not found. Run 'python benchmark/generate_samples.py' first.")
