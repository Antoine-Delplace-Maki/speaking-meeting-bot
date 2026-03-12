import os
from typing import Any, Dict, List, Optional

import aiohttp
from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

from config.persona_utils import PersonaManager

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class CartesiaVoiceManager:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CARTESIA_API_KEY")
        if not self.api_key:
            logger.warning("Cartesia API key not found in environment variables")

    async def list_voices(self) -> List[Dict]:
        """List all available Cartesia voices"""
        if not self.api_key:
            logger.warning("Cannot list voices: No API key provided")
            return []

        url = "https://api.cartesia.ai/voices/"
        headers = {"X-API-Key": self.api_key, "Cartesia-Version": "2024-06-10"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        voices = await response.json()
                        return voices
                    else:
                        error_msg = await response.text()
                        logger.error(f"Failed to fetch voices: {error_msg}")
                        return []
        except Exception as e:
            logger.error(f"Error connecting to Cartesia API: {e}")
            return []


cartesia_voice_manager = CartesiaVoiceManager()


class VoiceUtils:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.persona_manager = PersonaManager()

    async def match_voice_to_persona(
        self,
        persona_key: Optional[str] = None,
        language_code: str = "en",
        persona_details: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Use GPT to match a persona with an appropriate Cartesia voice."""
        try:
            persona = None
            if persona_details:
                persona = persona_details
                logger.info("Using provided persona details for voice matching.")
            elif persona_key:
                persona = self.persona_manager.personas.get(persona_key)
                logger.info(f"Attempting to match voice for predefined persona: {persona_key}")

            if not persona:
                logger.error(f"Persona not found, neither by key '{persona_key}' nor provided details.")
                return None

            voices = await cartesia_voice_manager.list_voices()
            voices = [v for v in voices if v.get("language") == language_code]

            if not voices:
                logger.error(f"No voices available for language {language_code}")
                return None

            voices_text = "\n".join(
                f"Voice {i+1}: {v['name']} - {v.get('description', 'No description')}"
                for i, v in enumerate(voices)
            )

            persona_prompt = persona.get("prompt", "")
            max_prompt_chars = 1500
            if len(persona_prompt) > max_prompt_chars:
                persona_prompt = persona_prompt[:max_prompt_chars] + "..."
                logger.info(f"Truncated persona prompt for voice matching (was {len(persona['prompt'])} chars)")

            prompt = f"""Given this persona:
Name: {persona['name']}
Description: {persona_prompt}
Gender: {persona.get('gender', 'Unknown')}

And these available voices:
{voices_text}

Which voice number (1-{len(voices)}) would be the most appropriate match? 
Respond with ONLY the number."""

            logger.info(f"Voice matching prompt for '{persona['name']}': {prompt}")

            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
            )

            try:
                voice_index = int(response.choices[0].message.content.strip()) - 1
                selected_voice = voices[voice_index]
                logger.info(
                    f"Matched {persona['name']} with voice: {selected_voice['name']}"
                )
                return selected_voice["id"]
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing GPT response: {e}")
                return None

        except Exception as e:
            logger.error(f"Error matching voice to persona: {e}")
            return None
