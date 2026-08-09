
import asyncio
import json
import sys
import threading
import webbrowser
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from paths import BASE_PATH

#Global state
class AppState:
    #Holds the runtime objects shared across requests.
    running = False # whether the AI service is started
    config = {} # loaded settings.json dict
    vts = None  # VtubeControll instance
    chat_bot = None # ChatBot instance
    local_server = None # RunLocalServer instance (local LLM)
    tts = None # TTS instance

state = AppState()

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
    print("[WS] Cliente conectado.")

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "start":
                await _initialize()
                await ws.send_json(
                    {"type": "status_update", "payload": {"running": True}}
                )

            elif msg_type == "stop":
                await _shutdown()
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
        print("[WS] Cliente desconectado.")
    except Exception as e:
        print(f"[WS Error]: {e}")


#Chat Logic
async def _handle_message(ws: WebSocket, text: str) -> None:
    """Process one chat message through the chatbot, then TTS + VTS."""
    print(f"[CHAT RECIBIDO]: {text}")
    response_text = f"Procesado: {text}"
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
    """Build VTS, ChatBot, local LLM server and TTS from the current config."""
    state.running = True
    print("[SERVER] Servicios de IA inicializados correctamente.")


async def _shutdown() -> None:
    """Stop the LLM server, disconnect VTS and drop the chat/tTS objects."""
    state.running = False
    print("[SERVER] Servicios de IA detenidos.")


#Main
def _open_browser() -> None:
    #Open the GUI in a new browser tab once the server is up.
    webbrowser.open("http://127.0.0.1:5050", new=2)


if __name__ == "__main__":
    load_settings()
    print("Nous Intelligence GUI -> http://localhost:5050")
    threading.Timer(1.5, _open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=5050, log_level="info")
