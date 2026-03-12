"""MeetingBaas v2 API client for bot lifecycle management."""

import json
import logging
from enum import Enum
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

logger = logging.getLogger("meetingbaas-api")

_BASE_URL = "https://api.meetingbaas.com/v2"


class RecordingMode(str, Enum):
    """Available recording modes for the MeetingBaas API."""

    SPEAKER_VIEW = "speaker_view"
    AUDIO_ONLY = "audio_only"
    GALLERY_VIEW = "gallery_view"


class TimeoutConfig(BaseModel):
    """Timeout settings for automatic meeting exit."""

    waiting_room_timeout: int = 600
    no_one_joined_timeout: int = 600
    silence_timeout: int = 600


_FREQ_MAP: dict[str, int] = {
    "16khz": 16000,
    "24khz": 24000,
    "32khz": 32000,
    "48khz": 48000,
}


class StreamingConfig(BaseModel):
    """WebSocket streaming configuration (v2 field names)."""

    input_url: Optional[str] = None
    output_url: Optional[str] = None
    audio_frequency: int = 16000


class CallbackConfig(BaseModel):
    """Per-bot callback configuration."""

    url: str
    method: str = "POST"
    secret: Optional[str] = None


class MeetingBaasRequest(BaseModel):
    """Model for the MeetingBaas v2 POST /v2/bots request.

    Reference: https://docs.meetingbaas.com/api-v2/reference/bots/create-bot
    """

    bot_name: str
    meeting_url: str

    bot_image: Optional[str] = None
    entry_message: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    recording_mode: RecordingMode = RecordingMode.SPEAKER_VIEW
    allow_multiple_bots: bool = True

    timeout_config: TimeoutConfig = Field(
        default_factory=TimeoutConfig
    )

    streaming_enabled: bool = False
    streaming_config: Optional[StreamingConfig] = None

    callback_enabled: bool = False
    callback_config: Optional[CallbackConfig] = None


def _stringify_values(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable values to strings."""
    if isinstance(obj, dict):
        return {k: _stringify_values(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_stringify_values(item) for item in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)


def create_meeting_bot(
    meeting_url: str,
    websocket_url: str,
    bot_id: str,
    persona_name: str,
    api_key: str,
    bot_image: Optional[str] = None,
    entry_message: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    streaming_audio_frequency: str = "16khz",
    webhook_url: Optional[str] = None,
) -> Optional[str]:
    """Create a bot via the MeetingBaas v2 API.

    Args:
        meeting_url: URL of the meeting to join.
        websocket_url: Base WebSocket URL for audio streaming.
        bot_id: Internal client identifier (used in the WS path).
        persona_name: Display name for the bot in the meeting.
        api_key: MeetingBaas API key.
        bot_image: Optional avatar URL (HTTPS, JPEG/PNG).
        entry_message: Optional chat message on join.
        extra: Optional custom metadata dict.
        streaming_audio_frequency: "16khz" or "24khz".
        webhook_url: Optional per-bot callback URL.

    Returns:
        The MeetingBaas bot_id on success, None on failure.
    """
    if bot_image is not None:
        bot_image = str(bot_image)

    ws_path = f"{websocket_url}/ws/{bot_id}"
    freq_hz = _FREQ_MAP.get(
        streaming_audio_frequency, 16000
    )
    streaming_config = StreamingConfig(
        input_url=ws_path,
        output_url=ws_path,
        audio_frequency=freq_hz,
    )

    callback_config = None
    callback_enabled = False
    if webhook_url:
        callback_config = CallbackConfig(url=webhook_url)
        callback_enabled = True

    request = MeetingBaasRequest(
        meeting_url=meeting_url,
        bot_name=persona_name,
        bot_image=bot_image,
        entry_message=entry_message,
        extra=extra,
        streaming_enabled=True,
        streaming_config=streaming_config,
        callback_enabled=callback_enabled,
        callback_config=callback_config,
    )

    config = _stringify_values(
        request.model_dump(exclude_none=True)
    )

    url = f"{_BASE_URL}/bots"
    headers = {
        "Content-Type": "application/json",
        "x-meeting-baas-api-key": api_key,
    }

    try:
        logger.info(f"Creating MeetingBaas v2 bot for {meeting_url}")
        logger.debug(f"Request payload: {json.dumps(config)}")

        response = requests.post(url, json=config, headers=headers)
        data = response.json()

        if response.status_code == 201 and data.get("success"):
            result_bot_id = data["data"]["bot_id"]
            logger.info(f"Bot created with ID: {result_bot_id}")
            return result_bot_id

        error_code = data.get("code", "unknown")
        error_msg = data.get("message", response.text)
        logger.error(
            f"Failed to create bot: {response.status_code} "
            f"[{error_code}] {error_msg}"
        )
        return None
    except Exception as e:
        logger.error(f"Error creating bot: {e}")
        return None


def leave_meeting_bot(bot_id: str, api_key: str) -> bool:
    """Tell a bot to leave its meeting via the v2 API.

    Args:
        bot_id: The MeetingBaas bot UUID.
        api_key: MeetingBaas API key.

    Returns:
        True on success, False otherwise.
    """
    url = f"{_BASE_URL}/bots/{bot_id}/leave"
    headers = {"x-meeting-baas-api-key": api_key}

    try:
        logger.info(f"Requesting bot {bot_id} to leave meeting")
        response = requests.post(url, headers=headers)
        data = response.json()

        if response.status_code == 200 and data.get("success"):
            logger.info(f"Bot {bot_id} successfully left the meeting")
            return True

        error_code = data.get("code", "unknown")
        error_msg = data.get("message", response.text)
        logger.error(
            f"Failed to remove bot: {response.status_code} "
            f"[{error_code}] {error_msg}"
        )
        return False
    except Exception as e:
        logger.error(f"Error removing bot: {e}")
        return False
