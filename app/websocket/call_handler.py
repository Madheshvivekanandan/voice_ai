import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.greeting_loader import get_greeting, GreetingNotFoundError
from services.llm_service import LLMService, LLMServiceError
from services.tts_service import SarvamTTSService, TTSServiceError

logger = logging.getLogger(__name__)

router = APIRouter()

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
        logger.info("LLM confirmation: %s", confirmation_message)
    except LLMServiceError as e:
        logger.error("LLM failed, using raw text as fallback: %s", e)
        confirmation_message = raw_text

    tts = SarvamTTSService()
    try:
        await tts.stream_synthesize(confirmation_message, websocket)
    except TTSServiceError as e:
        logger.error("Streaming TTS failed, using fallback tone: %s", e)
        fallback_audio = SarvamTTSService.generate_fallback_tone()
        await websocket.send_bytes(fallback_audio)

    logger.info("Waiting for incoming frames (idle mode)")
    try:
        while True:
            message = await websocket.receive()

            if "text" in message:
                logger.warning("Received text frame, ignoring")
                continue

            if "bytes" in message:
                logger.debug("Received %d bytes (ignored — outbound only)", len(message["bytes"]))

    except WebSocketDisconnect:
        logger.info("Client %s:%s disconnected", client.host, client.port)
