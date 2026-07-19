import numpy as np

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RESET = '\033[0m'


class LocalSTT:
    DEFAULT_MODEL = "Systran/faster-whisper-base"

    def __init__(
        self,
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "en",
        detailed_logs: bool = False,
    ) -> None:
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.detailed_logs = detailed_logs
        self._model = None

    def cleanup(self) -> None:
        if self._model:
            self._model = None

    def load_model(self) -> None:
        """Load Whisper model from Hugging Face cache (downloads on first run).
        
        Models are cached in ~/.cache/huggingface/hub/
        """
        try:
            from faster_whisper import WhisperModel

            if self.detailed_logs:
                print(f"{YELLOW}Loading Whisper STT model: {self.DEFAULT_MODEL} "
                    f"(device={self.device}, compute={self.compute_type}){RESET}")
            self._model = WhisperModel(
                self.DEFAULT_MODEL,
                device=self.device,
                compute_type=self.compute_type
            )
        except Exception as e:
            print(f"{RED}Failed to load Whisper STT model: {e}{RESET}")
            raise

    def transcribe(self, frames: list) -> str:
        if not frames:
            return ""

        try:
            audio_data = b''.join(frames)
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            segments, info = self._model.transcribe(
                audio_np,
                beam_size=5,
                language=self.language if self.language else None,
                vad_filter=True
            )

            text = " ".join(segment.text.strip() for segment in segments)
            return text.strip()
        except Exception as e:
            print(f"{RED}Transcription error: {e}{RESET}")
            return ""
