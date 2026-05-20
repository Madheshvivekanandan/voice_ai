from pydantic import BaseModel


class LLMResponse(BaseModel):
    """Structured response returned by the LLM service."""
    response: str
    end_conversation: bool = False
