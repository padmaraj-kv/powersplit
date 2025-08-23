"""
Sarvam AI client for speech-to-text and other AI services
"""

import asyncio
import json
from typing import Dict, Any, Optional, List
import httpx

from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SarvamError(Exception):
    """Base exception for Sarvam AI API errors"""

    pass


class SarvamClient:
    """
    Client for Sarvam AI services including speech-to-text

    Implements Saarika (speech recognition) and Saaras (translation) models
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.sarvam_api_key
        self.base_url = "https://api.sarvam.ai/v1"
        self.timeout = 60.0  # seconds

    async def transcribe_audio(self, audio_data: bytes) -> str:
        """
        Transcribe audio data to text using Sarvam AI's Speech-to-Text API

        Args:
            audio_data: Raw audio file bytes

        Returns:
            Transcribed text

        Raises:
            SarvamError: If transcription fails
        """
        try:
            logger.info("Sending audio to Sarvam AI for transcription")

            # Prepare the API request
            url = f"{self.base_url}/speech/recognition"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/octet-stream",
            }

            # Send the request
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    content=audio_data,
                    params={
                        "model": "saarika"
                    },  # Using Saarika model for Indian languages
                )

                # Check for errors
                if response.status_code != 200:
                    logger.error(
                        f"Sarvam API error: {response.status_code} - {response.text}"
                    )
                    raise SarvamError(f"Transcription failed: {response.text}")

                # Parse the response
                result = response.json()
                transcript = result.get("text", "")

                if not transcript:
                    raise SarvamError("Empty transcript returned")

                logger.info(f"Successfully transcribed audio: {transcript[:50]}...")
                return transcript

        except httpx.RequestError as e:
            logger.error(f"Network error during Sarvam API call: {e}")
            raise SarvamError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during transcription: {e}")
            raise SarvamError(f"Transcription failed: {str(e)}")

    async def health_check(self) -> bool:
        """
        Check if the Sarvam AI API is available

        Returns:
            True if API is available, False otherwise
        """
        try:
            # Simple ping to check API availability
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Sarvam API health check failed: {e}")
            return False
