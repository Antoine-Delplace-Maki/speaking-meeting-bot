"""WebSocket routes for the Speaking Meeting Bot API."""

import asyncio
import os
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.connection import (
    BOT_ID_TO_CLIENT,
    BOT_STATUS,
    CLEANED_UP_CLIENTS,
    CLEANUP_REMEMBER_SECONDS,
    MEETING_DETAILS,
    PIPECAT_PROCESSES,
    TERMINAL_STATUSES,
    registry,
)
from core.process import terminate_process_gracefully
from core.router import router as message_router
from meetingbaas_pipecat.utils.logger import logger
from utils.ngrok import LOCAL_DEV_MODE, log_ngrok_status, release_ngrok_url

INTERNAL_PORT = os.getenv("PORT", "7014")

websocket_router = APIRouter()


def find_client_id_by_meetingbaas_bot_id(
    meetingbaas_bot_id: str,
) -> str | None:
    """Look up the internal client_id by MeetingBaas bot_id."""
    client_id = BOT_ID_TO_CLIENT.get(meetingbaas_bot_id)
    if client_id:
        return client_id
    for internal_id, details in MEETING_DETAILS.items():
        if len(details) > 2 and details[2] == meetingbaas_bot_id:
            return internal_id
    return None


def _is_stale_client(client_id: str) -> bool:
    """Return True if this client reached a terminal state."""
    ts = CLEANED_UP_CLIENTS.get(client_id)
    if ts is None:
        return False
    if time.monotonic() - ts > CLEANUP_REMEMBER_SECONDS:
        CLEANED_UP_CLIENTS.pop(client_id, None)
        return False
    return True


def _get_bot_status(client_id: str) -> str | None:
    """Look up the latest webhook status for a client."""
    details = MEETING_DETAILS.get(client_id)
    if not details or len(details) < 3:
        return None
    meetingbaas_bot_id = details[2]
    if not meetingbaas_bot_id:
        return None
    return BOT_STATUS.get(meetingbaas_bot_id)


