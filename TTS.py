import numpy as np
from gtts import gTTS
from openai import OpenAI
import sounddevice as sd
import soundfile as sf
import scipy.io.wavfile
import os
from os import getenv
import threading
from paths import BASE_PATH

try:
    from pocket_tts import TTSModel
except Exception:
    TTSModel = None

try:
    from omnivoice import OmniVoice
except Exception:
    OmniVoice = None

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

class TTS:
    def __init__(self, tts_language: str = "en", chatbot_name: str = "Nous", tts_service: str = "gtts", openai_tts_model: str = None, openai_tts_voice: str = "ash", tts_voice: str = "ash", tts_speed: float = 1.0, voice_cloning: bool = False, voice_design: bool = False, omnivoice_device: str = "cuda", detailed_logs: bool = True):
        self.chatbot_name = chatbot_name
        self.openai_tts_voice = openai_tts_voice
        self.openai_tts_model = openai_tts_model
        self.tts_service = tts_service
        self.tts_language = tts_language
        self.tts_voice = tts_voice
        self.tts_speed = tts_speed
        self.voice_cloning = voice_cloning
        self.voice_design = voice_design
        self.omnivoice_device = omnivoice_device
        self.detailed_logs = detailed_logs
        self.cable_device_id = None
        
    def load_openai_tts_personality(self) -> list:
        with open(os.path.join(BASE_PATH, "openai-TTS-instructions.txt"), "r") as personality:
            text = personality.read()
            return text

    def initialize(self):
        self.tts_instructions = self.load_openai_tts_personality()
        self.cable_device_id = self.get_cable_device_id()

        #try to get virtual audio cable
        if self.cable_device_id is not None:
            print(f"{GREEN}VB Cable device set to id: {self.cable_device_id}{RESET}")
        else:
            print(f"{ORANGE}No VB cable found, lypsinc may not work.{RESET}")
        
        #initialize pocket tts
        self.pockettts_model = None
        self.pockettts_voice_state = None
        if self.tts_service == "pockettts":
            if TTSModel is None:
                print(f"{RED}pocket-tts is not installed. Install with: pip install pocket-tts scipy{RESET}")
            else:
                try:
                    hf_token = getenv("HF_TOKEN")
                    if hf_token:
                        from huggingface_hub import login
                        login(token=hf_token)

                    self.pockettts_model = TTSModel.load_model()

                    ref_path = os.path.abspath(os.path.join(BASE_PATH, "Data", "reference.wav"))
                    if self.voice_cloning and os.path.exists(ref_path):
                        try:
                            self.pockettts_voice_state = self.pockettts_model.get_state_for_audio_prompt(ref_path)
                            print(f"{GREEN}Pocket TTS initialized with voice cloning from: {ref_path}{RESET}")
                        except Exception as e:
                            print(f"{YELLOW}Voice cloning failed: {e}{RESET}")
                            print(f"{YELLOW}Falling back to built-in voice.{RESET}")
                            voice = self.tts_voice if self.tts_voice else "alba"
                            self.pockettts_voice_state = self.pockettts_model.get_state_for_audio_prompt(voice)
                            print(f"{GREEN}Pocket TTS initialized (voice={voice}){RESET}")
                    else:
                        if self.voice_cloning and not os.path.exists(ref_path):
                            print(f"{YELLOW}reference.wav not found at {ref_path}. Add a reference.wav to the Data folder for voice cloning.{RESET}")
                        voice = self.tts_voice if self.tts_voice else "alba"
                        self.pockettts_voice_state = self.pockettts_model.get_state_for_audio_prompt(voice)
                        print(f"{GREEN}Pocket TTS initialized (voice={voice}){RESET}")

                except Exception as e:
                    print(f"{RED}Failed to initialize Pocket TTS: {e}{RESET}")

        #initialize omnivoice tts
        self.omnivoice_model = None
        self.omnivoice_ref_audio = None
        self.omnivoice_ref_text = None
        self.omnivoice_instruct = None
        if self.tts_service == "omnivoice":
            if OmniVoice is None:
                print(f"{RED}OmniVoice is not installed. Install with: pip install git+https://github.com/k2-fsa/OmniVoice.git{RESET}")
            else:
                try:
                    import torch
                    if self.omnivoice_device == "cuda" and self.detailed_logs:
                        print(f"{GREEN}CUDA available: {torch.cuda.is_available()}{RESET}")
                        print(f"{GREEN}CUDA device count: {torch.cuda.device_count()}{RESET}")
                        print(f"{GREEN}CUDA current device: {torch.cuda.current_device()}{RESET}")
                        print(f"{GREEN}CUDA device name: {torch.cuda.get_device_name(0)}{RESET}")
                    self.omnivoice_model = OmniVoice.from_pretrained(
                        "k2-fsa/OmniVoice",
                        device_map=f"{self.omnivoice_device}:0" if self.omnivoice_device == "cuda" else self.omnivoice_device,
                        dtype=torch.float16,
                    )

                    ref_audio_path = os.path.abspath(os.path.join(BASE_PATH, "Data", "reference.wav"))
                    ref_text_path = os.path.abspath(os.path.join(BASE_PATH, "Data", "reference.txt"))
                    design_path = os.path.abspath(os.path.join(BASE_PATH, "Data", "omnivoice-design.txt"))

                    if self.voice_cloning and os.path.exists(ref_audio_path) and os.path.exists(ref_text_path):
                        self.omnivoice_ref_audio = ref_audio_path
                        with open(ref_text_path, "r", encoding="utf-8") as f:
                            self.omnivoice_ref_text = f.read().strip()
                        print(f"{GREEN}OmniVoice initialized with voice cloning{RESET}")
                    elif self.voice_cloning and not os.path.exists(ref_audio_path):
                        print(f"{YELLOW}reference.wav not found. Falling back to auto voice.{RESET}")
                    elif self.voice_cloning and not os.path.exists(ref_text_path):
                        print(f"{YELLOW}reference.txt not found. Falling back to auto voice.{RESET}")

                    if self.omnivoice_ref_audio is None and self.voice_design and os.path.exists(design_path):
                        with open(design_path, "r", encoding="utf-8") as f:
                            self.omnivoice_instruct = f.read().strip()
                        print(f"{GREEN}OmniVoice initialized with voice design{RESET}")
                    elif self.voice_design and not os.path.exists(design_path):
                        print(f"{YELLOW}omnivoice-design.txt not found. Falling back to auto voice.{RESET}")

                    if self.omnivoice_ref_audio is None and self.omnivoice_instruct is None:
                        print(f"{GREEN}OmniVoice initialized with auto voice{RESET}")

                except Exception as e:
                    print(f"{RED}Failed to initialize OmniVoice: {e}{RESET}")

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

                case "elevenlabs":
                    #TO DO: IMPLEMENT ELEVENLABS TTS
                    pass

                case "omnivoice":
                    if self.omnivoice_model is None:
                        print(f"{YELLOW}OmniVoice not initialized, falling back to gtts...{RESET}")
                        gTTS(text=text, lang=self.tts_language, slow=False, lang_check=False).save(output_path)
                        return
                    generate_kwargs = {"text": text}
                    if self.omnivoice_ref_audio is not None:
                        generate_kwargs["ref_audio"] = self.omnivoice_ref_audio
                        generate_kwargs["ref_text"] = self.omnivoice_ref_text
                    elif self.omnivoice_instruct is not None:
                        generate_kwargs["instruct"] = self.omnivoice_instruct
                    audio = self.omnivoice_model.generate(**generate_kwargs)
                    sf.write(output_path, audio[0], 24000)

                case "pockettts":
                    if self.pockettts_model is None or self.pockettts_voice_state is None:
                        print(f"{YELLOW}Pocket TTS not initialized, falling back to gtts...{RESET}")
                        gTTS(text=text, lang=self.tts_language, slow=False, lang_check=False).save(output_path)
                        return
                    audio = self.pockettts_model.generate_audio(self.pockettts_voice_state, text)
                    scipy.io.wavfile.write(output_path, self.pockettts_model.sample_rate, audio.numpy())

                case _:
                    print(f"{YELLOW} TTS service not supported falling back to gtts... {RESET}")
                    gTTS(text=text, lang=self.tts_language, slow=False, lang_check=False).save(output_path)

        except Exception as e:
            print(f"{RED}Error generating TTS: {e}{RESET}")
            self.is_speaking = False
            return

        if not os.path.exists(output_path):
            print(f"{RED}error: output.wav file not created!{RESET}")
            self.is_speaking = False
            return

        try:
            data, samplerate = sf.read(output_path)

            silence_samples = int(samplerate * 0.15)
            silence = np.zeros(silence_samples, dtype=data.dtype)
            data = np.concatenate([silence, data])

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
