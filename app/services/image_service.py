"""Service for generating persona images using the OpenAI GPT Image API."""

import asyncio
import base64
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

load_dotenv()

_MAX_PROMPT_LENGTH = 4000


class ImageService:
    """Generates persona images via OpenAI gpt-image-1."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self._enabled = bool(api_key)

        if self._enabled:
            self._client = OpenAI(api_key=api_key)
            logger.info("ImageService ready (OpenAI gpt-image-1)")
        else:
            self._client = None
            logger.warning(
                "Image generation disabled — OPENAI_API_KEY not configured"
            )

    async def generate_persona_image(
        self,
        name: str,
        prompt: str,
        style: str = "realistic",
        size: tuple[int, int] = (1024, 1024),
        raw_prompt: bool = False,
    ) -> str:
        """Generate a persona image and return its URL.

        Uses gpt-image-1 for photorealistic output. Falls back to
        dall-e-3 if gpt-image-1 is unavailable.

        Args:
            name: Persona display name.
            prompt: Description of the desired image.
            style: Artistic style hint (ignored when raw_prompt=True).
            size: Desired dimensions.
            raw_prompt: If True, use prompt as-is without wrapping.

        Returns:
            A URL pointing to the generated image, or empty string on failure.
        """
        if not self._enabled:
            logger.debug("Skipping image generation (not configured)")
            return ""

        dall_e_size = _pick_size(size)

        if raw_prompt:
            full_prompt = prompt
        else:
            full_prompt = (
                f"Professional headshot portrait of a person named {name}. "
                f"Style: {style}. {prompt}. "
                "Single person, face and shoulders, centered, "
                "neutral background, no text or watermarks."
            )

        if len(full_prompt) > _MAX_PROMPT_LENGTH:
            full_prompt = full_prompt[:_MAX_PROMPT_LENGTH]

        logger.info(
            f"Generating image via gpt-image-1 "
            f"(size={dall_e_size}, prompt={len(full_prompt)} chars)"
        )

        try:
            response = await asyncio.to_thread(
                self._client.images.generate,
                model="gpt-image-1",
                prompt=full_prompt,
                size=dall_e_size,
                quality="medium",
                output_format="png",
            )

            image_b64 = getattr(response.data[0], "b64_json", None)
            image_url = getattr(response.data[0], "url", None)

            if image_url:
                logger.info(f"Image generated for '{name}': {image_url[:80]}...")
                return image_url

            if image_b64:
                data_uri = f"data:image/png;base64,{image_b64}"
                logger.info(f"Image generated for '{name}' (base64, {len(image_b64)} chars)")
                return data_uri

            logger.warning("gpt-image-1 returned no image data")
            return ""

        except Exception as e:
            logger.error(f"gpt-image-1 failed: {e}, falling back to dall-e-3")
            return await self._fallback_dalle3(name, full_prompt, dall_e_size)

    async def _fallback_dalle3(
        self, name: str, prompt: str, size: str
    ) -> str:
        """Fallback to DALL-E 3 if gpt-image-1 is unavailable."""
        try:
            response = await asyncio.to_thread(
                self._client.images.generate,
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            logger.info(f"Fallback image generated for '{name}': {image_url[:80]}...")
            return image_url
        except Exception as e:
            logger.error(f"dall-e-3 fallback also failed: {e}")
            return ""


def _pick_size(size: tuple[int, int]) -> str:
    """Map an arbitrary (w, h) to the closest supported size string."""
    w, h = size
    ratio = w / h if h else 1.0
    if ratio > 1.3:
        return "1536x1024"
    if ratio < 0.77:
        return "1024x1536"
    return "1024x1024"


image_service = ImageService()
