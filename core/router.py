"""Routes messages between clients and Pipecat."""

import time

from core.connection import registry
from core.converter import converter
from meetingbaas_pipecat.utils.logger import logger

_LOG_INTERVAL_SECONDS = 5


class MessageRouter:
    """Routes messages between clients and Pipecat."""

    def __init__(self, registry, converter, logger=logger):
        self.registry = registry
        self.converter = converter
        self.logger = logger
        self.closing_clients = set()
        self._to_pipecat_count: dict[str, int] = {}
        self._from_pipecat_count: dict[str, int] = {}
        self._to_pipecat_bytes: dict[str, int] = {}
        self._from_pipecat_bytes: dict[str, int] = {}
        self._last_log_time: dict[str, float] = {}

    def mark_closing(self, client_id: str):
        """Mark a client as closing to prevent sending more data to it."""
        self.closing_clients.add(client_id)
        self.logger.debug(f"Marked client {client_id} as closing")

    async def send_binary(self, message: bytes, client_id: str):
        """Send binary data to a client."""
        if client_id in self.closing_clients:
            self.logger.debug(f"Skipping send to closing client {client_id}")
            return

        client = self.registry.get_client(client_id)
        if client:
            try:
                await client.send_bytes(message)
                self.logger.debug(f"Sent {len(message)} bytes to client {client_id}")
            except Exception as e:
                self.logger.debug(f"Error sending binary to client {client_id}: {e}")

    async def send_text(self, message: str, client_id: str):
        """Send text message to a specific client."""
        if client_id in self.closing_clients:
            self.logger.debug(f"Skipping send_text to closing client {client_id}")
            return

        client = self.registry.get_client(client_id)
        if client:
            try:
                await client.send_text(message)
                self.logger.debug(
                    f"Sent text message to client {client_id}: {message[:100]}..."
                )
            except Exception as e:
                self.logger.debug(f"Error sending text to client {client_id}: {e}")

    async def broadcast(self, message: str):
        """Broadcast text message to all clients."""
        for client_id, connection in self.registry.active_connections.items():
            if client_id not in self.closing_clients:
                try:
                    await connection.send_text(message)
                    self.logger.debug(f"Broadcast text message to client {client_id}")
                except Exception as e:
                    self.logger.debug(f"Error broadcasting to client {client_id}: {e}")

    def _maybe_log_audio_stats(self, client_id: str):
        """Log periodic audio flow stats at INFO level."""
        now = time.monotonic()
        last = self._last_log_time.get(client_id, 0.0)
        if now - last < _LOG_INTERVAL_SECONDS:
            return
        self._last_log_time[client_id] = now

        to_cnt = self._to_pipecat_count.get(client_id, 0)
        from_cnt = self._from_pipecat_count.get(client_id, 0)
        to_bytes = self._to_pipecat_bytes.get(client_id, 0)
        from_bytes = self._from_pipecat_bytes.get(client_id, 0)

        self.logger.info(
            f"[AUDIO] client={client_id[:8]}… "
            f"→pipecat: {to_cnt} frames ({to_bytes} B) "
            f"←pipecat: {from_cnt} frames ({from_bytes} B)"
        )
        self._to_pipecat_count[client_id] = 0
        self._from_pipecat_count[client_id] = 0
        self._to_pipecat_bytes[client_id] = 0
        self._from_pipecat_bytes[client_id] = 0

    async def send_to_pipecat(self, message: bytes, client_id: str):
        """Convert raw audio to Protobuf frame and send to Pipecat."""
        if client_id in self.closing_clients:
            self.logger.debug(
                f"Skipping send to Pipecat for closing client {client_id}"
            )
            return

        pipecat = self.registry.get_pipecat(client_id)
        if pipecat:
            try:
                serialized_frame = self.converter.raw_to_protobuf(message)
                await pipecat.send_bytes(serialized_frame)
                self._to_pipecat_count[client_id] = (
                    self._to_pipecat_count.get(client_id, 0) + 1
                )
                self._to_pipecat_bytes[client_id] = (
                    self._to_pipecat_bytes.get(client_id, 0) + len(message)
                )
                self._maybe_log_audio_stats(client_id)
            except Exception as e:
                if "close" in str(e).lower() or "closed" in str(e).lower():
                    self.logger.debug(
                        f"Connection closed when sending to Pipecat for client {client_id}: {e}"
                    )
                    self.mark_closing(client_id)
                else:
                    self.logger.error(f"Error sending to Pipecat: {str(e)}")
        else:
            self.logger.warning(
                f"No Pipecat connection for client {client_id[:8]}… — dropping audio"
            )

    async def send_from_pipecat(self, message: bytes, client_id: str):
        """Extract audio from Protobuf frame and send to client."""
        if client_id in self.closing_clients:
            self.logger.debug(
                f"Skipping send from Pipecat for closing client {client_id}"
            )
            return

        client = self.registry.get_client(client_id)
        if client:
            try:
                audio_data = self.converter.protobuf_to_raw(message)
                if audio_data:
                    await client.send_bytes(audio_data)
                    self._from_pipecat_count[client_id] = (
                        self._from_pipecat_count.get(client_id, 0) + 1
                    )
                    self._from_pipecat_bytes[client_id] = (
                        self._from_pipecat_bytes.get(client_id, 0)
                        + len(audio_data)
                    )
                    self._maybe_log_audio_stats(client_id)
            except Exception as e:
                if "close" in str(e).lower() or "closed" in str(e).lower():
                    self.logger.debug(
                        f"Connection closed when sending to client {client_id}: {e}"
                    )
                    self.mark_closing(client_id)
                else:
                    self.logger.error(f"Error processing Pipecat message: {str(e)}")
        else:
            self.logger.warning(
                f"No client connection for {client_id[:8]}… — dropping Pipecat audio"
            )


# Create a singleton instance
router = MessageRouter(registry, converter)
