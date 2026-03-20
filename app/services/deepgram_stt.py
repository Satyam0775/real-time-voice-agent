"""
deepgram_stt.py
Deepgram SDK: 3.5.0  |  LiveKit SDK: 1.1.2

ROOT CAUSE FIX:
- Deepgram asynclive REQUIRES all handlers to be `async def` (it awaits them internally)
- Deepgram 3.5.0 fires Transcript event TWICE:
    1st: result = LiveResultResponse object  <- parse transcript from this
    2nd: result = plain string               <- guard against this with isinstance check
- Changing handler to regular def() caused "a coroutine was expected, got None" crash
"""

import asyncio
import logging
import os
from typing import Awaitable, Callable, Optional

from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from livekit import rtc

logger = logging.getLogger(__name__)

STT_SAMPLE_RATE = 16000
STT_CHANNELS = 1


class DeepgramSTT:

    def __init__(self):
        api_key = os.getenv("DEEPGRAM_API_KEY", "")
        if not api_key:
            raise EnvironmentError("DEEPGRAM_API_KEY is not set")
        self._client = DeepgramClient(api_key)
        self._connection = None
        self._on_transcript: Optional[Callable[[str], Awaitable[None]]] = None
        self._audio_tasks: list[asyncio.Task] = []

    async def start(
        self,
        room: rtc.Room,
        on_transcript: Callable[[str], Awaitable[None]],
    ) -> None:
        self._on_transcript = on_transcript

        self._connection = self._client.listen.asynclive.v("1")

        # IMPORTANT: All handlers MUST be async def
        # Deepgram asynclive internally awaits every registered handler
        self._connection.on(LiveTranscriptionEvents.Transcript, self._handle_transcript)
        self._connection.on(LiveTranscriptionEvents.Error, self._handle_error)
        self._connection.on(LiveTranscriptionEvents.Close, self._handle_close)

        options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            channels=STT_CHANNELS,
            sample_rate=STT_SAMPLE_RATE,
            interim_results=False,
            endpointing=300,
        )

        started = await self._connection.start(options)
        if not started:
            raise RuntimeError("Failed to open Deepgram live connection")

        logger.info("Deepgram live connection opened")

        for participant in room.remote_participants.values():
            for pub in participant.track_publications.values():
                if (
                    pub.track is not None
                    and pub.track.kind == rtc.TrackKind.KIND_AUDIO
                ):
                    self._launch_audio_task(pub.track)

        @room.on("track_subscribed")
        def _on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Audio track subscribed: {participant.identity}")
                self._launch_audio_task(track)

    async def stop(self) -> None:
        for task in self._audio_tasks:
            task.cancel()
        self._audio_tasks.clear()
        if self._connection is not None:
            await self._connection.finish()
            self._connection = None
            logger.info("Deepgram connection closed")

    def _launch_audio_task(self, track: rtc.RemoteAudioTrack) -> None:
        task = asyncio.ensure_future(self._stream_track(track))
        self._audio_tasks.append(task)

    async def _stream_track(self, track: rtc.RemoteAudioTrack) -> None:
        logger.info(f"Streaming audio track {track.sid} -> Deepgram")
        try:
            audio_stream = rtc.AudioStream(
                track,
                sample_rate=STT_SAMPLE_RATE,
                num_channels=STT_CHANNELS,
            )
            async for event in audio_stream:
                if self._connection is None:
                    break
                await self._connection.send(bytes(event.frame.data))
        except asyncio.CancelledError:
            logger.debug("Audio stream task cancelled")
        except Exception as e:
            logger.error(f"Error streaming audio track: {e}")

    # MUST be async def — Deepgram asynclive awaits this internally
    async def _handle_transcript(self, _connection, result, **kwargs) -> None:
        # Deepgram 3.5.0 fires this event TWICE per utterance:
        #   Call 1: result is a LiveResultResponse object  <- we want this
        #   Call 2: result is a plain str                  <- skip silently
        if isinstance(result, str):
            return

        try:
            transcript: str = result.channel.alternatives[0].transcript.strip()
        except (AttributeError, IndexError):
            return

        if not transcript or self._on_transcript is None:
            return

        logger.debug(f"Deepgram transcript: {transcript!r}")
        await self._on_transcript(transcript)

    # MUST be async def
    async def _handle_error(self, _connection, error, **kwargs) -> None:
        logger.error(f"Deepgram error: {error}")

    # MUST be async def
    async def _handle_close(self, _connection, close, **kwargs) -> None:
        logger.warning(f"Deepgram connection closed: {close}")