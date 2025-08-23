from typing import Any, Dict
from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.services.litellm_client import LiteLLMClient


class LlmAgent(BaseAgent):
    def __init__(self, model: str = "gemini/gemini-pro"):
        self.client = LiteLLMClient()
        self.client.model = model

    async def run(self, prompt: str, context: AgentContext) -> AgentResult:
        # Minimal wrapper: ask model to respond, attach context keys for trace
        bill = await self.client.extract_bill_from_text(prompt)
        return AgentResult(
            content=f"Parsed bill total: {bill.total_amount} {bill.currency}",
            metadata={"step": "llm_agent", "session_id": context.session_id},
        )
