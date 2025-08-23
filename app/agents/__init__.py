"""
Lightweight agent abstractions (ADK-inspired) without external dependency.

This package provides:
- BaseAgent: minimal interface for running tasks with context
- LlmAgent: adapter over our existing AI stack
- Workflow (sequential) agent: composes agents deterministically
- Agent registry: simple name → factory mapping
"""

from .base import BaseAgent, AgentContext, AgentResult  # noqa: F401
from .llm_agent import LlmAgent  # noqa: F401
from .workflow.sequential import SequentialAgent  # noqa: F401
from .registry import agent_registry  # noqa: F401
