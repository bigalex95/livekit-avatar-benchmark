import asyncio

from livekit import api, rtc

# Configuration matches docker-compose.yml
LIVEKIT_URL = "ws://localhost:7880"
API_KEY = "devkey"
API_SECRET = "secret"
ROOM_NAME = "benchmark-room"


async def main():
    print(f"Connecting to {LIVEKIT_URL} room '{ROOM_NAME}'...")

    # 1. Create a token for the tester
    token = (
        api.AccessToken(API_KEY, API_SECRET)
        .with_identity("python-tester")
        .with_name("Python Tester")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=ROOM_NAME,
            )
        )
    ).to_jwt()

    # 2. Connect to the room
    room = rtc.Room()

    agent_found_event = asyncio.Event()

    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        print(f"Participant connected: {participant.identity} ({participant.kind})")
        # In newer LiveKit versions, agents might have a specific kind or we assume any other participant is the agent
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            print("✅ Detected Agent participant!")
            agent_found_event.set()
        elif participant.identity.startswith("agent-"):  # Fallback check
            print("✅ Detected participant with 'agent-' prefix!")
            agent_found_event.set()

    try:
        await room.connect(LIVEKIT_URL, token)
        print("Connected to room.")

        # Check existing participants
        for identity, participant in room.remote_participants.items():
            print(f"Existing participant: {identity} ({participant.kind})")
            if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT or identity.startswith("agent-"):
                print("✅ Found existing Agent!")
                agent_found_event.set()

        print("Waiting for agent to join...")
        try:
            await asyncio.wait_for(agent_found_event.wait(), timeout=10)
            print("\nSUCCESS: Agent connected to the room.")
        except TimeoutError:
            print("\nFAILURE: Agent did not connect within 10 seconds.")
            print("Make sure the agent is running (use scripts/start.sh)")

    finally:
        await room.disconnect()


if __name__ == "__main__":
    # Ensure livekit package is installed
    try:
        asyncio.run(main())
    except ImportError:
        print("Please install livekit python sdk: pip install livekit")
    except Exception as e:
        print(f"An error occurred: {e}")
