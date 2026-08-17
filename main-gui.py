
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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from paths import BASE_PATH

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


#Front end
gui_dir = Path(BASE_PATH) / "gui"
gui_dir.mkdir(exist_ok=True)


@app.get("/api/browse")
async def browse_path(type: str = "folder", ext: str = ""):
    """Open a tkinter file/folder dialog and return the selected path."""
    import subprocess, sys

    lines = [
        "import tkinter as tk",
        "from tkinter import filedialog",
        "root = tk.Tk()",
        "root.withdraw()",
        'root.attributes("-topmost", True)',
    ]
    if type == "folder":
        lines.append('path = filedialog.askdirectory(title="Select Folder")')
    else:
        if ext:
            ext_list = [e.strip() for e in ext.split(",")]
            ft = ", ".join(f'("{e.upper()} files", "*.{e}")' for e in ext_list)
            lines.append(
                f'path = filedialog.askopenfilename(title="Select File", '
                f'filetypes=[{ft}, ("All files", "*.*")])'
            )
        else:
            lines.append('path = filedialog.askopenfilename(title="Select File")')
    lines.append("root.destroy()")
    lines.append("print(path)")

    script = "\n".join(lines)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=300,
    )
    return {"path": result.stdout.strip()}


@app.get("/")
async def index():
    """Serve the GUI page."""
    return FileResponse(str(gui_dir / "index.html"))


