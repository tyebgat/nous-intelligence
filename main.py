import asyncio
import json
import os
import colorama

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
    #opens the json setting
    try:
        #========================
        # GET JSON CONFIGURATION
        # ========================
        with open(os.path.join(BASE_PATH, "settings.json"), 'r') as f:
            print(f"{YELLOW}loading settings from json....{RESET}")
            config = json.load(f)
            user_input_service = config.get("user_input_service", "console")
            chatbot_service = config.get("chatbot_service", "openai")
            tts_language = config.get("tts_language", "en")
            tts_service = config.get("tts_service", "gtts")
            openai_model = config.get("openai_model", "gpt-4o-mini")
            openai_tts_model = config.get("openai_tts_model", "gpt-4o-mini-tts")
            openai_tts_voice = config.get("openai_tts_voice", "ash")
            app_language = config.get("app_language", "english")
            detailed_logs = config.get("logs", True)
            print_audio_devices = config.get("print_audio_devices", False)
            model_dir = config.get("model_dir", "")
            remember_conversation = config.get("remember_conversation", False)
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
        user_input_service = "console"
        chatbot_service = "test"
        tts_language = "en"
        tts_service = "gtts"
        openai_model = "gpt-4o-mini"
        openai_tts_model = "gpt-4o-mini-tts"
        openai_tts_voice = "ash"
        app_language = "english"
        detailed_logs = True
        print_audio_devices = False
        model_dir = ""
        remember_conversation = False
        show_ollama_server_logs = False
    
        print(f'{YELLOW}Starting Vtube Studio Plugin...{RESET}')
    
    #VTS Plugin
    vts = VtubeControll(detailed_logs=detailed_logs)

    #Chat bot scirpt
    chat_bot = ChatBot(chatbot_service, openai_model, detailed_logs, model_dir, remember_conversation)
    chat_bot.initialize()
    
    #LLama server
    local_server = RunLocalServer(show_ollama_server_logs)

    #user input
    user_input_obj = UserInput(user_input_service, detailed_logs, app_language)

    #text to speech
    tts = TTS(tts_language=tts_language, tts_service=tts_service, openai_tts_model=openai_tts_model, openai_tts_voice=openai_tts_voice)

    #----------------------
    #START VTS PLUGIN
    #----------------------
    try:
        print(f'{YELLOW}Intializing Plugin...{RESET}')
        await vts.initialize()
        print(f'{GREEN}done.{RESET}')

    #if gone wrong then print out an error
    except Exception as e:
        print(f"{RED}Failed to initialize or authenticate: {e}{RESET}")

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
    ai = Nous(vts=vts, ChatBot=chat_bot, detailed_logs=detailed_logs, print_audio_devices=print_audio_devices, user_input=user_input_obj, tts=tts)

    print(f"{YELLOW}Initializing nous...{RESET}")
    ai.initialize(mic_index=None)
    print(f"{GREEN}Nous initialized.{RESET}")

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
        user_input_obj.cleanup()
        local_server.stop_server()

#if this file is executed directly it will run the main funtion
if __name__ == "__main__":
    asyncio.run(main())
