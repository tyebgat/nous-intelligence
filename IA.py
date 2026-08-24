#local imports
from VtubeS_Plugin import VtubeControll
from chat_bot import ChatBot
from user_input import UserInput
from TTS import TTS

import asyncio
import sounddevice as sd
from dotenv import load_dotenv

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

class Nous:
    def __init__(
        self, 
        vts: VtubeControll = None, 
        ChatBot: ChatBot = None, 
        detailed_logs: bool = False, 
        print_audio_devices: bool = False, 
        user_input: UserInput = None,
        tts: TTS = None) -> None:
        
        self.detailed_logs = detailed_logs
        self.print_audio_devices = print_audio_devices
        self.chat_bot = ChatBot
        self.vts = vts
        self.user_input = user_input
        self.tts = tts

    def debug_audio_devices(self):
        devices = sd.query_devices()
        print("\n=== ALL AUDIO DEVICES ===")
        for i, device in enumerate(devices):
            print(f"[{i}] {device['name']}")
            print(f"    Max input channels: {device['max_input_channels']}")
            print(f"    Max output channels: {device['max_output_channels']}")
            print(f"    Default sample rate: {device['default_samplerate']}")
            print()

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
                print(f"{ORANGE}Emotion analysis error: {e}{RESET}")

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
            print(f"{ORANGE}Shutting down...{RESET}")
            raise

def main():
    from TTS import TTS
    user_input = UserInput("console", False, "english")
    tts = TTS(tts_language="en")
    ai = Nous(tts=tts, user_input=user_input)
    ai.initialize()
    try:
        while True:
            asyncio.run(ai.conversation_cycle())
    except KeyboardInterrupt:
        print(f"{ORANGE}Shutting down...{RESET}")
    finally:
        ai.user_input.cleanup()

if __name__ == "__main__":
    main()
