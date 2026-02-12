import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.greeting_loader import get_greeting, GreetingNotFoundError
from services.llm_service import LLMService, LLMServiceError
from services.tts_service import SarvamTTSService, TTSServiceError

logger = logging.getLogger(__name__)

router = APIRouter()

CHUNK_SIZE: int = 1024
CHUNK_INTERVAL: float = 0.032


async def _stream_audio(websocket: WebSocket, audio: bytes) -> None:
    total = len(audio)
    sent = 0
    logger.info("Audio streaming started — %d bytes total", total)

    while sent < total:
        chunk = audio[sent : sent + CHUNK_SIZE]
        await websocket.send_bytes(chunk)
        sent += len(chunk)
        await asyncio.sleep(CHUNK_INTERVAL)

    logger.info("Audio streaming finished — %d bytes sent", sent)


@router.websocket("/ws/audio")
async def audio_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client
    logger.info("WebSocket connection opened from %s:%s", client.host, client.port)

    try:
        raw_text = get_greeting()
        logger.info("Order data loaded: %s", raw_text[:60])
    except (GreetingNotFoundError, ValueError) as e:
        logger.error("Failed to load order data: %s", e)
        raw_text = "Hello, we have an order for you."

    llm = LLMService()
    try:
        confirmation_message = await llm.generate_confirmation(raw_text)
        logger.info("LLM confirmation: %s", confirmation_message[:80])
    except LLMServiceError as e:
        logger.error("LLM failed, using raw text as fallback: %s", e)
        confirmation_message = raw_text

    tts = SarvamTTSService()
    try:
        audio = await tts.synthesize(confirmation_message)
    except TTSServiceError as e:
        logger.error("TTS synthesis failed, using fallback tone: %s", e)
        audio = SarvamTTSService.generate_fallback_tone()

    try:
        await _stream_audio(websocket, audio)

        logger.info("Waiting for incoming frames (idle mode)")
        while True:
            message = await websocket.receive()

            if "text" in message:
                logger.warning("Received text frame, ignoring")
                continue

            if "bytes" in message:
                logger.debug("Received %d bytes (ignored — outbound only)", len(message["bytes"]))

    except WebSocketDisconnect:
        logger.info("Client %s:%s disconnected", client.host, client.port)
    except Exception as e:
        logger.error("Unexpected error on connection %s:%s — %s", client.host, client.port, e)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
