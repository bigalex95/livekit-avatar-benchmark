import asyncio
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import psutil
from dotenv import load_dotenv
from livekit import api, rtc

# Load env variables
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")


@dataclass
class SystemMetrics:
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    gpu_util: float | None = None
    gpu_mem_mb: float | None = None


@dataclass
class AgentMetric:
    timestamp: float
    type: str
    data: list


class AgentRunner:
    def __init__(self, script_path: str):
        self.script_path = script_path
        self.process = None
        self.metrics: list[AgentMetric] = []
        self._log_thread = None

    def _read_logs(self):
        while True:
            if self.process and self.process.stdout:
                line = self.process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    print(f"[AGENT] {line}")  # Debug
                    if line.startswith("[METRIC]"):
                        parts = line.split(" ")
                        # [METRIC] TYPE TIMESTAMP ...
                        if len(parts) >= 3:
                            m_type = parts[1]
                            m_ts = float(parts[2])
                            m_data = parts[3:]
                            self.metrics.append(AgentMetric(m_ts, m_type, m_data))
            else:
                break

    def start(self):
        print(f"🚀 Starting Agent: {self.script_path}")
        # Assuming run with `python <script>`
        import sys

        cmd = [sys.executable, "-u", self.script_path, "dev"]  # -u for unbuffered
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self._log_thread = threading.Thread(target=self._read_logs, daemon=True)
        self._log_thread.start()

        return self.process.pid

    def stop(self):
        if self.process:
            print(f"🛑 Stopping Agent (PID: {self.process.pid})...")
            # Check if process is still running
            if self.process.poll() is None:
                try:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print("   -> Agent did not stop politely, killing...")
                        self.process.kill()
                        self.process.wait(timeout=1)
                except Exception as e:
                    print(f"   -> Error stopping agent: {e}")

            self.process = None


