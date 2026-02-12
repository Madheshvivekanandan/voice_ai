import base64
import logging
import math
import os
import struct
from typing import Optional
import asyncio
from sarvamai import AsyncSarvamAI, AudioOutput
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class TTSServiceError(Exception):
    pass


class SarvamTTSService:
    def __init__(self) -> None:
        api_key = os.getenv("SARVAM_API_KEY")
        if not api_key:
            raise RuntimeError("SARVAM_API_KEY environment variable is not set")

        self._client = AsyncSarvamAI(api_subscription_key=api_key)

        # Load browser config safely
        self.speech_sample_rate = int(
            os.getenv("browser_speech_sample_rate", 16000)
        )
        self.output_audio_codec = os.getenv(
            "browser_output_audio_codec", "pcm"
        )

        logger.info(
            "TTS initialized — sample_rate=%s codec=%s",
            self.speech_sample_rate,
            self.output_audio_codec,
        )

    async def stream_synthesize(self, text: str, websocket) -> None:
        logger.info(
            "Streaming TTS request — text length: %d chars", len(text)
        )

        try:
            async with self._client.text_to_speech_streaming.connect(
                model="bulbul:v3"
            ) as ws:

                await ws.configure(
                    target_language_code="ta-IN",
                    speaker="pooja",
                    speech_sample_rate=16000,
                    output_audio_codec="linear16"
                )

                await ws.convert(text)
                await ws.flush()

                logger.info("Text sent to TTS stream and flushed")

                async for message in ws:

                    if isinstance(message, AudioOutput):
                        audio_chunk = base64.b64decode(message.data.audio)
                        # logger.info("Streaming chunk — %d bytes", len(audio_chunk))
                        await websocket.send_bytes(audio_chunk)
                          # 🔥 Real-time pacing
                        bytes_per_second = self.speech_sample_rate * 2  # 16-bit PCM
                        duration = len(audio_chunk) / bytes_per_second

                        await asyncio.sleep(duration)
                    else:
                        logger.error("Full streaming message: %s", message)


        except Exception as e:
            logger.error("Streaming TTS failed: %s", e)
            raise TTSServiceError(str(e))

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
            value = int(
                amplitude
                * math.sin(
                    2.0 * math.pi * frequency * i / sample_rate
                )
            )
            samples.append(struct.pack("<h", value))

        tone = b"".join(samples)
        logger.info("Generated fallback tone — %d bytes", len(tone))
        return tone


# -------------------------
# Optional standalone test
# -------------------------
if __name__ == "__main__":
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    async def _test():
        tts = SarvamTTSService()

        # Fake websocket for testing
        class DummyWS:
            async def send_bytes(self, data):
                print(f"Received chunk: {len(data)} bytes")

        await tts.stream_synthesize(
            "Vanakkam! How are you today?",
            DummyWS(),
        )

    asyncio.run(_test())
