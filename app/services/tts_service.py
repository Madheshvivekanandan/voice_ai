import base64
import logging
import math
import os
import struct
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

        # 🔥 IMPORTANT — match what you actually configure
        self.speech_sample_rate = 16000

        logger.info(
            "TTS initialized — sample_rate=%s codec=linear16",
            self.speech_sample_rate,
        )

    async def stream_synthesize(self, text: str, websocket) -> None:
        logger.info(
            "Streaming TTS request — text length: %d chars", len(text)
        )

        try:
            # 🔥 Enable completion event for clean stream termination
            async with self._client.text_to_speech_streaming.connect(
                model="bulbul:v3",
                send_completion_event=True,
            ) as ws:

                await ws.configure(
                    target_language_code="ta-IN",
                    speaker="pooja",
                    speech_sample_rate=16000,
                    output_audio_codec="linear16",
                )

                await ws.convert(text)
                await ws.flush()

                logger.info("Text sent to TTS stream and flushed")

                # 🔥 Listen for audio chunks and completion event
                async for message in ws:

                    if isinstance(message, AudioOutput):
                        audio_chunk = base64.b64decode(message.data.audio)
                        await websocket.send_bytes(audio_chunk)

                        # Real-time pacing
                        bytes_per_second = 16000 * 2  # 16-bit PCM
                        duration = len(audio_chunk) / bytes_per_second
                        await asyncio.sleep(duration)

                    else:
                        # 🔥 Completion event received - exit immediately
                        logger.info("TTS completion event received: %s", message)
                        break

                logger.info("TTS stream completed cleanly")

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

        class DummyWS:
            async def send_bytes(self, data):
                print(f"Received chunk: {len(data)} bytes")

        await tts.stream_synthesize(
            "Vanakkam! How are you today?",
            DummyWS(),
        )

    asyncio.run(_test())
