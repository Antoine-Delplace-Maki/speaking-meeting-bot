"""API routes for the Speaking Meeting Bot application."""

import asyncio
import random
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.models import (
    BotRequest,
    JoinResponse,
    LeaveBotRequest,
    PersonaImageRequest,
    PersonaImageResponse,
)
from app.services.image_service import image_service
from config.persona_utils import persona_manager
from core.connection import (
    BOT_ID_TO_CLIENT,
    BOT_STATUS,
    CLEANED_UP_CLIENTS,
    IN_CALL_STATUSES,
    MEETING_DETAILS,
    MEETING_MONITORS,
    PENDING_PIPECAT_PARAMS,
    PIPECAT_PROCESSES,
    TERMINAL_STATUSES,
    registry,
)
from core.meeting_monitor import MeetingMonitor
from core.process import (
    cleanup_greeting_trigger,
    get_greeting_trigger_path,
    start_pipecat_process,
    terminate_process_gracefully,
    trigger_greeting,
)
from core.router import router as message_router

# Import from the app module (will be defined in __init__.py)
from meetingbaas_pipecat.utils.logger import logger
from scripts.meetingbaas_api import create_meeting_bot, leave_meeting_bot
from utils.ngrok import (
    LOCAL_DEV_MODE,
    determine_websocket_url,
    log_ngrok_status,
    release_ngrok_url,
    update_ngrok_client_id,
)
from config.prompts import PERSONA_INTERACTION_INSTRUCTIONS
from config.candidate_randomizer import generate_random_candidate

# Import the new persona detail extraction service
from app.services.persona_detail_extraction import extract_persona_details_from_prompt
import os

INTERNAL_PORT = os.getenv("PORT", "7014")

# Tracks clients whose greeting has already been triggered (avoids duplicate triggers)
_GREETING_TRIGGERED: set[str] = set()


def _to_absolute_url(image_path: str, websocket_url: str) -> str:
    """Convert a local /static/... path to a full HTTP URL using the server base."""
    if not image_path or not image_path.startswith("/static/"):
        return image_path
    base = websocket_url
    if base.startswith("wss://"):
        base = "https://" + base[6:]
    elif base.startswith("ws://"):
        base = "http://" + base[5:]
    return base.rstrip("/") + image_path

router = APIRouter()


def _build_image_prompt(persona: dict) -> str:
    """Build a short, appearance-only prompt for image generation.

    For randomized candidates, produces a realistic webcam interview look.
    For other personas, produces a standard appearance prompt.
    """
    name = persona.get("name", "a professional")
    gender = persona.get("gender", "")
    characteristics = persona.get("characteristics", [])

    if persona.get("is_randomized_candidate"):
        import random as _rng
        gender_word = gender.lower() if gender and gender.lower() != "non-binary" else "person"
        age = persona.get("age", "late twenties")
        cultural_bg = persona.get("cultural_background", "")

        clothing = _rng.choice([
            "a plain crew-neck t-shirt",
            "a button-up shirt with rolled sleeves",
            "a cozy knit sweater",
            "a hoodie with the zipper half-open",
            "a casual blazer over a simple tee",
            "a flannel shirt",
            "a polo shirt",
        ])
        hair = _rng.choice([
            "short cropped hair",
            "shoulder-length wavy hair",
            "a neat bun",
            "curly natural hair",
            "straight hair tucked behind one ear",
            "a buzz cut",
            "medium-length tousled hair",
            "braids",
            "long straight hair",
        ])
        room = _rng.choice([
            "a small bedroom with a bookshelf in the background",
            "a tidy home office with a plant on the desk",
            "a living room with a couch and curtains behind them",
            "a kitchen table setup with cabinets blurred in the back",
            "a cluttered desk in a college dorm room",
            "a minimalist room with a white wall and a single poster",
            "a cozy apartment with warm lamp light in the background",
        ])
        expression = _rng.choice([
            "a natural, slightly nervous but friendly expression",
            "a warm, relaxed smile",
            "a focused, attentive look with a slight smile",
            "a calm, composed expression with a hint of confidence",
            "a thoughtful look, mid-sentence",
        ])

        return (
            f"A candid webcam photograph of a person named {name}. "
            f"They are a {cultural_bg + ' ' if cultural_bg else ''}{gender_word}, "
            f"around {age} years old, with {hair}. "
            f"Captured from a laptop webcam during a video interview. "
            f"They are sitting in {room}. "
            f"They are wearing {clothing}. "
            f"They have {expression} — like someone in a real job interview. "
            f"The webcam angle is slightly above eye level, typical of a laptop camera. "
            f"Natural window light mixed with warm indoor lighting. "
            f"Skin texture, minor imperfections, and natural hair are visible. "
            f"No makeup filters, no beauty retouching, no studio lighting. "
            f"The image looks exactly like a still frame from a real Zoom or Google Meet call. "
            f"Photorealistic, 35mm film grain, shallow depth of field on the background."
        )

    parts = [f"A friendly {gender.lower()} professional" if gender else "A friendly professional"]

    if characteristics:
        parts.append(", ".join(characteristics[:4]))

    return ". ".join(parts)


