
import asyncio
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
    return {"running": state.running}


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
                await ws.send_json(
                    {"type": "status_update", "payload": {"running": True}}
                )

            elif msg_type == "stop":
                await _shutdown()
                await asyncio.sleep(0.01)
                await ws.send_json(
                    {"type": "status_update", "payload": {"running": False}}
                )

            elif msg_type == "chat":
                text = payload.get("message") or payload.get("text", "")
                if text:
                    await _handle_message(ws, text)

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


#Chat Logic
def _run_coroutine(coro):
    """Run an async function to completion inside a worker thread."""
    return asyncio.run(coro)


async def _handle_message(ws: WebSocket, text: str) -> None:
    """
    Process one chat message independently through the pipeline:
    chatbot response -> VTS emotion -> TTS playback.
    Slow/blocking stages (TTS audio) run in a thread so they never freeze
    the WebSocket. Temporary "stage" messages are shown while the AI works
    (thinking, then generating TTS), and the real answer is sent last.
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
                # Reset the avatar emotion after speaking
                if state.vts is not None:
                    try:
                        await state.vts.trigger_hotkey("Neutral")
                    except Exception as e:
                        _log(f"{ORANGE}[VTS NEUTRAL ERROR]: {e}{RESET}")

        # Wait for the voice to finish so the "Generating TTS..." stage message
        # is actually visible in the chat panel before the answer is shown.
        await _speak_and_reset()

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