@websocket_router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket, client_id: str
):
    """Handle WebSocket connections from MeetingBaas clients."""
    await registry.connect(websocket, client_id)

    if _is_stale_client(client_id):
        logger.info(
            f"Ignoring reconnection from terminal client "
            f"{client_id}"
        )
        await websocket.close(
            code=1000, reason="Session already ended"
        )
        return

    message_router.unmark_closing(client_id)
    logger.info(f"Client {client_id} connected")

    internal_client_id = client_id
    try:
        if client_id not in MEETING_DETAILS:
            internal_client_id = (
                find_client_id_by_meetingbaas_bot_id(client_id)
            )
            if internal_client_id:
                logger.info(
                    f"Found internal client_id "
                    f"{internal_client_id} for MeetingBaas "
                    f"bot_id {client_id}"
                )
                message_router.unmark_closing(
                    internal_client_id
                )
            else:
                logger.warning(
                    f"No meeting details found for "
                    f"client {client_id}"
                )
                await websocket.close(
                    code=1008,
                    reason="Missing meeting details",
                )
                return

        meeting_details = MEETING_DETAILS[internal_client_id]
        meeting_url = (
            meeting_details[0]
            if len(meeting_details) > 0
            else None
        )
        persona_name = (
            meeting_details[1]
            if len(meeting_details) > 1
            else None
        )
        meetingbaas_bot_id = (
            meeting_details[2]
            if len(meeting_details) > 2
            else None
        )
        enable_tools = (
            meeting_details[3]
            if len(meeting_details) > 3
            else False
        )
        streaming_audio_frequency = (
            meeting_details[4]
            if len(meeting_details) > 4
            else "16khz"
        )

        logger.info(
            f"Retrieved meeting details for "
            f"{internal_client_id}: {meeting_url}, "
            f"{persona_name}, {meetingbaas_bot_id}, "
            f"{enable_tools}, {streaming_audio_frequency}"
        )

        if (
            internal_client_id in PIPECAT_PROCESSES
            and PIPECAT_PROCESSES[internal_client_id].poll()
            is None
        ):
            logger.info(
                f"Pipecat process running for "
                f"client {internal_client_id}"
            )
        else:
            logger.info(
                f"Pipecat not yet running for "
                f"{internal_client_id} — will start when "
                f"bot joins the meeting"
            )

        while True:
            try:
                message = await websocket.receive()
            except RuntimeError as e:
                if "disconnect" in str(e).lower():
                    logger.info(
                        f"WebSocket for client {client_id} "
                        f"closed by client."
                    )
                    break
                raise

            if "bytes" in message:
                audio_data = message["bytes"]
                await message_router.send_to_pipecat(
                    audio_data, internal_client_id
                )
            elif "text" in message:
                text_data = message["text"]
                logger.info(
                    f"Received text from client "
                    f"{client_id}: {text_data[:100]}..."
                )
    except WebSocketDisconnect:
        logger.info(
            f"WebSocket disconnected for client {client_id}"
        )
    except Exception as e:
        logger.error(
            f"Error in WebSocket connection: {e} "
            f"(repr: {repr(e)})"
        )
    finally:
        bot_status = _get_bot_status(internal_client_id)
        is_terminal = bot_status in TERMINAL_STATUSES

        if is_terminal:
            CLEANED_UP_CLIENTS[client_id] = time.monotonic()
            if internal_client_id != client_id:
                CLEANED_UP_CLIENTS[
                    internal_client_id
                ] = time.monotonic()

            if internal_client_id in PIPECAT_PROCESSES:
                process = PIPECAT_PROCESSES.pop(
                    internal_client_id
                )
                if process and process.poll() is None:
                    try:
                        terminate_process_gracefully(
                            process, timeout=3.0
                        )
                    except Exception as e:
                        logger.error(
                            f"Error terminating process: {e}"
                        )

            MEETING_DETAILS.pop(internal_client_id, None)
            message_router.mark_closing(internal_client_id)

            logger.info(
                f"Full cleanup for terminal client "
                f"{client_id} (status={bot_status})"
            )

            if LOCAL_DEV_MODE:
                release_ngrok_url(client_id)
                log_ngrok_status()
        else:
            logger.info(
                f"Client {client_id} disconnected "
                f"(status={bot_status}) — allowing "
                f"reconnection"
            )

        try:
            await registry.disconnect(client_id)
        except Exception:
            pass


@websocket_router.websocket("/pipecat/{client_id}")
async def pipecat_websocket(websocket: WebSocket, client_id: str):
    """Handle WebSocket connections from Pipecat."""
    await registry.connect(websocket, client_id, is_pipecat=True)
    try:
        while True:
            try:
                message = await websocket.receive()
            except RuntimeError as e:
                if "disconnect" in str(e).lower():
                    logger.info(
                        f"Pipecat WebSocket for client {client_id} closed."
                    )
                    break
                raise

            if "bytes" in message:
                data = message["bytes"]
                logger.debug(
                    f"Received binary data ({len(data)} bytes) from Pipecat client {client_id}"
                )
                await message_router.send_from_pipecat(data, client_id)
            elif "text" in message:
                data = message["text"]
                logger.info(
                    f"Received text message from Pipecat client {client_id}: {data[:100]}..."
                )
    except WebSocketDisconnect:
        logger.info(f"Pipecat WebSocket disconnected for client {client_id}")
    except Exception as e:
        logger.error(
            f"Error in Pipecat WebSocket handler for client {client_id}: {str(e)}"
        )
    finally:
        # Mark client as closing before disconnecting
        message_router.mark_closing(client_id)

        try:
            await registry.disconnect(client_id, is_pipecat=True)
            logger.info(f"Pipecat client {client_id} disconnected")
        except Exception as e:
            # Log at debug level since this can happen during normal shutdown
            logger.debug(f"Error disconnecting Pipecat client {client_id}: {e}")

        # Release ngrok URL
        if LOCAL_DEV_MODE:
            release_ngrok_url(client_id)
            log_ngrok_status()
