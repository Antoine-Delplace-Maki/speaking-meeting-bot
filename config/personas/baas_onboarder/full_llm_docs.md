file: ./content/docs/api/community-and-support.mdx

# undefined: Community & Support

Join our Discord Community, or ping us on our socials.

import { ContactLink } from "@/components/contact-link";

## Community:

-   [Join our Discord](https://discord.com/invite/dsvFgDTr6c)
-   [Star us on Github](https://github.com/Meeting-Baas/Meeting-Bot-As-A-Service)

## Contact & Support

Planning to use more than 100 hours a month?\
Expect a response within the day.

-   Twitter
-   <ContactLink />
-   Slack and Teams channels for customers and partners.

file: ./content/docs/api/index.mdx

# undefined: Introduction

Deploy AI for video meetings through a single unified API.

**Meeting Baas** 🐟 provides _Meetings Bots As A Service_, with integrated transcription.

This allows you to:

1. **interact with**
2. **transcribe**
3. **AI summarize**

video-meetings through a single unified API. Using Meeting Baas, you can deploy bots on Microsoft Teams, Google Meet, and Zoom in less than 1 minute.

Our meeting bots behave just like any other attendee of a meeting – except they won’t talk. _For now._

Bots can hear and see other people talking, read and write in the chat, and present themselves with a name and a profile picture.

Just provide a meeting URL through a simple command, and meeting bots will connect to the meeting, give their name and ask to be let in.

Once inside, they record the meeting until it ends, and provide you with the data as they go.

file: ./content/docs/speaking-bots/index.mdx

# undefined: Introduction

Deploy AI for video meetings through a single unified API.

**Meeting Baas** 🐟 provides _Meetings Bots As A Service_, with integrated transcription.

This allows you to:

1. **interact with**
2. **transcribe**
3. **AI summarize**

video-meetings through a single unified API. Using Meeting Baas, you can deploy bots on Microsoft Teams, Google Meet, and Zoom in less than 1 minute.

Our meeting bots behave just like any other attendee of a meeting – except they won’t talk. _For now._

Bots can hear and see other people talking, read and write in the chat, and present themselves with a name and a profile picture.

Just provide a meeting URL through a simple command, and meeting bots will connect to the meeting, give their name and ask to be let in.

Once inside, they record the meeting until it ends, and provide you with the data as they go.

file: ./content/docs/api/api-reference/create_calendar.mdx

# undefined: Create Calendar

Establishes a new calendar integration with specified provider and authentication details.

<APIPage document={"./openapi.json"} operations={[{"path":"/calendars/","method":"post"}]} hasHead={false} />

file: ./content/docs/api/api-reference/delete_calendar.mdx

# undefined: Delete a Calendar

Removes a calendar integration and cleans up associated resources including scheduled recordings.

<APIPage document={"./openapi.json"} operations={[{"path":"/calendars/{uuid}","method":"delete"}]} hasHead={false} />

file: ./content/docs/api/api-reference/get_bot.mdx

# undefined: Get Bot

Retrieves available information about a specific bot instance including its current status, configuration and meeting details.

<APIPage document={"./openapi.json"} operations={[{"path":"/bots/{uuid}","method":"get"}]} hasHead={false} />

file: ./content/docs/api/api-reference/get_calendar.mdx

# undefined: Get a Calendar

Retrieves detailed information about a specific calendar integration including sync status and events.

<APIPage document={"./openapi.json"} operations={[{"path":"/calendars/{uuid}","method":"get"}]} hasHead={false} />

file: ./content/docs/api/api-reference/get_event.mdx

# undefined: Get Event

Retrieves comprehensive details about a specific calendar event including meeting links, participants, and recording status.

<APIPage document={"./openapi.json"} operations={[{"path":"/calendar_events/{uuid}","method":"get"}]} hasHead={false} />

file: ./content/docs/api/api-reference/get_meeting_data.mdx

# undefined: Get Meeting Data

Retrieves available meeting information including participants, transcript, duration, and recording status for a specific bot session.

<APIPage document={"./openapi.json"} operations={[{"path":"/bots/meeting_data","method":"get"}]} hasHead={false} />

file: ./content/docs/api/api-reference/join.mdx

# undefined: Join Meeting

Initiates a bot to join a meeting either immediately or at a scheduled future time. Returns a bot ID.

<APIPage document={"./openapi.json"} operations={[{"path":"/bots/","method":"post"}]} hasHead={false} />

file: ./content/docs/api/api-reference/leave.mdx

# undefined: Leave Meeting

Commands a bot to immediately leave its current meeting.

<APIPage document={"./openapi.json"} operations={[{"path":"/bots/{uuid}","method":"delete"}]} hasHead={false} />

file: ./content/docs/api/api-reference/list_calendars.mdx

# undefined: List Calendars

Retrieves all configured calendars for the authenticated account with their integration status and settings.

<APIPage document={"./openapi.json"} operations={[{"path":"/calendars/","method":"get"}]} hasHead={false} />

file: ./content/docs/api/api-reference/list_events.mdx

# undefined: List Events

Retrieves all calendar events within the configured time range, including their recording status and bot assignments.

<APIPage document={"./openapi.json"} operations={[{"path":"/calendar_events/","method":"get"}]} hasHead={false} />

file: ./content/docs/api/api-reference/list_raw_calendars.mdx

# undefined: List Raw Calendars

Retrieves unprocessed calendar data directly from the provider, including all available metadata and settings.

<APIPage document={"./openapi.json"} operations={[{"path":"/calendars/raw","method":"post"}]} hasHead={false} />

file: ./content/docs/api/api-reference/schedule_record_event.mdx

# undefined: Schedule Record Event

Configures a bot to automatically join and record a specific calendar event at its scheduled time.

<APIPage document={"./openapi.json"} operations={[{"path":"/calendar_events/{uuid}/bot","method":"post"}]} hasHead={false} />

file: ./content/docs/api/api-reference/unschedule_record_event.mdx

# undefined: Unschedule Record Event

Cancels a previously scheduled recording for a calendar event and releases associated bot resources.

<APIPage document={"./openapi.json"} operations={[{"path":"/calendar_events/{uuid}/bot","method":"delete"}]} hasHead={false} />

file: ./content/docs/api/getting-started/getting-the-data.mdx

# undefined: Getting the data

Learn how to receive and process meeting data through webhooks, including live events and post-meeting recordings

To get your meeting data, listen for POST requests to the webhook URL you set up in your account.
There you'll get two types of data:

-   **live meeting events**, as the bot interacts with the meeting. Right now, the events supported share bot status updates.

-   **post-meeting data:** the video-recording, speech time events, ...

### 1. Live Meeting Events

The events we send you during the meeting are in the following format:

```http
POST /your-endpoint HTTP/1.1
Host: your-company.com
Content-Type: application/json
x-meeting-baas-api-key: YOUR-API-KEY

{
  "event": "bot.status_change",
  "data": {
    "bot_id": "asfdgfdewsrtiuydsfgklafsd",
    "status": {
      "code": "joining_call",
      "created_at": "2024-01-01T12:00:00.000Z"
    }
  }
}
```

Here we have:

-   `event`: The key-value pair for bot status events. Always `bot.status_change`.

-   `data.bot_id`: The identifier of the bot.

-   `data.status.code`: The code of the event. One of:

    -   `joining_call`: The bot has acknowledged the request to join the call.

    -   `in_waiting_room`: The bot is in the "waiting room" of the meeting.

    -   `in_call_not_recording`: The bot has joined the meeting, however it is not recording yet.

    -   `in_call_recording`: The bot is in the meeting and recording the audio and video.

    -   `call_ended`: The bot has left the call.

-   `data.status.created_at`: An ISO string of the datetime of the event.

### 2. Success webhook

To get the final meeting data, listen for POST requests to the webhook URL you set up in your account.&#x20;

You either get:

-   &#x20; `"event": "complete",`

or

-   &#x20; `"event": "failed".`

Here's an example for a `complete event`, assuming `[https://your-company.com/your-endpoint](https://your-company.com/your-endpoint)` is your webhook URL:

```http
POST /your-endpoint HTTP/1.1
Host: your-company.com
Content-Type: application/json
x-meeting-baas-api-key: YOUR-API-KEY

{
  "event": "complete",
  "data": {
    "bot_id": "asfdgfdewsrtiuydsfgklafsd",
    "mp4": "https://bots-videos.s3.eu-west-3.amazonaws.com/path/to/video.mp4?X-Amz-Signature=...",
    "speakers": ["Alice", "Bob"],
    "transcript": [{
      "speaker": "Alice",
      "words": [{
        "start": 1.3348110430839002,
        "end": 1.4549110430839003,
        "word": "Hi"
      }, {
        "start": 1.4549110430839003,
        "end": 1.5750110430839004,
        "word": "Bob!"
      }]
    }, {
      "speaker": "Bob",
      "words": [{
        "start": 2.6583010430839,
        "end": 2.778401043083901,
        "word": "Hello"
      }, {
        "start": 2.778401043083901,
        "end": 2.9185110430839005,
        "word": "Alice!"
      }]
    }]
  }
}
```

Let's break this down:

-   `bot_id`: the identifier of the bot.

-   `mp4`: A private AWS S3 URL of the mp4 recording of the meeting. Valid for one hour only.

-   `speakers`: The list of speakers in this meeting. Currently, this requires the transcription to be enabled. Stay tuned :sunny:

-   `transcript | optional`: The meeting transcript. Only given when `speech_to_text` is set when asking for a bot. An array of:

    -   `transcript.speaker`: The speaker name.

    -   `transcript.words`: The list of words. An array of:
        -   `transcript.words.start`: The start time of the word.
            -   `transcript.words.end`: The end time of the word.
            -   `transcript.words.word`: The word itself.

### 3. Failed webhook

Here's an example of a failed recording:

```http
POST /your-endpoint HTTP/1.1
Host: your-company.com
Content-Type: application/json
x-meeting-baas-api-key: YOUR-API-KEY

{
  "event": "failed",
  "data": {
    "bot_id": "asfdgfdewsrtiuydsfgklafsd",
    "error": "CannotJoinMeeting"
  }
}
```

The failure types can be:

| Error                 | Description                                                                                                                                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CannotJoinMeeting     | The bot could not join the meeting URL provided.                                                                                                                                                                    |
| TimeoutWaitingToStart | The bot has quit after waiting to be accepted. By default this is 10 minutes, configurable via `timeout_config.waiting_room_timeout` or `timeout_config.no_one_joined_timeout` (both default to 600 seconds).       |
| BotNotAccepted        | The bot has been refused in the meeting.                                                                                                                                                                            |
| InternalError         | An unexpected error occurred. Please contact us if the issue persists.                                                                                                                                              |
| InvalidMeetingUrl     | The meeting URL provided is not a valid (Zoom, Meet, Teams) URL.                                                                                                                                                    |

file: ./content/docs/api/getting-started/removing-a-bot.mdx

# undefined: Removing a bot

Learn how to remove a bot from an ongoing meeting using the API

import { Tab, Tabs } from "fumadocs-ui/components/tabs";

If you want to remove a bot from a meeting, send a POST request to `https://api.meetingbaas.com/v2/bots/YOUR_BOT_ID/leave` with the bot identifier:

<Tabs items={['Bash', 'Python', 'JavaScript']}>
<Tab value="Bash">
`bash title="leave_meeting.sh"
    curl -X POST "https://api.meetingbaas.com/v2/bots/YOUR_BOT_ID/leave" \
         -H "Content-Type: application/json" \
         -H "x-meeting-baas-api-key: YOUR-API-KEY"
    `
</Tab>

  <Tab value="Python">
    ```python title="leave_meeting.py"
    import requests

    bot_id = "YOUR_BOT_ID"
    url = f"https://api.meetingbaas.com/v2/bots/{bot_id}/leave"
    headers = {
        "Content-Type": "application/json",
        "x-meeting-baas-api-key": "YOUR-API-KEY",
    }

    response = requests.post(url, headers=headers)
    data = response.json()
    if data.get("success"):
        print("Bot successfully removed from the meeting.")
    else:
        print("Failed to remove the bot:", data)
    ```

  </Tab>

  <Tab value="JavaScript">
    ```javascript title="leave_meeting.js"
    const botId = "YOUR_BOT_ID";
    fetch(`https://api.meetingbaas.com/v2/bots/${botId}/leave`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-meeting-baas-api-key": "YOUR-API-KEY",
      },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          console.log("Bot successfully removed from the meeting.");
        } else {
          console.error("Failed to remove the bot:", data.message);
        }
      })
      .catch((error) => console.error("Error:", error));
    ```
  </Tab>
</Tabs>

Both API key and bot ID are mandatory.

The bot will leave the meeting and you will get the meeting data up to this point.

Expect a v2 standardized response:

```http
HTTP/2 200
Content-Type: application/json

