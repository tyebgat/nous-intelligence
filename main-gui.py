
import asyncio
import base64
import json
import logging
import sys
import threading
import webbrowser
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from paths import BASE_PATH
import i18n

#Modules
try:
    from run_local_server import RunLocalServer
except ImportError:
    RunLocalServer = None

try:
    from chat_bot import ChatBot
except ImportError:
    ChatBot = None

try:
    from VtubeS_Plugin import VtubeControll
except ImportError:
    VtubeControll = None

try:
    from TTS import TTS
except ImportError:
    TTS = None

try:
    from user_input import UserInput
except ImportError:
    UserInput = None

nous_task = None

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'


#Global state
class AppState:
    #Holds the runtime objects shared across requests.
    running = False # whether the AI service is started
    config = {} # loaded settings.json dict
    vts = None  # VtubeControll instance
    chat_bot = None # ChatBot instance
    local_server = None # RunLocalServer instance (local LLM)
    tts = None # TTS instance
    user_input = None # UserInput instance (speech / wake word)
    ai_busy = False # True while a response is being generated/spoken; blocks voice input
    nous_task = None
    _lock = None

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

state = AppState()

#Connected WebSocket clients
clients = set()

#Sample rate reported by each client's browser mic (for resampling to 16 kHz).
mic_rate = {}


async def _broadcast(message: dict) -> None:
    """Send a message to every connected WebSocket client."""
    if not clients:
        return
    dead = []
    for client in list(clients):
        try:
            await client.send_json(message)
        except Exception:
            dead.append(client)
    for client in dead:
        clients.discard(client)


def _log(line: str) -> None:
    """
    Print a line to the server console and forward it to the GUI over
    WebSocket so it can be shown in the init panel / terminal.
    """
    print(line)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if loop.is_running():
        loop.create_task(_broadcast({"type": "log", "payload": {"line": line}}))


