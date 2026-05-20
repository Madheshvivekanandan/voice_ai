import asyncio
import logging
import os
import json
import re
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
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _call_llm(self, raw_text: str) -> str:
        messages = self.history + [{"role": "user", "content": raw_text}]
        response = self._client.chat.completions(
            messages=messages,
            temperature=0.2,
            max_tokens=1000,
        )
        content = response.choices[0].message.content
        return content

    async def generate_confirmation(self, raw_text: str) -> dict:
        logger.info("LLM request sent — input length: %d chars", len(raw_text))

        try:
            result_str = await asyncio.to_thread(self._call_llm, raw_text)
            
            clean_result = re.sub(r'```json\n|\n```|```', '', result_str.strip())
            try:
                result_json = json.loads(clean_result)
            except json.JSONDecodeError:
                logger.warning("Failed to decode JSON from LLM response. Using fallback.")
                result_json = {"response": clean_result, "end_conversation": False}

            # Update history after successful generation
            self.history.append({"role": "user", "content": raw_text})
            # Storing the raw completion so context structure is predictable for next generation
            self.history.append({"role": "assistant", "content": clean_result})
            
            # Keep history manageable (last 10 turns)
            if len(self.history) > 21:  # 1 system + 10 user/assistant pairs
                self.history = [self.history[0]] + self.history[-20:]

        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            raise LLMServiceError(f"LLM generation failed: {e}") from e

        if not result_str or not result_str.strip():
            logger.error("LLM returned empty response")
            raise LLMServiceError("LLM returned empty response")

        logger.info("LLM output parsed successfully")
        return result_json


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    async def _test() -> None:
        llm = LLMService()
        sample_input = "Can you confirm the order for 2 Biryanis?"
        message = await llm.generate_confirmation(sample_input)
        print(f"Generated message:\n{message}")

    asyncio.run(_test())