{ "success": true, "data": { ... } }
```

file: ./content/docs/api/getting-started/sending-a-bot.mdx

# undefined: Sending a bot

Learn how to send AI bots to meetings through the Meeting Baas API, with options for immediate or scheduled joining and customizable settings

import { Tab, Tabs } from "fumadocs-ui/components/tabs";

You can summon a bot:

1. Immediately to a meeting, provided your bot pool is sufficient.
2. Or reserve one to come in 4 minutes.

Here's an example POST request to `https://api.meetingbaas.com/v2/bots`, sending a bot to a meeting:

<Tabs items={['Bash', 'Python', 'JavaScript']}>
<Tab value="Bash">
`bash title="join_meeting.sh"
    curl -X POST "https://api.meetingbaas.com/v2/bots" \
         -H "Content-Type: application/json" \
         -H "x-meeting-baas-api-key: YOUR-API-KEY" \
         -d '{
               "meeting_url": "YOUR-MEETING-URL",
               "bot_name": "AI Notetaker",
               "recording_mode": "speaker_view",
               "bot_image": "https://example.com/bot.jpg",
               "entry_message": "I am a good meeting bot :)",
               "transcription_enabled": true,
               "transcription_config": {
                 "provider": "gladia"
               },
               "timeout_config": {
                 "waiting_room_timeout": 600,
                 "no_one_joined_timeout": 600,
                 "silence_timeout": 600
               }
             }'
    `
