import logging
import os

from livekit.agents import cli

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main-entrypoint")

if __name__ == "__main__":
    # Read the flag (default to 'interactive' if missing)
    mode = os.getenv("RUN_MODE", "interactive").lower()

    logger.info(f"🚀 STARTING AGENT IN MODE: === {mode.upper()} ===")

    if mode == "benchmark":
        try:
            from autotest_agent import server

            cli.run_app(server)
        except ImportError as e:
            logger.error(f"Failed to import benchmark agent: {e}")
            raise

    elif mode == "bithuman":
        try:
            from bithuman_agent import server

            cli.run_app(server)
        except ImportError as e:
            logger.error(f"Failed to import bithuman agent: {e}")
            raise

    elif mode == "tavus":
        try:
            from tavus_agent import server

            cli.run_app(server)
        except ImportError as e:
            logger.error(f"Failed to import tavus agent: {e}")
            raise

    elif mode == "simli":
        try:
            from simli_agent import server

            cli.run_app(server)
        except ImportError as e:
            logger.error(f"Failed to import tavus agent: {e}")
            raise

    elif mode == "anam":
        try:
            from anam_agent import server

            cli.run_app(server)
        except ImportError as e:
            logger.error(f"Failed to import tavus agent: {e}")
            raise

    else:
        # Default to interactive
        try:
            from agent import server

            cli.run_app(server)
        except ImportError as e:
            logger.error(f"Failed to import interactive agent: {e}")
            raise
