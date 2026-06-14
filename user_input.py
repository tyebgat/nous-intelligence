import asyncio
import speech_recognition as sr
import pyaudio
import wave
import tempfile
import keyboard
import time
import os

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
                    print(f"console input error: {e}")
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
                        print("recording, release space to stop...", flush=True)
                    elif self.app_language == "spanish":
                        print("Grabando, suelte espacio para parar...", flush=True)
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
                            print("recording stopped. Processing...")
                        elif self.app_language == "spanish":
                            print("Grabacion parada. Procesando...")
                        stream.stop_stream()
                        stream.close()

                        if not frames:
                            if self.app_language == "english":
                                print("No audio captures. Try again...")
                            elif self.app_language == "spanish":
                                print("Audio no caputrado. Intente denuevo...")
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
                                    print(f"text Captured: {text}")
                                elif self.app_language == "spanish":
                                    print(f"texto capturado: {text}")

                                try:
                                    os.unlink(temp_filename)
                                except OSError:
                                    pass

                                return text
                            except sr.UnknownValueError as e:
                                if self.detailed_logs:
                                    print(f"Unknown value error in sr: {e}")
                                if self.app_language == "english":
                                    print("Could not understand audio. Try again...")
                                elif self.app_language == "spanish":
                                    print("No se pudo entender. Intente denuevo...")

                                try:
                                    os.unlink(temp_filename)
                                except OSError:
                                    pass

                                continue
                            except sr.RequestError as e:
                                if self.detailed_logs:
                                    print(f"Rquest Error in google sr: {e}")
                                if self.app_language == "english":
                                    print("Request error from google. Try again...")
                                elif self.app_language == "spanish":
                                    print("Error de Google. Intente denuevo...")

                                try:
                                    os.unlink(temp_filename)
                                except OSError:
                                    pass

                                continue
                    except Exception as e:
                        if self.detailed_logs:
                            print(f"unexpected error during reecording: {e}")
                        if self.app_language:
                            print("Error during recording.")
                        elif self.app_language == "spanish":
                            print("Eror durante grabacion.")
                        if self.detailed_logs:
                            print("Cleaning up audio stream...")
                        try:
                            if 'stream' in locals():
                                stream.stop_stream()
                                stream.close()
                        except:
                            pass

                        if self.detailed_logs:
                            print("Cleaning up temp file...")
                        try:
                            if 'temp_filename' in locals():
                                os.unlink(temp_filename)
                        except OSError:
                            pass
                        if self.app_language == "english":
                            print("Please try again...")
                        elif self.app_language == "spanish":
                            print("Please try again...")
                        continue
            return await asyncio.to_thread(get_speech_blocking)
        else:
            if self.app_language:
                print(f"unknown input service: {self.user_input_service}")
            elif self.app_language == "spanish":
                print(f"Input service desconocido: {self.user_input_service}")
            return ""
