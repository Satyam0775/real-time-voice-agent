"""
tts_service.py
Converts response text to audio using gTTS, then chunks it into
livekit AudioFrame objects ready for capture_frame().
"""

import asyncio
import io
import logging
from typing import List

import numpy as np
from gtts import gTTS
from pydub import AudioSegment
from livekit import rtc

logger = logging.getLogger(__name__)

# Audio output parameters (must match AudioSource config in agent.py)
SAMPLE_RATE = 24000
NUM_CHANNELS = 1
SAMPLE_WIDTH = 2          # 16-bit PCM → 2 bytes per sample
FRAME_DURATION_MS = 20    # 20 ms frames — standard for real-time audio


class TTSService:
    """
    Synthesises speech from text using gTTS and returns a list of
    livekit rtc.AudioFrame objects suitable for capture_frame().
    """

    async def synthesize(self, text: str) -> List[rtc.AudioFrame]:
        """
        Run gTTS in a thread executor (blocking I/O) and return frames.
        """
        loop = asyncio.get_event_loop()
        raw_pcm = await loop.run_in_executor(None, self._text_to_pcm, text)
        return self._pcm_to_frames(raw_pcm)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _text_to_pcm(self, text: str) -> bytes:
        """
        Generate MP3 with gTTS, then transcode to 16-bit PCM at SAMPLE_RATE.
        This runs in a thread (blocking).
        """
        logger.debug(f"TTS synthesizing: {text[:60]}...")

        # Generate MP3 into an in-memory buffer
        mp3_buf = io.BytesIO()
        tts = gTTS(text=text, lang="en", slow=False)
        tts.write_to_fp(mp3_buf)
        mp3_buf.seek(0)

        # Decode and normalise with pydub
        audio: AudioSegment = AudioSegment.from_mp3(mp3_buf)
        audio = audio.set_frame_rate(SAMPLE_RATE)
        audio = audio.set_channels(NUM_CHANNELS)
        audio = audio.set_sample_width(SAMPLE_WIDTH)

        logger.debug(
            f"TTS produced {len(audio.raw_data)} PCM bytes "
            f"({audio.duration_seconds:.2f}s)"
        )
        return audio.raw_data

    def _pcm_to_frames(self, raw_pcm: bytes) -> List[rtc.AudioFrame]:
        """
        Split raw 16-bit PCM into fixed-duration livekit AudioFrames.
        """
        samples_per_frame = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)
        bytes_per_frame = samples_per_frame * NUM_CHANNELS * SAMPLE_WIDTH

        frames: List[rtc.AudioFrame] = []
        for offset in range(0, len(raw_pcm), bytes_per_frame):
            chunk = raw_pcm[offset : offset + bytes_per_frame]

            # Pad the last (possibly short) frame with silence
            if len(chunk) < bytes_per_frame:
                chunk = chunk + b"\x00" * (bytes_per_frame - len(chunk))

            arr = np.frombuffer(chunk, dtype=np.int16)

            frame = rtc.AudioFrame(
                data=arr.tobytes(),
                sample_rate=SAMPLE_RATE,
                num_channels=NUM_CHANNELS,
                samples_per_channel=samples_per_frame,
            )
            frames.append(frame)

        logger.debug(f"TTS produced {len(frames)} audio frames")
        return frames
