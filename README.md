# Speaking Meeting Bot

AI-powered speaking agents that join Google Meet, Zoom, or Microsoft Teams meetings with distinct personalities. Built on [Pipecat](https://github.com/pipecat-ai/pipecat) for voice AI and [MeetingBaas](https://meetingbaas.com) for meeting connectivity.

## How It Works

A FastAPI server exposes a simple API. You send a POST request with a meeting URL and a persona name. The server:

1. Loads the persona from a Markdown file
2. Generates an avatar image (OpenAI gpt-image-1)
3. Matches a voice (Cartesia, selected by GPT)
4. Creates a bot in the meeting via MeetingBaas
5. Starts a Pipecat voice pipeline (Deepgram STT → OpenAI GPT-4 → Cartesia TTS)

The bot then listens and speaks in the meeting, staying in character.

## Quick Start

### 1. Install

```bash
poetry install
```

### 2. Configure

```bash
cp .env.example .env
```

Fill in your API keys:

| Key | Service | Purpose |
|-----|---------|---------|
| `MEETING_BAAS_API_KEY` | [MeetingBaas](https://meetingbaas.com) | Join meetings |
| `OPENAI_API_KEY` | [OpenAI](https://platform.openai.com/) | LLM + image generation |
| `DEEPGRAM_API_KEY` | [Deepgram](https://deepgram.com/) | Speech-to-text |
| `CARTESIA_API_KEY` | [Cartesia](https://cartesia.ai/) | Text-to-speech |

### 3. Compile Protocol Buffers

```bash
poetry run python -m grpc_tools.protoc --proto_path=./protobufs --python_out=./protobufs frames.proto
```

### 4. Run

```bash
source .env
poetry run uvicorn app:app --host 0.0.0.0 --port ${PORT:-7014}
```

### 5. Create a Bot

```bash
source .env
curl -X POST "http://localhost:${PORT}/bots" \
  -H "Content-Type: application/json" \
  -H "x-meeting-baas-api-key: ${MEETING_BAAS_API_KEY}" \
  -d '{
    "meeting_url": "https://meet.google.com/xxx-yyyy-zzz",
    "personas": ["maki_candidate"]
  }'
```

### 6. Remove a Bot

```bash
curl -X DELETE "http://localhost:${PORT}/bots/{bot_id}" \
  -H "Content-Type: application/json" \
  -H "x-meeting-baas-api-key: ${MEETING_BAAS_API_KEY}" \
  -d '{}'
```

## API Reference

### `POST /bots`

Create a bot and send it into a meeting.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `meeting_url` | string | Yes | Google Meet, Zoom, or Teams URL |
| `personas` | string[] | No | Persona folder names (first match is used) |
| `prompt` | string | No | Custom prompt (skips persona lookup) |
| `bot_name` | string | No | Display name override |
| `bot_image` | string | No | Avatar URL override |
| `entry_message` | string | No | Chat message on join |
| `extra` | object | No | Custom metadata |
| `enable_tools` | bool | No | Enable weather/time tools (default: true) |

Returns `{ "bot_id": "..." }` (HTTP 201).

### `DELETE /bots/{bot_id}`

Remove a bot from its meeting and clean up resources.

### `POST /webhook`

MeetingBaas callback endpoint. Handles `bot.status_change`, `bot.completed`, and `bot.failed` events.

### `GET /health`

Health check.

### API Docs

Interactive Swagger UI available at `/docs` when the server is running.

## Personas

Each persona lives in `config/personas/<name>/` with a `README.md` that defines personality, prompt, and metadata.

```
config/personas/
└── maki_candidate/
    └── README.md
```

The README follows this structure:

```markdown
# Display Name

<system prompt — this becomes the LLM's instructions>

## Metadata
- image: <url or empty>
- entry_message: <greeting or empty>
- cartesia_voice_id: <voice ID or empty>
- gender: MALE | FEMALE | NON-BINARY
- randomize: true | false
- relevant_links: <space-separated URLs>
```

When `randomize: true`, the bot generates a fresh random identity (name, background, personality) for each session using GPT.

Additional `.md` files in the persona folder are loaded as extra context for the LLM.

## Local Development with ngrok

For local development, MeetingBaas needs a public URL to reach your server:

```bash
# Start ngrok
ngrok http ${PORT:-7014}

# Set BASE_URL in .env to the ngrok HTTPS URL
BASE_URL=https://xxxx.ngrok-free.app

# Or use the built-in local dev mode
poetry run python app/main.py --local-dev
```

## Production

Set `BASE_URL` to your server's public domain and run:

```bash
poetry run uvicorn app:app --host 0.0.0.0 --port ${PORT:-7014}
```

Or use Docker:

```bash
docker build -t speaking-meeting-bot .
docker run -p 7014:7014 --env-file .env speaking-meeting-bot
```

## Project Structure

```
app/
  main.py              # FastAPI app setup, middleware, server
  routes.py            # POST /bots, DELETE /bots, webhook
  models.py            # Pydantic request/response models
  websockets.py        # WebSocket endpoints
  services/
    image_service.py   # Avatar generation (OpenAI gpt-image-1)
    persona_detail_extraction.py  # Extract persona from custom prompts
config/
  prompts.py           # System prompts
  persona_utils.py     # Persona loading from markdown
  candidate_randomizer.py  # Random candidate generation
  voice_utils.py       # Voice matching (Cartesia + GPT)
  personas/            # Persona definitions (markdown)
core/
  connection.py        # WebSocket connection registry
  process.py           # Pipecat process management
  router.py            # Message routing
  converter.py         # Audio format conversion
scripts/
  meetingbaas.py       # Pipecat pipeline (the actual bot runtime)
  meetingbaas_api.py   # MeetingBaas API client
utils/
  ngrok.py             # ngrok URL management
  url.py               # URL utilities
  process.py           # Process utilities
protobufs/
  frames.proto         # Protobuf schema for Pipecat frames
```
