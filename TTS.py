import numpy as np
from gtts import gTTS
from openai import OpenAI
import sounddevice as sd
import soundfile as sf
import scipy.io.wavfile
import os
from os import getenv
import sys
import time
import threading
from paths import BASE_PATH
from loguru import logger

# Used by the CLI "Generating TTS..." spinner (kept as raw ANSI writes).
YELLOW = '\033[33m'
RESET = '\033[0m'


def warm_up_heavy_imports(tts_service: str, stt_service: str) -> None:
    """Pre-import the heavy AI backends on the caller's thread.

    OmniVoice drags in torch/torchaudio/transformers and faster-whisper brings
    CTranslate2 + its CUDA wrappers; each takes seconds to import and build a
    CUDA context. When two of them do that in separate worker threads at the
    same time, the concurrent heavy importing can sever each other (OmniVoice
    fails with an ImportError on cold start, then "works on retry" once its
    dependencies are cached in sys.modules). Importing them here, single
    threaded and before the per-service initializers run in parallel, makes
    those inits cache hits instead of a race.
    """
    if tts_service == "omnivoice":
        try:
            import omnivoice  # noqa: F401
        except Exception as e:
            logger.exception(f"Failed to import OmniVoice backend: {e}")
    if stt_service == "whisper":
        try:
            import faster_whisper  # noqa: F401
        except Exception as e:
            logger.warning(f"Failed to import faster-whisper backend: {e}")