@router.post(
    "/bots",
    tags=["bots"],
    response_model=JoinResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Bot successfully created and joined the meeting"},
        400: {"description": "Bad request - Missing required fields or invalid data"},
        500: {
            "description": "Server error - Failed to create bot through MeetingBaas API"
        },
    },
)
async def join_meeting(request: BotRequest, client_request: Request):
    """
    Create and deploy a speaking bot in a meeting.

    Launches an AI-powered bot that joins a video meeting through MeetingBaas
    and processes audio using Pipecat's voice AI framework.
    """
    # Validate required parameters
    if not request.meeting_url:
        return JSONResponse(
            content={"message": "Meeting URL is required", "status": "error"},
            status_code=400,
        )

    # Get API key from request state (set by middleware)
    api_key = client_request.state.api_key

    # Log local dev mode status
    if LOCAL_DEV_MODE:
        logger.info("🔍 Running in LOCAL_DEV_MODE - will prioritize ngrok URLs")
    else:
        logger.info("🔍 Running in standard mode")

    # Determine WebSocket URL (works in all cases now)
    websocket_url, temp_client_id = determine_websocket_url(None, client_request)

    logger.info(f"Starting bot for meeting {request.meeting_url}")
    logger.info(f"WebSocket URL: {websocket_url}")
    logger.info(
        f"Bot name: {request.bot_name or '(empty, will resolve from persona)'}"
    )

    # INTERNAL PARAMETER: Set a fixed value for streaming_audio_frequency
    # This is not exposed in the API and is always "16khz"
    streaming_audio_frequency = "16khz"
    logger.info(f"Using fixed streaming audio frequency: {streaming_audio_frequency}")

    # Set the converter sample rate based on our fixed streaming_audio_frequency
    from core.converter import converter

    sample_rate = 16000  # Always 16000 Hz for 16khz audio
    converter.set_sample_rate(sample_rate)
    logger.info(
        f"Set audio sample rate to {sample_rate} Hz for {streaming_audio_frequency}"
    )

    # Generate a unique client ID for this bot
    bot_client_id = str(uuid.uuid4())

    # If we're in local dev mode and we have a temp client ID, update the mapping
    if LOCAL_DEV_MODE and temp_client_id:
        update_ngrok_client_id(temp_client_id, bot_client_id)
        log_ngrok_status()

    # --- Streamlined Persona and Prompt Resolution Logic ---
    final_prompt: str = ""
    resolved_persona_data: Dict[str, Any] = {}
    persona_name_for_logging: str = "Unknown"

    if request.prompt: # Case 1: Custom prompt provided (dynamic persona)
        logger.info(f"Processing custom prompt for bot {bot_client_id}")
        prompt_derived_details = await extract_persona_details_from_prompt(request.prompt)

        if prompt_derived_details and isinstance(prompt_derived_details, dict): # Ensure it's a dict
            # Construct resolved_persona_data from derived details
            resolved_persona_data = {
                "name": prompt_derived_details.get("name", "Bot"),
                "prompt": request.prompt, # Store original request prompt as the base prompt for dynamic persona
                "description": prompt_derived_details.get("description", request.prompt), # Use derived description or fallback to full prompt
                "gender": prompt_derived_details.get("gender", "male"),
                "characteristics": prompt_derived_details.get("characteristics", []), # Ensure it's a list
                "image": None, # Will be generated/resolved later
                "cartesia_voice_id": None, # Will be matched later
                "relevant_links": [],
                "additional_content": None,
                "is_temporary": True # Mark as temporary persona
            }
            persona_name_for_logging = resolved_persona_data["name"]
            final_prompt = request.prompt + PERSONA_INTERACTION_INSTRUCTIONS
            logger.info(f"Dynamically created persona '{persona_name_for_logging}' from prompt.")
        else:
            # Fallback if prompt details extraction fails or returns unexpected type
            logger.warning("Failed to extract persona details from custom prompt or received unexpected type. Falling back to default bot persona.")
            resolved_persona_data = persona_manager.get_persona("maki_candidate")
            resolved_persona_data["is_temporary"] = False
            persona_name_for_logging = resolved_persona_data.get("name", "maki_candidate")
            final_prompt = resolved_persona_data["prompt"] + PERSONA_INTERACTION_INSTRUCTIONS

    else: # Case 2: No custom prompt, use pre-defined persona
        resolved_persona_name: str

        # Priority: request.personas > request.bot_name > random > maki_candidate
        if request.personas and len(request.personas) > 0:
            resolved_persona_name = request.personas[0]
            logger.info(f"Using specified persona '{resolved_persona_name}' for bot.")
        elif request.bot_name and request.bot_name in persona_manager.personas:
            resolved_persona_name = request.bot_name
            logger.info(f"Using bot_name as persona '{resolved_persona_name}' for bot.")
        else:
            available_personas = list(persona_manager.personas.keys())
            if available_personas:
                resolved_persona_name = random.choice(available_personas)
                logger.info(f"No persona specified, using random persona '{resolved_persona_name}' for bot.")
            else:
                resolved_persona_name = "maki_candidate"
                logger.warning("No personas found, using fallback persona: maki_candidate.")

        try:
            resolved_persona_data = persona_manager.get_persona(resolved_persona_name)
            resolved_persona_data["is_temporary"] = False # Mark as not temporary
            persona_name_for_logging = resolved_persona_data.get("name", resolved_persona_name)
            final_prompt = resolved_persona_data["prompt"] + PERSONA_INTERACTION_INSTRUCTIONS
            logger.info(f"Using pre-defined persona '{persona_name_for_logging}'.")

            if resolved_persona_data.get("randomize"):
                logger.info(f"Persona '{persona_name_for_logging}' has randomize=true, generating random identity...")
                resolved_persona_data = await generate_random_candidate(resolved_persona_data)
                persona_name_for_logging = resolved_persona_data["name"]
                final_prompt = resolved_persona_data["prompt"] + PERSONA_INTERACTION_INSTRUCTIONS
                logger.info(f"Randomized persona to '{persona_name_for_logging}' ({resolved_persona_data['gender']})")
        except KeyError as e:
            logger.error(f"Resolved persona '{resolved_persona_name}' not found: {e}. Falling back to maki_candidate.")
            resolved_persona_data = persona_manager.get_persona("maki_candidate")
            resolved_persona_data["is_temporary"] = False
            persona_name_for_logging = resolved_persona_data.get("name", "maki_candidate")
            final_prompt = resolved_persona_data["prompt"] + PERSONA_INTERACTION_INSTRUCTIONS
            logger.info(f"Using fallback persona '{persona_name_for_logging}'.")

    # Populate image if not present
    if not resolved_persona_data.get("image"):
        image_prompt = _build_image_prompt(resolved_persona_data)
        logger.info(
            f"Generating image for '{persona_name_for_logging}': "
            f"{image_prompt}"
        )
        is_raw = bool(resolved_persona_data.get("is_randomized_candidate"))
        image_size = (1536, 1024) if is_raw else (1024, 1024)
        try:
            generated_image = await image_service.generate_persona_image(
                name=resolved_persona_data.get("name", "Bot"),
                prompt=image_prompt,
                raw_prompt=is_raw,
                size=image_size,
            )
            if generated_image:
                resolved_persona_data["image"] = generated_image
                logger.info(
                    f"Generated image URL for "
                    f"'{persona_name_for_logging}': {generated_image}"
                )
            else:
                logger.warning("Image generation returned no URL.")
                resolved_persona_data["image"] = None
        except Exception as e:
            logger.error(
                f"Failed to generate image for "
                f"'{persona_name_for_logging}': {e}"
            )

    # Populate voice ID if not present
    if not resolved_persona_data.get("cartesia_voice_id"):
        from config.voice_utils import VoiceUtils # Import here to avoid circular dependency issues
        voice_utils = VoiceUtils()
        cartesia_voice_id = await voice_utils.match_voice_to_persona(persona_details=resolved_persona_data) # Pass the whole dict
        resolved_persona_data["cartesia_voice_id"] = cartesia_voice_id
        logger.info(f"Resolved Cartesia voice ID for '{persona_name_for_logging}': {cartesia_voice_id}")

    logger.info(f"Final resolved persona data for Pipecat process:")
    logger.info(f"  Name: {resolved_persona_data.get('name')}")
    logger.info(f"  Image: {resolved_persona_data.get('image')}")
    logger.info(f"  Voice ID: {resolved_persona_data.get('cartesia_voice_id')}")
    logger.info(f"  Is Temporary: {resolved_persona_data.get('is_temporary')}")

    # Store all relevant details in MEETING_DETAILS dictionary
    MEETING_DETAILS[bot_client_id] = (
        request.meeting_url,
        resolved_persona_data.get("name", persona_name_for_logging),  # Use display name from resolved data
        None,  # meetingbaas_bot_id, will be set after creation
        request.enable_tools,
        streaming_audio_frequency
    )

    bot_image = request.bot_image
    if not bot_image and resolved_persona_data.get("image"):
        bot_image = str(resolved_persona_data["image"])
        logger.info(f"Using persona image from resolved persona data: {bot_image}")

    # Convert local /static/ paths to full external URLs
    bot_image_str = str(bot_image) if bot_image is not None else None
    if bot_image_str:
        bot_image_str = _to_absolute_url(bot_image_str, websocket_url)
        logger.info(f"Final bot image URL: {bot_image_str}")
    else:
        logger.info("No bot image URL resolved.")

    # Determine the final entry message
    final_entry_message: Optional[str] = request.entry_message
    if not final_entry_message and resolved_persona_data.get("entry_message"):
        final_entry_message = resolved_persona_data.get("entry_message")
    elif not final_entry_message and resolved_persona_data.get("is_temporary", False) and not resolved_persona_data.get("is_randomized_candidate", False):
        final_entry_message = f"Hello, I'm {persona_name_for_logging}, ready to assist you throughout this session."

    # Create bot directly through MeetingBaas API
    # Use persona display name from resolved_persona_data for MeetingBaas API call
    # Use the websocket_url as the webhook_url (same base URL, different endpoint)
    webhook_url = f"{websocket_url}/webhook"
    meetingbaas_bot_id = create_meeting_bot(
        meeting_url=request.meeting_url,
        websocket_url=websocket_url,
        bot_id=bot_client_id,
        persona_name=resolved_persona_data.get("name", persona_name_for_logging),  # Use resolved display name
        api_key=api_key,
        bot_image=bot_image_str,  # Use the pre-stringified value
        entry_message=final_entry_message,
        extra=request.extra,
        streaming_audio_frequency=streaming_audio_frequency,
        webhook_url=webhook_url,
    )

    if meetingbaas_bot_id:
        details = list(MEETING_DETAILS[bot_client_id])
        details[2] = meetingbaas_bot_id
        MEETING_DETAILS[bot_client_id] = tuple(details)

        BOT_ID_TO_CLIENT[meetingbaas_bot_id] = bot_client_id

        logger.info(
            f"Bot created with MeetingBaas bot_id: "
            f"{meetingbaas_bot_id}"
        )
        logger.info(
            f"Internal client_id for WebSocket connections: "
            f"{bot_client_id}"
        )

        pipecat_ws_url = (
            f"ws://127.0.0.1:{INTERNAL_PORT}"
            f"/pipecat/{bot_client_id}"
        )
        greeting_trigger_file = get_greeting_trigger_path(bot_client_id)

        auto_leave_dict = request.auto_leave.model_dump()

        pipecat_params = {
            "websocket_url": pipecat_ws_url,
            "meeting_url": request.meeting_url,
            "persona_data": resolved_persona_data,
            "streaming_audio_frequency": streaming_audio_frequency,
            "enable_tools": request.enable_tools,
            "api_key": api_key,
            "meetingbaas_bot_id": meetingbaas_bot_id,
            "greeting_trigger_file": greeting_trigger_file,
            "auto_leave_config": auto_leave_dict,
        }

        monitor = MeetingMonitor(
            client_id=bot_client_id,
            meetingbaas_bot_id=meetingbaas_bot_id,
            api_key=api_key,
            idle_timeout=request.auto_leave.idle_timeout,
            alone_timeout=request.auto_leave.alone_timeout,
        )
        MEETING_MONITORS[bot_client_id] = monitor

        # Store params as fallback in case the early start fails
        PENDING_PIPECAT_PARAMS[bot_client_id] = pipecat_params

        try:
            process = start_pipecat_process(
                client_id=bot_client_id, **pipecat_params
            )
            PIPECAT_PROCESSES[bot_client_id] = process
            logger.info(
                "Pipecat process pre-started "
                "(will greet when bot joins the meeting)"
            )
        except Exception as e:
            logger.error(f"Failed to pre-start Pipecat: {e}")
            logger.info(
                "Pipecat process deferred until bot joins "
                "the meeting (webhook: in_call_recording)"
            )

        return JoinResponse(bot_id=meetingbaas_bot_id)
    else:
        # Clean up MEETING_DETAILS if bot creation failed
        if bot_client_id in MEETING_DETAILS:
             MEETING_DETAILS.pop(bot_client_id)

        return JSONResponse(
            content={
                "message": "Failed to create bot through MeetingBaas API",
                "status": "error",
            },
            status_code=500,
        )


