import sounddevice as sd
import soundfile as sf
import openwakeword
from openwakeword.model import Model as OwwModel
import pyaudio
import numpy as np
import os

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'


class WakeWordListener:
    def __init__(
        self,
        model_path: str,
        threshold: float = 0.5,
        confirm_sound: bool = True,
        silence_duration: float = 1.5,
        detailed_logs: bool = False,
    ) -> None:
        self.model_path = model_path
        self.threshold = threshold
        self.confirm_sound = confirm_sound
        self.silence_duration = silence_duration
        self.detailed_logs = detailed_logs
        self._model = None

    def cleanup(self) -> None:
        if self._model:
            self._model = None

    def load_model(self) -> None:
        try:
            oww_dir = os.path.join(os.path.dirname(openwakeword.__file__), "resources", "models")
            if not os.path.isdir(oww_dir) or not os.path.exists(os.path.join(oww_dir, "melspectrogram.onnx")):
                print(f"{YELLOW}OpenWakeWord models not found, downloading...{RESET}")
                from openwakeword.utils import download_models
                download_models()

            if not os.path.isfile(self.model_path):
                raise FileNotFoundError(f"Wake word model not found: {self.model_path}")

            if self.detailed_logs:
                print(f"{YELLOW}Loading wake word model: {self.model_path}{RESET}")
            self._model = OwwModel(
                wakeword_models=[self.model_path],
                inference_framework="onnx"
            )
            if self.detailed_logs:
                print(f"{GREEN}Wake word model loaded.{RESET}")
        except Exception as e:
            print(f"{RED}Failed to load wake word model: {e}{RESET}")
            raise

    def listen(self, audio: pyaudio.PyAudio) -> bool:
        chunk_size = 1280
        self._model.reset()
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=chunk_size
            )
            try:
                while True:
                    data = stream.read(chunk_size, exception_on_overflow=False)
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    prediction = self._model.predict(audio_np)

                    for model_name in prediction:
                        score = prediction[model_name]
                        if isinstance(score, dict):
                            score = score["raw"]["openwakeword"]
                        if score > self.threshold:
                            return True
            finally:
                stream.stop_stream()
                stream.close()
        except Exception as e:
            if self.detailed_logs:
                print(f"{RED}Wake word listen error: {e}{RESET}")
            return False

    def record_until_silence(self, audio: pyaudio.PyAudio) -> list:
        chunk_size = 1024
        rate = 16000
        frames = []
        silent_chunks = 0
        chunks_per_second = rate / chunk_size
        threshold_chunks = int(self.silence_duration * chunks_per_second)

        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                input=True,
                frames_per_buffer=chunk_size
            )
            try:
                got_speech = False
                while True:
                    data = stream.read(chunk_size, exception_on_overflow=False)
                    frames.append(data)

                    audio_chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                    rms = np.sqrt(np.mean(audio_chunk ** 2))
                    energy_threshold = 300

                    if rms > energy_threshold:
                        got_speech = True
                        silent_chunks = 0
                    else:
                        silent_chunks += 1

                    if got_speech and silent_chunks > threshold_chunks:
                        break
            finally:
                stream.stop_stream()
                stream.close()
        except Exception as e:
            if self.detailed_logs:
                print(f"{RED}Recording error: {e}{RESET}")
            return []

        return frames

    def play_confirm_sound(self) -> None:
        try:
            sound_path = os.path.join(os.path.dirname(__file__), "Data", "confirm_beep.wav")
            if os.path.exists(sound_path):
                data, samplerate = sf.read(sound_path)
                sd.play(data, samplerate)
                sd.wait()
            else:
                duration = 0.15
                sr_rate = 16000
                t = np.linspace(0, duration, int(sr_rate * duration), False)
                tone = np.sin(2 * np.pi * 880 * t) * 0.3
                fade_samples = int(sr_rate * 0.01)
                tone[:fade_samples] *= np.linspace(0, 1, fade_samples)
                tone[-fade_samples:] *= np.linspace(1, 0, fade_samples)
                sd.play(tone.astype(np.float32), sr_rate)
                sd.wait()
        except Exception as e:
            if self.detailed_logs:
                print(f"{ORANGE}Could not play confirm sound: {e}{RESET}")