class TTS:
    def __init__(self, tts_language: str = "en", chatbot_name: str = "Nous", tts_service: str = "gtts", openai_tts_model: str = None, openai_tts_voice: str = "ash", tts_voice: str = "ash", tts_speed: float = 1.0, voice_cloning: bool = False, voice_design: bool = False, reference_wav: str = None, omnivoice_device: str = "cuda", play_only_cable: bool = False, gain: float = 1.0):
        self.chatbot_name = chatbot_name
        self.openai_tts_voice = openai_tts_voice
        self.openai_tts_model = openai_tts_model
        self.tts_service = tts_service
        self.tts_language = tts_language
        self.tts_voice = tts_voice
        self.tts_speed = tts_speed
        self.voice_cloning = voice_cloning
        self.voice_design = voice_design
        self.reference_wav = reference_wav or "Data/reference.wav"
        self.omnivoice_device = omnivoice_device
        self.play_only_cable = play_only_cable
        self.gain = gain
        self.cable_device_id = None
        self.is_playing = False
        self.on_playback_start = None
        self.on_playback_end = None
        # Set when the current speech must be cut short (interrupt/stop).
        self._stop_requested = False
        # OutputStreams currently playing, so stop() can abort() them safely
        # from any thread. The global sd.play()/sd.wait()/sd.stop() functions
        # are NOT thread-safe and crash when play/stop cross threads.
        self._streams = []
        
    def load_openai_tts_personality(self) -> list:
        with open(os.path.join(BASE_PATH, "openai-TTS-instructions.txt"), "r") as personality:
            text = personality.read()
            return text

    def _resolve_reference_path(self, path: str) -> str:
        if not path:
            return None
        if os.path.isabs(path):
            return os.path.abspath(path)
        return os.path.abspath(os.path.join(BASE_PATH, path))

    def initialize(self):
        self.tts_instructions = self.load_openai_tts_personality()
        self.cable_device_id = self.get_cable_device_id()

        #try to get virtual audio cable
        if self.cable_device_id is not None:
            logger.success(f"VB Cable device set to id: {self.cable_device_id}")
        else:
            logger.warning("No VB cable found, lypsinc may not work.")
        
        #initialize pocket tts
        self.pockettts_model = None
        self.pockettts_voice_state = None
        if self.tts_service == "pockettts":
            try:
                from pocket_tts import TTSModel
            except Exception:
                TTSModel = None
            if TTSModel is None:
                logger.error("pocket-tts is not installed. Install with: pip install pocket-tts scipy")
            else:
                try:
                    hf_token = getenv("HF_TOKEN")
                    if hf_token:
                        from huggingface_hub import login
                        login(token=hf_token)

                    self.pockettts_model = TTSModel.load_model()

                    ref_path = self._resolve_reference_path(self.reference_wav)
                    if self.voice_cloning and ref_path and os.path.exists(ref_path):
                        try:
                            self.pockettts_voice_state = self.pockettts_model.get_state_for_audio_prompt(ref_path)
                            logger.success(f"Pocket TTS initialized with voice cloning from: {ref_path}")
                        except Exception as e:
                            logger.warning(f"Voice cloning failed: {e}")
                            logger.warning("Falling back to built-in voice.")
                            voice = self.tts_voice if self.tts_voice else "alba"
                            self.pockettts_voice_state = self.pockettts_model.get_state_for_audio_prompt(voice)
                            logger.success(f"Pocket TTS initialized (voice={voice})")
                    else:
                        if self.voice_cloning:
                            logger.warning(f"reference wav not found at {ref_path}. Add a reference.wav (or set the reference_wav setting) for voice cloning.")
                        voice = self.tts_voice if self.tts_voice else "alba"
                        self.pockettts_voice_state = self.pockettts_model.get_state_for_audio_prompt(voice)
                        logger.success(f"Pocket TTS initialized (voice={voice})")

                except Exception as e:
                    logger.error(f"Failed to initialize Pocket TTS: {e}")

        #initialize omnivoice tts
        self.omnivoice_model = None
        self.omnivoice_ref_audio = None
        self.omnivoice_ref_text = None
        self.omnivoice_instruct = None
        if self.tts_service == "omnivoice":
            try:
                from omnivoice import OmniVoice
            except Exception as e:
                # Don't misread every import failure as "not installed": log the
                # real cause (e.g. a concurrent heavy import on cold start).
                logger.exception(f"Failed to import OmniVoice: {e}")
                OmniVoice = None
            if OmniVoice is None:
                logger.error("OmniVoice unavailable. Install with: pip install git+https://github.com/k2-fsa/OmniVoice.git")
            else:
                try:
                    hf_token = getenv("HF_TOKEN")
                    if hf_token:
                        from huggingface_hub import login
                        login(token=hf_token)

                    import torch
                    if self.omnivoice_device == "cuda":
                        logger.debug(f"CUDA available: {torch.cuda.is_available()}")
                        logger.debug(f"CUDA device count: {torch.cuda.device_count()}")
                        logger.debug(f"CUDA current device: {torch.cuda.current_device()}")
                        logger.debug(f"CUDA device name: {torch.cuda.get_device_name(0)}")
                    self.omnivoice_model = OmniVoice.from_pretrained(
                        "k2-fsa/OmniVoice",
                        device_map=f"{self.omnivoice_device}:0" if self.omnivoice_device == "cuda" else self.omnivoice_device,
                        dtype=torch.float16,
                    )

                    ref_audio_path = self._resolve_reference_path(self.reference_wav)
                    ref_text_path = os.path.abspath(os.path.join(BASE_PATH, "Data", "reference.txt"))
                    design_path = os.path.abspath(os.path.join(BASE_PATH, "Data", "omnivoice-design.txt"))

                    if self.voice_cloning and ref_audio_path and os.path.exists(ref_audio_path) and os.path.exists(ref_text_path):
                        self.omnivoice_ref_audio = ref_audio_path
                        with open(ref_text_path, "r", encoding="utf-8") as f:
                            self.omnivoice_ref_text = f.read().strip()
                        logger.success(f"OmniVoice initialized with voice cloning from: {ref_audio_path}")
                    elif self.voice_cloning and not (ref_audio_path and os.path.exists(ref_audio_path)):
                        logger.warning(f"reference wav not found at {ref_audio_path}. Falling back to auto voice.")
                    elif self.voice_cloning and not os.path.exists(ref_text_path):
                        logger.warning("reference.txt not found. Falling back to auto voice.")

                    if self.omnivoice_ref_audio is None and self.voice_design and os.path.exists(design_path):
                        with open(design_path, "r", encoding="utf-8") as f:
                            self.omnivoice_instruct = f.read().strip()
                        logger.success("OmniVoice initialized with voice design")
                    elif self.voice_design and not os.path.exists(design_path):
                        logger.warning("omnivoice-design.txt not found. Falling back to auto voice.")

                    if self.omnivoice_ref_audio is None and self.omnivoice_instruct is None:
                        logger.success("OmniVoice initialized with auto voice")

                except Exception as e:
                    logger.error(f"Failed to initialize OmniVoice: {e}")

    def get_cable_device_id(self):
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            name = str(device['name']).lower()
            if (device['max_output_channels'] > 0 and
                'cable input' in name and
                'vb-audio virtual cable' in name and
                device['default_samplerate'] == 44100.0):
                logger.success(f"Found VB Cable Input: [{i}] {device['name']}")
                return i
        return None

    def _start_spinner(self, label="Generating TTS"):
        self._spinner_active = True
        chars = ['-', '\\', '|', '/']
        def spin():
            i = 0
            while self._spinner_active:
                sys.stdout.write(f"\r{YELLOW}{label} {chars[i % len(chars)]}{RESET}")
                sys.stdout.flush()
                time.sleep(0.1)
                i += 1
            sys.stdout.write(f"\r{YELLOW}{label} done.{RESET}\n")
            sys.stdout.flush()
        self._spinner_thread = threading.Thread(target=spin, daemon=True)
        self._spinner_thread.start()

    def _stop_spinner(self):
        self._spinner_active = False
        if hasattr(self, '_spinner_thread'):
            self._spinner_thread.join()

    def stop(self) -> None:
        """Request the current utterance to stop.

        Sets the cooperative flag and immediately aborts every active playback
        stream (abort() is safe to call from any thread). The blocking play
        loop in tts_say() then exits right away."""
        self._stop_requested = True
        for stream in list(self._streams):
            try:
                stream.abort()
            except Exception:
                pass

    async def tts_say(self, text: str) -> None:
        logger.info(f"{self.chatbot_name}: {text}")
        self.is_speaking = True
        self._stop_requested = False

        output_path = os.path.join(BASE_PATH, 'Data', 'output.wav')

        self._start_spinner()

        try:
            match self.tts_service:
                case "gtts":
                    gTTS(text=text, lang=self.tts_language, slow=False, lang_check=False).save(output_path)

                case "openai":
                    client = OpenAI(api_key=getenv("OPENAI_API_KEY"), timeout=120.0)
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
                        logger.warning("OmniVoice not initialized, falling back to gtts...")
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
                        logger.warning("Pocket TTS not initialized, falling back to gtts...")
                        gTTS(text=text, lang=self.tts_language, slow=False, lang_check=False).save(output_path)
                        return
                    audio = self.pockettts_model.generate_audio(self.pockettts_voice_state, text)
                    scipy.io.wavfile.write(output_path, self.pockettts_model.sample_rate, audio.numpy())

                case _:
                    logger.warning("TTS service not supported falling back to gtts...")
                    gTTS(text=text, lang=self.tts_language, slow=False, lang_check=False).save(output_path)

        except Exception as e:
            self._stop_spinner()
            logger.error(f"Error generating TTS: {e}")
            self.is_speaking = False
            return

        self._stop_spinner()

        if not os.path.exists(output_path):
            logger.error("error: output.wav file not created!")
            self.is_speaking = False
            return

        # Interrupt landed while the audio was being generated: the wav exists
        # but the user already cancelled, so skip playing it entirely.
        if self._stop_requested:
            self._stop_requested = False
            self.is_speaking = False
            return

        self.is_playing = True
        if self.on_playback_start:
            self.on_playback_start()

        streams = []
        try:
            data, samplerate = sf.read(output_path)

            # PortAudio has no 64-bit float format: OpenAL/OutputStream would
            # fail with "Invalid output sample format". Normalise early.
            data = np.ascontiguousarray(data, dtype=np.float32)

            silence_samples = int(samplerate * 0.15)
            silence = np.zeros(silence_samples, dtype=data.dtype)
            data = np.concatenate([silence, data])

            if self.gain != 1.0:
                data = data * self.gain
                data = np.clip(data, -1.0, 1.0)

            if self.cable_device_id is not None:
                if self.play_only_cable:
                    devices = [self.cable_device_id]
                else:
                    devices = [None, self.cable_device_id]
            else:
                devices = [None]

            channels = 1 if data.ndim == 1 else data.shape[1]
            all_done = threading.Event()

            def _make_callback():
                pos = [0]
                def _cb(outdata, frames, time_info, status):
                    remaining = len(data) - pos[0]
                    n = min(frames, remaining)
                    if n > 0:
                        chunk = data[pos[0]:pos[0] + n]
                        if chunk.ndim == 1:
                            chunk = chunk[:, None]
                        outdata[:n] = chunk
                        pos[0] += n
                    if n < frames:
                        outdata[n:] = 0
                    if len(data) - pos[0] == 0:
                        raise sd.CallbackStop
                return _cb

            # Each device plays the same audio on its OWN stream so an
            # abort() on one never affects the others. Owned streams avoid
            # the thread-unsafe global sd.play()/sd.wait()/sd.stop() that
            # crash when a stop arrives from another thread mid-playback.
            for device in devices:
                stream = sd.OutputStream(
                    samplerate=samplerate,
                    device=device,
                    channels=channels,
                    dtype=data.dtype,
                    callback=_make_callback(),
                    finished_callback=all_done.set,
                )
                stream.start()
                streams.append(stream)
            self._streams = streams

            while not all_done.is_set() and not self._stop_requested:
                time.sleep(0.05)

            if self._stop_requested:
                for stream in streams:
                    try:
                        stream.abort()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
        finally:
            for stream in streams:
                try:
                    stream.close()
                except Exception:
                    pass
            self._streams = []
            self.is_playing = False
            self.is_speaking = False
            if self.on_playback_end:
                self.on_playback_end()
