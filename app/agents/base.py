from typing import Any, Dict, Optional


class AgentContext:
    def __init__(
        self, session_id: str, user_id: str, metadata: Optional[Dict[str, Any]] = None
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.metadata = metadata or {}


class AgentResult:
    def __init__(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        self.content = content
        self.metadata = metadata or {}


class BaseAgent:
    async def run(self, prompt: str, context: AgentContext) -> AgentResult:
        raise NotImplementedError
