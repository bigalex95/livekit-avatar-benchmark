import asyncio
import os
import signal
from livekit import rtc, api

# Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
ROOM_NAME = "benchmark-room"


async def main():
    print(f"Connecting to {LIVEKIT_URL} room '{ROOM_NAME}' as Listener...")

    token = (
        api.AccessToken(API_KEY, API_SECRET)
        .with_identity("listener_bot")
        .with_name("Listener Bot")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=ROOM_NAME,
                can_subscribe=True,
                can_publish=False,
                can_publish_data=True,
            )
        )
    ).to_jwt()

    room = rtc.Room()

    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        print(f"received track: {track.kind} from {participant.identity}")

    await room.connect(LIVEKIT_URL, token)
    print(
        "Listener joined! Keeping connection open for 100 seconds to allow Agent to perform..."
    )

    # Stay connected
    for i in range(100):
        await asyncio.sleep(1)
        if i % 10 == 0:
            print(f"Listening... {i}s")

    await room.disconnect()
    print("Listener disconnected.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Listener stopped.")
