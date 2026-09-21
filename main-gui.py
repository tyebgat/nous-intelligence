
import asyncio
import base64
import json
import socket
import sys
import threading
import time
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from loguru import logger
import uvicorn

from paths import BASE_PATH
from logging_setup import setup_logging
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
    from TTS import TTS, warm_up_heavy_imports
except ImportError:
    TTS = None

try:
    from user_input import UserInput
except ImportError:
    UserInput = None

nous_task = None


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
    processing = False # True while an AI turn is in flight (thinking -> talking)
    cancel_event = None # threading.Event set when the user asks to interrupt
    _think_task = None # asyncio task running the chatbot call in a thread
    _speak_task = None # asyncio task speaking the reply (TTS)
    chat_tasks = set() # spawned _handle_message tasks (cancelled on disconnect)
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


#Running asyncio loop captured at startup (used to push loguru records
#from worker threads into the WebSocket broadcaster).
_loop_ref = None


def _gui_log_sink(message) -> None:
    """Loguru sink that forwards each record to the GUI over WebSocket.

    `str(message)` is the colored, fully formatted line shown in the
    terminal; the record's `level` and `message` drive the init status text.
    """
    record = message.record
    loop = _loop_ref
    if loop is None or not loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(
        _broadcast({
            "type": "log",
            "payload": {
                "line": str(message),
                "level": record["level"].name,
                "message": record["message"],
            },
        }),
        loop,
    )

#Fast api
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop_ref
    _loop_ref = asyncio.get_running_loop()
    yield
    _loop_ref = None


app = FastAPI(title="Nous Intelligence GUI", lifespan=lifespan)

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
        logger.error(f"File dialog failed: {e}")
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
    logger.info(i18n.t("ws_connected"))

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
                    logger.error(f"[SERVER ERROR] {e}")
                    logger.error(f"{i18n.t('crash')}")
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
                    # Run as a background task so this connection keeps reading
                    # messages while the AI thinks (e.g. an "interrupt" sent by
                    # the same socket must be handled mid-generation).
                    task = asyncio.create_task(_handle_message(ws, text))
                    state.chat_tasks.add(task)
                    task.add_done_callback(state.chat_tasks.discard)

            elif msg_type == "interrupt":
                await _interrupt_ai()

            elif msg_type == "mic":
                await _handle_mic(ws, payload)

            elif msg_type == "settings_update":
                save_settings(payload)

            elif msg_type == "ping":
                await ws.send_json({"type": "pong", "payload": {}})

    except WebSocketDisconnect:
        logger.info(i18n.t("ws_disconnected"))
    except Exception as e:
        logger.error(f"[WS Error]: {e}")
    finally:
        clients.discard(ws)
        mic_rate.pop(ws, None)
        # If this connection was driving an AI turn, abort it so no orphaned
        # generation keeps running (and cutting it also unblocks voice input).
        if state.processing:
            try:
                await _interrupt_ai()
            except Exception:
                pass
        for task in list(state.chat_tasks):
            task.cancel()
            state.chat_tasks.discard(task)


#Chat Logic
def _run_coroutine(coro):
    """Run an async function to completion inside a worker thread."""
    return asyncio.run(coro)


async def _interrupt_ai() -> None:
    """
    Abort the current AI turn: cancel any thinking request, cut any speech,
    reset the avatar and unlock input. Safe to call at any time, even when
    nothing is in flight.

    Ordering matters: cancelling the sub-tasks makes their cleanup/FINALLY
    run, and the GUI-unlocking broadcasts MUST go out before we touch
    anything that could hang (e.g. a dead VTS connection). Otherwise the
    client never learns the turn ended and stays stuck in "busy".
    """
    for task in (state._think_task, state._speak_task):
        if task is not None and not task.done():
            task.cancel()
    state._think_task = None
    state._speak_task = None

    if state.cancel_event is not None:
        state.cancel_event.set()
    state.ai_busy = False
    state.processing = False
    state.cancel_event = None

    # Cut any active speech. Synchronous (sd.stop()), cannot hang.
    if state.tts is not None:
        try:
            state.tts.stop()
        except Exception as e:
            logger.warning(f"{i18n.t('tts_error', e=e)}")

    # Tell every client NOW that the turn is over and input is unlocked.
    await _broadcast({"type": "chat_interrupted", "payload": {}})
    await _broadcast({"type": "tts_done", "payload": {}})

    # Don't leave the avatar emoting a reply that was just cancelled.
    # Timed out so an unresponsive VTS can never block the unlock above.
    if state.vts is not None:
        try:
            await asyncio.wait_for(state.vts.trigger_hotkey("Neutral"), timeout=3)
        except Exception as e:
            logger.warning(f"{i18n.t('vts_neutral_error', e=e)}")


