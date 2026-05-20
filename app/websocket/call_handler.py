import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.state_machine import ConversationState
from services.greeting_loader import get_greeting
from services.llm_service import LLMService
from services.tts_service import SarvamTTSService
from services.stt_service import SarvamSTTService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/audio")
async def audio_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client
    logger.info(
        "WebSocket connection opened from %s:%s",
        client.host,
        client.port,
    )

    llm = LLMService()
    tts = SarvamTTSService()
    
    # Conversation state
    state = ConversationState.AGENT_SPEAKING
    
    try:
        # 🔥 STEP 1: Play greeting (AGENT_SPEAKING)
        raw_text = get_greeting()
        confirmation_data = await llm.generate_confirmation(raw_text)
        confirmation_message = confirmation_data.get("response", str(confirmation_data))
        logger.info("Confirmation message: %s", confirmation_message)
        
        logger.info("STATE: %s - Playing greeting", state.value)
        await tts.stream_synthesize(confirmation_message, websocket)
        logger.info("Greeting completed")
        
        # 🔥 STEP 2: Transition to USER_SPEAKING
        state = ConversationState.USER_SPEAKING
        logger.info("STATE: %s - Listening to user", state.value)
        
        # Start STT session for conversation loop
        async with SarvamSTTService() as stt:
            
            # Create tasks for audio forwarding and transcript reading
            audio_forward_task = None
            transcript_read_task = None
            
            async def forward_audio_to_stt():
                """Forward audio chunks to STT only during USER_SPEAKING state"""
                nonlocal state
                
                try:
                    while True:
                        message = await websocket.receive()
                        
                        if message["type"] == "websocket.receive":
                            audio_bytes = message.get("bytes")
                            
                            if audio_bytes:
                                # 🔥 Only forward during USER_SPEAKING
                                if state == ConversationState.USER_SPEAKING:
                                    await stt.send_audio(audio_bytes)
                                else:
                                    # Drop audio during AGENT_SPEAKING or PROCESSING
                                    logger.debug(
                                        "Dropping audio chunk (%d bytes) - state: %s",
                                        len(audio_bytes),
                                        state.value,
                                    )
                        
                        elif message["type"] == "websocket.disconnect":
                            logger.info("Client disconnected")
                            break
                
                except WebSocketDisconnect:
                    logger.info("Client disconnected (exception)")
                finally:
                    try:
                        await stt.flush()
                    except Exception:
                        pass
            
            async def process_transcripts():
                """Process STT transcripts and manage conversation turns"""
                nonlocal state
                
                transcript_buffer = ""
                
                async for event_type, data in stt.listen_transcripts():
                    
                    if event_type == "start_speech":
                        logger.info("VAD: speech started")
                        transcript_buffer = ""
                    
                    elif event_type == "transcript":
                        # Accumulate partial transcripts
                        transcript_buffer = data
                        logger.info("Partial transcript: %s", data)
                    
                    elif event_type == "end_speech":
                        # 🔥 User finished speaking
                        if transcript_buffer.strip():
                            logger.info("FINAL TRANSCRIPT: %s", transcript_buffer)
                            
                            # Transition to PROCESSING
                            state = ConversationState.PROCESSING
                            logger.info("STATE: %s - Generating response", state.value)
                            
                            try:
                                # Generate LLM response (Structured JSON)
                                response_data = await llm.generate_confirmation(
                                    transcript_buffer
                                )
                                response_text = response_data.get("response", str(response_data))
                                end_call = response_data.get("end_conversation", False)

                                logger.info("LLM response: %s (end_call: %s)", response_text, end_call)
                                
                                # Transition to AGENT_SPEAKING
                                state = ConversationState.AGENT_SPEAKING
                                logger.info("STATE: %s - Agent responding", state.value)
                                
                                # Speak the response
                                await tts.stream_synthesize(response_text, websocket)
                                logger.info("Agent response completed")
                                
                                if end_call:
                                    await asyncio.sleep(0.3)
                                    logger.info("Bot decided to end the call based on structured LLM response.")
                                    await websocket.close()
                                    break
                                
                                # Transition back to USER_SPEAKING
                                state = ConversationState.USER_SPEAKING
                                logger.info("STATE: %s - Listening to user", state.value)
                                
                            except Exception as e:
                                logger.error("Failed to generate/speak response: %s", e)
                                # Recover by going back to listening
                                state = ConversationState.USER_SPEAKING
                        
                        # Reset buffer
                        transcript_buffer = ""
            
            # 🔥 Run both tasks concurrently
            await asyncio.gather(
                forward_audio_to_stt(),
                process_transcripts(),
            )

    except Exception as e:
        logger.error("Voice session failed: %s", e)

    finally:
        logger.info("WebSocket session ended")
