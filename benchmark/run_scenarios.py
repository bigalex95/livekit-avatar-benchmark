import os
import time
import subprocess
import glob
from pathlib import Path
from dotenv import load_dotenv

# 1. Configuration
# Load env variables to get API keys for the CLI
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

AUDIO_DIR = "benchmark/audio_samples"
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
ROOM_NAME = "benchmark-room"

# How long to wait between scenarios (to let Agent finish speaking)
SCENARIO_DELAY_SECONDS = 15


def run_scenario(audio_file):
    filename = os.path.basename(audio_file)
    print(f"\n🎬 STARTING SCENARIO: {filename}")
    print(f"   (Injecting audio via LiveKit CLI...)")

    # 2. Construct the 'lk' CLI command
    # We use --publish to play the file as a microphone
    cmd = [
        "lk",
        "room",
        "join",
        "--url",
        LIVEKIT_URL,
        "--api-key",
        API_KEY,
        "--api-secret",
        API_SECRET,
        "--identity",
        f"tester_{filename}",  # Unique ID per test
        "--publish",
        audio_file,
        ROOM_NAME,
    ]

    try:
        # 3. Run the command
        # We wait for the process to complete (audio file finished uploading/playing)
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Note: 'lk' usually exits after publishing if we don't use --subscribe?
        # Actually 'lk room join' stays open. We need to make sure we only publish
        # and then exit, or kill it after a duration.
        #
        # FIX: The 'lk' tool stays connected indefinitely by default.
        # We should probably run it with a timeout or use a flag if available.
        # Since 'lk' doesn't have "publish and quit", we will use 'timeout' logic in python.

    except subprocess.CalledProcessError as e:
        print(f"❌ Error running scenario {filename}:")
        print(e.stderr)
    except Exception as e:
        print(f"⚠️ execution error: {e}")


def run_timed_scenario(audio_file, duration=10):
    """
    Runs lk CLI for a fixed duration (enough to say the prompt + hear response)
    then kills it to move to next scenario.
    """
    filename = os.path.basename(audio_file)
    print(f"\n------------------------------------------------")
    print(f"🎬 SCENARIO: {filename}")
    print(f"------------------------------------------------")

    cmd = [
        "lk",
        "room",
        "join",
        "--url",
        LIVEKIT_URL,
        "--api-key",
        API_KEY,
        "--api-secret",
        API_SECRET,
        "--identity",
        "tester_bot",
        "--publish",
        audio_file,
        ROOM_NAME,
    ]

    # Start the process non-blocking
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    print(f"   -> 🗣️  Speaking prompt (Process PID: {process.pid})...")

    # Wait while the conversation happens (Agent responding)
    # You can adjust this 'sleep' based on how long your agent usually talks
    for i in range(duration):
        print(f"   -> 👂 Listening... ({duration - i}s remaining)", end="\r")
        time.sleep(1)

    print("\n   -> ⏹️  Finished. Stopping connection.")
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()


def main():
    # 1. Find all .ogg files
    ogg_files = sorted(glob.glob(os.path.join(AUDIO_DIR, "*.ogg")))

    if not ogg_files:
        print(f"❌ No .ogg files found in {AUDIO_DIR}")
        print("   Run 'python benchmark/generate_samples.py' first!")
        return

    print(f"Found {len(ogg_files)} scenarios. Connecting to {LIVEKIT_URL}...")

    # 2. Iterate through them
    for ogg in ogg_files:
        # Run each scenario for 15 seconds (Adjust if agent answers are long)
        run_timed_scenario(ogg, duration=SCENARIO_DELAY_SECONDS)

        # Small buffer between tests
        time.sleep(2)

    print("\n✅ All scenarios completed.")


if __name__ == "__main__":
    main()
