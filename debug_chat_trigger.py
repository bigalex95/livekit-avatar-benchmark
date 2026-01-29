import asyncio
import json
import os

from dotenv import load_dotenv
from livekit import api, rtc

load_dotenv()

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")


async def main():
    token = (
        api.AccessToken(API_KEY, API_SECRET)
        .with_identity("debug_trigger")
        .with_grants(api.VideoGrants(room_join=True, room="benchmark-room"))
        .to_jwt()
    )
    room = rtc.Room()
    await room.connect(LIVEKIT_URL, token)
    print("Connected. Sending Hello...")

    chat_data = json.dumps({"message": "Hello", "timestamp": 123456}).encode("utf-8")

    await room.local_participant.publish_data(payload=chat_data, topic="lk-chat-topic", reliable=True)
    print("Sent. Waiting 60s for agent to join/reply...")
    for i in range(60):
        print(f"Wait {i}...", end="\r")
        await asyncio.sleep(1)
    await room.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
