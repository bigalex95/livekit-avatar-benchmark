import os
from pathlib import Path

from benchmark_hooks import attach_benchmark_hooks
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import Agent, AgentServer, AgentSession, room_io
from livekit.plugins import google, liveavatar, noise_cancellation

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
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            voice="Puck",
            temperature=0.8,
        ),
    )

    liveavatar_avatar_id = os.getenv("LIVEAVATAR_AVATAR_ID")
    avatar = liveavatar.AvatarSession(avatar_id=liveavatar_avatar_id)
    await avatar.start(session, room=ctx.room)

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

    attach_benchmark_hooks(ctx.room, session)

    await session.generate_reply(instructions="Greet the user and offer your assistance.")


if __name__ == "__main__":
    agents.cli.run_app(server)
