# Benchmarking Guide

This project includes a system benchmark tool located at `benchmark/system_benchmark.py`. It is designed to measure the end-to-end latency and system resource usage of your LiveKit agents.

## 🚀 Quick Start

To run the benchmark against an agent:

```bash
uv run python benchmark/system_benchmark.py --agent agent/tavus_agent.py --text "Hello"
```

**What this does:**
1.  Starts the specified agent (`agent/tavus_agent.py`) in a background process.
2.  Connects a "Driver" user to the LiveKit room.
3.  Waits for the Agent to join.
4.  Sends the chat message "Hello".
5.  Measures the time until the Agent replies (audio/text).
6.  Reports detailed latency breakdown and CPU/RAM/GPU usage.

---

## 📊 Metrics Explained

The benchmark reports the following metrics:

| Metric | Description |
| :--- | :--- |
| **LiveKit (Network Uplink)** | Time from *Client Sending Message* -> *Agent Receiving Message*. |
| **Google API (Thinking)** | Time from *Agent Receiving Message* -> *Agent Starting to Speak* (processing time). |
| **Total Response Latency** | Time from *Client Sending Message* -> *Client Hearing Audio*. |
| **Visual Latency** | (If applicable) Time until the avatar's first video frame is received. |
| **System Resources** | CPU, Memory, and GPU usage of the Agent process during the test. |

> **Note:** "N/A" in the breakdown usually means the specific timestamp logs were missed (e.g. if the agent started speaking before the log was captured), but **Total Response Latency** is always measured from the client side and is the most important metric.

---

## 🛠️ Instrumenting Your Agent

To enable the detailed breakdown (Network vs Thinking time), your agent must log specific events. We provide a helper to make this easy.

**File:** `agent/benchmark_hooks.py`

### How to use:
In your agent implementation (e.g., `my_agent.py`), import and attach the hooks:

```python
from benchmark_hooks import attach_benchmark_hooks

@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    session = AgentSession(...)
    
    # 1. Start the session (Crucial!)
    await session.start(room=ctx.room, ...)

    # 2. Attach hooks immediately after start
    attach_benchmark_hooks(ctx.room, session) 
```

**What the hook does:**
- Listens for `lk-chat-topic` data packets (used by the benchmark to send text).
- Triggers `session.generate_reply(...)` when a message is received.
- Logs `[METRIC] AGENT_RECEIVED` and `[METRIC] AGENT_STATE` to stdout, which the benchmark script parses.

---

## ⚠️ Troubleshooting

**1. "Waiting for agent to join..." (Hangs forever)**
- Ensure you have the correct API keys in your `.env` file.
- Check if old "zombie" python processes are running in the background stealing the connection. Run:
  ```bash
  pkill -f agent/
  ```

**2. "RuntimeError: AgentSession isn't running"**
- You likely forgot to call `await session.start(...)` before attaching the hooks.

**3. Latency Breakdown is "N/A"**
- The Total Latency is still valid. "N/A" breakdown just means the internal logs weren't parsed perfectly (often due to race conditions in logging vs stdout buffering). The End-to-End latency is the source of truth.
