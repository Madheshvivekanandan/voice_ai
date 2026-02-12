import asyncio
import logging
import os
from prompts.system_prompt import SYSTEM_PROMPT
from sarvamai import SarvamAI

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Raised when LLM generation fails."""


class LLMService:
    def __init__(self) -> None:
        api_key = os.getenv("SARVAM_API_KEY")
        if not api_key:
            raise RuntimeError("SARVAM_API_KEY environment variable is not set")

        self._client = SarvamAI(api_subscription_key=api_key)

    def _call_llm(self, raw_text: str) -> str:
        response = self._client.chat.completions(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            temperature=0.2,
            max_tokens=1000,
        )
        return response.choices[0].message.content

    async def generate_confirmation(self, raw_text: str) -> str:
        logger.info("LLM request sent — input length: %d chars", len(raw_text))

        try:
            result = await asyncio.to_thread(self._call_llm, raw_text)
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            raise LLMServiceError(f"LLM generation failed: {e}") from e

        if not result or not result.strip():
            logger.error("LLM returned empty response")
            raise LLMServiceError("LLM returned empty response")

        logger.info("LLM response received — output length: %d chars", len(result))
        return result.strip()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    async def _test() -> None:
        llm = LLMService()
        message = await llm.generate_confirmation(sample)
        print(f"Generated message:\n{message}")

    asyncio.run(_test())
