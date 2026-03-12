"""Connection management for WebSocket clients and Pipecat processes."""

import subprocess
from typing import Any, Dict, List, Optional, Tuple

from fastapi import WebSocket

from meetingbaas_pipecat.utils.logger import logger

# Global dictionary to store meeting details for each client
MEETING_DETAILS: Dict[
    str, Tuple[str, str, Optional[str], bool, str]
] = {}  # client_id -> (meeting_url, persona_name, meetingbaas_bot_id, enable_tools, streaming_audio_frequency)

# Global dictionary to store Pipecat processes
PIPECAT_PROCESSES: Dict[
    str, subprocess.Popen
] = {}  # client_id -> process

# Bot status from MeetingBaas webhooks
BOT_STATUS: Dict[str, str] = {}  # meetingbaas_bot_id -> status_code

# Reverse mapping for fast lookup
BOT_ID_TO_CLIENT: Dict[
    str, str
] = {}  # meetingbaas_bot_id -> internal client_id

# Deferred Pipecat launch params (consumed when bot joins the call)
PENDING_PIPECAT_PARAMS: Dict[
    str, Dict[str, Any]
] = {}  # client_id -> kwargs for start_pipecat_process

# Clients that reached a terminal state (reject further reconnections)
CLEANED_UP_CLIENTS: Dict[
    str, float
] = {}  # client_id -> monotonic timestamp

CLEANUP_REMEMBER_SECONDS = 300

# client_id -> MeetingMonitor instance (auto-leave tracking)
MEETING_MONITORS: Dict[str, Any] = {}

TERMINAL_STATUSES = frozenset({"call_ended", "fatal_error"})
IN_CALL_STATUSES = frozenset({
    "in_call_recording",
    "in_call_not_recording",
})


class ConnectionRegistry:
    """Manages WebSocket connections for clients and Pipecat."""

    def __init__(self, logger=logger):
        self.active_connections: Dict[str, WebSocket] = {}
        self.pipecat_connections: Dict[str, WebSocket] = {}
        self.logger = logger

    async def connect(
        self, websocket: WebSocket, client_id: str, is_pipecat: bool = False
    ):
        """Register a new connection."""
        await websocket.accept()
        if is_pipecat:
            self.pipecat_connections[client_id] = websocket
            self.logger.info(f"Pipecat client {client_id} connected")
        else:
            self.active_connections[client_id] = websocket
            self.logger.info(f"Client {client_id} connected")

    async def disconnect(self, client_id: str, is_pipecat: bool = False):
        """Remove a connection and close the websocket."""
        try:
            # First, remove the connection from our dictionaries before attempting to close it
            if is_pipecat:
                if client_id in self.pipecat_connections:
                    websocket = self.pipecat_connections.pop(client_id)
                    # Try to close it if possible
                    try:
                        await websocket.close(code=1000, reason="Bot disconnected")
                    except Exception as e:
                        # It's normal for this to fail if the connection is already closed
                        self.logger.debug(
                            f"Could not close Pipecat WebSocket for {client_id}: {e}"
                        )
                    self.logger.info(f"Pipecat client {client_id} disconnected")
            else:
                if client_id in self.active_connections:
                    websocket = self.active_connections.pop(client_id)
                    # Try to close it if possible
                    try:
                        await websocket.close(code=1000, reason="Bot disconnected")
                    except Exception as e:
                        # It's normal for this to fail if the connection is already closed
                        self.logger.debug(
                            f"Could not close client WebSocket for {client_id}: {e}"
                        )
                    self.logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            # This should rarely happen now, but just in case
            self.logger.debug(f"Error during disconnect for {client_id}: {e}")

    def get_client(self, client_id: str) -> Optional[WebSocket]:
        """Get a client connection by ID."""
        return self.active_connections.get(client_id)

    def get_pipecat(self, client_id: str) -> Optional[WebSocket]:
        """Get a Pipecat connection by ID."""
        return self.pipecat_connections.get(client_id)


# Create a singleton instance
registry = ConnectionRegistry()