@router.delete(
    "/bots/{bot_id}",
    tags=["bots"],
    response_model=Dict[str, Any],
    responses={
        200: {"description": "Bot successfully removed from meeting"},
        400: {"description": "Bad request - Missing required fields or identifiers"},
        404: {"description": "Bot not found - No bot with the specified ID"},
        500: {
            "description": "Server error - Failed to remove bot from MeetingBaas API"
        },
    },
)
async def leave_bot(
    bot_id: str,
    request: LeaveBotRequest,
    client_request: Request,
):
    """
    Remove a bot from a meeting by its ID.

    This will:
    1. Call the MeetingBaas API to make the bot leave
    2. Close WebSocket connections if they exist
    3. Terminate the associated Pipecat process
    """
    logger.info(f"Removing bot with ID: {bot_id}")
    # Get API key from request state (set by middleware)
    api_key = client_request.state.api_key

    # Verify we have the bot_id
    if not bot_id and not request.bot_id:
        return JSONResponse(
            content={
                "message": "Bot ID is required",
                "status": "error",
            },
            status_code=400,
        )

    # Use the path parameter bot_id if provided, otherwise use request.bot_id
    meetingbaas_bot_id = bot_id or request.bot_id
    client_id = None

    # Look through MEETING_DETAILS to find the client ID for this bot ID
    for cid, details in MEETING_DETAILS.items():
        # Check if the stored meetingbaas_bot_id matches
        if details[2] == meetingbaas_bot_id: # Accessing tuple element by index
            client_id = cid
            logger.info(f"Found client ID {client_id} for bot ID {meetingbaas_bot_id}")
            break

    if not client_id:
        logger.warning(f"No client ID found for bot ID {meetingbaas_bot_id}")

    success = True

    # 1. Call MeetingBaas API to make the bot leave
    if meetingbaas_bot_id:
        logger.info(f"Removing bot with ID: {meetingbaas_bot_id} from MeetingBaas API")
        result = leave_meeting_bot(
            bot_id=meetingbaas_bot_id,
            api_key=api_key,
        )
        if not result:
            success = False
            logger.error(
                f"Failed to remove bot {meetingbaas_bot_id} from MeetingBaas API"
            )
    else:
        logger.warning("No MeetingBaas bot ID or API key found, skipping API call")

    # 2. Close WebSocket connections if they exist
    if client_id:
        # Mark the client as closing to prevent further messages
        message_router.mark_closing(client_id)

        # Close Pipecat WebSocket first
        if client_id in registry.pipecat_connections:
            try:
                await registry.disconnect(client_id, is_pipecat=True)
                logger.info(f"Closed Pipecat WebSocket for client {client_id}")
            except Exception as e:
                success = False
                logger.error(f"Error closing Pipecat WebSocket: {e}")

        # Then close client WebSocket if it exists
        if client_id in registry.active_connections:
            try:
                await registry.disconnect(client_id, is_pipecat=False)
                logger.info(f"Closed client WebSocket for client {client_id}")
            except Exception as e:
                success = False
                logger.error(f"Error closing client WebSocket: {e}")

        # Add a small delay to allow for clean disconnection
        await asyncio.sleep(0.5)

    # 3. Stop the meeting monitor
    if client_id:
        monitor = MEETING_MONITORS.pop(client_id, None)
        if monitor:
            monitor.stop()

    # 4. Terminate the Pipecat process after WebSockets are closed
    if client_id and client_id in PIPECAT_PROCESSES:
        process = PIPECAT_PROCESSES[client_id]
        if process and process.poll() is None:  # If process is still running
            try:
                if terminate_process_gracefully(process, timeout=3.0):
                    logger.info(
                        f"Gracefully terminated Pipecat process for client {client_id}"
                    )
                else:
                    logger.warning(
                        f"Had to forcefully kill Pipecat process for client {client_id}"
                    )
            except Exception as e:
                success = False
                logger.error(f"Error terminating Pipecat process: {e}")

        PIPECAT_PROCESSES.pop(client_id, None)

        MEETING_DETAILS.pop(client_id, None)
        PENDING_PIPECAT_PARAMS.pop(client_id, None)

        if LOCAL_DEV_MODE and client_id:
            release_ngrok_url(client_id)
            log_ngrok_status()
    else:
        logger.warning(
            f"No Pipecat process found for client {client_id}"
        )

    if meetingbaas_bot_id:
        BOT_ID_TO_CLIENT.pop(meetingbaas_bot_id, None)
        BOT_STATUS.pop(meetingbaas_bot_id, None)

    return {
        "message": "Bot removal request processed",
        "status": "success" if success else "partial",
        "bot_id": meetingbaas_bot_id,
    }


