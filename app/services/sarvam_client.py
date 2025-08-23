"""
Sarvam AI client for speech-to-text conversion
"""
import httpx
import asyncio
from typing import Optional, Dict, Any
from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SarvamError(Exception):
    """Base exception for Sarvam API errors"""
    pass


class SarvamClient:
    """Client for Sarvam AI speech-to-text API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.sarvam_api_key
        self.base_url = "https://api.sarvam.ai/speech-to-text"
        self.timeout = 30.0
        
    async def transcribe_audio(self, audio_data: bytes, language: str = "hi-IN") -> str:
        """
        Transcribe audio data to text using Sarvam AI
        
        Args:
            audio_data: Audio file bytes (supports WAV, MP3, M4A)
            language: Language code (default: hi-IN for Hindi)
            
        Returns:
            Transcribed text
            
        Raises:
            SarvamError: If transcription fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                files = {
                    "file": ("audio.wav", audio_data, "audio/wav")
                }
                
                data = {
                    "language_code": language,
                    "model": "saaras:v1"  # Sarvam's speech model
                }
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                logger.info(f"Sending audio transcription request to Sarvam AI")
                
                response = await client.post(
                    f"{self.base_url}/transcribe",
                    files=files,
                    data=data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    transcript = result.get("transcript", "")
                    
                    logger.info(f"Successfully transcribed audio: {len(transcript)} characters")
                    return transcript
                    
                elif response.status_code == 429:
                    logger.warning("Sarvam API rate limit exceeded")
                    raise SarvamError("Rate limit exceeded. Please try again later.")
                    
                else:
                    error_msg = f"Sarvam API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise SarvamError(error_msg)
                    
        except httpx.TimeoutException:
            logger.error("Sarvam API request timed out")
            raise SarvamError("Speech transcription timed out. Please try again.")
            
        except httpx.RequestError as e:
            logger.error(f"Sarvam API request failed: {e}")
            raise SarvamError(f"Failed to connect to speech service: {e}")
            
        except Exception as e:
            logger.error(f"Unexpected error in Sarvam transcription: {e}")
            raise SarvamError(f"Speech transcription failed: {e}")
    
    async def health_check(self) -> bool:
        """
        Check if Sarvam API is available
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                response = await client.get(
                    f"{self.base_url}/health",
                    headers=headers
                )
                
                return response.status_code == 200
                
        except Exception as e:
            logger.warning(f"Sarvam health check failed: {e}")
            return False
    
    async def get_supported_languages(self) -> Dict[str, str]:
        """
        Get list of supported languages
        
        Returns:
            Dictionary mapping language codes to language names
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                response = await client.get(
                    f"{self.base_url}/languages",
                    headers=headers
                )
                
                if response.status_code == 200:
                    return response.json().get("languages", {})
                else:
                    logger.warning(f"Failed to get supported languages: {response.status_code}")
                    return {"hi-IN": "Hindi", "en-IN": "English"}
                    
        except Exception as e:
            logger.warning(f"Failed to get supported languages: {e}")
            # Return default supported languages
            return {"hi-IN": "Hindi", "en-IN": "English"}