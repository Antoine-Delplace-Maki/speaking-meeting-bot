"""Meeting activity monitor with auto-leave logic.

Runs as an asyncio background task that periodically checks two conditions:
- **Idle timeout** – no speech detected for a configurable number of seconds.
- **Alone timeout** – no human participants remaining for a configurable duration.

When either condition fires, the monitor calls the MeetingBaas leave API so the
bot exits the meeting automatically.
"""

import asyncio
import math
import struct
import time
from typing import Optional

from meetingbaas_pipecat.utils.logger import logger

SPEECH_RMS_THRESHOLD = 500


def audio_rms(pcm_bytes: bytes) -> float:
    """Compute RMS amplitude of 16-bit little-endian PCM audio."""
    n_samples = len(pcm_bytes) // 2
    if n_samples == 0:
        return 0.0
    samples = struct.unpack(f"<{n_samples}h", pcm_bytes[: n_samples * 2])
    return math.sqrt(sum(s * s for s in samples) / n_samples)


class MeetingMonitor:
    """Monitors meeting activity and triggers auto-leave when conditions are met."""

    def __init__(
        self,
        client_id: str,
        meetingbaas_bot_id: str,
        api_key: str,
        idle_timeout: int = 300,
        alone_timeout: int = 120,
    ):
        self.client_id = client_id
        self.meetingbaas_bot_id = meetingbaas_bot_id
        self.api_key = api_key
        self.idle_timeout = idle_timeout
        self.alone_timeout = alone_timeout

        self._last_speech_time: float = time.monotonic()
        self._participant_count: int = 1  # assume ≥1 human when bot joins
        self._alone_since: Optional[float] = None
        self._task: Optional[asyncio.Task] = None
        self._stopped = False
        self._started = False

    # ------------------------------------------------------------------
    # Public helpers (called from WebSocket / webhook handlers)
    # ------------------------------------------------------------------

    def record_audio_activity(self, pcm_bytes: bytes) -> None:
        """Update last-speech timestamp when speech is detected."""
        if audio_rms(pcm_bytes) > SPEECH_RMS_THRESHOLD:
            self._last_speech_time = time.monotonic()

    def update_participant_count(self, count: int) -> None:
        """Set the number of human participants (excluding the bot)."""
        self._participant_count = max(count, 0)
        if self._participant_count <= 0:
            if self._alone_since is None:
                self._alone_since = time.monotonic()
                logger.info(
                    f"[monitor] Bot is alone in meeting "
                    f"(client {self.client_id[:8]}…)"
                )
        else:
            if self._alone_since is not None:
                logger.info(
                    f"[monitor] Participants present again "
                    f"(client {self.client_id[:8]}…)"
                )
            self._alone_since = None

    def participant_left(self) -> None:
        self.update_participant_count(self._participant_count - 1)

    def participant_joined(self) -> None:
        self.update_participant_count(self._participant_count + 1)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._last_speech_time = time.monotonic()
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"[monitor] Started for client {self.client_id[:8]}… "
            f"(idle={self.idle_timeout}s, alone={self.alone_timeout}s)"
        )

    def stop(self) -> None:
        self._stopped = True
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info(f"[monitor] Stopped for client {self.client_id[:8]}…")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        try:
            while not self._stopped:
                await asyncio.sleep(10)
                now = time.monotonic()

                if self.idle_timeout > 0:
                    idle_secs = now - self._last_speech_time
                    if idle_secs >= self.idle_timeout:
                        await self._auto_leave(
                            f"no speech for {int(idle_secs)}s "
                            f"(idle timeout {self.idle_timeout}s)"
                        )
                        return

                if self.alone_timeout > 0 and self._alone_since is not None:
                    alone_secs = now - self._alone_since
                    if alone_secs >= self.alone_timeout:
                        await self._auto_leave(
                            f"alone for {int(alone_secs)}s "
                            f"(alone timeout {self.alone_timeout}s)"
                        )
                        return
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[monitor] Error in monitor loop: {e}")

    async def _auto_leave(self, reason: str) -> None:
        logger.info(
            f"[monitor] Auto-leaving: {reason} "
            f"(bot {self.meetingbaas_bot_id})"
        )
        try:
            from scripts.meetingbaas_api import leave_meeting_bot

            success = await asyncio.to_thread(
                leave_meeting_bot, self.meetingbaas_bot_id, self.api_key
            )
            if success:
                logger.info(
                    f"[monitor] Auto-leave successful "
                    f"for bot {self.meetingbaas_bot_id}"
                )
            else:
                logger.warning(
                    f"[monitor] Auto-leave API call failed "
                    f"for bot {self.meetingbaas_bot_id}"
                )
        except Exception as e:
            logger.error(f"[monitor] Error during auto-leave: {e}")