</Tab>

  <Tab value="Python">
    ```python title="join_meeting.py"
    import requests
    url = "https://api.meetingbaas.com/v2/bots"
    headers = {
        "Content-Type": "application/json",
        "x-meeting-baas-api-key": "YOUR-API-KEY",
    }
    config = {
        "meeting_url": "YOUR-MEETING-URL",
        "bot_name": "AI Notetaker",
        "recording_mode": "speaker_view",
        "bot_image": "https://example.com/bot.jpg",
        "entry_message": "I am a good meeting bot :)",
        "transcription_enabled": True,
        "transcription_config": {
            "provider": "gladia"
        },
        "timeout_config": {
            "waiting_room_timeout": 600,
            "no_one_joined_timeout": 600,
            "silence_timeout": 600,
        }
    }
    response = requests.post(url, json=config, headers=headers)
    data = response.json()
    print(data["data"]["bot_id"])
    ```
  </Tab>

  <Tab value="JavaScript">
    ```javascript title="join_meeting.js"
    fetch("https://api.meetingbaas.com/v2/bots", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-meeting-baas-api-key": "YOUR-API-KEY",
      },
      body: JSON.stringify({
        meeting_url: "YOUR-MEETING-URL",
        bot_name: "AI Notetaker",
        recording_mode: "speaker_view",
        bot_image: "https://example.com/bot.jpg",
        entry_message: "I am a good meeting bot :)",
        transcription_enabled: true,
        transcription_config: {
          provider: "gladia",
        },
        timeout_config: {
          waiting_room_timeout: 600,
          no_one_joined_timeout: 600,
          silence_timeout: 600,
        },
      }),
    })
      .then((response) => response.json())
      .then((data) => console.log(data.data.bot_id))
      .catch((error) => console.error("Error:", error));
    ```
  </Tab>
