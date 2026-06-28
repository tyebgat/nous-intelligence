#local imports
from VtubeS_Plugin import VtubeControll
from chat_bot import ChatBot
from user_input import UserInput
from TTS import TTS

import asyncio
from dotenv import load_dotenv

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'
class Nous:
    def __init__(self, vts: VtubeControll = None, ChatBot: ChatBot = None, tts_language: str = "english", detailed_logs: bool = False, print_audio_devices: bool = False, user_input: UserInput = None, tts: TTS = None) -> None:
        self.detailed_logs = detailed_logs
        self.tts_language = tts_language
        self.chat_bot = ChatBot
        self.vts = vts
        self.user_input = user_input

        if tts is not None:
            self.tts = tts
        else:
            self.tts = TTS(tts_language=tts_language, print_audio_devices=print_audio_devices)

    @property
    def is_speaking(self):
        return self.tts.is_speaking

    @is_speaking.setter
    def is_speaking(self, value):
        self.tts.is_speaking = value

    @property
    def last_audio_duration(self):
        return self.tts.last_audio_duration

    @last_audio_duration.setter
    def last_audio_duration(self, value):
        self.tts.last_audio_duration = value

    @property
    def cable_device_id(self):
        return self.tts.cable_device_id

    @cable_device_id.setter
    def cable_device_id(self, value):
        self.tts.cable_device_id = value

    def initialize(self, mic_index: int = None) -> None:
        self.tts.initialize()

        if self.user_input:
            self.user_input.setup_mic(mic_index)

        load_dotenv()
        self.chat_bot.load_chatbot_data()

    async def tts_say(self, text: str) -> None:
        await self.tts.tts_say(text)

    async def analyze_emotion(self, text:str):
        if self.vts:
            try:
                dominant_emotion = self.vts.analyze_dominant_emotion(text)
                await self.vts.trigger_hotkey(dominant_emotion)
            except Exception as e:
                print(f"{ORANGE}Emotion analysis error: {e}{RESET}")

    async def conversation_cycle(self):
        try:
            while True:
                user_input =  await self.user_input.get_user_input()
                if not user_input:
                    return ""
                response =  self.chat_bot.get_chatbot_response(user_input)

                await self.analyze_emotion(response)

                await self.tts_say(response)

                if self.vts:
                    try:
                        await self.vts.trigger_hotkey("Neutral")
                    except Exception as e:
                        print(f"{ORANGE}Error resetting to Neutral: {e}{RESET}")
        except KeyboardInterrupt:
            print(f"{ORANGE}Shutting down...{RESET}")
            raise

def main():
    user_input = UserInput("console", False, "english")
    ai = Nous(tts_language="english", user_input=user_input)
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
