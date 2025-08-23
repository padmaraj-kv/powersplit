from typing import List
from app.agents.base import BaseAgent, AgentContext, AgentResult


class SequentialAgent(BaseAgent):
    def __init__(self, steps: List[BaseAgent]):
        self.steps = steps

    async def run(self, prompt: str, context: AgentContext) -> AgentResult:
        current_prompt = prompt
        last = None
        for agent in self.steps:
            last = await agent.run(current_prompt, context)
            current_prompt = last.content
        return last or AgentResult(content="")
