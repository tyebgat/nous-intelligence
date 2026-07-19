import asyncio
import speech_recognition as sr
import pyaudio
import wave
import tempfile
import keyboard
import time
import os

from wake_word import WakeWordListener
from local_stt import LocalSTT

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'


class UserInput:
    def __init__(
        self,
        user_input_service: str = "speech",
        detailed_logs: bool = False,
        app_language: str = "english",
        wake_word_model_path: str = "",
        wake_word_threshold: float = 0.5,
        wake_word_confirm_sound: bool = True,
        stt_service: str = "whisper",
        stt_device: str = "cpu",
        stt_compute_type: str = "int8",
        stt_language: str = "en",
        silence_duration: float = 1.5,
    ) -> None:
        self.user_input_service = user_input_service
        self.stt_service = stt_service
        self.stt_language = stt_language
        self.detailed_logs = detailed_logs
        self.app_language = app_language
        self.mic = None
        self.audio = None
        self.recogniser = sr.Recognizer()
        self._running = True

        self.wake_word = WakeWordListener(
            model_path=wake_word_model_path,
            threshold=wake_word_threshold,
            confirm_sound=wake_word_confirm_sound,
            silence_duration=silence_duration,
            detailed_logs=detailed_logs,
        )

        self.local_stt = LocalSTT(
            device=stt_device,
            compute_type=stt_compute_type,
            language=stt_language,
            detailed_logs=detailed_logs,
        )

    def setup_mic(self, mic_index: int = None) -> None:
        self.mic = sr.Microphone(device_index=mic_index)
        self.audio = pyaudio.PyAudio()

    def setup_wake_word(self) -> None:
        if self.user_input_service != "wake_word":
            return
        self.wake_word.load_model()

    def setup_whisper(self) -> None:
        if self.stt_service != "whisper":
            return
        self.local_stt.load_model()

    def _transcribe_with_google(self, frames: list) -> str:
        format = pyaudio.paInt16
        channels = 1
        rate = 16000
        temp_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_filename = temp_audio_file.name
        temp_audio_file.close()
        wf = wave.open(temp_filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(self.audio.get_sample_size(format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        try:
            with sr.AudioFile(temp_filename) as source:
                audio_data = self.recogniser.record(source)
            text = self.recogniser.recognize_google(audio_data, language=self.stt_language)
            return text
        except (sr.UnknownValueError, sr.RequestError):
            return ""
        finally:
            try:
                os.unlink(temp_filename)
            except OSError:
                pass

    def cleanup(self) -> None:
        self._running = False
        self.wake_word.cleanup()
        self.local_stt.cleanup()
        if self.audio:
            self.audio.terminate()
            self.audio = None


    #=============================================
    # CONSOLE INPUT
    #=============================================
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

        #=============================================
        # PUSH TO TALK INPUT
        #=============================================
        elif self.user_input_service == "speech":
            def get_speech_blocking():
                while self._running:
                    if self.app_language == "english":
                        print("-----Press space to start listening, release to stop----", flush=True)
                    elif self.app_language == "spanish":
                        print("-----Presione espacio para hablar. Suelte espacio para parar----", flush=True)
                    while not keyboard.is_pressed(' ') and self._running:
                        time.sleep(0.05)

                    if not self._running:
                        break

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

                        while keyboard.is_pressed(' ') and self._running:
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

                        if self.stt_service == "whisper":
                            text = self.local_stt.transcribe(frames)
                        else:
                            text = self._transcribe_with_google(frames)

                        if not text:
                            if self.app_language == "english":
                                print(f"{ORANGE}Could not understand audio. Try again...{RESET}")
                            elif self.app_language == "spanish":
                                print(f"{ORANGE}No se pudo entender. Intente denuevo...{RESET}")
                            continue

                        if self.app_language == "english":
                            print(f"{GREEN}text Captured: {text}{RESET}")
                        elif self.app_language == "spanish":
                            print(f"{GREEN}texto capturado: {text}{RESET}")

                        return text
                    except Exception as e:
                        if self.detailed_logs:
                            print(f"{RED}unexpected error during recording: {e}{RESET}")
                        if self.app_language == "english":
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

                        if self.app_language == "english":
                            print(f"{ORANGE}Please try again...{RESET}")
                        elif self.app_language == "spanish":
                            print(f"{ORANGE}Porfavor intente denuevo...{RESET}")
                        continue
                return ""
            return await asyncio.to_thread(get_speech_blocking)
        
        #=============================================
        # WAKE WORD INPUT
        #=============================================
        elif self.user_input_service == "wake_word":
            def get_wake_word_blocking():
                if self.app_language == "english":
                    print(f"{YELLOW}Listening for wake word...{RESET}", flush=True)
                elif self.app_language == "spanish":
                    print(f"{YELLOW}Escuchando palabra de activacion...{RESET}", flush=True)

                while self._running:
                    detected = self.wake_word.listen(self.audio)
                    if not detected:
                        continue

                    if self.app_language == "english":
                        print(f"{GREEN}Wake word detected! Start speaking...{RESET}", flush=True)
                    elif self.app_language == "spanish":
                        print(f"{GREEN}Palabra de activacion detectada! Hable...{RESET}", flush=True)

                    if self.wake_word.confirm_sound:
                        self.wake_word.play_confirm_sound()

                    frames = self.wake_word.record_until_silence(self.audio)

                    if not frames:
                        if self.app_language == "english":
                            print(f"{ORANGE}No speech detected. Listening again...{RESET}", flush=True)
                        elif self.app_language == "spanish":
                            print(f"{ORANGE}No se detecto voz. Escuchando de nuevo...{RESET}", flush=True)
                        continue

                    if self.app_language == "english":
                        print(f"{YELLOW}Transcribing...{RESET}", flush=True)
                    elif self.app_language == "spanish":
                        print(f"{YELLOW}Transcribiendo...{RESET}", flush=True)

                    text = self.local_stt.transcribe(frames)

                    if not text:
                        if self.app_language == "english":
                            print(f"{ORANGE}Could not understand audio. Listening again...{RESET}", flush=True)
                        elif self.app_language == "spanish":
                            print(f"{ORANGE}No se pudo entender. Escuchando de nuevo...{RESET}", flush=True)
                        continue

                    if self.app_language == "english":
                        print(f"{GREEN}text Captured: {text}{RESET}")
                    elif self.app_language == "spanish":
                        print(f"{GREEN}texto capturado: {text}{RESET}")

                    return text

                return ""

            return await asyncio.to_thread(get_wake_word_blocking)

        else:
            if self.app_language == "english":
                print(f"{ORANGE}unknown input service: {self.user_input_service}{RESET}")
            elif self.app_language == "spanish":
                print(f"{ORANGE}Input service desconocido: {self.user_input_service}{RESET}")
            return ""
