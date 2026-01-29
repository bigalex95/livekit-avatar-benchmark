import os
from pathlib import Path

from bithuman import AsyncBithuman
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import Agent, AgentServer, AgentSession, room_io
from livekit.plugins import bithuman, google, noise_cancellation
from loguru import logger

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env.local")
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are a friendly and professional restaurant waiter serving international tourists. 

Start the conversation in English by greeting the customer and asking how you can help them today. 

Pay close attention to the language the customer uses when they respond. Once you detect their preferred language, immediately switch to speaking in that language for the rest of the conversation. Continue the entire conversation in their language.

Your goal is to:
1. Greet them warmly
2. Detect and switch to their language
3. Help them understand the menu
4. Take their food and drink order
5. Confirm the order back to them
6. Ask if they need anything else

Be patient, helpful, and make them feel welcome. Adapt your responses naturally to whatever language they speak.""",
        )


server = AgentServer()


@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    # Check for required environment variables
    bithuman_model_path = os.getenv("BITHUMAN_MODEL_PATH")
    bithuman_avatar_id = os.getenv("BITHUMAN_AVATAR_ID")
    bithuman_api_secret = os.getenv("BITHUMAN_API_SECRET")
    bithuman_device = os.getenv("BITHUMAN_DEVICE", "cpu")

    # Retrieve prewarmed runtime if available
    runtime = ctx.proc.userdata.get("bithuman_runtime")

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            voice="Puck",
            temperature=0.8,
        ),
    )

    bithuman_avatar = bithuman.AvatarSession(
        # model_path=bithuman_model_path,
        avatar_id=bithuman_avatar_id,
        api_secret=bithuman_api_secret,
        runtime=runtime,
        model="expression" if bithuman_device == "gpu" else "essence",
    )

    logger.info(f"Starting BitHuman avatar with {bithuman_model_path=}, {bithuman_device=}")
    try:
        await bithuman_avatar.start(session, room=ctx.room)
        logger.info("BitHuman avatar started successfully")
    except Exception as e:
        logger.error(f"Failed to start BitHuman avatar: {e}", exc_info=True)
        raise

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    await session.generate_reply(instructions="Greet the user and offer your assistance.")


def prewarm(proc: agents.JobProcess):
    bithuman_model_path = os.getenv("BITHUMAN_MODEL_PATH")
    bithuman_api_secret = os.getenv("BITHUMAN_API_SECRET")
    bithuman_avatar_id = os.getenv("BITHUMAN_AVATAR_ID")

    # Only prewarm if using local model mode (not cloud mode with avatar_id)
    if not bithuman_model_path or bithuman_avatar_id:
        return

    # if we know the model path before job received, prewarm the runtime
    logger.info("loading bithuman runtime")
    try:
        runtime = AsyncBithuman(
            model_path=bithuman_model_path,
            api_secret=bithuman_api_secret,
            load_model=True,
        )
        proc.userdata["bithuman_runtime"] = runtime
        logger.info("bithuman runtime loaded")
    except Exception as e:
        logger.error(f"failed to prewarm bithuman runtime: {e}")


server.setup_fnc = prewarm

if __name__ == "__main__":
    agents.cli.run_app(server)