class WSBroadcastHandler(logging.Handler):
    """Python logging handler that forwards uvicorn logs to the GUI."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if msg:
                _log(msg)
        except Exception:
            pass


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(message)s"},
        "access": {"format": "%(message)s"},
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "ws": {
            "formatter": "default",
            "()": WSBroadcastHandler,
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default", "ws"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default", "ws"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["access", "ws"], "level": "INFO", "propagate": False},
    },
}

#Fast api
app = FastAPI(title="Nous Intelligence GUI")

#settings functions
def settings_path() -> Path:
    return Path(BASE_PATH) / "settings.json"


def load_settings() -> dict:
    #Read settings.json into state.config. Returns {} on failure.
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            state.config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state.config = {}
    i18n.set_lang(state.config.get("app_language", "english"))
    return state.config


def _coerce_value(key: str, raw_value, existing: dict) -> object:
    """
    Convert a value coming from the GUI form into the type it already has in
    settings.json (e.g. keep floats as floats, bools as bools).
    """
    current = existing.get(key)

    #Booleans stay booleans (checkbox sends true/false directly).
    if isinstance(current, bool):
        return bool(raw_value)

    #Match a stored number: int vs float (e.g. tts_speed=1.0 stays float).
    if isinstance(current, (int, float)):
        try:
            value = float(raw_value)
            #Keep decimals if the user typed them, otherwise respect stored type.
            if "." in str(raw_value) or isinstance(current, float):
                return value
            return int(value)
        except (TypeError, ValueError):
            return current

    #Anything else falls back to a string.
    return str(raw_value)


def save_settings(updates: dict) -> None:
    """
    Merge only the changed values from the GUI into settings.json.
    Each incoming value is coerced to match the type already stored.
    """
    config = state.config if state.config else load_settings()

    for key, value in updates.items():
        if key.startswith("_"): #filter out comment keys in json
            continue
        config[key] = _coerce_value(key, value, config)

    with open(settings_path(), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    state.config = config
    i18n.set_lang(config.get("app_language", "english"))


#Front end
gui_dir = Path(BASE_PATH) / "gui"
gui_dir.mkdir(exist_ok=True)


#Only one native file dialog at a time (Tcl interpreters are single-threaded)
_dialog_lock = threading.Lock()


def _browse_sync(type: str, ext: str) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if type == "folder":
            path = filedialog.askdirectory(title="Select Folder", parent=root)
        else:
            filters = []
            if ext:
                filters.extend(
                    (f"{e.upper()} files", f"*.{e}")
                    for e in (x.strip() for x in ext.split(",") if x.strip())
                )
            filters.append(("All files", "*.*"))
            path = filedialog.askopenfilename(title="Select File", filetypes=filters, parent=root)
    finally:
        root.destroy()
    return path or ""


@app.get("/api/browse")
async def browse_path(type: str = "folder", ext: str = ""):
    """Open a native file/folder dialog and return the selected path."""
    if not _dialog_lock.acquire(blocking=False):
        return {"path": ""}
    try:
        path = await asyncio.to_thread(_browse_sync, type, ext)
    except Exception as e:
        print(f"{RED}File dialog failed: {e}{RESET}")
        return {"path": ""}
    finally:
        _dialog_lock.release()
    return {"path": path}


@app.get("/")
async def index():
    """Serve the GUI page."""
    return FileResponse(str(gui_dir / "index.html"))


app.mount("/gui", StaticFiles(directory=str(gui_dir)), name="gui")


@app.middleware("http")
async def no_cache_static(request: dict, call_next):
    """
    Force browsers to revalidate GUI files (html/css/js) on every load.
    Without this, a restart may keep serving stale cached JS/CSS.
    """
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/gui"):
        response.headers["Cache-Control"] = "no-cache"
    return response


#Rest of the api
@app.get("/api/settings")
async def get_settings():
    """Return the current settings to populate the settings panel."""
    config = state.config if state.config else load_settings()
    return config


@app.post("/api/settings")
async def apply_settings(data: dict):
    """
    Apply settings changed in the GUI.
    The GUI only sends the values that actually changed, so we merge them
    into the existing config and persist back to settings.json.
    """
    save_settings(data)
    return {"ok": True, "config": state.config}


#Editable text files (personality, TTS instructions, voice design)
TEXT_FILES = {
    "personality": Path(BASE_PATH) / "personality.txt",
    "tts_instructions": Path(BASE_PATH) / "openai-TTS-instructions.txt",
    "voice_design": Path(BASE_PATH) / "Data" / "omnivoice-design.txt",
    "reference": Path(BASE_PATH) / "Data" / "reference.txt",
}


@app.get("/api/text/{name}")
async def get_text_file(name: str):
    """Return the current content of an editable text file."""
    path = TEXT_FILES.get(name)
    if path is None:
        return JSONResponse(status_code=404, content={"error": "unknown file"})
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    return {"name": name, "text": text}


@app.post("/api/text/{name}")
async def set_text_file(name: str, data: dict):
    """Save the content of an editable text file."""
    path = TEXT_FILES.get(name)
    if path is None:
        return JSONResponse(status_code=404, content={"error": "unknown file"})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(data.get("text", "")), encoding="utf-8")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    return {"ok": True}


#Environment variables (.env)
ENV_PATH = Path(BASE_PATH) / ".env"


def _parse_env_file(path: Path) -> dict:
    """Read a .env file into a dict of key=value pairs."""
    result = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def _write_env_file(path: Path, env: dict) -> None:
    """Write a dict back to a .env file, preserving key order."""
    lines = [f"{k}={v}" for k, v in env.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@app.get("/api/env")
async def get_env():
    """Return the current .env values (API keys)."""
    return _parse_env_file(ENV_PATH)


@app.post("/api/env")
async def set_env(data: dict):
    """Merge changed values into .env and reload into os.environ."""
    env = _parse_env_file(ENV_PATH)
    for key, value in data.items():
        if key.startswith("_"):
            continue
        env[key] = str(value)
        os.environ[key] = str(value)
    _write_env_file(ENV_PATH, env)
    return {"ok": True, "env": env}


@app.post("/api/start")
async def start_service():
    """Initialize all AI components and mark the service as running."""
    await _initialize()
    return {"ok": True, "running": state.running}


@app.post("/api/stop")
async def stop_service():
    """Shut down all AI components cleanly."""
    await _shutdown()
    return {"ok": True, "running": state.running}


@app.get("/api/status")
async def get_status():
    """Return whether the AI service is currently running."""
    voice_mode = state.user_input.user_input_service if state.user_input else None
    return {"running": state.running, "voice_mode": voice_mode}


#Websocket
@app.websocket("/ws")
async def chat_socket(ws: WebSocket):
    """
    Real-time chat channel. The GUI sends {"type":"chat","message":"..."}
    and receives user/ai message frames back.
    """
    await ws.accept()
    clients.add(ws)
    _log(i18n.t("ws_connected"))

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "start":
                try:
                    await _initialize()
                    # Let queued log broadcasts flush before signaling completion.
                    await asyncio.sleep(0.01)
                    if state.running:
                        voice_mode = state.user_input.user_input_service if state.user_input else None
                        await ws.send_json(
                            {"type": "status_update", "payload": {"running": True, "voice_mode": voice_mode}}
                        )
                    else:
                        await ws.send_json(
                            {"type": "crash", "payload": {}}
                        )
                except Exception as e:
                    _log(f"{RED}[SERVER ERROR] {e}{RESET}")
                    _log(f"{RED}{i18n.t('crash')}{RESET}")
                    await ws.send_json(
                        {"type": "crash", "payload": {}}
                    )

            elif msg_type == "stop":
                await _shutdown()
                await asyncio.sleep(0.01)
                await ws.send_json(
                    {"type": "status_update", "payload": {"running": False, "voice_mode": None}}
                )

            elif msg_type == "chat":
                text = payload.get("message") or payload.get("text", "")
                if text:
                    await _handle_message(ws, text)

            elif msg_type == "mic":
                await _handle_mic(ws, payload)

            elif msg_type == "settings_update":
                save_settings(payload)

            elif msg_type == "ping":
                await ws.send_json({"type": "pong", "payload": {}})

    except WebSocketDisconnect:
        _log(i18n.t("ws_disconnected"))
    except Exception as e:
        _log(f"[WS Error]: {e}")
    finally:
        clients.discard(ws)
        mic_rate.pop(ws, None)


#Chat Logic
def _run_coroutine(coro):
    """Run an async function to completion inside a worker thread."""
    return asyncio.run(coro)


async def _handle_message(ws: WebSocket, text: str) -> None:
    """
    Process one chat message independently through the pipeline:
    chatbot response -> VTS emotion -> TTS playback.
    Slow/blocking stages (TTS audio) run in a background task so they never
    freeze the WebSocket. The GUI shows "Generating response" / "Generating TTS"
    notifications while each stage runs, and a "tts_done" message is sent when
    the voice playback finishes.
    """
    _log(i18n.t("chat_received", text=text))

    if state.chat_bot is None:
        await ws.send_json(
            {
                "type": "chat_response",
                "payload": {
                    "text": "ChatBot is not initialized. Start the service first.",
                    "sender": "bot"
                }
            }
        )
        return

    # Block voice input while this message is processed end-to-end
    # (thinking -> TTS generation -> playback). Unlocked via tts_done.
    state.ai_busy = True

    # Stage 1: chatbot is thinking
    await ws.send_json(
        {"type": "chat_stage", "payload": {"stage": "thinking", "text": "Generating answer..."}}
    )

    try:
        response_text, detected_emotion = await asyncio.to_thread(
            state.chat_bot.get_chatbot_response, text
        )
    except Exception as e:
        _log(f"{RED}{i18n.t('chatbot_error', e=e)}{RESET}")
        state.ai_busy = False  # don't leave the input locked forever
        await ws.send_json({"type": "tts_done", "payload": {}})
        return

    _log(i18n.t("bot_response", text=response_text))

    # Resolve the emotion now (chatbot's structured label, keyword analyzer as
    # fallback) but only apply it once the voice actually starts playing.
    pending_emotion = detected_emotion
    if state.vts is not None and pending_emotion is None:
        try:
            pending_emotion = state.vts.analyze_dominant_emotion(response_text)
        except Exception as e:
            _log(f"{ORANGE}{i18n.t('vts_emotion_error', e=e)}{RESET}")
    if pending_emotion:
        _log(i18n.t("emotion", emotion=pending_emotion))

    # Stage 2: generating the voice
    if state.tts is not None:
        await ws.send_json(
            {"type": "chat_stage", "payload": {"stage": "voice", "text": "Generating TTS..."}}
        )

        async def _speak_and_reset():
            loop = asyncio.get_event_loop()
            playback_started = False

            def _on_playback_start():
                nonlocal playback_started
                playback_started = True
                asyncio.run_coroutine_threadsafe(
                    ws.send_json({"type": "chat_stage", "payload": {"stage": "speaking", "text": "Speaking..."}}),
                    loop
                )
                # emote exactly while the avatar is speaking
                if state.vts is not None and pending_emotion:
                    asyncio.run_coroutine_threadsafe(
                        state.vts.trigger_hotkey(pending_emotion), loop
                    )

            def _on_playback_end():
                if state.vts is not None:
                    asyncio.run_coroutine_threadsafe(
                        state.vts.trigger_hotkey("Neutral"), loop
                    )

            state.tts.on_playback_start = _on_playback_start
            state.tts.on_playback_end = _on_playback_end
            try:
                await asyncio.to_thread(_run_coroutine, state.tts.tts_say(response_text))
            except Exception as e:
                _log(f"{RED}{i18n.t('tts_error', e=e)}{RESET}")
            finally:
                state.tts.on_playback_start = None
                state.tts.on_playback_end = None
                # The AI finished speaking (or TTS failed): unlock input and go
                # back to waiting for the wake word.
                state.ai_busy = False
                try:
                    await ws.send_json({"type": "tts_done", "payload": {}})
                except Exception:
                    pass
                if not playback_started and state.vts is not None:
                    try:
                        await state.vts.trigger_hotkey("Neutral")
                    except Exception as e:
                        _log(f"{ORANGE}{i18n.t('vts_neutral_error', e=e)}{RESET}")

        asyncio.create_task(_speak_and_reset())
    else:
        # No TTS configured: nothing will speak, so unlock right away.
        state.ai_busy = False
        await ws.send_json({"type": "tts_done", "payload": {}})

    # Final answer replaces the temporary messages, playback continues behind it.
    await ws.send_json(
        {
            "type": "chat_response",
            "payload": {
                "text": response_text,
                "sender": "bot"
            }
        }
    )


async def _handle_mic(ws: WebSocket, payload: dict) -> None:
    """
    Handle audio chunks streamed from the browser's microphone.
    The browser captures raw PCM, base64-encodes it, and the server resamples
    it to 16 kHz then feeds it to the configured STT / wake word pipeline.

    Event flow:
      speech (push-to-talk):  init -> start -> audio* -> stop
      wake_word:              init -> audio* (continuous stream)
    """
    ui = state.user_input
    if ui is None:
        return

    event = payload.get("event")

    if event == "init":
        try:
            mic_rate[ws] = int(payload.get("rate") or 16000)
        except (TypeError, ValueError):
            mic_rate[ws] = 16000
        return

    # Push-to-talk control events carry no audio data, so handle them first.
    if ui.user_input_service == "speech":
        if event == "start":
            if state.ai_busy:
                _log(f"{ORANGE}{i18n.t('voice_blocked')}{RESET}")
            else:
                ui.start_utterance()
            return
        if event == "stop":
            if state.ai_busy:
                ui.end_utterance()  # discard anything buffered
                await ws.send_json({"type": "speech_result", "payload": {"text": ""}})
                return
            try:
                frames = ui.utterance_frames()
                stats = ui.utterance_stats(frames)
                if stats["chunks"]:
                    _stats = dict(
                        chunks=stats["chunks"], bytes=stats["bytes"],
                        seconds=f"{stats['seconds']:.2f}",
                        peak=f"{stats['peak']:.0f}", rms=f"{stats['rms']:.0f}",
                    )
                    _log(f"{YELLOW}{i18n.t('voice_stats', **_stats)}{RESET}")
                    dump_path = os.path.join(BASE_PATH, "debug_utterance.wav")
                    await asyncio.to_thread(ui.dump_utterance, dump_path, frames)
                    _log(f"{YELLOW}{i18n.t('voice_saved', path=dump_path)}{RESET}")
                else:
                    _log(f"{YELLOW}{i18n.t('voice_no_chunks')}{RESET}")

                text = await asyncio.to_thread(ui._transcribe_frames, frames, True)
                if not text and ui.stt_service == "whisper" and ui.local_stt._model is not None:
                    _log(f"{YELLOW}{i18n.t('vad_retry')}{RESET}")
                    text = await asyncio.to_thread(ui._transcribe_frames, frames, False)
                ui.end_utterance()  # clear the buffer

                if text:
                    _log(f"{GREEN}{i18n.t('voice_text', text=text)}{RESET}")
                else:
                    _log(f"{ORANGE}{i18n.t('voice_no_speech')}{RESET}")
                await ws.send_json({"type": "speech_result", "payload": {"text": text}})
            except Exception as e:
                _log(f"{RED}{i18n.t('voice_input_error', e=e)}{RESET}")
            return

    raw = base64.b64decode(payload.get("data") or "")
    if not raw:
        return

    rate = mic_rate.get(ws, 16000)
    pcm = ui.resample16k(raw, rate)

    try:
        if ui.user_input_service == "speech":
            if event == "audio":
                ui.add_audio(pcm)

        elif ui.user_input_service == "wake_word":
            # While the AI is generating/speaking, all input is blocked. The
            # wake word model keeps running just so we can warn the user that
            # they must wait; it never re-enters listening mode from here.
            if state.ai_busy:
                if not ui.listening and ui.feed_wake_audio(pcm):
                    ui.wake_word.reset()
                    _log(f"{ORANGE}{i18n.t('wake_ignored')}{RESET}")
                    await ws.send_json({"type": "wake_busy", "payload": {}})
                return

            if not ui.listening:
                if ui.feed_wake_audio(pcm):
                    ui.wake_word.reset()  # clear streaming state so it can't double-fire
                    ui.start_listening()
                    _log(f"{GREEN}{i18n.t('wake_detected')}{RESET}")
                    if ui.wake_word.confirm_sound:
                        await asyncio.to_thread(ui.wake_word.play_confirm_sound)
                    await ws.send_json({"type": "wake_detected", "payload": {}})
            else:
                if ui.add_listen_audio(pcm):
                    frames = ui.listen_frames()
                    stats = ui.utterance_stats(frames)
                    if stats["chunks"]:
                        _ustats = dict(
                            chunks=stats["chunks"], bytes=stats["bytes"],
                            seconds=f"{stats['seconds']:.2f}",
                            peak=f"{stats['peak']:.0f}", rms=f"{stats['rms']:.0f}",
                        )
                        _log(f"{YELLOW}{i18n.t('wake_utterance', **_ustats)}{RESET}")
                        dump_path = os.path.join(BASE_PATH, "debug_utterance.wav")
                        await asyncio.to_thread(ui.dump_utterance, dump_path, frames)
                    text = await asyncio.to_thread(ui.stop_listening)
                    ui.wake_word.reset()  # fresh detection state for the next wake word
                    if text:
                        # Lock input immediately (before the client's chat round
                        # trip) so no new wake word can slip in mid-transition.
                        state.ai_busy = True
                        _log(f"{GREEN}{i18n.t('voice_text', text=text)}{RESET}")
                    else:
                        _log(f"{ORANGE}{i18n.t('voice_no_speech')}{RESET}")
                    await ws.send_json({"type": "speech_result", "payload": {"text": text}})
    except Exception as e:
        _log(f"{RED}{i18n.t('voice_input_error', e=e)}{RESET}")


async def _initialize() -> None:
    """Build ChatBot, TTS, VTS and the local LLM server from settings.json."""
    async with state.lock:
        if state.running:
            return

        config = state.config if state.config else load_settings()
        _log(f"{YELLOW}{i18n.t('start_services')}{RESET}")

        try:
            # 1. ChatBot
            if "ChatBot" in globals() and ChatBot is not None:
                try:
                    service = config.get("chatbot_service", "openai")
                    _log(f"{YELLOW}{i18n.t('init_chatbot', service=service)}{RESET}")
                    state.chat_bot = ChatBot(
                        chat_bot_service=service,
                        openai_model=config.get("openai_model", "gpt-4o-mini"),
                        detailed_logs=config.get("logs", True),
                        model_path=config.get("model_dir", ""),
                        remember_conversation=config.get("remember_conversation", False)
                    )
                    await asyncio.to_thread(state.chat_bot.initialize)
                    _log(f"{GREEN}{i18n.t('chatbot_ok')}{RESET}")
                except Exception as e:
                    _log(f"{RED}{i18n.t('chatbot_fail', e=e)}{RESET}")
                    state.chat_bot = None

            # 2. Local LLM Server (only needed for the "local" chatbot service)
            if (
                config.get("chatbot_service", "openai") == "local"
                and "RunLocalServer" in globals()
                and RunLocalServer is not None
            ):
                try:
                    _log(f"{YELLOW}{i18n.t('start_llm')}{RESET}")
                    state.local_server = RunLocalServer(
                        config.get("show_ollama_server_logs", False),
                        config.get("model_dir", ""),
                        config.get("llama_server_device", "cuda")
                    )
                    await state.local_server.launch_server(timeout=30)
                    _log(f"{GREEN}{i18n.t('llm_ok')}{RESET}")
                except Exception as e:
                    _log(f"{RED}{i18n.t('llm_fail', e=e)}{RESET}")
                    state.local_server = None

            # 3. TTS Engine
            if "TTS" in globals() and TTS is not None:
                try:
                    service = config.get("tts_service", "gtts")
                    _log(f"{YELLOW}{i18n.t('init_tts', service=service)}{RESET}")
                    state.tts = TTS(
                        tts_language=config.get("tts_language", "en"),
                        tts_service=service,
                        chatbot_name=config.get("chatbot_name", "Nous"),
                        openai_tts_model=config.get("openai_tts_model", "gpt-4o-mini-tts"),
                        openai_tts_voice=config.get("openai_tts_voice", "ash"),
                        tts_voice=config.get("tts_voice", "ash"),
                        tts_speed=config.get("tts_speed", 1.0),
                        voice_cloning=config.get("voice_cloning", False),
                        voice_design=config.get("voice_design", False),
                        omnivoice_device=config.get("omnivoice_device", "cuda"),
                        detailed_logs=config.get("logs", True),
                        play_only_cable=config.get("play_only_cable", False),
                        gain=config.get("gain", 1.0)
                    )
                    await asyncio.to_thread(state.tts.initialize)
                    _log(f"{GREEN}{i18n.t('tts_ok')}{RESET}")
                except Exception as e:
                    _log(f"{RED}{i18n.t('tts_fail', e=e)}{RESET}")
                    state.tts = None

            # 4. VTube Studio Plugin
            if "VtubeControll" in globals() and VtubeControll is not None:
                try:
                    _log(f"{YELLOW}{i18n.t('connecting_vts')}{RESET}")
                    state.vts = VtubeControll(
                        detailed_logs=config.get("logs", True),
                        log_callback=_log
                    )
                    await state.vts.initialize()
                    _log(f"{GREEN}{i18n.t('vts_ok')}{RESET}")
                except Exception as e:
                    _log(f"{RED}{i18n.t('vts_fail', e=e)}{RESET}")
                    state.vts = None

            # 5. Voice input (speech / wake word)
            if "UserInput" in globals() and UserInput is not None:
                try:
                    ui_service = config.get("user_input_service", "console")
                    if ui_service in ("speech", "wake_word"):
                        _log(f"{YELLOW}{i18n.t('init_voice', service=ui_service)}{RESET}")
                        state.user_input = UserInput(
                            user_input_service=ui_service,
                            detailed_logs=config.get("logs", True),
                            app_language=config.get("app_language", "english"),
                            wake_word_model_path=os.path.join(
                                BASE_PATH,
                                config.get("wake_word_model", "models/openwakeword/hey_jarvis_v0.1.onnx"),
                            ),
                            wake_word_threshold=config.get("wake_word_threshold", 0.5),
                            wake_word_confirm_sound=config.get("wake_word_confirm_sound", True),
                            stt_service=config.get("stt_service", "whisper"),
                            stt_device=config.get("stt_device", "cpu"),
                            stt_compute_type=config.get("stt_compute_type", "int8"),
                            stt_language=config.get("stt_language", "en"),
                            silence_duration=config.get("silence_duration", 1.5),
                        )
                        if ui_service == "wake_word":
                            await asyncio.to_thread(state.user_input.setup_wake_word)
                        if config.get("stt_service", "whisper") == "whisper":
                            await asyncio.to_thread(state.user_input.setup_whisper)
                        _log(f"{GREEN}{i18n.t('voice_ok')}{RESET}")
                except Exception as e:
                    _log(f"{RED}{i18n.t('voice_fail', e=e)}{RESET}")
                    state.user_input = None

            state.running = True
            _log(f"{GREEN}{i18n.t('all_online')}{RESET}")

        except Exception as e:
            _log(f"{RED}[SERVER ERROR] {e}{RESET}")
            _log(f"{RED}{i18n.t('crash')}{RESET}")
            await _broadcast({"type": "crash", "payload": {}})


async def _shutdown() -> None:
    """Stop the LLM server, disconnect VTS, and drop the ChatBot/TTS objects."""
    async with state.lock:
        _log(f"{YELLOW}{i18n.t('stopping')}{RESET}")

        # Clean VTube Studio disconnect
        if state.vts:
            try:
                if hasattr(state.vts, "vts") and state.vts.vts is not None:
                    if hasattr(state.vts.vts, "close"):
                        await state.vts.vts.close()
                        _log(f"{GREEN}{i18n.t('vts_disconnected')}{RESET}")
                    else:
                        _log(f"{YELLOW}{i18n.t('vts_skip_close')}{RESET}")
            except Exception as e:
                _log(f"{RED}{i18n.t('vts_error', e=e)}{RESET}")
            state.vts = None

        # Clean Local LLM stop
        if state.local_server:
            try:
                if hasattr(state.local_server, "stop_server"):
                    state.local_server.stop_server()
                elif hasattr(state.local_server, "stop"):
                    state.local_server.stop()
                _log(f"{GREEN}{i18n.t('llm_stopped')}{RESET}")
            except Exception as e:
                _log(f"{RED}{i18n.t('local_server_error', e=e)}{RESET}")
            state.local_server = None

        state.chat_bot = None
        state.tts = None
        state.ai_busy = False

        # Clean voice input
        if state.user_input:
            try:
                state.user_input.cleanup()
                _log(f"{GREEN}{i18n.t('voice_stopped')}{RESET}")
            except Exception as e:
                _log(f"{RED}{i18n.t('user_input_error', e=e)}{RESET}")
            state.user_input = None

        state.running = False
        _log(f"{GREEN}{i18n.t('shut_down')}{RESET}")


#Main
def _open_browser() -> None:
    #Open the GUI in a new browser tab once the server is up.
    webbrowser.open("http://127.0.0.1:5050", new=2)


def _port_in_use(host: str = "127.0.0.1", port: int = 5050) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


if __name__ == "__main__":
    load_settings()
    try:
        if _port_in_use():
            print(f"{RED}Port 5050 is already in use. Another instance of NOUS (or another program) is running.{RESET}")
            print(f"{ORANGE}Close it first, or the GUI cannot start.{RESET}")
        else:
            _log("Nous Intelligence GUI -> http://localhost:5050")
            threading.Timer(1.5, _open_browser).start()
            uvicorn.run(app, host="127.0.0.1", port=5050, log_config=LOGGING_CONFIG)
    except KeyboardInterrupt:
        print(f"{YELLOW}Server stopped by user.{RESET}")
    except Exception as e:
        print(f"{RED}Fatal error: {e}{RESET}")
    finally:
        #keep the terminal open so crash/shutdown messages can be read
        input(f"{ORANGE}Press Enter to close this window...{RESET}")
