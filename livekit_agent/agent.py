"""
agent.py  -  Real-Time Voice AI Agent
Python 3.10 | LiveKit 1.1.2 | Deepgram 3.5.0 | gTTS 2.5.4
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli

from app.services.deepgram_stt import DeepgramSTT
from app.services.faq_service import FAQService
from app.services.intent_service import IntentService
from app.services.tts_service import TTSService

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
)
logger = logging.getLogger("voice-agent")

SILENCE_TIMEOUT_SEC: float = 10.0
TTS_SAMPLE_RATE: int = 24_000
TTS_CHANNELS: int = 1


async def entrypoint(ctx: JobContext) -> None:
    logger.info(f"Job accepted - connecting to room: {ctx.room.name}")

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    faq_service    = FAQService()
    intent_service = IntentService(faq_service)
    tts_service    = TTSService()
    stt            = DeepgramSTT()

    audio_source = rtc.AudioSource(
        sample_rate=TTS_SAMPLE_RATE,
        num_channels=TTS_CHANNELS,
    )
    local_track = rtc.LocalAudioTrack.create_audio_track("agent-voice", audio_source)
    publish_opts = rtc.TrackPublishOptions(
        source=rtc.TrackSource.SOURCE_MICROPHONE,
    )
    await ctx.room.local_participant.publish_track(local_track, publish_opts)
    logger.info("Agent audio track published")

    # ── Agent state ────────────────────────────────────────────────────
    state = {
        "interrupted":  False,   # True while in "hold on" mode
        "silence_task": None,    # Task for 10s silence check
        "speak_task":   None,    # Task for current TTS playback
        "ended":        False,   # True after farewell — agent goes silent
    }

    # ── Helpers ────────────────────────────────────────────────────────

    def _cancel_silence_task() -> None:
        t = state["silence_task"]
        if t and not t.done():
            t.cancel()
        state["silence_task"] = None

    def _cancel_speak_task() -> None:
        t = state["speak_task"]
        if t and not t.done():
            t.cancel()
        state["speak_task"] = None

    async def _speak(text: str) -> None:
        """Synthesise text and stream frames to the room."""
        try:
            logger.info(f"Speaking: {text[:80]}{'...' if len(text) > 80 else ''}")
            frames = await tts_service.synthesize(text)
            for frame in frames:
                if state["interrupted"]:
                    logger.debug("Speak interrupted - stopping playback")
                    break
                await audio_source.capture_frame(frame)
            logger.info("Speaking complete")
        except asyncio.CancelledError:
            logger.debug("_speak task cancelled")
        except Exception as e:
            logger.error(f"_speak error: {e}", exc_info=True)

    async def _speak_and_end(text: str) -> None:
        """Speak farewell message then go permanently silent."""
        await _speak(text)
        logger.info("Conversation ended - agent going silent")
        state["ended"] = True

    async def _silence_watchdog() -> None:
        """Wait 10s after interrupt, then ask 'Are you still there?'"""
        logger.info(f"Waiting {SILENCE_TIMEOUT_SEC}s for user to resume...")
        try:
            await asyncio.sleep(SILENCE_TIMEOUT_SEC)
            if state["interrupted"]:
                state["interrupted"] = False
                await _speak("Are you still there?")
        except asyncio.CancelledError:
            logger.debug("Silence watchdog cancelled - user resumed")

    # ── Transcript callback ────────────────────────────────────────────

    async def on_transcript(text: str) -> None:
        text = text.strip()
        if not text:
            return

        # Conversation already ended — ignore all further speech
        if state["ended"]:
            logger.debug(f"Conversation ended, ignoring: '{text}'")
            return

        logger.info(f"Transcript received: '{text}'")

        # INTERRUPT check
        if intent_service.is_interrupt(text):
            logger.info("Interrupt phrase detected - pausing agent")
            state["interrupted"] = True
            _cancel_speak_task()
            _cancel_silence_task()
            state["silence_task"] = asyncio.ensure_future(_silence_watchdog())
            return

        # User resumed after interrupt
        if state["interrupted"]:
            logger.info("User resumed - cancelling watchdog")
            state["interrupted"] = False
            _cancel_silence_task()

        # Get FAQ response
        response = intent_service.get_response(text)

        _cancel_speak_task()

        # Farewell → speak goodbye then go silent
        if intent_service.is_farewell(text):
            logger.info("Farewell detected - will end conversation after speaking")
            state["speak_task"] = asyncio.ensure_future(_speak_and_end(response))
        else:
            state["speak_task"] = asyncio.ensure_future(_speak(response))

    # ── Start STT ──────────────────────────────────────────────────────
    await stt.start(ctx.room, on_transcript)
    logger.info("Voice agent is live - listening for speech...")

    # ── Greet first participant ────────────────────────────────────────
    async def _greet_when_ready() -> None:
        try:
            participant = await asyncio.wait_for(
                ctx.wait_for_participant(), timeout=30.0
            )
            logger.info(f"Participant joined: {participant.identity}")
            await asyncio.sleep(1.0)
            await _speak(
                "Hello! Welcome to Wise support. "
                "I can help you with your transfer status, arrival times, "
                "proof of payment, and more. How can I help you today?"
            )
        except asyncio.TimeoutError:
            logger.warning("No participant joined within 30 seconds")
        except Exception as e:
            logger.error(f"Greeting error: {e}")

    asyncio.ensure_future(_greet_when_ready())

    # ── Keep alive ─────────────────────────────────────────────────────
    try:
        await asyncio.sleep(float("inf"))
    except asyncio.CancelledError:
        logger.info("Agent job cancelled - shutting down")
    finally:
        await stt.stop()
        logger.info("Agent shut down cleanly")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))