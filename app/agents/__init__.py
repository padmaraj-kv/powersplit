"""
Agent abstractions for bill splitting application.

This package provides:
- BaseAgent: minimal interface for running tasks with context
- LlmAgent: adapter over our existing AI stack
- ADK Agent: Google ADK implementation for bill extraction
- Agent registry: simple name → factory mapping
"""

from .base import BaseAgent, AgentContext, AgentResult  # noqa: F401
from .llm_agent import LlmAgent  # noqa: F401
from .registry import agent_registry  # noqa: F401
from .adk_agent import adk_agent  # noqa: F401
