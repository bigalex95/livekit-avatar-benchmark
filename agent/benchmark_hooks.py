import asyncio
import json
import time

from livekit import rtc
from livekit.agents import AgentSession


def attach_benchmark_hooks(room: rtc.Room, session: AgentSession):
    """
    Attaches benchmark event listeners to the Room and AgentSession.

    1. Listens for 'lk-chat-topic' data packets to trigger Agent replies.
    2. Logs '[METRIC]' events for latency measurement.
    3. Monitors Agent State changes (Thinking/Speaking).
    """

    # --- 1. Chat Listener ---
    @room.on("data_received")
    def on_data_received(dp: rtc.DataPacket):
        if dp.topic == "lk-chat-topic":
            try:
                payload = json.loads(dp.data.decode("utf-8"))
                text = payload.get("message", "")
                timestamp = payload.get("timestamp", 0)

                # Log reception
                print(f"[METRIC] AGENT_RECEIVED {timestamp} {time.time()} {text}", flush=True)

                # Trigger Agent Reply
                async def reply_wrapper():
                    # We send instructions to the agent to reply to this specific text
                    await session.generate_reply(instructions=f"Reply to user: {text}")

                # Schedule on the existing event loop
                asyncio.create_task(reply_wrapper())

            except Exception as e:
                print(f"Error handling benchmark chat: {e}", flush=True)

    # --- 2. State Monitor ---
    # We poll state changes to log when the agent starts speaking (Thinking -> Speaking)
    async def monitor_state():
        last_state = session.agent_state
        while True:
            current = session.agent_state
            if current != last_state:
                print(f"[METRIC] AGENT_STATE {time.time()} {current}", flush=True)
                last_state = current
            await asyncio.sleep(0.01)

    asyncio.create_task(monitor_state())

    print("✅ Benchmark Hooks Attached")
