from typing import Callable, Dict
from app.agents.base import BaseAgent
from app.agents.llm_agent import LlmAgent


class AgentRegistry:
    def __init__(self):
        self._factories: Dict[str, Callable[[], BaseAgent]] = {}
        self.register("llm", lambda: LlmAgent())

    def register(self, name: str, factory: Callable[[], BaseAgent]) -> None:
        self._factories[name] = factory

    def create(self, name: str) -> BaseAgent:
        if name not in self._factories:
            raise KeyError(f"Unknown agent: {name}")
        return self._factories[name]()


agent_registry = AgentRegistry()