app.mount("/gui", StaticFiles(directory=str(gui_dir)), name="gui")


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
    _log("[WS] Cliente conectado.")

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "start":
                await _initialize()
                # Let queued log broadcasts flush before signaling completion.
                await asyncio.sleep(0.01)
                voice_mode = state.user_input.user_input_service if state.user_input else None
                await ws.send_json(
                    {"type": "status_update", "payload": {"running": True, "voice_mode": voice_mode}}
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
        _log("[WS] Cliente desconectado.")
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
    _log(f"[CHAT RECIBIDO]: {text}")

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

    # Stage 1: chatbot is thinking
    await ws.send_json(
        {"type": "chat_stage", "payload": {"stage": "thinking", "text": "Generating answer..."}}
    )

    response_text = await asyncio.to_thread(state.chat_bot.get_chatbot_response, text)
    _log(f"[BOT RESPONSE]: {response_text}")

    # Trigger the avatar emotion in the background so it can't block the chat.
    if state.vts is not None:
        try:
            emotion = state.vts.analyze_dominant_emotion(response_text)
            asyncio.create_task(state.vts.trigger_hotkey(emotion))
        except Exception as e:
            _log(f"{ORANGE}[VTS EMOTION ERROR]: {e}{RESET}")

    # Stage 2: generating the voice
    if state.tts is not None:
        await ws.send_json(
            {"type": "chat_stage", "payload": {"stage": "voice", "text": "Generating TTS..."}}
        )

        async def _speak_and_reset():
            try:
                # TTS does blocking audio work (generation + playback), so run it
                # in a thread. It keeps playing while the answer is shown.
                await asyncio.to_thread(_run_coroutine, state.tts.tts_say(response_text))
            except Exception as e:
                _log(f"{RED}[TTS ERROR]: {e}{RESET}")
            finally:
                try:
                    # Tell the GUI to drop the "Generating TTS" notification.
                    await ws.send_json({"type": "tts_done", "payload": {}})
                except Exception:
                    pass
                # Reset the avatar emotion after speaking
                if state.vts is not None:
                    try:
                        await state.vts.trigger_hotkey("Neutral")
                    except Exception as e:
                        _log(f"{ORANGE}[VTS NEUTRAL ERROR]: {e}{RESET}")

        asyncio.create_task(_speak_and_reset())

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
            ui.start_utterance()
            return
        if event == "stop":
            try:
                frames = ui.utterance_frames()
                stats = ui.utterance_stats(frames)
                if stats["chunks"]:
                    _log(f"{YELLOW}[VOICE] Received {stats['chunks']} chunks, {stats['bytes']} bytes "
                         f"(~{stats['seconds']:.2f}s) | Peak {stats['peak']:.0f}, RMS {stats['rms']:.0f}{RESET}")
                    dump_path = os.path.join(BASE_PATH, "debug_utterance.wav")
                    await asyncio.to_thread(ui.dump_utterance, dump_path, frames)
                    _log(f"{YELLOW}[VOICE] Saved audio to {dump_path}{RESET}")
                else:
                    _log(f"{YELLOW}[VOICE] Stop received, but NO audio chunks arrived.{RESET}")

                text = await asyncio.to_thread(ui._transcribe_frames, frames, True)
                if not text and ui.stt_service == "whisper" and ui.local_stt._model is not None:
                    _log(f"{YELLOW}[VOICE] VAD filtered everything; retrying without VAD...{RESET}")
                    text = await asyncio.to_thread(ui._transcribe_frames, frames, False)
                ui.end_utterance()  # clear the buffer

                if text:
                    _log(f"{GREEN}[VOICE TEXT]: {text}{RESET}")
                else:
                    _log(f"{ORANGE}[VOICE] No speech detected.{RESET}")
                await ws.send_json({"type": "speech_result", "payload": {"text": text}})
            except Exception as e:
                _log(f"{RED}[VOICE INPUT ERROR]: {e}{RESET}")
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
            if not ui.listening:
                if ui.feed_wake_audio(pcm):
                    ui.start_listening()
                    _log(f"{GREEN}[WAKE WORD] Detected. Listening...{RESET}")
                    if ui.wake_word.confirm_sound:
                        await asyncio.to_thread(ui.wake_word.play_confirm_sound)
                    await ws.send_json({"type": "wake_detected", "payload": {}})
            else:
                if ui.add_listen_audio(pcm):
                    text = await asyncio.to_thread(ui.stop_listening)
                    if text:
                        _log(f"{GREEN}[VOICE TEXT]: {text}{RESET}")
                    else:
                        _log(f"{ORANGE}[VOICE] No speech detected.{RESET}")
                    await ws.send_json({"type": "speech_result", "payload": {"text": text}})
    except Exception as e:
        _log(f"{RED}[VOICE INPUT ERROR]: {e}{RESET}")


async def _initialize() -> None:
    """Build ChatBot, TTS, VTS and the local LLM server from settings.json."""
    async with state.lock:
        if state.running:
            return

        config = state.config if state.config else load_settings()
        _log(f"{YELLOW}[SERVER] Starting AI Services...{RESET}")

        # 1. ChatBot
        if "ChatBot" in globals() and ChatBot is not None:
            try:
                service = config.get("chatbot_service", "openai")
                _log(f"{YELLOW}[SERVER] Initializing ChatBot ({service})...{RESET}")
                state.chat_bot = ChatBot(
                    chat_bot_service=service,
                    openai_model=config.get("openai_model", "gpt-4o-mini"),
                    detailed_logs=config.get("logs", True),
                    model_path=config.get("model_dir", ""),
                    remember_conversation=config.get("remember_conversation", False)
                )
                await asyncio.to_thread(state.chat_bot.initialize)
                _log(f"{GREEN}[SERVER] ChatBot initialized successfully.{RESET}")
            except Exception as e:
                _log(f"{RED}[SERVER ERROR] ChatBot initialization failed: {e}{RESET}")
                state.chat_bot = None

        # 2. Local LLM Server (only needed for the "local" chatbot service)
        if (
            config.get("chatbot_service", "openai") == "local"
            and "RunLocalServer" in globals()
            and RunLocalServer is not None
        ):
            try:
                _log(f"{YELLOW}[SERVER] Starting local LLM server...{RESET}")
                state.local_server = RunLocalServer(
                    config.get("show_ollama_server_logs", False),
                    config.get("model_dir", "")
                )
                await state.local_server.launch_server(timeout=30)
                _log(f"{GREEN}[SERVER] Local LLM server running successfully.{RESET}")
            except Exception as e:
                _log(f"{RED}[SERVER ERROR] Could not start local LLM: {e}{RESET}")
                state.local_server = None

        # 3. TTS Engine
        if "TTS" in globals() and TTS is not None:
            try:
                service = config.get("tts_service", "gtts")
                _log(f"{YELLOW}[SERVER] Initializing TTS ({service})...{RESET}")
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
                _log(f"{GREEN}[SERVER] TTS Engine ready successfully.{RESET}")
            except Exception as e:
                _log(f"{RED}[SERVER ERROR] TTS initialization failed: {e}{RESET}")
                state.tts = None

        # 4. VTube Studio Plugin
        if "VtubeControll" in globals() and VtubeControll is not None:
            try:
                _log(f"{YELLOW}[SERVER] Connecting to VTube Studio...{RESET}")
                state.vts = VtubeControll(
                    detailed_logs=config.get("logs", True)
                )
                await state.vts.initialize()
                _log(f"{GREEN}[SERVER] VTube Studio connected successfully.{RESET}")
            except Exception as e:
                _log(f"{RED}[SERVER ERROR] VTube Studio failed to connect: {e}{RESET}")
                state.vts = None

        # 5. Voice input (speech / wake word)
        if "UserInput" in globals() and UserInput is not None:
            try:
                ui_service = config.get("user_input_service", "console")
                if ui_service in ("speech", "wake_word"):
                    _log(f"{YELLOW}[SERVER] Initializing voice input ({ui_service})...{RESET}")
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
                    _log(f"{GREEN}[SERVER] Voice input ready.{RESET}")
            except Exception as e:
                _log(f"{RED}[SERVER ERROR] Voice input initialization failed: {e}{RESET}")
                state.user_input = None

        state.running = True
        _log(f"{GREEN}[SERVER] All requested AI services are online.{RESET}")


async def _shutdown() -> None:
    """Stop the LLM server, disconnect VTS, and drop the ChatBot/TTS objects."""
    async with state.lock:
        _log(f"{YELLOW}[SERVER] Stopping AI services...{RESET}")

        # Clean VTube Studio disconnect
        if state.vts:
            try:
                if hasattr(state.vts, "vts") and state.vts.vts is not None:
                    if hasattr(state.vts.vts, "close"):
                        await state.vts.vts.close()
                        _log(f"{GREEN}[SERVER] VTube Studio disconnected.{RESET}")
                    else:
                        _log(f"{YELLOW}[SERVER] VTS has no close() method, skipping.{RESET}")
            except Exception as e:
                _log(f"{RED}[VTS ERROR]: {e}{RESET}")
            state.vts = None

        # Clean Local LLM stop
        if state.local_server:
            try:
                if hasattr(state.local_server, "stop_server"):
                    state.local_server.stop_server()
                elif hasattr(state.local_server, "stop"):
                    state.local_server.stop()
                _log(f"{GREEN}[SERVER] Local LLM server stopped.{RESET}")
            except Exception as e:
                _log(f"{RED}[LOCAL SERVER ERROR]: {e}{RESET}")
            state.local_server = None

        state.chat_bot = None
        state.tts = None

        # Clean voice input
        if state.user_input:
            try:
                state.user_input.cleanup()
                _log(f"{GREEN}[SERVER] Voice input stopped.{RESET}")
            except Exception as e:
                _log(f"{RED}[USER INPUT ERROR]: {e}{RESET}")
            state.user_input = None

        state.running = False
        _log(f"{GREEN}[SERVER] AI services shut down completely.{RESET}")


#Main
def _open_browser() -> None:
    #Open the GUI in a new browser tab once the server is up.
    webbrowser.open("http://127.0.0.1:5050", new=2)


if __name__ == "__main__":
    load_settings()
    _log("Nous Intelligence GUI -> http://localhost:5050")
    threading.Timer(1.5, _open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=5050, log_config=LOGGING_CONFIG)
