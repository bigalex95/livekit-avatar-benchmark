import os
import asyncio
from dotenv import load_dotenv
from livekit import api

# 1. Load environment variables
load_dotenv()

API_KEY = os.getenv("LIVEKIT_API_KEY")
API_SECRET = os.getenv("LIVEKIT_API_SECRET")

if not API_KEY or not API_SECRET:
    print("Error: LIVEKIT_API_KEY or LIVEKIT_API_SECRET not found in .env")
    exit(1)


def create_token(room_name="benchmark-room", participant_identity="manual_tester"):
    print(
        f"Generating token for Room: '{room_name}' | Identity: '{participant_identity}'"
    )

    # 2. Create Access Token
    token = (
        api.AccessToken(API_KEY, API_SECRET)
        .with_identity(participant_identity)
        .with_name("Manual Tester")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
            )
        )
    )

    # 3. Generate JWT
    jwt_token = token.to_jwt()

    print("\n--- TOKEN ---")
    print(jwt_token)
    print("-------------\n")
    return jwt_token


if __name__ == "__main__":
    create_token()