async def _handle_message(ws: WebSocket, text: str) -> None:
    """
    Process one chat message independently through the pipeline:
    chatbot response -> VTS emotion -> TTS playback.
    Slow/blocking stages (TTS audio) run in a background task so they never
    freeze the WebSocket. The GUI shows "Generating response" / "Generating TTS"
    notifications while each stage runs, and a "tts_done" message is sent when
    the voice playback finishes.
    """
    logger.info(i18n.t("chat_received", text=text))

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

    if state.processing:
        # A previous turn is still in flight. The GUI turns the send button
        # into a stop button while busy, so this is only a safety net.
        logger.warning(f"{i18n.t('voice_blocked')}")
        await ws.send_json(
            {"type": "chat_stage", "payload": {"stage": "stopped", "text": ""}}
        )
        return

    # Block voice/chat input while this message is processed end-to-end
    # (thinking -> TTS generation -> playback). Unlocked via tts_done.
    state.processing = True
    state.ai_busy = True
    state.cancel_event = threading.Event()

    try:
        # Stage 1: chatbot is thinking
        await ws.send_json(
            {"type": "chat_stage", "payload": {"stage": "thinking", "text": "Generating answer..."}}
        )

        try:
            think_task = asyncio.create_task(
                asyncio.to_thread(state.chat_bot.get_chatbot_response, text, state.cancel_event)
            )
            state._think_task = think_task
            try:
                response_text, detected_emotion = await think_task
            except asyncio.CancelledError:
                # Interrupted while thinking; _interrupt_ai already unlocked us.
                state.processing = False
                return
            finally:
                state._think_task = None
        except Exception as e:
            logger.error(f"{i18n.t('chatbot_error', e=e)}")
            state.ai_busy = False  # don't leave the input locked forever
            state.processing = False
            await ws.send_json({"type": "tts_done", "payload": {}})
            return

        # No answer: the turn was aborted or the model returned nothing.
        if state.cancel_event is None or state.cancel_event.is_set() or not response_text:
            state.ai_busy = False
            state.processing = False
            await ws.send_json({"type": "tts_done", "payload": {}})
            return

        logger.info(i18n.t("bot_response", text=response_text))

        # Resolve the emotion now (chatbot's structured label, keyword analyzer
        # as fallback) but only apply it once the voice actually starts playing.
        pending_emotion = detected_emotion
        if state.vts is not None and pending_emotion is None:
            try:
                pending_emotion = state.vts.analyze_dominant_emotion(response_text)
            except Exception as e:
                logger.warning(f"{i18n.t('vts_emotion_error', e=e)}")
        if pending_emotion:
            logger.info(i18n.t("emotion", emotion=pending_emotion))

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
                except asyncio.CancelledError:
                    pass  # interrupted: state.tts.stop() already cut the audio
                except Exception as e:
                    logger.error(f"{i18n.t('tts_error', e=e)}")
                finally:
                    state.tts.on_playback_start = None
                    state.tts.on_playback_end = None
                    # The AI finished speaking (or TTS failed / was interrupted):
                    # unlock input and go back to waiting for the wake word.
                    state.ai_busy = False
                    state.processing = False
                    state._speak_task = None
                    try:
                        await ws.send_json({"type": "tts_done", "payload": {}})
                    except (Exception, asyncio.CancelledError):
                        pass
                    if not playback_started and state.vts is not None:
                        try:
                            await state.vts.trigger_hotkey("Neutral")
                        except Exception as e:
                            logger.warning(f"{i18n.t('vts_neutral_error', e=e)}")

            state._speak_task = asyncio.create_task(_speak_and_reset())
        else:
            # No TTS configured: nothing will speak, so unlock right away.
            state.ai_busy = False
            state.processing = False
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
    except asyncio.CancelledError:
        # Turn aborted mid-flight (interrupt or disconnect): _interrupt_ai()
        # unlocks input, cuts speech and resets the avatar.
        try:
            await _interrupt_ai()
        except Exception:
            pass
        raise
    except Exception as e:
        logger.error(f"{i18n.t('chatbot_error', e=e)}")
        # Don't leave the input locked if anything unexpected happened.
        try:
            await _interrupt_ai()
        except Exception:
            pass


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
                logger.warning(f"{i18n.t('voice_blocked')}")
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
                    logger.info(f"{i18n.t('voice_stats', **_stats)}")
                    dump_path = os.path.join(BASE_PATH, "debug_utterance.wav")
                    await asyncio.to_thread(ui.dump_utterance, dump_path, frames)
                    logger.info(f"{i18n.t('voice_saved', path=dump_path)}")
                else:
                    logger.info(f"{i18n.t('voice_no_chunks')}")

                text = await asyncio.to_thread(ui._transcribe_frames, frames, True)
                if not text and ui.stt_service == "whisper" and ui.local_stt._model is not None:
                    logger.info(f"{i18n.t('vad_retry')}")
                    text = await asyncio.to_thread(ui._transcribe_frames, frames, False)
                ui.end_utterance()  # clear the buffer

                if text:
                    logger.success(f"{i18n.t('voice_text', text=text)}")
                else:
                    logger.warning(f"{i18n.t('voice_no_speech')}")
                await ws.send_json({"type": "speech_result", "payload": {"text": text}})
            except Exception as e:
                logger.error(f"{i18n.t('voice_input_error', e=e)}")
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
                    logger.warning(f"{i18n.t('wake_ignored')}")
                    await ws.send_json({"type": "wake_busy", "payload": {}})
                return

            if not ui.listening:
                if ui.feed_wake_audio(pcm):
                    ui.wake_word.reset()  # clear streaming state so it can't double-fire
                    ui.start_listening()
                    logger.success(f"{i18n.t('wake_detected')}")
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
                        logger.info(f"{i18n.t('wake_utterance', **_ustats)}")
                        dump_path = os.path.join(BASE_PATH, "debug_utterance.wav")
                        await asyncio.to_thread(ui.dump_utterance, dump_path, frames)
                    text = await asyncio.to_thread(ui.stop_listening)
                    ui.wake_word.reset()  # fresh detection state for the next wake word
                    if text:
                        # Lock input immediately (before the client's chat round
                        # trip) so no new wake word can slip in mid-transition.
                        state.ai_busy = True
                        logger.success(f"{i18n.t('voice_text', text=text)}")
                    else:
                        logger.warning(f"{i18n.t('voice_no_speech')}")
                    await ws.send_json({"type": "speech_result", "payload": {"text": text}})
    except Exception as e:
        logger.error(f"{i18n.t('voice_input_error', e=e)}")


