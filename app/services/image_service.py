"""Service for generating persona images using the OpenAI DALL-E API."""

import asyncio
import os

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

load_dotenv()

_MAX_PROMPT_LENGTH = 3500


class ImageService:
    """Generates persona headshot images via OpenAI DALL-E 3."""

    def __init__(self):
        """Initialize the image service."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        self._enabled = bool(api_key)

        if self._enabled:
            self._client = OpenAI(api_key=api_key)
            logger.info("ImageService ready (OpenAI DALL-E 3)")
        else:
            self._client = None
            logger.warning(
                "Image generation disabled — OPENAI_API_KEY "
                "not configured"
            )

    async def generate_persona_image(
        self,
        name: str,
        prompt: str,
        style: str = "realistic",
        size: tuple[int, int] = (1024, 1024),
    ) -> str:
        """Generate a persona headshot and return its URL.

        Args:
            name: Persona display name (used in the prompt).
            prompt: Description of the persona's appearance.
            style: Artistic style hint prepended to the prompt.
            size: Desired dimensions (mapped to nearest DALL-E 3
                size: 1024x1024, 1024x1792, or 1792x1024).

        Returns:
            A URL pointing to the generated image, or an empty
            string when generation is disabled or fails.
        """
        if not self._enabled:
            logger.debug("Skipping image generation (not configured)")
            return ""

        dall_e_size = _pick_dalle_size(size)
        full_prompt = (
            f"Professional headshot portrait of a person named {name}. "
            f"Style: {style}. {prompt}. "
            "Single person, face and shoulders, centered, "
            "neutral background, no text or watermarks."
        )
        if len(full_prompt) > _MAX_PROMPT_LENGTH:
            full_prompt = full_prompt[:_MAX_PROMPT_LENGTH]

        logger.info(
            f"Generating image via DALL-E 3 "
            f"(size={dall_e_size}, prompt={len(full_prompt)} chars)"
        )

        try:
            response = await asyncio.to_thread(
                self._client.images.generate,
                model="dall-e-3",
                prompt=full_prompt,
                size=dall_e_size,
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            logger.info(f"Image generated for '{name}': {image_url[:80]}…")
            return image_url

        except Exception as e:
            logger.error(f"Failed to generate image: {e}")
            return ""


def _pick_dalle_size(size: tuple[int, int]) -> str:
    """Map an arbitrary (w, h) to the closest DALL-E 3 size string."""
    w, h = size
    ratio = w / h if h else 1.0
    if ratio > 1.3:
        return "1792x1024"
    if ratio < 0.77:
        return "1024x1792"
    return "1024x1024"


image_service = ImageService()
