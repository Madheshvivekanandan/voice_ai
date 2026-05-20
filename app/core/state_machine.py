from enum import Enum


class ConversationState(Enum):
    """Turn-based conversation states for the voice AI session."""
    AGENT_SPEAKING = "agent_speaking"   # TTS active — incoming audio is dropped
    USER_SPEAKING = "user_speaking"     # STT active — audio forwarded to Sarvam
    PROCESSING = "processing"           # LLM is generating a response
