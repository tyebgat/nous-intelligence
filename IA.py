#local imports
from VtubeS_Plugin import VtubeControll
from chat_bot import ChatBot
from user_input import UserInput
from TTS import TTS

import asyncio
import sounddevice as sd
from dotenv import load_dotenv
from loguru import logger

class Nous:
    def __init__(
        self, 
        vts: VtubeControll = None, 
        ChatBot: ChatBot = None, 
        print_audio_devices: bool = False, 
        user_input: UserInput = None,
        tts: TTS = None) -> None:
        
        self.print_audio_devices = print_audio_devices
        self.chat_bot = ChatBot
        self.vts = vts
        self.user_input = user_input
        self.tts = tts

    def debug_audio_devices(self):
        devices = sd.query_devices()
        logger.info("=== ALL AUDIO DEVICES ===")
        for i, device in enumerate(devices):
            logger.info(f"[{i}] {device['name']}")
            logger.info(f"    Max input channels: {device['max_input_channels']}")
            logger.info(f"    Max output channels: {device['max_output_channels']}")
            logger.info(f"    Default sample rate: {device['default_samplerate']}")

    def initialize(self, mic_index: int = None) -> None:
        if self.print_audio_devices:
            self.debug_audio_devices()
        self.tts.initialize()

        if self.user_input:
            self.user_input.setup_mic(mic_index)

        load_dotenv()
        self.chat_bot.initialize()

    async def tts_say(self, text: str) -> None:
        await self.tts.tts_say(text)

    async def analyze_emotion(self, text: str, detected_emotion: str | None = None):
        if self.vts:
            try:
                # trust the chatbot's structured label when present, otherwise
                # fall back to the keyword analyzer
                dominant_emotion = detected_emotion or self.vts.analyze_dominant_emotion(text)
                await self.vts.trigger_hotkey(dominant_emotion)
            except Exception as e:
                logger.warning(f"Emotion analysis error: {e}")

    def _vts_trigger_callback(self, emotion_name: str):
        """Sync callback for TTS playback hooks; schedules the hotkey trigger."""
        def _trigger():
            if not self.vts:
                return
            try:
                asyncio.get_running_loop().create_task(self.vts.trigger_hotkey(emotion_name))
            except RuntimeError:
                pass
        return _trigger

    async def conversation_cycle(self):
        try:
            while True:
                user_input = await self.user_input.get_user_input()
                if not user_input:
                    return ""
                response, emotion = self.chat_bot.get_chatbot_response(user_input)

                # resolve which emotion fits, but only emote while speaking
                pending_emotion = emotion or (
                    self.vts.analyze_dominant_emotion(response) if self.vts else None
                )

                if self.tts and self.vts and pending_emotion:
                    self.tts.on_playback_start = self._vts_trigger_callback(pending_emotion)
                    self.tts.on_playback_end = self._vts_trigger_callback("Neutral")

                try:
                    await self.tts_say(response)
                finally:
                    if self.tts:
                        self.tts.on_playback_start = None
                        self.tts.on_playback_end = None
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            raise

def main():
    from TTS import TTS
    user_input = UserInput(user_input_service="console", app_language="english")
    tts = TTS(tts_language="en")
    ai = Nous(tts=tts, user_input=user_input)
    ai.initialize()
    try:
        while True:
            asyncio.run(ai.conversation_cycle())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        ai.user_input.cleanup()

if __name__ == "__main__":
    main()
