import asyncio
import os
import signal
import statistics
import sys
import time
from pathlib import Path

from benchmark_hooks import attach_benchmark_hooks
from bithuman import AsyncBithuman
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import Agent, AgentServer, AgentSession, room_io
from livekit.plugins import bithuman, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from loguru import logger

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env.local")
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# Global list to store latencies
LATENCIES = []


def handle_sigint(signum, frame):
    """Handle Ctrl+C to print statistics before exiting."""
    print("\n\n" + "=" * 30)
    print("       LATENCY STATISTICS       ")
    print("=" * 30)

    if LATENCIES:
        min_lat = min(LATENCIES)
        max_lat = max(LATENCIES)
        avg_lat = statistics.mean(LATENCIES)
        count = len(LATENCIES)

        print(f"Total Responses: {count}")
        print(f"Min Latency:     {min_lat:.4f}s")
        print(f"Max Latency:     {max_lat:.4f}s")
        print(f"Avg Latency:     {avg_lat:.4f}s")
    else:
        print("No latencies recorded.")

    print("=" * 30 + "\n")
    sys.exit(0)


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

    # session = AgentSession(
    #     llm=google.realtime.RealtimeModel(
    #         voice="Puck",
    #         temperature=0.8,
    #     ),
    # )

    session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    # Attach the stats handler for local run
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    # Monitor latency
    # We use a mutable container to share state between the event handler and the loop
    latency_state = {"request_start_time": None}

    @ctx.room.on("data_received")
    def on_data_received(dp: rtc.DataPacket):
        if dp.topic == "lk-chat-topic":
            latency_state["request_start_time"] = time.time()
            # print(f"[DEBUG] Request received at {latency_state['request_start_time']}", flush=True)

    async def monitor_latency(sess: AgentSession):
        print("Starting Latency Monitor...", flush=True)
        last_state = sess.agent_state

        while True:
            current_state = sess.agent_state

            if current_state != last_state:
                now = time.time()

                if current_state == "speaking":
                    if latency_state["request_start_time"]:
                        latency = now - latency_state["request_start_time"]
                        LATENCIES.append(latency)
                        print(f"[LATENCY] Response Time: {latency:.4f}s", flush=True)
                        latency_state["request_start_time"] = None
                    else:
                        # Fallback: maybe we missed the packet or it was voice input?
                        # For now, we only track text-chat triggered latency as per request context
                        pass

                last_state = current_state

            await asyncio.sleep(0.01)

    # Create monitoring task
    asyncio.create_task(monitor_latency(session))

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

    attach_benchmark_hooks(ctx.room, session)

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
    # Ensure signal is registered in main thread
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)
    agents.cli.run_app(server)