@router.post(
    "/personas/generate-image",
    tags=["personas"],
    response_model=PersonaImageResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Image successfully generated"},
        400: {"description": "Invalid request data"},
    },
)
async def generate_persona_image(request: PersonaImageRequest) -> PersonaImageResponse:
    """Generate an image for a persona using OpenAI DALL-E."""
    try:
        # Build the prompt from available fields
        # Build the prompt using a more concise approach
        name = request.name
        prompt = f"A detailed professional portrait of a single person named {name}"

        if request.gender:
            prompt += f". {request.gender.capitalize()}"

        if request.description:
            cleaned_desc = request.description.strip().rstrip(".")
            prompt += f". Who {cleaned_desc}"

        if request.characteristics and len(request.characteristics) > 0:
            traits = ", ".join(request.characteristics)
            prompt += f". With features like {traits}"

        # Add standard quality guidelines
        prompt += ". High quality, single person, only face and shoulders, centered, neutral background, avoid borders."

        # Generate the image
        image_generation_result = await image_service.generate_persona_image(
            name=name, prompt=prompt, style="realistic", size=(512, 512)
        )

        if not image_generation_result: # Check if the string is empty/None
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to generate image: No URL returned."
            )

        image_url = image_generation_result # Use the string directly

        return PersonaImageResponse(
            name=name,
            image_url=image_url,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Error generating image: {str(e)}")
        if isinstance(e, ValueError):
            # ValueError typically indicates invalid input
            status_code = status.HTTP_400_BAD_REQUEST
        elif "connection" in str(e).lower() or "timeout" in str(e).lower():
            # Network errors should be 503 Service Unavailable
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            # Default to internal server error
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(status_code=status_code, detail=str(e))


def _maybe_start_pipecat(meetingbaas_bot_id: str) -> None:
    """Start the Pipecat process (or trigger its greeting if pre-started)."""
    client_id = BOT_ID_TO_CLIENT.get(meetingbaas_bot_id)
    if not client_id:
        logger.warning(
            f"[webhook] No client_id for bot "
            f"{meetingbaas_bot_id}"
        )
        return

    if client_id in _GREETING_TRIGGERED:
        logger.info(
            f"[webhook] Greeting already triggered for "
            f"{client_id}, skipping"
        )
        return

    monitor = MEETING_MONITORS.get(client_id)
    if monitor:
        monitor.start()

    if client_id in PIPECAT_PROCESSES:
        proc = PIPECAT_PROCESSES[client_id]
        if proc.poll() is None:
            logger.info(
                f"[webhook] Pipecat already running for "
                f"{client_id}, triggering greeting"
            )
            trigger_greeting(client_id)
            _GREETING_TRIGGERED.add(client_id)
            PENDING_PIPECAT_PARAMS.pop(client_id, None)
            return
        else:
            PIPECAT_PROCESSES.pop(client_id, None)

    params = PENDING_PIPECAT_PARAMS.pop(client_id, None)
    if not params:
        logger.warning(
            f"[webhook] No pending Pipecat params for "
            f"{client_id}"
        )
        return

    process = start_pipecat_process(
        client_id=client_id, **params
    )
    PIPECAT_PROCESSES[client_id] = process
    trigger_greeting(client_id)
    _GREETING_TRIGGERED.add(client_id)
    logger.info(
        f"[webhook] Started Pipecat for bot "
        f"{meetingbaas_bot_id} (client {client_id})"
    )


def _cleanup_bot(meetingbaas_bot_id: str) -> None:
    """Clean up all resources for a bot after a terminal event."""
    client_id = BOT_ID_TO_CLIENT.get(meetingbaas_bot_id)
    if not client_id:
        return

    monitor = MEETING_MONITORS.pop(client_id, None)
    if monitor:
        monitor.stop()

    PENDING_PIPECAT_PARAMS.pop(client_id, None)
    _GREETING_TRIGGERED.discard(client_id)
    cleanup_greeting_trigger(client_id)

    if client_id in PIPECAT_PROCESSES:
        process = PIPECAT_PROCESSES.pop(client_id)
        if process and process.poll() is None:
            try:
                if terminate_process_gracefully(
                    process, timeout=3.0
                ):
                    logger.info(
                        f"[cleanup] Terminated Pipecat for "
                        f"{client_id}"
                    )
                else:
                    logger.warning(
                        f"[cleanup] Force-killed Pipecat for "
                        f"{client_id}"
                    )
            except Exception as e:
                logger.error(
                    f"[cleanup] Error terminating Pipecat: {e}"
                )

    MEETING_DETAILS.pop(client_id, None)
    BOT_ID_TO_CLIENT.pop(meetingbaas_bot_id, None)

    CLEANED_UP_CLIENTS[client_id] = time.monotonic()
    message_router.mark_closing(client_id)

    logger.info(
        f"[cleanup] Cleaned up bot {meetingbaas_bot_id} "
        f"(client {client_id})"
    )


@router.post(
    "/webhook",
    tags=["webhook"],
    status_code=status.HTTP_200_OK,
)
async def meetingbaas_webhook(request: Request):
    """Webhook/callback endpoint for MeetingBaas v2 events.

    Receives events such as bot.status_change, bot.completed,
    and bot.failed.  The v2 payload structure is:

        {"event": "<type>", "data": {...}, "sent_at": "..."}
    """
    try:
        body = await request.json()
        event = body.get("event", "unknown")
        data = body.get("data", {})
        bot_id = data.get("bot_id", "unknown")

        if event == "bot.status_change":
            raw_status = data.get("status", {})
            status_code = (
                raw_status.get("code", "unknown")
                if isinstance(raw_status, dict)
                else str(raw_status)
            )
            BOT_STATUS[bot_id] = status_code
            logger.info(
                f"[webhook] bot.status_change  "
                f"bot_id={bot_id}  status={raw_status}"
            )

            if status_code in IN_CALL_STATUSES:
                _maybe_start_pipecat(bot_id)
            elif status_code in TERMINAL_STATUSES:
                _cleanup_bot(bot_id)

        elif event == "bot.completed":
            logger.info(
                f"[webhook] bot.completed  bot_id={bot_id}"
            )
            _cleanup_bot(bot_id)

        elif event == "bot.failed":
            error_code = data.get("error_code", "unknown")
            error_msg = data.get("error_message", "")
            logger.warning(
                f"[webhook] bot.failed  bot_id={bot_id}  "
                f"error={error_code}: {error_msg}"
            )
            _cleanup_bot(bot_id)

        elif event in ("participant.joined", "bot.participant_joined"):
            client_id = BOT_ID_TO_CLIENT.get(bot_id)
            monitor = MEETING_MONITORS.get(client_id) if client_id else None
            if monitor:
                monitor.participant_joined()
            logger.info(
                f"[webhook] {event}  bot_id={bot_id}  "
                f"participant={data.get('participant', {}).get('name', 'unknown')}"
            )

        elif event in ("participant.left", "bot.participant_left"):
            client_id = BOT_ID_TO_CLIENT.get(bot_id)
            monitor = MEETING_MONITORS.get(client_id) if client_id else None
            if monitor:
                monitor.participant_left()
            logger.info(
                f"[webhook] {event}  bot_id={bot_id}  "
                f"participant={data.get('participant', {}).get('name', 'unknown')}"
            )

        else:
            logger.info(
                f"[webhook] {event}  bot_id={bot_id}  "
                f"payload_keys={list(data.keys())}"
            )

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}
