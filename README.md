# Voice AI — Real-Time Conversational Agent

A real-time, turn-based voice AI system that handles end-to-end phone-call-style conversations using **Sarvam AI** for Speech-to-Text (STT), Large Language Model (LLM), and Text-to-Speech (TTS). Built with **FastAPI** (backend) and **React/Vite** (browser tester).

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Conversation Flow](#conversation-flow)
- [State Machine](#state-machine)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Running the Project](#running-the-project)
- [Configuration](#configuration)
- [Services](#services)
- [Frontend Tester](#frontend-tester)

---

## Architecture Overview

```
┌─────────────┐    WebSocket (16kHz PCM)    ┌──────────────────────┐
│   Browser   │ ◄──────────────────────────► │  FastAPI Backend      │
│ (React/Vite)│                              │  (call_handler.py)   │
└─────────────┘                              └──────┬───────────────┘
                                                    │
                          ┌─────────────────────────┼──────────────────────┐
                          ▼                         ▼                      ▼
                   ┌─────────────┐          ┌─────────────┐        ┌─────────────┐
                   │ Sarvam STT  │          │ Sarvam LLM  │        │ Sarvam TTS  │
                   │ (Saaras v3) │          │    (v2)     │        │(Bulbul v3)  │
                   └─────────────┘          └─────────────┘        └─────────────┘
```

| Component | Technology | Purpose |
|---|---|---|
| **Frontend** | React + Vite | Captures mic audio, resamples to 16 kHz, streams over WebSocket; plays back TTS audio |
| **Backend** | FastAPI + uvicorn | WebSocket server, state machine, service orchestration |
| **STT** | Sarvam Saaras v3 | Streams audio → transcript + VAD events (`START_SPEECH`, `END_SPEECH`) |
| **LLM** | Sarvam Chat v2 | Generates contextual Tamil responses with rolling 10-turn history |
| **TTS** | Sarvam Bulbul v3 | Synthesises Tamil text → 16 kHz PCM audio stream |

---

## Project Structure

```
voice_ai/
├── app/                        # FastAPI backend
│   ├── main.py                 # App entry point (uvicorn)
│   ├── core/
│   │   ├── state_machine.py    # ConversationState enum
│   │   └── session_manager.py  # (reserved for multi-session support)
│   ├── models/
│   │   └── schemas.py          # Pydantic models (LLMResponse)
│   ├── prompts/
│   │   └── system_prompt.py    # System prompt for the LLM
│   ├── services/
│   │   ├── greeting_loader.py  # Loads greeting text from file
│   │   ├── llm_service.py      # LLM wrapper with history management
│   │   ├── stt_service.py      # Streaming STT via Sarvam Saaras v3
│   │   └── tts_service.py      # Streaming TTS via Sarvam Bulbul v3
│   ├── websocket/
│   │   └── call_handler.py     # WebSocket route + conversation loop
│   └── data/
│       └── greeting.txt        # Initial greeting spoken to the user (Tamil)
│
├── ws_tester/                  # React/Vite browser test client
│   ├── src/
│   │   └── App.jsx             # WebSocket client with mic capture & audio playback
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── .gitignore
└── PROJECT_FLOW.md             # Detailed architecture and sequence diagrams
```

---

## Conversation Flow

```
Browser connects via WebSocket
        │
        ▼
[AGENT_SPEAKING] ──► Load greeting.txt ──► LLM confirmation ──► TTS streams audio to browser
        │
        ▼
[USER_SPEAKING]  ──► Browser mic audio forwarded to Sarvam STT
        │               │
        │         STT emits END_SPEECH signal
        │
        ▼
[PROCESSING]     ──► LLM generates structured JSON response
                      { "response": "...(Tamil)...", "end_conversation": false }
        │
        ▼
[AGENT_SPEAKING] ──► TTS streams response audio back to browser
        │
        └──► if end_conversation == true: close WebSocket
             else: back to [USER_SPEAKING]
```

---

## State Machine

Defined in `app/core/state_machine.py`:

| State | Description | Transition |
|---|---|---|
| `AGENT_SPEAKING` | TTS is streaming audio. Incoming mic audio is **dropped** to prevent echo. | TTS stream completes |
| `USER_SPEAKING` | STT is listening. Audio chunks are forwarded to Sarvam. | STT `END_SPEECH` event |
| `PROCESSING` | LLM is generating a response. | LLM response received |

---

## Prerequisites

- Python 3.11+
- Node.js 18+ (for the frontend tester)
- A [Sarvam AI](https://sarvam.ai) API key

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/Madheshvivekanandan/voice_ai.git
cd voice_ai
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and set SARVAM_API_KEY=<your_key>
```

### 3. Set up the Python backend

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Set up the frontend tester

```bash
cd ws_tester
npm install
```

---

## Running the Project

### Start the backend

```bash
# From the project root
source venv/bin/activate
cd app
python main.py
# Server starts at http://localhost:8000
# WebSocket endpoint: ws://localhost:8000/ws/audio
```

### Start the frontend tester

```bash
cd ws_tester
npm run dev
# Open http://localhost:5173 in your browser
```

Click **Connect** in the browser to start a voice session. The agent speaks a greeting first, then listens for your response.

---

## Configuration

| Variable | Location | Description |
|---|---|---|
| `SARVAM_API_KEY` | `.env` | Sarvam AI API subscription key |
| `greeting.txt` | `app/data/greeting.txt` | Tamil text spoken at the start of each call |
| `SYSTEM_PROMPT` | `app/prompts/system_prompt.py` | LLM persona and output format instructions |
| `language_code` | `app/services/stt_service.py` | STT language (default: `ta-IN`) |
| `target_language_code` | `app/services/tts_service.py` | TTS language (default: `ta-IN`) |
| `speaker` | `app/services/tts_service.py` | TTS voice (default: `pooja`) |

---

## Services

### `LLMService` (`app/services/llm_service.py`)

- Calls Sarvam Chat completions with a rolling conversation history (last 10 turns).
- Expects the LLM to return a JSON object: `{"response": "...", "end_conversation": bool}`.
- Strips markdown code fences from the response before parsing.

### `SarvamSTTService` (`app/services/stt_service.py`)

- Streams raw 16-bit PCM audio to Sarvam Saaras v3 via WebSocket.
- Wraps each PCM chunk in a WAV container before sending (required by the API).
- Yields `(event_type, data)` tuples: `transcript`, `start_speech`, `end_speech`.

### `SarvamTTSService` (`app/services/tts_service.py`)

- Streams synthesised audio from Sarvam Bulbul v3 to the browser via WebSocket.
- Paces delivery in real time (`bytes / bytes_per_second` sleep) to avoid buffer overflow.
- Terminates cleanly on the `completion` event from the Sarvam API.

### `GreetingLoader` (`app/services/greeting_loader.py`)

- Reads `app/data/greeting.txt` at runtime.
- Raises `GreetingNotFoundError` if the file is missing or empty.

---

## Frontend Tester

Located in `ws_tester/`, the React app:

1. Opens a WebSocket to `ws://localhost:8000/ws/audio`.
2. Captures microphone audio via the Web Audio API.
3. **Resamples** from the browser's native sample rate (typically 48 kHz) **down to 16 kHz** before sending.
4. Receives raw 16-bit PCM audio from the backend and plays it back using a `BufferSource`.

> **Note:** The frontend tester is intended for local development only, not production use.
