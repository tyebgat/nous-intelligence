import asyncio
import numpy as np
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
        self.silence_duration = silence_duration
        self.mic = None
        self.audio = None
        self.recogniser = sr.Recognizer()
        self._running = True

        # Event-driven (GUI) voice input state
        self._speech_active = False
        self._utterance_buffer = []
        self.listening = False
        self._listen_buffer = b""
        self._got_speech = False
        self._silent_seconds = 0.0
        self._energy_threshold = 300

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

    def resample16k(self, pcm: bytes, src_rate: int = 16000) -> bytes:
        """Resample raw int16 PCM from src_rate down to 16 kHz for STT/wake word."""
        if not pcm or src_rate == 16000:
            return pcm
        try:
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
            target_len = max(1, int(round(len(audio) * 16000 / src_rate)))
            x_old = np.arange(len(audio))
            x_new = np.linspace(0, len(audio) - 1, target_len)
            return np.interp(x_new, x_old, audio).astype(np.int16).tobytes()
        except Exception as e:
            if self.detailed_logs:
                print(f"{RED}Resample error: {e}{RESET}")
            return pcm

    #=============================================
    # EVENT-DRIVEN INPUT (used by the GUI)
    #=============================================
    def start_utterance(self) -> None:
        """Begin buffering a push-to-talk utterance (non-blocking)."""
        self._utterance_buffer = []
        self._speech_active = True

    def add_audio(self, pcm: bytes) -> None:
        """Append a chunk of raw int16 PCM (16 kHz mono) to the active utterance."""
        if self._speech_active and pcm:
            self._utterance_buffer.append(pcm)

    def buffered_bytes(self) -> int:
        """Total raw bytes currently buffered for the active utterance."""
        return sum(len(c) for c in self._utterance_buffer)

    def utterance_frames(self) -> list:
        """Copy of the currently buffered frames (does not consume them)."""
        return list(self._utterance_buffer)

    def utterance_stats(self, frames: list = None) -> dict:
        """Peak / RMS amplitude of the buffered audio (diagnostics)."""
        frames = self._utterance_buffer if frames is None else frames
        if not frames:
            return {"chunks": 0, "bytes": 0, "seconds": 0.0, "peak": 0.0, "rms": 0.0}
        audio = np.frombuffer(b"".join(frames), dtype=np.int16)
        n = int(audio.size)
        if n == 0:
            return {"chunks": len(frames), "bytes": 0, "seconds": 0.0, "peak": 0.0, "rms": 0.0}
        peak = float(np.max(np.abs(audio)))
        rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
        return {"chunks": len(frames), "bytes": n * 2, "seconds": n / 16000.0, "peak": peak, "rms": rms}

    def dump_utterance(self, path: str, frames: list = None) -> None:
        """Write the buffered audio to a 16 kHz mono WAV for debugging."""
        frames = self._utterance_buffer if frames is None else frames
        if not frames:
            return
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"".join(frames))

    def end_utterance(self) -> str:
        """Stop buffering and transcribe the push-to-talk utterance."""
        self._speech_active = False
        frames = self._utterance_buffer
        self._utterance_buffer = []
        return self._transcribe_frames(frames)

    def feed_wake_audio(self, pcm: bytes) -> bool:
        """Feed a PCM chunk to the wake word model; True when it is detected."""
        return self.wake_word.process_audio(pcm)

    def start_listening(self) -> None:
        """Begin recording after the wake word; silence detection auto-stops it."""
        self._listen_buffer = b""
        self._got_speech = False
        self._silent_seconds = 0.0
        self.listening = True

    def add_listen_audio(self, pcm: bytes) -> bool:
        """Feed PCM while listening. Returns True once the user stops talking."""
        if not pcm:
            return False
        self._listen_buffer += pcm
        audio_chunk = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(audio_chunk ** 2))) if audio_chunk.size else 0.0
        chunk_seconds = len(pcm) / 2 / 16000.0
        if rms > self._energy_threshold:
            self._got_speech = True
            self._silent_seconds = 0.0
        elif self._got_speech:
            self._silent_seconds += chunk_seconds
            if self._silent_seconds >= self.silence_duration:
                return True
        return False

    def stop_listening(self) -> str:
        """Stop the post-wake-word recording and transcribe what was heard."""
        self.listening = False
        buffer = self._listen_buffer
        self._listen_buffer = b""
        self._got_speech = False
        self._silent_seconds = 0.0
        frames = [buffer] if buffer else []
        return self._transcribe_frames(frames)

    def _transcribe_frames(self, frames: list, vad_filter: bool = True) -> str:
        if not frames:
            return ""
        if self.stt_service == "whisper":
            if self.local_stt._model is None:
                self.setup_whisper()
            return self.local_stt.transcribe(frames, vad_filter=vad_filter)
        return self._transcribe_with_google(frames)

    def _transcribe_with_google(self, frames: list) -> str:
        channels = 1
        rate = 16000
        temp_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_filename = temp_audio_file.name
        temp_audio_file.close()
        wf = wave.open(temp_filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # paInt16 = 2 bytes
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
        self._speech_active = False
        self.listening = False
        self._utterance_buffer = []
        self._listen_buffer = b""
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
