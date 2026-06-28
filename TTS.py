from gtts import gTTS
import sounddevice as sd
import soundfile as sf
import os
import threading

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

class TTS:
    def __init__(self, tts_language: str = "english", print_audio_devices: bool = False):
        self.tts_language = tts_language
        self.print_audio_devices = print_audio_devices
        self.is_speaking = False
        self.last_audio_duration = 0
        self.cable_device_id = None

    def initialize(self):
        if self.print_audio_devices:
            self.debug_audio_devices()
        self.cable_device_id = self.get_cable_device_id()
        if self.cable_device_id is not None:
            print(f"{GREEN}VB Cable device set to id: {self.cable_device_id}{RESET}")
        else:
            print(f"{ORANGE}No VB cable found, lypsinc may not work.{RESET}")

    def debug_audio_devices(self):
        devices = sd.query_devices()
        print("\n=== ALL AUDIO DEVICES ===")
        for i, device in enumerate(devices):
            print(f"[{i}] {device['name']}")
            print(f"    Max input channels: {device['max_input_channels']}")
            print(f"    Max output channels: {device['max_output_channels']}")
            print(f"    Default sample rate: {device['default_samplerate']}")
            print()

    def get_cable_device_id(self):
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            name = str(device['name']).lower()
            if (device['max_output_channels'] > 0 and
                'cable input' in name and
                'vb-audio virtual cable' in name and
                device['default_samplerate'] == 44100.0):
                print(f"{GREEN}Found VB Cable Input: [{i}] {device['name']}{RESET}")
                return i
        return None

    async def tts_say(self, text: str) -> None:
        print(f"NOUS: {text}")
        self.is_speaking = True

        try:
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

        if not os.path.exists('Data/output.wav'):
            print(f"{RED}error: output.wav file not created!{RESET}")
            self.is_speaking = False
            return

        try:
            data, samplerate = sf.read('Data/output.wav')
            self.last_audio_duration = len(data) / samplerate

            if self.cable_device_id is not None:
                def play_default():
                    sd.play(data, samplerate)
                    sd.wait()
                def play_cable():
                    sd.play(data, samplerate, device=self.cable_device_id)
                    sd.wait()
                t1 = threading.Thread(target=play_default)
                t2 = threading.Thread(target=play_cable)
                t1.start()
                t2.start()
                t1.join()
                t2.join()
            else:
                sd.play(data, samplerate)
                sd.wait()
        except Exception as e:
            print(f"{RED}Error playing audio: {e}{RESET}")
        finally:
            self.is_speaking = False
