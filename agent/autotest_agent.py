import asyncio
import signal
import statistics
import sys
import time
from pathlib import Path

from benchmark_hooks import attach_benchmark_hooks
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import Agent, AgentServer, AgentSession, room_io
from livekit.plugins import google, noise_cancellation

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


# SCENARIOS: The lines you want the avatar to speak for Lip Sync testing
SCENARIOS = [
    "Hello! Welcome to our restaurant. My name is Alex.",
    "Today's special is a spicy chicken burger with a side of curly fries.",
    "Would you like to see the dessert menu? We have excellent cheesecake.",
    "Thank you very much. Your order will be ready in about 10 minutes.",
    "Can I get you anything else? Maybe some water or a coffee?",
]


class AutoTestAgent(Agent):
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
async def entrypoint(ctx: agents.JobContext):
    # 1. Setup the Google Realtime Session
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            voice="Puck",
            temperature=0.8,
        ),
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

    # 2. Start the Agent
    # 3. Schedule the Performance Loop (since session.start blocks)
    async def run_performance():
        # Wait for a human to actually join (so you don't perform to an empty room)
        print("🎭 Agent ready. Waiting for a spectator to join...")

        # Simple check: wait until there is more than 0 remote participants
        while len(ctx.room.remote_participants) == 0:
            await asyncio.sleep(1)

        print("👀 Spectator joined! Starting the performance in 3 seconds...")

        # Give session a moment to be fully ready if needed
        await asyncio.sleep(3)

        # 4. The Performance Loop
        for i, text in enumerate(SCENARIOS):
            print(f"🎬 Scene {i + 1}/{len(SCENARIOS)}: '{text}'")

            # Force the model to say specifically this text
            # We wrap it in a prompt to ensure it repeats it exactly
            prompt = f"Please say exactly this sentence: '{text}'"

            await session.generate_reply(instructions=prompt)

            # 5. Wait for the avatar to finish speaking + extra pause
            # (Adjust sleep time based on sentence length)
            await asyncio.sleep(10)

        print("✅ Performance complete.")

    asyncio.create_task(run_performance())

    # 4. Start the Agent (This blocks)
    await session.start(
        room=ctx.room,
        agent=AutoTestAgent(),
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

    # Note: run_performance generates replies, so we might not need an initial greeting here if the performance script controls flow.
    # However, to be consistent with other agents, we can leave it out or handle it.
    # The original autotest_agent didn't have a final explicit generate_reply after start, it relied on run_performance.


if __name__ == "__main__":
    # Ensure signal is registered in main thread
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)
    agents.cli.run_app(server)
