import numpy as np

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'


class LocalSTT:
    DEFAULT_MODEL = "Systran/faster-whisper-base"
    # English-only variant: its vocabulary cannot emit other languages,
    # which stops random Spanish output on noisy/silent chunks.
    DEFAULT_MODEL_EN = "Systran/faster-whisper-base.en"

    # Well-known Whisper hallucinations on silence/noise (e.g. the classic
    # Spanish "Amara.org" captions credit). Dropped before joining segments.
    HALLUCINATIONS = (
        "amara.org", "amara.org", "subtítulos por", "subtitulos por",
        "subtitles by", "gracias por ver", "thanks for watching",
        "thank you for watching", "suscríbete", "suscribete",
        "hasta la próxima", "música de fondo",
    )

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
        try:
            from faster_whisper import WhisperModel

            model_name = self.DEFAULT_MODEL
            if (self.language or "").lower().startswith("en"):
                # English requested: use the English-only weights so the
                # decoder physically cannot output Spanish/other languages.
                model_name = self.DEFAULT_MODEL_EN

            if self.detailed_logs:
                print(f"{YELLOW}Loading Whisper STT model: {model_name} "
                    f"(device={self.device}, compute={self.compute_type}, lang={self.language}){RESET}")
            self._model = WhisperModel(
                model_name,
                device=self.device,
                compute_type=self.compute_type
            )
        except Exception as e:
            print(f"{RED}Failed to load Whisper STT model: {e}{RESET}")
            raise

    def transcribe(self, frames: list, vad_filter: bool = True) -> str:
        if not frames:
            return ""

        try:
            audio_data = b''.join(frames)
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            segments, info = self._model.transcribe(
                audio_np,
                beam_size=5,
                language=self.language if self.language else None,
                vad_filter=vad_filter,
                # Don't condition on previous segments: prevents a hallucinated
                # phrase from snowballing into repeated garbage.
                condition_on_previous_text=False,
            )

            parts = []
            for segment in segments:
                text = segment.text.strip()
                low = text.lower().strip(" .,!?¡¿\"'")
                if not low:
                    continue
                if any(h in low for h in self.HALLUCINATIONS):
                    if self.detailed_logs:
                        print(f"{ORANGE}[STT] Dropped hallucinated segment: {text}{RESET}")
                    continue
                parts.append(text)
            return " ".join(parts).strip()
        except Exception as e:
            print(f"{RED}Transcription error: {e}{RESET}")
            return ""
