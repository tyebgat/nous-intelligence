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
    def __init__(self, vts: VtubeControll = None, ChatBot: ChatBot = None, detailed_logs: bool = False, print_audio_devices: bool = False, user_input: UserInput = None, tts: TTS = None) -> None:
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

    async def analyze_emotion(self, text: str):
        if self.vts: #checks if there is a vts instance
            try:
                dominant_emotion = self.vts.analyze_dominant_emotion(text) #gets dominant emotion form chatgpt response
                await self.vts.trigger_hotkey(dominant_emotion) #triggers the hotkey corresponding to dominant emotion
            except Exception as e:
                print(f"{ORANGE}Emotion analysis error: {e}{RESET}")

    async def conversation_cycle(self):
        try:
            while True:
                user_input = await self.user_input.get_user_input()
                if not user_input:
                    return ""
                response = self.chat_bot.get_chatbot_response(user_input) #gets chatgpt response or test response

                await self.analyze_emotion(response) #analyzes emotion in response

                await self.tts_say(response) #waits for tts to finish

                if self.vts:
                    try:
                        await self.vts.trigger_hotkey("Neutral") #after tts is finish turn clear hotkeys
                    except Exception as e:
                        print(f"{ORANGE}Error resetting to Neutral: {e}{RESET}")
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
