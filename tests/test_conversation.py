import sys
import os
import pytest
from unittest.mock import MagicMock

# Add the project root to the python path so imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.autotest_agent import AutoTestAgent, SCENARIOS


def test_scenarios_exist():
    assert len(SCENARIOS) > 0
    assert "Hello! Welcome to our restaurant." in SCENARIOS[0]


def test_agent_initialization():
    # We might need to mock if Agent does network stuff on init, but usually it doesn't
    agent = AutoTestAgent()
    assert agent is not None
    # Check if instructions are set
    assert "restaurant waiter" in agent.instructions