class SystemMonitor:
    def __init__(self, pid: int, interval: float = 0.5):
        self.pid = pid
        self.interval = interval
        self.stop_event = threading.Event()
        self.metrics: list[SystemMetrics] = []
        self._thread = threading.Thread(target=self._monitor_loop)
        try:
            self.process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            self.process = None

    def start(self):
        if self.process:
            self._thread.start()

    def stop(self):
        self.stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _get_gpu_metrics(self):
        # basic nvidia-smi parsing
        try:
            # Let's try querying for our specific PID using nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = line.split(",")
                    if len(parts) >= 2:
                        try:
                            p = int(parts[0].strip())
                            if p == self.pid:
                                return float(parts[1].strip())  # MB
                        except ValueError:
                            pass
            return 0.0
        except Exception:
            return None

    def _monitor_loop(self):
        while not self.stop_event.is_set():
            try:
                # CPU/Mem
                with self.process.oneshot():
                    cpu = self.process.cpu_percent()
                    mem_info = self.process.memory_info()
                    mem_percent = self.process.memory_percent()

                # GPU
                gpu_mem = self._get_gpu_metrics()

                self.metrics.append(
                    SystemMetrics(
                        timestamp=time.time(),
                        cpu_percent=cpu,
                        memory_percent=mem_percent,
                        memory_mb=mem_info.rss / 1024 / 1024,
                        gpu_mem_mb=gpu_mem,
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except Exception:
                # print(f"Monitor error: {e}")
                pass

            time.sleep(self.interval)


async def run_latency_test(room_name: str, text_prompts: list[str]):
    # Connect as a driver
    token = (
        api.AccessToken(API_KEY, API_SECRET)
        .with_identity("bench_driver")
        .with_name("Benchmark Driver")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )

    room = rtc.Room()

    current_active_speakers = []

    @room.on("active_speakers_changed")
    def on_active_speakers_changed(speakers: list[rtc.Participant]):
        nonlocal current_active_speakers
        current_active_speakers = speakers

    try:
        await room.connect(LIVEKIT_URL, token)
        print("   -> Connected to Room")

        # Wait for agent
        print("   -> Waiting for agent to join...")
        start_wait = time.time()
        while len(room.remote_participants) == 0:
            if time.time() - start_wait > 30:
                print("   -> ⚠️  Timeout waiting for agent to join room")
                return [], []
            await asyncio.sleep(0.5)
        print("   -> Agent found!")

        # Collect detailed latencies
        test_results = []  # List of dicts

        # Give a moment
        await asyncio.sleep(2)

        for text in text_prompts:
            print(f"\n   -> 📨 Sending: '{text}'")
            t_sent = time.time()

            # Send chat message via Data Packet (standard LiveKit chat protocol)
            import json

            chat_data = json.dumps({"message": text, "timestamp": int(t_sent * 1000)}).encode("utf-8")

            await room.local_participant.publish_data(payload=chat_data, topic="lk-chat-topic", reliable=True)

            # For now, let's poll for active speakers becoming the agent
            responded = False
            t_response_detected = 0
            timeout = 15
            poll_start = time.time()

            while time.time() - poll_start < timeout:
                # Check active speakers
                # print(f"Active speakers: {[s.identity for s in current_active_speakers]}")
                is_agent_speaking = any(
                    ("agent" in s.identity or "tavus" in s.identity or "avatar" in s.identity)
                    for s in current_active_speakers
                )

                if is_agent_speaking:
                    t_response_detected = time.time()
                    print(f"   -> ⚡ Response detected in {(t_response_detected - t_sent):.3f}s")
                    responded = True
                    break

                await asyncio.sleep(0.05)

            test_results.append(
                {
                    "prompt": text,
                    "sent_ts": t_sent,
                    "response_ts": t_response_detected if responded else None,
                    "total_latency": (t_response_detected - t_sent) if responded else None,
                }
            )

            if not responded:
                print("   -> ❌ Timeout waiting for response")

            # Wait before next prompt
            await asyncio.sleep(5)

    finally:
        try:
            await room.disconnect()
        except Exception:
            pass

    return [], test_results  # Latencies not used directly, using test_results


def main():
    import argparse
    import atexit
    import signal
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True, help="Path to agent script")
    parser.add_argument("--text", action="append", help="Text prompt(s) to send")
    args = parser.parse_args()

    prompts = args.text or ["Hello, are you there?", "What is the capital of France?"]

    runner = AgentRunner(args.agent)
    monitor = None

    cleanup_done = False

    def cleanup(signu=None, frame=None):
        nonlocal cleanup_done, monitor, runner
        if cleanup_done:
            return
        cleanup_done = True
        print("\n🧹 Cleaning up process...")

        if monitor:
            monitor.stop()
        if runner:
            runner.stop()

        if signu is not None:
            sys.exit(0)

    # Register Signal Handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    # Register atexit
    atexit.register(cleanup)

    # 1. Start Agent
    pid = runner.start()

    # 2. Start Monitor
    monitor = SystemMonitor(pid)
    monitor.start()

    # 3. Run Test
    try:
        # Give agent time to warmup
        print("Waiting 10s for agent warmup...")
        time.sleep(10)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            _, results = loop.run_until_complete(run_latency_test("benchmark-room", prompts))
        finally:
            loop.close()

        # 4. Report
        print("\n" + "=" * 60)
        print("BENCHMARK RESULTS - LATENCY BREAKDOWN")
        print("=" * 60)
        print(f"{'Metric':<30} | {'Avg':<8} | {'Min':<8} | {'Max':<8}")
        print("-" * 60)

        # Calculate Logic
        livekit_delays = []
        process_delays = []
        total_delays = []

        agent_metrics = runner.metrics

        for res in results:
            if not res["response_ts"]:
                continue

            sent_ts_ms = int(res["sent_ts"] * 1000)

            # Find matching RECEIVED
            found_received = None
            for m in agent_metrics:
                if m.type == "AGENT_RECEIVED":
                    # Check if timestamp matches sent (approx)
                    try:
                        m_ts_ms = int(m.timestamp)
                        if abs(m_ts_ms - sent_ts_ms) < 200:
                            found_received = m
                            break
                    except (ValueError, IndexError):
                        pass

            # Find matching SPEAKING
            found_speaking = None
            if found_received:
                for m in agent_metrics:
                    if m.type == "AGENT_STATE" and "speaking" in str(m.data[0]):
                        if m.timestamp > float(found_received.data[0]):
                            found_speaking = m
                            break

            # Calculate Component Latencies
            total = res["total_latency"]
            total_delays.append(total)

            if found_received:
                # LiveKit Latency: Received Time (S) - Sent Time (S)
                recv_ts = float(found_received.data[0])
                lk_lat = recv_ts - res["sent_ts"]
                livekit_delays.append(lk_lat)

                if found_speaking:
                    # Processing Latency: Speaking Time (S) - Received Time (S)
                    proc_lat = found_speaking.timestamp - recv_ts
                    process_delays.append(proc_lat)

        def print_stat(name, data):
            if data:
                print(f"{name:<30} | {sum(data) / len(data):.3f} s  | {min(data):.3f} s  | {max(data):.3f} s")
            else:
                print(f"{name:<30} | N/A      | N/A      | N/A")

        print_stat("LiveKit (Network Uplink)", livekit_delays)
        print_stat("Google API (Thinking)", process_delays)
        print_stat("Total Response Latency", total_delays)

        monitor.stop()

        # System Stats
        if monitor.metrics:
            print("\n" + "=" * 60)
            print("SYSTEM USAGE")
            print("=" * 60)
            avg_cpu = sum(m.cpu_percent for m in monitor.metrics) / len(monitor.metrics)
            max_cpu = max(m.cpu_percent for m in monitor.metrics)
            avg_mem = sum(m.memory_mb for m in monitor.metrics) / len(monitor.metrics)
            max_mem = max(m.memory_mb for m in monitor.metrics)

            print(f"CPU Usage (avg): {avg_cpu:.1f}%")
            print(f"CPU Usage (max): {max_cpu:.1f}%")
            print(f"Memory (avg):    {avg_mem:.1f} MB")
            print(f"Memory (max):    {max_mem:.1f} MB")

            gpu_data = [m.gpu_mem_mb for m in monitor.metrics if m.gpu_mem_mb is not None]
            if gpu_data:
                print(f"GPU Mem (max):   {max(gpu_data):.1f} MB")
            else:
                print("GPU Mem:         N/A (or 0)")

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error running benchmark: {e}")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
