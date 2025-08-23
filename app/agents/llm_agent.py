from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.clients.litellm_client import LiteLLMClient


class LlmAgent(BaseAgent):
    def __init__(self, model: str = "gemini/gemini-pro"):
        self.client = LiteLLMClient()
        self.client.model = model

    async def run(self, prompt: str, context: AgentContext) -> AgentResult:
        # Extract structured bill data from text and return it in metadata
        bill = await self.client.extract_bill_from_text(prompt)
        return AgentResult(
            content="bill_extraction_completed",
            metadata={
                "agent": "llm",
                "session_id": context.session_id,
                "bill_data": bill.dict(),
            },
        )
