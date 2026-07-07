from gtts import gTTS
from openai import OpenAI
import sounddevice as sd
import soundfile as sf
import os
from os import getenv
import threading
from paths import BASE_PATH

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

class TTS:
    def __init__(self, tts_language: str = "en", chatbot_name: str = "Nous",tts_service: str = "gtts", openai_tts_model: str = None, openai_tts_voice: str = "ash"):
        self.chatbot_name = chatbot_name
        self.openai_tts_voice = openai_tts_voice
        self.openai_tts_model = openai_tts_model
        self.tts_service = tts_service
        self.tts_language = tts_language
        self.cable_device_id = None
        
    def load_openai_tts_personality(self) -> list:
        with open(os.path.join(BASE_PATH, "openai-TTS-instructions.txt"), "r") as personality:
            text = personality.read()
            return text

    def initialize(self):
        self.tts_instructions = self.load_openai_tts_personality()
        self.cable_device_id = self.get_cable_device_id()
        if self.cable_device_id is not None:
            print(f"{GREEN}VB Cable device set to id: {self.cable_device_id}{RESET}")
        else:
            print(f"{ORANGE}No VB cable found, lypsinc may not work.{RESET}")

    def get_cable_device_id(self):
        devices = sd.query_devices()
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
        #response from the chatbot
        print(f"{self.chatbot_name}: {text}")
        self.is_speaking = True

        output_path = os.path.join(BASE_PATH, 'Data', 'output.wav')

        try:
            match self.tts_service:
                case "gtts":
                    gTTS(text=text, lang=self.tts_language, slow=False, lang_check=False).save(output_path)

                case "openai":
                    client = OpenAI(api_key=getenv("OPENAI_API_KEY"))
                    response = client.audio.speech.create(
                        model= self.openai_tts_model,
                        voice= self.openai_tts_voice,
                        input= text,
                        instructions= self.tts_instructions,
                        response_format="wav"
                    )
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                
                case "default":
                    print(f"{YELLOW} TTS service not supported falling back to gtts... {RESET}")
                    gTTS(text=text, lang=self.tts_language, slow=False, lang_check=False).save(output_path)

        except Exception as e:
            print(f"{RED}Error generating TTS: {e}{RESET}")
            self.is_speaking = False
            return

        if not os.path.exists(output_path): #error if the file output is not found
            print(f"{RED}error: output.wav file not created!{RESET}")
            self.is_speaking = False
            return

        try:
            #stores the two things sf reads return, data: raw audio data, samplerate: samplerate
            data, samplerate = sf.read(output_path)

            if self.cable_device_id is not None:

                def play_default(): #plays to default device
                    sd.play(data, samplerate)
                    sd.wait() 

                def play_cable(): #plays to virtual cable
                    sd.play(data, samplerate, device=self.cable_device_id)
                    sd.wait()

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
            self.is_speaking = False