</Tabs>

Let's break this down:

-   `meeting_url`: The meeting URL to join. Accepts Google Meet, Microsoft Teams or Zoom URLs. (Required)
-   `bot_name`: The display name of the bot. (Required)
-   `bot_image`: The URL of the image the bot will display. Must be a valid HTTPS URI pointing to JPEG or PNG. Optional.
-   `recording_mode`: Optional. One of:
    -   `"speaker_view"`: (default) The recording will only show the person speaking at any time
    -   `"gallery_view"`: The recording will show all the speakers
    -   `"audio_only"`: The recording will be audio-only (MP3)
-   `entry_message`: Optional. The message the bot will write in the meeting chat when it joins (max 500 characters). Available for Google Meet and Zoom.
-   `transcription_enabled`: Optional boolean. Set to `true` to enable transcription.
-   `transcription_config`: Required if `transcription_enabled` is `true`.
    -   `provider`: `"gladia"` (default). More providers coming soon.
    -   `api_key`: Optional. Your own transcription provider API key (BYOK).
    -   `custom_params`: Optional. Custom parameters for the transcription provider.
-   `timeout_config`: Optional object containing:
    -   `waiting_room_timeout`: Time in seconds the bot will wait in the waiting room (default 600, min 120, max 1800)
    -   `no_one_joined_timeout`: Time in seconds the bot will wait if no one joins (default 600, min 120, max 1800)
    -   `silence_timeout`: Time in seconds of silence before the bot leaves (default 600, min 300, max 1800)

Additional optional parameters:

-   `allow_multiple_bots`: Boolean, default `true`. Set to `false` to prevent duplicate bots joining the same meeting within 5 minutes.
-   `streaming_enabled`: Boolean, default `false`. Enable audio streaming.
-   `streaming_config`: Required if `streaming_enabled` is `true`:
    -   `output`: WebSocket endpoint to receive audio stream from the meeting
    -   `input`: WebSocket endpoint to stream audio back into the meeting
    -   `audio_frequency`: `"16khz"` or `"24khz"` (default `"24khz"`)
-   `callback_enabled`: Boolean, default `false`. Enable per-bot callbacks.
-   `callback_config`: Required if `callback_enabled` is `true`:
    -   `url`: The URL to receive `bot.completed` and `bot.failed` events.
    -   `method`: `"POST"` (default) or `"PUT"`.
    -   `secret`: Optional secret included in `x-mb-secret` header for verification.
-   `extra`: Additional custom metadata (included in webhooks and callbacks)

This request will respond with the identifier of the bot you just created:

```http
HTTP/2 201
Content-Type: application/json

{
  "success": true,
  "data": {
    "bot_id": "123e4567-e89b-12d3-a456-426614174000"
  }
}
```
