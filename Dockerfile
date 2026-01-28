FROM python:3.11-slim-bookworm

# 1. Install system dependencies for audio plugins (Opus) and OpenCV
RUN apt-get update && apt-get install -y \
    libopus0 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxcb1 \
    libatomic1 \
    libcurl4 \
    libsm6 \
    libxext6 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 3. Copy dependency definitions
COPY pyproject.toml uv.lock ./

# 4. Install dependencies into the SYSTEM python
# --system: installs into /usr/local/lib/python3.11/site-packages
# --deploy: ensures uv.lock is respected strictly
RUN uv pip install --system .

# 5. Copy the rest of the project
COPY . .

# 6. Download models during build
# RUN python agent/agent.py download-files

# 7. Run the agent
# Note the path: agent/agent.py
CMD ["python", "agent/agent.py", "dev"]