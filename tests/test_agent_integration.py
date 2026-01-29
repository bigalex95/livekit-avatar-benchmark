import asyncio
import os
import signal
import subprocess
import sys

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from livekit import api, rtc

# Load env variables (ensuring we get the same ones as the agent)
load_dotenv()

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY")
API_SECRET = os.getenv("LIVEKIT_API_SECRET")
TEST_ROOM = "test-agent-room"

# Path to a sample audio file for testing
AUDIO_SAMPLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmark/audio_samples/01_greeting.ogg"
)


@pytest_asyncio.fixture(scope="module")
async def agent_process():
    """
    Fixture to start the agent in a subprocess and clean it up after.
    """
    # Path to agent/main.py
    agent_main = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent/main.py")

    # Run in "benchmark" mode or "interactive"
    env = os.environ.copy()
    env["RUN_MODE"] = "interactive"

    # Start the process
    proc = subprocess.Popen(
        [sys.executable, agent_main, "start"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=os.setsid,  # Create a new process group so we can kill the whole tree
    )

    print(f"Started Agent Process (PID: {proc.pid})")

    # Give it a moment to startup
    await asyncio.sleep(2)

    yield proc

    # Cleanup
    print("Terminating Agent Process...")
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass
    proc.wait()


@pytest.mark.asyncio
async def test_agent_connection_and_response(agent_process):
    """
    Test that the agent connects to the room and we can see it.
    """
    # 1. Create a token for our test driver
    token = (
        api.AccessToken(API_KEY, API_SECRET)
        .with_identity("pytest_driver")
        .with_name("Pytest Driver")
        .with_grants(api.VideoGrants(room_join=True, room=TEST_ROOM))
        .to_jwt()
    )

    room = rtc.Room()

    try:
        # 2. Connect to LiveKit
        print(f"Connecting to {LIVEKIT_URL}...")
        await room.connect(LIVEKIT_URL, token)
        print("Connected to room.")

        # 3. Wait for the agent to join
        print("Waiting for agent to join...")

        async def wait_for_agent():
            while not any(p.identity.startswith("agent") for p in room.remote_participants.values()):
                await asyncio.sleep(0.5)
            return True

        await asyncio.wait_for(wait_for_agent(), timeout=10.0)

        agent_participant = next(p for p in room.remote_participants.values() if p.identity.startswith("agent"))
        print(f"Agent detected: {agent_participant.identity}")

        # 4. Verify agent publishes an audio track (it should, as it greets)
        # We wait for a track subscription
        print("Waiting for agent to publish audio...")

        future = asyncio.Future()

        @room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            if participant.identity == agent_participant.identity and track.kind == rtc.TrackKind.KIND_AUDIO:
                if not future.done():
                    future.set_result(True)

        # Check if already subscribed (remote participants might already have tracks published when we join)
        for p in room.remote_participants.values():
            for pub in p.track_publications.values():
                if pub.track:
                    if pub.track.kind == rtc.TrackKind.KIND_AUDIO:
                        future.set_result(True)

        await asyncio.wait_for(future, timeout=10.0)
        print("Agent audio track received!")

    finally:
        await room.disconnect()
