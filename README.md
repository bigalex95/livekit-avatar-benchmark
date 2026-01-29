# LiveKit Avatar Benchmark

This project is designed to benchmark and test LiveKit-based AI agents. It provides a framework for running, testing, and evaluating the performance of conversational agents in a real-time environment.

## 🚀 Overview

The goal of this project is to create a reliable and reproducible environment for benchmarking LiveKit agents. It includes:
- **Agent Implementation**: A reference agent using the LiveKit Python SDK.
- **Benchmarking Tools**: Scripts to simulate users and measure performance.
- **Automated Testing**: Integration tests to ensure agent connectivity and responsiveness.
- **Dockerized Environment**: Full local setup using Docker Compose.

## 📂 Project Structure

- **`agent/`**: Contains the implemented LiveKit agent code.
- **`benchmark/`**: Tools for running performance benchmarks.
- **`scripts/`**: Utility scripts for operations, testing, and maintenance.
  - `start.sh`: Starts the environment (Docker + Agent).
  - `check_and_test.sh`: Runs linting, formatting, and tests.
  - `generate_token.py`: Helper to generate LiveKit tokens.
- **`tests/`**: Pytest-based integration tests.
- **`docs/`**: Documentation files.

## 🛠️ Setup & Installation

### Prerequisites

- Linux or macOS
- [Docker](https://www.docker.com/) & Docker Compose
- [uv](https://github.com/astral-sh/uv) (Recommended Python manager) or Python 3.11+

### Quick Start

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd livekit-avatar-benchmark
    ```

2.  **Environment Setup**:
    Create a `.env` file from the example:
    ```bash
    cp .env.example .env
    ```
    *Note: The default `.env.example` is configured for local development usage.*

3.  **Install Dependencies**:
    If using `uv`:
    ```bash
    uv sync
    ```
    Or with pip:
    ```bash
    pip install -r requirements.txt  # If requirements.txt exists
    ```

## 🏃 Usage

### standard

**Start the Environment:**
Use the provided script to build and start the LiveKit server and agent services. This will also generate a token for you to test manually.

```bash
./scripts/start.sh
```

**Run Tests:**
To ensure code quality and functionality, run the check script. This runs `ruff` (formatting/linting) and `pytest`.

```bash
./scripts/check_and_test.sh
```

### Manual Scripts

All scripts are located in the `scripts/` directory. You should run them from the project root.

- **Generate Token**:
  ```bash
  python scripts/generate_token.py
  ```

- **Run Simple Listener**:
  Starts a bot that listens to the room (useful for debugging).
  ```bash
  python scripts/run_simple_listener.py
  ```

## 🧪 Testing

We use `pytest` for testing. The integration tests spin up a real connection to the running LiveKit server and verify that the agent connects and responds.

```bash
pytest tests/
```