async def _initialize() -> None:
    """Build ChatBot, TTS, VTS and the local LLM server from settings.json.

    VTube Studio is deliberately left out of the parallel batch: connecting
    can block until you accept the plugin's authorization popup in VTube
    Studio, so it runs on its own first and keeps that prompt front and
    center instead of burying it under the other services' log lines.

    The remaining components initialize in two ordered phases (they used to
    all share one asyncio.gather). On a cold first run OmniVoice's multi-GB
    model download saturates the disk and starves llama-server while it reads
    its GGUF file, blowing past the health-check timeout and taking down both
    the local LLM and OmniVoice's own init. Running the downloads first and
    launching llama.cpp afterwards removes that race; when the model caches
    are warm the download phase is near-instant, so wall time stays close to
    the *longest* single stage instead of the *sum*.
    """
    async with state.lock:
        if state.running:
            return

        config = state.config if state.config else load_settings()
        logger.info(f"{i18n.t('start_services')}")

        # Import the heavy AI backends (OmniVoice -> torch/transformers,
        # faster-whisper -> CTranslate2) on the main thread BEFORE firing the
        # initializers into parallel worker threads. Racing those imports can
        # break OmniVoice's cold start (it then only "works on retry" once its
        # dependencies are cached in sys.modules).
        warm_up_heavy_imports(
            tts_service=config.get("tts_service", "gtts"),
            stt_service=config.get("stt_service", "whisper"),
        )

        async def _init_chatbot():
            if "ChatBot" not in globals() or ChatBot is None:
                return
            try:
                service = config.get("chatbot_service", "openai")
                logger.info(f"{i18n.t('init_chatbot', service=service)}")
                state.chat_bot = ChatBot(
                    chat_bot_service=service,
                    openai_model=config.get("openai_model", "gpt-4o-mini"),
                    model_path=config.get("model_dir", ""),
                    remember_conversation=config.get("remember_conversation", False)
                )
                await asyncio.to_thread(state.chat_bot.initialize)
                logger.success(f"{i18n.t('chatbot_ok')}")
            except Exception as e:
                logger.error(f"{i18n.t('chatbot_fail', e=e)}")
                state.chat_bot = None

        async def _init_llm():
            if (
                config.get("chatbot_service", "openai") != "local"
                or "RunLocalServer" not in globals()
                or RunLocalServer is None
            ):
                return
            try:
                logger.info(f"{i18n.t('start_llm')}")
                state.local_server = RunLocalServer(
                    config.get("show_ollama_server_logs", False),
                    config.get("model_dir", ""),
                    config.get("llama_server_device", "cuda"),
                    ctx_size=config.get("llama_ctx_size", 4096)
                )
                # Bumped timeout: it no longer blocks the other services, so
                # we can afford to wait longer for the model to load.
                await state.local_server.launch_server(timeout=60)
                logger.success(f"{i18n.t('llm_ok')}")
            except Exception as e:
                logger.error(f"{i18n.t('llm_fail', e=e)}")
                state.local_server = None

        async def _init_tts():
            if "TTS" not in globals() or TTS is None:
                return
            try:
                service = config.get("tts_service", "gtts")
                logger.info(f"{i18n.t('init_tts', service=service)}")
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
                    reference_wav=config.get("reference_wav", "Data/reference.wav"),
                    omnivoice_device=config.get("omnivoice_device", "cuda"),
                    play_only_cable=config.get("play_only_cable", False),
                    gain=config.get("gain", 1.0)
                )
                await asyncio.to_thread(state.tts.initialize)
                logger.success(f"{i18n.t('tts_ok')}")
            except Exception as e:
                logger.error(f"{i18n.t('tts_fail', e=e)}")
                state.tts = None

        async def _init_vts():
            if "VtubeControll" not in globals() or VtubeControll is None:
                return
            try:
                logger.info(f"{i18n.t('connecting_vts')}")
                state.vts = VtubeControll()
                await state.vts.initialize()
                logger.success(f"{i18n.t('vts_ok')}")
            except Exception as e:
                logger.error(f"{i18n.t('vts_fail', e=e)}")
                state.vts = None

        async def _init_voice():
            if "UserInput" not in globals() or UserInput is None:
                return
            ui_service = config.get("user_input_service", "console")
            if ui_service not in ("speech", "wake_word"):
                return
            try:
                logger.info(f"{i18n.t('init_voice', service=ui_service)}")
                state.user_input = UserInput(
                    user_input_service=ui_service,
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
                logger.success(f"{i18n.t('voice_ok')}")
            except Exception as e:
                logger.error(f"{i18n.t('voice_fail', e=e)}")
                state.user_input = None

        try:
            # VTS first, blocking, so the "accept the token in VTube Studio"
            # prompt stays visible instead of being scrolled away while the
            # rest of the services spin up.
            await _init_vts()

            # Phase 1 (model downloads): TTS + voice. On a cold first run
            # these pull the multi-GB OmniVoice / faster-whisper weights from
            # HuggingFace. Launching llama.cpp at the same time made the
            # download saturate the disk, starve the GGUF read, and blow past
            # llama-server's 60s health-check timeout, and the resulting
            # I/O/GPU contention also broke OmniVoice's init -> both failed.
            await asyncio.gather(_init_tts(), _init_voice())

            # Phase 2 (fast paths): chatbot + local llama server, now that
            # the heavy downloads are done. With warmed caches phase 1 is
            # near-instant, so the extra serialization only costs wall time
            # on the first-run download it exists to make reliable.
            await asyncio.gather(_init_chatbot(), _init_llm())

            state.running = True
            logger.success(f"{i18n.t('all_online')}")

        except Exception as e:
            logger.error(f"[SERVER ERROR] {e}")
            logger.error(f"{i18n.t('crash')}")
            await _broadcast({"type": "crash", "payload": {}})


async def _shutdown() -> None:
    """Stop the LLM server, disconnect VTS, and drop the ChatBot/TTS objects."""
    async with state.lock:
        logger.info(f"{i18n.t('stopping')}")

        # Abort any in-flight thinking/speaking so the Stop button always works
        # immediately, even mid-response, instead of waiting for it to finish.
        await _interrupt_ai()

        # Clean VTube Studio disconnect
        if state.vts:
            try:
                if hasattr(state.vts, "vts") and state.vts.vts is not None:
                    if hasattr(state.vts.vts, "close"):
                        await state.vts.vts.close()
                        logger.success(f"{i18n.t('vts_disconnected')}")
                    else:
                        logger.info(f"{i18n.t('vts_skip_close')}")
            except Exception as e:
                logger.error(f"{i18n.t('vts_error', e=e)}")
            state.vts = None

        # Clean Local LLM stop
        if state.local_server:
            try:
                if hasattr(state.local_server, "stop_server"):
                    state.local_server.stop_server()
                elif hasattr(state.local_server, "stop"):
                    state.local_server.stop()
                logger.success(f"{i18n.t('llm_stopped')}")
            except Exception as e:
                logger.error(f"{i18n.t('local_server_error', e=e)}")
            state.local_server = None

        state.chat_bot = None
        state.tts = None
        state.ai_busy = False

        # Clean voice input
        if state.user_input:
            try:
                state.user_input.cleanup()
                logger.success(f"{i18n.t('voice_stopped')}")
            except Exception as e:
                logger.error(f"{i18n.t('user_input_error', e=e)}")
            state.user_input = None

        state.running = False
        logger.success(f"{i18n.t('shut_down')}")


#Main
HOST = "127.0.0.1"
DEFAULT_PORT = 5050

#Keeps the ctypes callback alive for the process lifetime.
_ctrl_c_handler_route = None


def install_ctrl_c_handler(server) -> None:
    """Make Ctrl+C gracefully shut the app down even while the pywebview
    window owns the main thread.

    On Windows, the edgechromium/winforms message pump blocks the main thread,
    so Python never gets a chance to raise KeyboardInterrupt there. Instead we
    register a Win32 console control handler that runs on its own thread when
    Ctrl+C (or Ctrl+Break) is pressed: it stops the uvicorn backend and closes
    the window, letting the normal post-window shutdown path finish.
    """
    global _ctrl_c_handler_route
    if sys.platform != "win32" or _ctrl_c_handler_route is not None:
        return

    import ctypes
    from ctypes import wintypes

    shutdown_started = {"done": False}

    def _handler(ctrl_type: int) -> bool:
        if shutdown_started["done"]:
            return True
        shutdown_started["done"] = True
        try:
            logger.warning("Ctrl+C received; shutting down...")
            server.should_exit = True
            try:
                import webview

                for win in list(webview.windows):
                    win.destroy()
            except Exception:
                pass
        except Exception as exc:
            logger.error(f"Ctrl+C shutdown failed: {exc}")
        return True

    _ctrl_c_handler_route = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)(_handler)
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, ctypes.c_bool]
        kernel32.SetConsoleCtrlHandler.restype = ctypes.c_int
        ok = kernel32.SetConsoleCtrlHandler(_ctrl_c_handler_route, True)
        if not ok:
            raise ctypes.WinError()
    except Exception as exc:
        logger.warning(f"Could not install the Ctrl+C handler: {exc}")
        _ctrl_c_handler_route = None


