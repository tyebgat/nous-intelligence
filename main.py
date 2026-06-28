import asyncio
import json

from IA import Nous
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

token_path = 'Data/noussoul_auth_token.txt'

async def main():
    try:
        with open("settings.json", 'r') as f:
            print(f"{YELLOW}loading settings from json....{RESET}")
            config = json.load(f)
            user_input_service = config.get("user_input_service", "console")
            chatbot_service = config.get("chatbot_service", "openai")
            tts_language = config.get("app_language", "english")
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
        print(f"{ORANGE}file not found using default settings...{RESET}")
        user_input_service = "console"
        chatbot_service = "test"
        tts_language = "english"
        detailed_logs = True
        print_audio_devices = False
        model_dir = ""
        remember_conversation = False
        show_ollama_server_logs = False

        print(f'{YELLOW}Starting Vtube Studio Plugin...{RESET}')

    vts = VtubeControll(detailed_logs=detailed_logs)

    chat_bot = ChatBot(tts_language, chatbot_service, detailed_logs, model_dir, remember_conversation)

    local_server = RunLocalServer(show_ollama_server_logs)

    try:
        print(f'{YELLOW}Intializing Plugin...{RESET}')
        await vts.initialize()
        print(f'{GREEN}done.{RESET}')

    except Exception as e:
        print(f"{RED}Failed to initialize or authenticate: {e}{RESET}")

    if chatbot_service == "local":
        try:
            print(f"{YELLOW}Initializing local Llama server{RESET}")
            await local_server.launch_server(timeout=30)
            print(f"{GREEN}Local server running{RESET}")
        except Exception as e:
            print(f"{RED}Failed to start local llama server: {e}{RESET}")

    user_input_obj = UserInput(user_input_service, detailed_logs, tts_language)

    tts = TTS(tts_language=tts_language)

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

if __name__ == "__main__":
    asyncio.run(main())
