import asyncio
import speech_recognition as sr
import pyaudio
import wave
import tempfile
import keyboard
import time
import os

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

class UserInput:
    def __init__(self, user_input_service: str = "speech", detailed_logs: bool = False, app_language: str = "english") -> None:
        self.user_input_service = user_input_service
        self.detailed_logs = detailed_logs
        self.app_language = app_language
        self.mic = None
        self.audio = None
        self.recogniser = sr.Recognizer()

    def setup_mic(self, mic_index: int = None) -> None:
        self.mic = sr.Microphone(device_index=mic_index)
        self.audio = pyaudio.PyAudio()

    def cleanup(self) -> None:
        if self.audio:
            self.audio.terminate()
            self.audio = None

    async def get_user_input(self) -> str:
        if self.user_input_service == "console":
            def get_input_blocking():
                try:
                    user_input = input("User: ")
                    return user_input
                except Exception as e:
                    print(f"{RED}console input error: {e}{RESET}")
                    return ""
            return await asyncio.to_thread(get_input_blocking)
        elif self.user_input_service == "speech":
            def get_speech_blocking():
                while True:
                    if self.app_language == "english":
                        print("-----Press space to start listening, release to stop----", flush=True)
                    elif self.app_language == "spanish":
                        print("-----Presione espacio para hablar. Suelte espacio para parar----", flush=True)
                    while not keyboard.is_pressed(' '):
                        time.sleep(0.1)

                    if self.app_language == "english":
                        print(f"{YELLOW}recording, release space to stop...{RESET}", flush=True)
                    elif self.app_language == "spanish":
                        print(f"{YELLOW}Grabando, suelte espacio para parar...{RESET}", flush=True)
                    chunk = 1024
                    format = pyaudio.paInt16
                    channels = 1
                    rate = 16000

                    if self.mic.device_index is not None:
                        device_index = self.mic.device_index
                    else:
                        device_index = None

                    try:
                        stream = self.audio.open(
                            format=format,
                            channels=channels,
                            rate=rate,
                            input=True,
                            input_device_index=device_index,
                            frames_per_buffer=chunk
                        )
                        frames = []

                        while keyboard.is_pressed(' '):
                            data = stream.read(chunk, exception_on_overflow=False)
                            frames.append(data)

                        if self.app_language == "english":
                            print(f"{YELLOW}recording stopped. Processing...{RESET}")
                        elif self.app_language == "spanish":
                            print(f"{YELLOW}Grabacion parada. Procesando...{RESET}")
                        stream.stop_stream()
                        stream.close()

                        if not frames:
                            if self.app_language == "english":
                                print(f"{ORANGE}No audio captures. Try again...{RESET}")
                            elif self.app_language == "spanish":
                                print(f"{ORANGE}Audio no caputrado. Intente denuevo...{RESET}")
                            continue

                        temp_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                        temp_filename = temp_audio_file.name
                        temp_audio_file.close()
                        wf = wave.open(temp_filename, 'wb')
                        wf.setnchannels(channels)
                        wf.setsampwidth(self.audio.get_sample_size(format))
                        wf.setframerate(rate)
                        wf.writeframes(b''.join(frames))
                        wf.close()

                        with sr.AudioFile(temp_filename) as source:
                            audio_data = self.recogniser.record(source)

                            try:
                                if self.app_language == "spanish":
                                    text = self.recogniser.recognize_google(audio_data, language="es-HN")
                                else:
                                    text = self.recogniser.recognize_google(audio_data, language="en-US")
                                if self.app_language == "english":
                                    print(f"{GREEN}text Captured: {text}{RESET}")
                                elif self.app_language == "spanish":
                                    print(f"{GREEN}texto capturado: {text}{RESET}")

                                try:
                                    os.unlink(temp_filename)
                                except OSError:
                                    pass

                                return text
                            except sr.UnknownValueError as e:
                                if self.detailed_logs:
                                    print(f"{ORANGE}Unknown value error in sr: {e}{RESET}")
                                if self.app_language == "english":
                                    print(f"{ORANGE}Could not understand audio. Try again...{RESET}")
                                elif self.app_language == "spanish":
                                    print(f"{ORANGE}No se pudo entender. Intente denuevo...{RESET}")

                                try:
                                    os.unlink(temp_filename)
                                except OSError:
                                    pass

                                continue
                            except sr.RequestError as e:
                                if self.detailed_logs:
                                    print(f"{ORANGE}Rquest Error in google sr: {e}{RESET}")
                                if self.app_language == "english":
                                    print(f"{ORANGE}Request error from google. Try again...{RESET}")
                                elif self.app_language == "spanish":
                                    print(f"{ORANGE}Error de Google. Intente denuevo...{RESET}")

                                try:
                                    os.unlink(temp_filename)
                                except OSError:
                                    pass

                                continue
                    except Exception as e:
                        if self.detailed_logs:
                            print(f"{RED}unexpected error during reecording: {e}{RESET}")
                        if self.app_language:
                            print(f"{RED}Error during recording.{RESET}")
                        elif self.app_language == "spanish":
                            print(f"{RED}Eror durante grabacion.{RESET}")
                        if self.detailed_logs:
                            print(f"{YELLOW}Cleaning up audio stream...{RESET}")
                        try:
                            if 'stream' in locals():
                                stream.stop_stream()
                                stream.close()
                        except:
                            pass

                        if self.detailed_logs:
                            print(f"{YELLOW}Cleaning up temp file...{RESET}")
                        try:
                            if 'temp_filename' in locals():
                                os.unlink(temp_filename)
                        except OSError:
                            pass
                        if self.app_language == "english":
                            print(f"{ORANGE}Please try again...{RESET}")
                        elif self.app_language == "spanish":
                            print(f"{ORANGE}Please try again...{RESET}")
                        continue
            return await asyncio.to_thread(get_speech_blocking)
        else:
            if self.app_language:
                print(f"{ORANGE}unknown input service: {self.user_input_service}{RESET}")
            elif self.app_language == "spanish":
                print(f"{ORANGE}Input service desconocido: {self.user_input_service}{RESET}")
            return ""
