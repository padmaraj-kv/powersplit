"""
ADK agent implementation for bill extraction using Google's Agent Development Kit
"""

from typing import Dict, Any

# asyncio is used by the ADK runner
from decimal import Decimal
import json

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.adk.models import LiteLlm

from app.models.schemas import BillData, BillItem
from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Unique identifiers for the agent
APP_NAME = "bill-splitting-agent"
USER_ID = "default-user"
SESSION_ID = "bill-extraction-session"


class BillExtractionADKAgent:
    """
    Google ADK agent for bill extraction
    """

    def __init__(self):
        self.session_service = InMemorySessionService()
        # Use LiteLLM with Gemini model
        self.model = LiteLlm(model="gemini/gemini-pro", api_key=settings.gemini_api_key)
        self.agent = self._create_agent()
        self.runner = Runner(agent=self.agent)

    def _create_agent(self) -> Agent:
        """Create and configure the ADK agent with tools"""
        # Define the extract_bill tool
        extract_bill_tool = FunctionTool(
            func=self._extract_bill_from_text,
            name="extract_bill",
            description="Extract bill information from text",
        )

        # Create the agent with the tool
        agent = Agent(
            name="BillExtractionAgent",
            description="An agent that extracts bill information from text input",
            instructions="""
            You are a bill extraction agent that helps users extract bill information from text.
            When given text about a bill, extract the following information:
            - Total amount
            - Description/purpose of the bill
            - Merchant/restaurant name if available
            - Individual items with name, amount, and quantity if available
            - Currency (default to INR)
            
            Use the extract_bill tool to process the text and return structured bill data.
            """,
            tools=[extract_bill_tool],
            model=self.model,
        )
        return agent

    async def _extract_bill_from_text(self, text: str) -> Dict[str, Any]:
        """
        Tool function to extract bill data from text

        Args:
            text: Text containing bill information

        Returns:
            Dictionary with extracted bill information
        """
        try:
            # Use Gemini to extract bill information
            prompt = f"""
            Extract bill information from this text and return it in JSON format:
            
            Text: "{text}"
            
            Return JSON in this exact format:
            {{
                "total_amount": <total amount as number>,
                "description": "<brief description>",
                "merchant": "<merchant name if mentioned>",
                "items": [
                    {{
                        "name": "<item name>",
                        "amount": <amount as number>,
                        "quantity": <quantity as number>
                    }}
                ],
                "currency": "INR"
            }}
            
            Rules:
            - If total amount is not mentioned, sum up individual items
            - If no items are mentioned, create items based on context
            - Use "INR" as currency for Indian context
            - Set quantity to 1 if not specified
            - If merchant is not mentioned, use null
            - Be conservative with amounts - only extract clear numbers
            """

            response = await self.model.generate_content(prompt)
            response_text = response.text

            # Parse JSON response
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()

            bill_json = json.loads(response_text)

            # Return the extracted data
            return bill_json

        except Exception as e:
            logger.error(f"Error extracting bill data: {e}")
            # Return a minimal structure on error
            return {
                "total_amount": 0,
                "description": "Failed to extract bill information",
                "merchant": None,
                "items": [],
                "currency": "INR",
                "error": str(e),
            }

    async def process_text(self, text: str) -> BillData:
        """
        Process text input and extract bill data using ADK agent

        Args:
            text: Text containing bill information

        Returns:
            BillData object with extracted information
        """
        try:
            # Get or create a session
            session = await self.session_service.get_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
            )

            if not session:
                session = Session(
                    app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID, state={}
                )
                await self.session_service.save_session(session)

            # Run the agent with the text input
            response = await self.runner.run_agent(
                agent=self.agent, user_message=text, session=session
            )

            # Get the extracted bill data from the response
            bill_json = response.get("extract_bill", {})
            if not bill_json:
                # Try to find it in the session state for backward compatibility
                bill_json = session.state.get("bill_data", {})

            # Convert to BillData object
            items = []
            for item_data in bill_json.get("items", []):
                items.append(
                    BillItem(
                        name=item_data.get("name", "Unknown item"),
                        amount=Decimal(str(item_data.get("amount", 0))),
                        quantity=item_data.get("quantity", 1),
                    )
                )

            bill_data = BillData(
                total_amount=Decimal(str(bill_json.get("total_amount", 0))),
                description=bill_json.get("description", "Bill from text"),
                items=items,
                currency=bill_json.get("currency", "INR"),
                merchant=bill_json.get("merchant"),
            )

            logger.info(f"Successfully extracted bill data: ₹{bill_data.total_amount}")
            return bill_data

        except Exception as e:
            logger.error(f"Error processing text with ADK agent: {e}")
            # Return a minimal BillData on error
            return BillData(
                total_amount=Decimal("0"),
                description=f"Error extracting bill: {str(e)}",
                items=[],
                currency="INR",
            )


# Singleton instance for dependency injection
adk_agent = BillExtractionADKAgent()
