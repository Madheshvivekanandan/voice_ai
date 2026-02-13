import base64
import logging
import os
import io
import wave

from sarvamai import AsyncSarvamAI
from sarvamai.types.speech_to_text_transcription_data import SpeechToTextTranscriptionData
from sarvamai.types.events_data import EventsData
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class STTServiceError(Exception):
    pass


class SarvamSTTService:
    """
    Streaming STT using Saaras v3 (WAV only).
    We accumulate PCM and stream as continuous WAV.
    """

    def __init__(self) -> None:
        api_key = os.getenv("SARVAM_API_KEY")
        if not api_key:
            raise RuntimeError("SARVAM_API_KEY environment variable is not set")

        self._client = AsyncSarvamAI(api_subscription_key=api_key)
        self._stt_ws = None
        self._ctx = None
        self._audio_sent = False

        # 🔥 Important: Must match model expectation
        self.sample_rate = 16000

    async def __aenter__(self):
        self._ctx = self._client.speech_to_text_streaming.connect(
            language_code="ta-IN",
            model="saaras:v3",
            input_audio_codec="audio/wav",
            vad_signals="true",
            high_vad_sensitivity="true",
        )

        self._stt_ws = await self._ctx.__aenter__()
        logger.info("STT WebSocket connected (saaras:v3)")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._ctx:
            await self._ctx.__aexit__(exc_type, exc_val, exc_tb)
            logger.info("STT WebSocket closed")

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """
        Wrap PCM chunk into WAV container with 16kHz.
        Browser MUST send 16kHz PCM.
        """

        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)        # mono
            wav_file.setsampwidth(2)        # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm_bytes)

        wav_bytes = wav_buffer.getvalue()
        encoded = base64.b64encode(wav_bytes).decode("ascii")

        await self._stt_ws.transcribe(
            audio=encoded,
            encoding="audio/wav",
            sample_rate=self.sample_rate,
        )

        self._audio_sent = True

    async def flush(self) -> None:
        if self._audio_sent:
            await self._stt_ws.flush()
            logger.info("STT flush sent")
        else:
            logger.info("Flush skipped — no audio sent")

    async def listen_transcripts(self):
        async for response in self._stt_ws:

            if (
                response.type == "data"
                and isinstance(response.data, SpeechToTextTranscriptionData)
            ):
                transcript = response.data.transcript
                if transcript:
                    yield ("transcript", transcript)

            elif (
                response.type == "events"
                and isinstance(response.data, EventsData)
            ):
                signal = response.data.signal_type

                if signal == "START_SPEECH":
                    yield ("start_speech", None)

                elif signal == "END_SPEECH":
                    yield ("end_speech", None)

            elif response.type == "error":
                logger.error("STT error: %s", response.data)
                raise STTServiceError(f"STT error: {response.data}")
