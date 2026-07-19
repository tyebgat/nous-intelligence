import asyncio
import json
import os
import colorama
from dotenv import load_dotenv

load_dotenv()
colorama.init()

from IA import Nous
from paths import BASE_PATH
from run_local_server import RunLocalServer
from chat_bot import ChatBot
from VtubeS_Plugin import VtubeControll
from user_input import UserInput
from TTS import TTS

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

token_path=os.path.join(BASE_PATH, 'Data', 'noussoul_auth_token.txt')

async def main():
    print(f"{YELLOW} Loading settings json...{RESET}")
    #opens the json setting
    try:
        #========================
        # GET JSON CONFIGURATION
        # ========================
        with open(os.path.join(BASE_PATH, "settings.json"), 'r') as f:
            print(f"{YELLOW}loading settings from json....{RESET}")
            config = json.load(f)
            # --- chatbot settings ---
            user_input_service = config.get("user_input_service", "console")
            chatbot_service = config.get("chatbot_service", "openai")
            chatbot_name = config.get("chatbot_name", "Nous")
            remember_conversation = config.get("remember_conversation", False)
            model_dir = config.get("model_dir", "")

            # ---- tts settings
            tts_language = config.get("tts_language", "en")
            tts_service = config.get("tts_service", "gtts")
            tts_voice = config.get("tts_voice", "ash")
            tts_speed = config.get("tts_speed", 1.0)
            voice_cloning = config.get("voice_cloning", False)
            voice_design = config.get("voice_design", False)

            # --- omnivoice settings ---
            omnivoice_device = config.get("omnivoice_device", "cuda")

            # --- openai settings ----
            openai_model = config.get("openai_model", "gpt-4o-mini")
            openai_tts_model = config.get("openai_tts_model", "gpt-4o-mini-tts")
            openai_tts_voice = config.get("openai_tts_voice", "ash")

            # --- general setting ---
            app_language = config.get("app_language", "english")

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

            # --- logs ---
            detailed_logs = config.get("logs", True)
            print_audio_devices = config.get("print_audio_devices", False)
            show_ollama_server_logs = config.get("show_ollama_server_logs", False)

            if detailed_logs:
                print("==================SETTINGS===================")
                print(json.dumps(config, indent=4))
                print("=" * 60)

    except FileNotFoundError:
        #========================
        # JSON DEFAULT SETTINGS
        # ========================
        print(f"{ORANGE}file not found using default settings...{RESET}")
        # --- chatbot settings ---
        user_input_service = "console"
        chatbot_service = "test"     
        chatbot_name = "Nous"
        remember_conversation = False
        model_dir = ""

        # --- tts settings ---
        tts_language = "en"
        tts_service = "gtts"
        tts_voice = "ash"
        tts_speed = 1.0
        voice_cloning = False
        voice_design = False

        # --- omnivoice settings ---
        omnivoice_device = "cuda"

        # --- openai settings ---
        openai_model = "gpt-4o-mini"
        openai_tts_model = "gpt-4o-mini-tts"
        openai_tts_voice = "ash"
        
        # --- general settings ---
        app_language = "english"

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

        # --- logs settings ---
        detailed_logs = True
        print_audio_devices = False
        show_ollama_server_logs = False

    print(f'{YELLOW}Starting Vtube Studio Plugin...{RESET}')
    
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
    local_server = RunLocalServer(show_ollama_server_logs, model_dir)

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
        omnivoice_device=omnivoice_device, 
        detailed_logs=detailed_logs
    )

    #----------------------
    #START VTS PLUGINS
    #----------------------
    try:
        print(f'{YELLOW}Intializing Plugin...{RESET}')
        await vts.initialize()
        print(f'{GREEN}done.{RESET}')

    #if gone wrong then print out an error
    except Exception as e:
        print(f"{RED}Failed to start VTube Studio plugin. Is it open?: {e}{RESET}")

    #----------------------
    #START LLAMA SERVER 
    #----------------------
    if chatbot_service == "local":
        try:
            print(f"{YELLOW}Initializing local Llama server{RESET}")
            await local_server.launch_server(timeout=30)
            print(f"{GREEN}Local server running{RESET}")
        except Exception as e:
            print(f"{RED}Failed to start local llama server: {e}{RESET}")

    #IA.py
    ai = Nous(
        vts=vts, 
        ChatBot=chat_bot, 
        detailed_logs=detailed_logs, 
        print_audio_devices=print_audio_devices, 
        user_input=user_input, 
        tts=tts
    )

    print(f"{YELLOW}Initializing nous...{RESET}")
    ai.initialize(mic_index=None)
    print(f"{GREEN}Nous initialized.{RESET}")

    #--- initialize wake word + whisper STT ---
    if user_input_service == "wake_word":
        print(f"{YELLOW}Loading wake word model...{RESET}")
        user_input.setup_wake_word()
        print(f"{GREEN}Wake word model loaded.{RESET}")

    if stt_service == "whisper" and user_input != "console":
        print(f"{YELLOW}Loading Whisper STT model...{RESET}")
        user_input.setup_whisper()
        print(f"{GREEN}Whisper STT model loaded.{RESET}")

    try:
        ai_task = asyncio.create_task(ai.conversation_cycle())

        await ai_task
    
    except KeyboardInterrupt:
        print(f"{ORANGE}Keyboard interrupt detected shutting down...{RESET}")

    except Exception as e:
        print(f"{RED}Unexpecter error occured in main loop, shutting down...{RESET}")
        if detailed_logs:
            print(f"{RED}Unexpected error occured in main loop, shutting down: {e}{RESET}")

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
