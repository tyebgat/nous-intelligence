import asyncio
import json
import os
import colorama
from dotenv import load_dotenv
from loguru import logger

load_dotenv()
colorama.init()

from IA import Nous
from paths import BASE_PATH
from run_local_server import RunLocalServer
from chat_bot import ChatBot
from VtubeS_Plugin import VtubeControll
from user_input import UserInput
from TTS import TTS
from logging_setup import setup_logging

token_path=os.path.join(BASE_PATH, 'Data', 'noussoul_auth_token.txt')

async def main():
    setup_logging()
    logger.info("Loading settings json...")
    #opens the json setting
    config = {}  # filled below; kept empty on missing/corrupt settings file
    try:
        #========================
        # GET JSON CONFIGURATION
        # ========================
        with open(os.path.join(BASE_PATH, "settings.json"), 'r') as f:
            logger.info("loading settings from json....")
            config = json.load(f)
            # --- chatbot settings ---
            user_input_service = config.get("user_input_service", "console")
            chatbot_service = config.get("chatbot_service", "openai")
            chatbot_name = config.get("chatbot_name", "Nous")
            remember_conversation = config.get("remember_conversation", False)
            model_dir = config.get("model_dir", "")
            llama_server_device = config.get("llama_server_device", "cuda")

            # ---- tts settings
            tts_language = config.get("tts_language", "en")
            tts_service = config.get("tts_service", "gtts")
            tts_voice = config.get("tts_voice", "ash")
            tts_speed = config.get("tts_speed", 1.0)
            voice_cloning = config.get("voice_cloning", False)
            voice_design = config.get("voice_design", False)
            reference_wav = config.get("reference_wav", "Data/reference.wav")
            gain = config.get("gain", 1.0)

            # --- omnivoice settings ---
            omnivoice_device = config.get("omnivoice_device", "cuda")

            # --- openai settings ----
            openai_model = config.get("openai_model", "gpt-4o-mini")
            openai_tts_model = config.get("openai_tts_model", "gpt-4o-mini-tts")
            openai_tts_voice = config.get("openai_tts_voice", "ash")

            # --- general setting ---
            app_language = config.get("app_language", "english")
            play_only_cable = config.get("play_only_cable", False)

            # --- wake word settings ---
            wake_word_model = config.get("wake_word_model", "models/openwakeword/hey_jarvis_v0.1.tflite")
            wake_word_threshold = config.get("wake_word_threshold", 0.5)
            wake_word_confirm_sound = config.get("wake_word_confirm_sound", True)

            # --- local stt settings ---
            stt_service = config.get("stt_service", "whisper")
            stt_device = config.get("stt_device", "cpu")
            stt_compute_type = config.get("stt_compute_type", "int8")
            stt_language = config.get("stt_language", "en")
            silence_duration = config.get("silence_duration", 1.5)

            # --- llama server ---
            llama_ctx_size = config.get("llama_ctx_size", 4096)

            # --- logs ---
            detailed_logs = config.get("logs", True)
            print_audio_devices = config.get("print_audio_devices", False)
            show_ollama_server_logs = config.get("show_ollama_server_logs", False)

            if detailed_logs:
                logger.debug("==================SETTINGS===================")
                logger.debug(json.dumps(config, indent=4))
                logger.debug("=" * 60)

    except FileNotFoundError:
        #========================
        # JSON DEFAULT SETTINGS
        # ========================
        logger.warning("file not found using default settings...")
        # --- chatbot settings ---
        user_input_service = "console"
        chatbot_service = "test"     
        chatbot_name = "Nous"
        remember_conversation = False
        model_dir = ""
        llama_server_device = "cuda"

        # --- tts settings ---
        tts_language = "en"
        tts_service = "gtts"
        tts_voice = "ash"
        tts_speed = 1.0
        voice_cloning = False
        voice_design = False
        reference_wav = "Data/reference.wav"
        gain = 1.0

        # --- omnivoice settings ---
        omnivoice_device = "cuda"

        # --- openai settings ---
        openai_model = "gpt-4o-mini"
        openai_tts_model = "gpt-4o-mini-tts"
        openai_tts_voice = "ash"
        
        # --- general settings ---
        app_language = "english"
        play_only_cable = False

        # --- wake word settings ---
        wake_word_model = "models/openwakeword/hey_jarvis_v0.1.tflite"
        wake_word_threshold = 0.5
        wake_word_confirm_sound = True

        # --- local stt settings ---
        stt_service = "whisper"
        stt_device = "cpu"
        stt_compute_type = "int8"
        stt_language = "en"
        silence_duration = 1.5

        # --- llama server ---
        llama_ctx_size = 4096

        # --- logs settings ---
        detailed_logs = True
        print_audio_devices = False
        show_ollama_server_logs = False

    # Level reflects the "Detailed Logs" toggle when enabled, otherwise the
    # configured log_level; file written to Data/logs/app.log per settings.
    setup_logging(
        level="DEBUG" if detailed_logs else config.get("log_level", "INFO"),
        rotation=config.get("log_rotation", "10 MB"),
        retention=config.get("log_retention", "30 days"),
        file_enabled=config.get("file_logs", True),
    )

    logger.info("Starting Vtube Studio Plugin...")
    
    #VTS Plugin
    vts = VtubeControll(detailed_logs=detailed_logs)

    #Chat bot scirpt
    chat_bot = ChatBot(
        chat_bot_service= chatbot_service,
        openai_model= openai_model,
        detailed_logs= detailed_logs,
        model_path= model_dir,
        remember_conversation= remember_conversation
    )
    chat_bot.initialize()
    
    #LLama server
    local_server = RunLocalServer(
        show_ollama_server_logs, model_dir, llama_server_device,
        ctx_size=llama_ctx_size
    )

    #user input
    user_input = UserInput(
        user_input_service=user_input_service,
        detailed_logs=detailed_logs,
        app_language=app_language,
        wake_word_model_path=os.path.join(BASE_PATH, wake_word_model),
        wake_word_threshold=wake_word_threshold,
        wake_word_confirm_sound=wake_word_confirm_sound,
        stt_service=stt_service,
        stt_device=stt_device,
        stt_compute_type=stt_compute_type,
        stt_language=stt_language,
        silence_duration=silence_duration,
    )

    #text to speech
    tts = TTS(
        tts_language=tts_language, 
        tts_service=tts_service, 
        chatbot_name=chatbot_name, 
        openai_tts_model=openai_tts_model, 
        openai_tts_voice=openai_tts_voice, 
        tts_voice=tts_voice, 
        tts_speed=tts_speed, 
        voice_cloning=voice_cloning, 
        voice_design=voice_design, 
        reference_wav=reference_wav,
        omnivoice_device=omnivoice_device, 
        detailed_logs=detailed_logs,
        play_only_cable=play_only_cable,
        gain=gain
    )

    #------------------------------------------------------------------
    # START ALL SERVICES IN PARALLEL
    #------------------------------------------------------------------
    # The local llama server takes the longest (loading the model into RAM),
    # so it is spawned as a background task while VTS, TTS, wake word and
    # whisper initialize at the same time instead of serially after it.
    #------------------------------------------------------------------

    async def _init_vts():
        #----------------------
        #START VTS PLUGINS
        #----------------------
        try:
            logger.info("Intializing Plugin...")
            await vts.initialize()
            logger.success("done.")
        #if gone wrong then print out an error
        except Exception as e:
            logger.error(f"Failed to start VTube Studio plugin. Is it open?: {e}")

    async def _start_llm():
        #----------------------
        #START LLAMA SERVER
        #----------------------
        if chatbot_service != "local":
            return
        try:
            logger.info("Initializing local Llama server")
            # Longer timeout: it no longer blocks the other services, so we
            # can afford to wait longer for the model to load.
            await local_server.launch_server(timeout=60)
            logger.success("Local server running")
        except Exception as e:
            logger.error(f"Failed to start local llama server: {e}")

    vts_task = asyncio.create_task(_init_vts())
    llm_task = asyncio.create_task(_start_llm())

    #IA.py
    ai = Nous(
        vts=vts, 
        ChatBot=chat_bot, 
        detailed_logs=detailed_logs, 
        print_audio_devices=print_audio_devices, 
        user_input=user_input, 
        tts=tts
    )

    logger.info("Initializing nous...")
    # Runs TTS.initialize + ChatBot.initialize + mic setup; block on it in a
    # thread so the llama server and VTS keep loading in the background.
    await asyncio.to_thread(ai.initialize, None)
    logger.success("Nous initialized.")

    #--- initialize wake word + whisper STT ---
    if user_input_service == "wake_word":
        logger.info("Loading wake word model...")
        user_input.setup_wake_word()
        logger.success("Wake word model loaded.")

    if stt_service == "whisper" and user_input_service != "console":
        logger.info("Loading Whisper STT model...")
        user_input.setup_whisper()
        logger.success("Whisper STT model loaded.")

    # Wait for the background services (VTS connect + llama model load).
    await vts_task
    await llm_task

    try:
        ai_task = asyncio.create_task(ai.conversation_cycle())

        await ai_task
    
    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt detected shutting down...")

    except Exception as e:
        logger.error("Unexpecter error occured in main loop, shutting down...")
        if detailed_logs:
            logger.debug(f"Unexpected error occured in main loop, shutting down: {e}")

    finally:
        user_input.cleanup()
        local_server.stop_server()
        try:
            if hasattr(vts, 'vts') and vts.vts:
                await vts.vts.disconnect()
        except Exception:
            pass

#if this file is executed directly it will run the main funtion
if __name__ == "__main__":
    asyncio.run(main())
