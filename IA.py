#local imports
from VtubeS_Plugin import VtubeControll
from chat_bot import ChatBot
from user_input import UserInput

import asyncio
from gtts import gTTS
import sounddevice as sd
import soundfile as sf
import os
from dotenv import load_dotenv
import threading

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'
class Nous:
    def __init__(self, vts: VtubeControll = None, ChatBot: ChatBot = None, tts_language: str = "english", detailed_logs: bool = False, print_audio_devices: bool = False, user_input: UserInput = None) -> None:
        self.detailed_logs = detailed_logs
        self.print_adio_devices = print_audio_devices
        self.tts_language = tts_language
        self.is_speaking = False
        self.chat_bot = ChatBot
        self.vts = vts
        self.user_input = user_input
        self.cable_device_id = None
        self.last_audio_duration = 0

    def initialize(self, mic_index: int = None) -> None:
        if self.print_adio_devices:
            self.debug_audio_devices()
        self.cable_device_id = self.get_cable_device_id()
        if self.cable_device_id is not None:
            print(f"{GREEN}VB Cable device set to id: {self.cable_device_id}{RESET}")
        else:
            print(f"{ORANGE}No VB cable found, lypsinc may not work.{RESET}")

        if self.user_input:
            self.user_input.setup_mic(mic_index)

        load_dotenv()
        self.chat_bot.load_chatbot_data()

    def debug_audio_devices(self):
        devices = sd.query_devices() #gets a lists of all audio devices
        print("\n=== ALL AUDIO DEVICES ===")
        for i, device in enumerate(devices):
            print(f"[{i}] {device['name']}")
            print(f"    Max input channels: {device['max_input_channels']}")
            print(f"    Max output channels: {device['max_output_channels']}")
            print(f"    Default sample rate: {device['default_samplerate']}")
            print()

    def get_cable_device_id(self):
        devices = sd.query_devices()
        #same loop logic as the past function
        #except this one checks if the name matches with cable input audio device
        for i, device in enumerate(devices):
            name = str(device['name']).lower()
            #checks the name output and sample rate to identify the audio cable
            if (device['max_output_channels'] > 0 and
                'cable input' in name and
                'vb-audio virtual cable' in name and
                device['default_samplerate'] == 44100.0):
                print(f"{GREEN}Found VB Cable Input: [{i}] {device['name']}{RESET}")
                return i
        return None

    async def tts_say(self, text: str) -> None:
        #chatgpt response or test response in console
        print(f"NOUS: {text}")
        self.is_speaking = True
            
        try:
            #generate tts with response from chatgpt or test reponse
            if self.tts_language == "english":
                gTTS(text=text, lang='en', slow=False, lang_check=False).save('Data/output.wav')
            elif self.tts_language == "spanish":
                gTTS(text=text, lang='es', slow=False, lang_check=False).save('Data/output.wav')
            else:
                print(f"{ORANGE}TTS language not supported. Either english or spanish.{RESET}")
        except Exception as e:
            print(f"{RED}Error generating TTS: {e}{RESET}")
            self.is_speaking = False
            return 
        
        if not os.path.exists('Data/output.wav'): #error if the file output is not found
            print(f"{RED}error: output.wav file not created!{RESET}")
            self.is_speaking = False
            return 

        try:
            #stores the two things sf reads return, data: raw audio data, samplerate: samplerate
            data, samplerate = sf.read('Data/output.wav')
            self.last_audio_duration = len(data) / samplerate #formula for calculating audio duration 

            if self.cable_device_id is not None:
                def play_default(): #plays to default device
                    sd.play(data, samplerate)
                    sd.wait() #waits for audio to finish
                def play_cable(): #prints to virtual cable
                    sd.play(data, samplerate, device=self.cable_device_id) #uses our function to find the deivce id and plays it to that device
                    sd.wait() #waits for audio to finish
                #calls threading
                t1 = threading.Thread(target=play_default)
                t2 = threading.Thread(target=play_cable)
                #starts threads
                t1.start()
                t2.start()
                #ends threads
                t1.join()
                t2.join()
            else: #if cable device is not found then just play it to the default device
                sd.play(data, samplerate)
                sd.wait()
        except Exception as e:
            print(f"{RED}Error playing audio: {e}{RESET}")
        finally:
            self.is_speaking =False

    async def analyze_emotion(self, text:str):
        if self.vts: #checks if there is a vts instance
            try:
                dominant_emotion = self.vts.analyze_dominant_emotion(text) #gets dominant emotion form chatgpt response
                await self.vts.trigger_hotkey(dominant_emotion) #triggers the hotkey corresponding to dominant emotion
            except Exception as e:
                print(f"{ORANGE}Emotion analysis error: {e}{RESET}")

    async def conversation_cycle(self):
        try:
            while True:
                user_input =  await self.user_input.get_user_input()
                if not user_input:
                    return ""
                response =  self.chat_bot.get_chatbot_response(user_input) #gets chatgpt response or test response

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