def open_server_console() -> None:
    """Give the server a real console window showing its live logs.

    When the app is launched without a console (e.g. via pythonw or a
    windowed launcher) a native console is allocated for this process and
    Python's std streams are reattached, so loguru's console output lands in
    that visible window next to the pywebview GUI. When the process already
    owns a console (normal `python main-gui.py` or a console=True build) the
    existing terminal already shows the logs and nothing is changed.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        if kernel32.GetConsoleWindow():
            return  # already attached to a console that shows the logs
        if kernel32.AllocConsole():
            kernel32.SetConsoleTitleW("NOUS Intelligence - Server Console")
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
            sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
            try:
                sys.stdin = open("CONIN$", "r")
            except OSError:
                pass
    except Exception as e:
        logger.warning(f"Could not open the server console window: {e}")


def get_free_port(preferred: int = DEFAULT_PORT) -> int:
    """Return the preferred port if it is free, otherwise any free port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, preferred))
            return preferred
    except OSError:
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def wait_for_server(host: str, port: int, timeout: float = 30.0) -> bool:
    """Poll until the uvicorn backend answers on host:port."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def start_backend(host: str, port: int, server: uvicorn.Server) -> None:
    """Run uvicorn inside a worker thread (pywebview owns the main thread)."""
    server.run()
    logger.info(f"Backend server stopped (http://{host}:{port}).")


def _open_browser(url: str) -> None:
    #Open the GUI in a new browser tab.
    webbrowser.open(url, new=2)


class Bridge:
    """JS bridge exposed to the GUI (via pywebview js_api)."""

    port = None  # injected at startup so the bridge knows the server URL

    def close_application(self):
        import webview

        try:
            if webview.windows:
                webview.windows[0].destroy()
                logger.info("Application window closed from the GUI.")
        except Exception as exc:
            logger.error(f"Failed to close the window: {exc}")

    def open_external(self, url: str):
        try:
            webbrowser.open(url, new=2)
        except Exception as exc:
            logger.error(f"Failed to open {url}: {exc}")


def shutdown_services_after_window(server: uvicorn.Server) -> None:
    """Stop every running AI service, then shut down the uvicorn backend.

    Called once the pywebview window closes. `_shutdown()` is async and must
    run on the FastAPI event loop, so it is scheduled there via
    `_loop_ref` (captured by the app lifespan) instead of a fresh loop.
    """
    loop = _loop_ref
    if loop is not None and loop.is_running():
        try:
            future = asyncio.run_coroutine_threadsafe(_shutdown(), loop)
            future.result(timeout=30)
            logger.success("All services shut down after window close.")
        except Exception as e:
            logger.error(f"Service shutdown after window close failed: {e}")
    else:
        logger.info("No running event loop; services were already stopped.")

    server.should_exit = True


if __name__ == "__main__":
    # Open (or reuse) a real server console that shows the live logs next to
    # the pywebview window. Must run BEFORE setup_logging so loguru binds to
    # the freshly attached stderr.
    open_server_console()
    load_settings()
    # Logging is a master on/off switch driven by enable_logs.
    setup_logging(
        enabled=state.config.get("enable_logs", True),
        rotation=state.config.get("log_rotation", "10 MB"),
        retention=state.config.get("log_retention", "30 days"),
        file_enabled=state.config.get("file_logs", True),
        gui_sink=_gui_log_sink,
    )
    try:
        port = get_free_port(DEFAULT_PORT)
        if port != DEFAULT_PORT:
            logger.warning(f"Port {DEFAULT_PORT} busy; using {port} instead.")
        logger.info(f"Nous Intelligence GUI -> http://{HOST}:{port}")

        config = uvicorn.Config(
            app,
            host=HOST,
            port=port,
            log_level="warning",
            access_log=False,
            log_config=None,  # loguru owns all logging
        )
        server = uvicorn.Server(config)
        server_thread = threading.Thread(
            target=start_backend,
            args=(HOST, port, server),
            daemon=True,
            name="uvicorn-backend",
        )
        server_thread.start()

        if not wait_for_server(HOST, port):
            logger.error("Backend did not become reachable in time. Aborting.")
            server.should_exit = True
            server_thread.join(timeout=5)
            raise SystemExit(1)

        #Ctrl+C must keep working: without this, the message pump behind
        #pywebview swallows the signal and the app can only stop via the GUI.
        install_ctrl_c_handler(server)

        if not state.config.get("display_separate_window", True):
            #Old logic: no desktop window, GUI runs in the browser tab and the
            #server keeps logging to this console until stopped (Ctrl+C).
            logger.info("Display in separate window is off; opening the default browser tab instead.")
            threading.Timer(1.5, _open_browser, args=(f"http://{HOST}:{port}",)).start()
            try:
                server_thread.join()
            except KeyboardInterrupt:
                logger.warning("Server stopped by user.")
            shutdown_services_after_window(server)
            raise SystemExit(0)

        try:
            import webview
        except ImportError:
            logger.warning("pywebview not installed; opening GUI in the default browser instead.")
            threading.Timer(1.5, _open_browser, args=(f"http://{HOST}:{port}",)).start()
            try:
                server_thread.join()
            except KeyboardInterrupt:
                logger.warning("Server stopped by user.")
            shutdown_services_after_window(server)
            input("Press Enter to close this window...")
            raise SystemExit(0)

        logger.info("Opening desktop window (pywebview)...")
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        bridge = Bridge()
        bridge.port = port
        icon = os.path.join(BASE_PATH, "icon.ico")
        webview.create_window(
            "Nous Intelligence",
            url=f"http://{HOST}:{port}",
            width=int(state.config.get("window_width", 1280)),
            height=int(state.config.get("window_height", 820)),
            min_size=(900, 600),
            js_api=bridge,
        )
        webview.start(gui="edgechromium", icon=icon if os.path.isfile(icon) else None)

        logger.info("Window closed; shutting down all services.")
        shutdown_services_after_window(server)
        server_thread.join(timeout=10)
    except KeyboardInterrupt:
        logger.warning("Server stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
