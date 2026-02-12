import asyncio
import base64
import logging
import math
import os
import struct

from sarvamai import SarvamAI

logger = logging.getLogger(__name__)


class TTSServiceError(Exception):
    """Raised when TTS synthesis fails."""


class SarvamTTSService:
    def __init__(self) -> None:
        api_key = os.getenv("SARVAM_API_KEY")
        if not api_key:
            raise RuntimeError("SARVAM_API_KEY environment variable is not set")

        self._client = SarvamAI(api_subscription_key=api_key)

    def _call_tts(self, text: str):
        return self._client.text_to_speech.convert(
            text=text,
            target_language_code="ta-IN",
            model="bulbul:v3",
            speaker="priya",
            speech_sample_rate=16000,
        )

    async def synthesize(self, text: str) -> bytes:
        logger.info("TTS request sent — text length: %d chars", len(text))

        try:
            response = await asyncio.to_thread(self._call_tts, text)
        except Exception as e:
            logger.error("TTS synthesis failed: %s", e)
            raise TTSServiceError(f"TTS synthesis failed: {e}") from e

        if not response.audios or not response.audios[0]:
            logger.error("TTS response contained no audio data")
            raise TTSServiceError("Empty audio in TTS response")

        audio_bytes = base64.b64decode(response.audios[0])
        logger.info("TTS audio received — %d bytes (PCM 16-bit 16kHz mono)", len(audio_bytes))
        return audio_bytes

    @staticmethod
    def generate_fallback_tone(
        frequency: float = 440.0,
        duration: float = 0.5,
        sample_rate: int = 16000,
        amplitude: int = 3000,
    ) -> bytes:
        num_samples = int(sample_rate * duration)
        samples: list[bytes] = []
        for i in range(num_samples):
            value = int(amplitude * math.sin(2.0 * math.pi * frequency * i / sample_rate))
            samples.append(struct.pack("<h", value))

        tone = b"".join(samples)
        logger.info("Generated fallback tone — %d bytes", len(tone))
        return tone


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    async def _test() -> None:
        tts = SarvamTTSService()
        audio = await tts.synthesize("Vanakkam! How are you?")
        print(f"Audio size: {len(audio)} bytes")

    asyncio.run(_test())
