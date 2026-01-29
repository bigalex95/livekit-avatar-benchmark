import asyncio

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession
from livekit.plugins import google

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

    # 2. Start the Agent
    await session.start(room=ctx.room, agent=AutoTestAgent())

    # 3. Wait for a human to actually join (so you don't perform to an empty room)
    print("🎭 Agent ready. Waiting for a spectator to join...")

    # Simple check: wait until there is more than 0 remote participants
    while len(ctx.room.remote_participants) == 0:
        await asyncio.sleep(1)

    print("👀 Spectator joined! Starting the performance in 3 seconds...")
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


if __name__ == "__main__":
    agents.cli.run_app(server)
