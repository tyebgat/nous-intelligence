import asyncio #library that lets me use the async and await syntax, vital for web requests (api requests basically :V)
import json #to load settings

from IA import Nous #imports nous class from the IA script
from run_local_server import RunLocalServer
from chat_bot import ChatBot
from VtubeS_Plugin import VtubeControll #imports VtubeCOnbtroll class from the plugin script

token_path='Data/noussoul_auth_token.txt' #store token path in a variable for ease of use

async def main():
    #opens the json setting
    try:
        #========================
        # GET JSON CONFIGURATION
        # ========================
        with open("settings.json", 'r') as f:
            print("loading settings from json....")
            config = json.load(f)
            user_input_service = config.get("user_input_service", "console") #gets user input
            chatbot_service = config.get("chatbot_service", "openai") #gets chatbor service
            tts_language = config.get("app_language", "english") #gets tts language
            detailed_logs = config.get("logs", True)
            print_audio_devices = config.get("print_audio_devices", False)
            if detailed_logs:
                print("==================SETTINGS===================")
                print(json.dumps(config, indent=4))
                print("="*60)
    except FileNotFoundError: #if file is not found use default settings
        #========================
        # JSON DEFAULT SETTINGS
        # ========================
        print("file not found using default settings...")
        user_input_service = "console"
        chatbot_service = "test"
        tts_language = "english"
        detailed_logs = True
        print_audio_devices = False
    
        print('Starting Vtube Studio Plugin...')
    
    #VTS Plugin
    vts = VtubeControll(detailed_logs=detailed_logs)

    #Chat bot scirpt
    chat_bot = ChatBot(tts_language, chatbot_service, detailed_logs) #creates chatbot object
    
    #LLama server
    local_server = RunLocalServer(detailed_logs)

    #----------------------
    #START VTS PLUGIN
    #----------------------
    try:
        print('Intializing Plugin...')
        await vts.initialize() #initializes the vtube studio plugin
        print('done.')

    #if gone wrong then print out an error
    except Exception as e:
        print(f"Failed to initialize or authenticate: {e}")

    #----------------------
    #START LLAMA SERVER 
    #----------------------
    if chatbot_service == "local":
        try:
            print("Initializing local Llama server")
            await local_server.launch_server(timeout=30)
            print("Local server running")
        except Exception as e:
            print("Failed to start local llama server: {e}")

    #IA.py
    ai = Nous(vts=vts, ChatBot=chat_bot, tts_language=tts_language, detailed_logs=detailed_logs, print_audio_devices=print_audio_devices) #decalring nous class

    ai.user_input_service = user_input_service

    print("Initializing nous...")
    ai.initialize(mic_index=None) #initializes nous
    print("Nous initialized.")

    try:
        ai_task = asyncio.create_task(ai.conversation_cycle())

        await ai_task
    
    except KeyboardInterrupt:
        print("Keyboard interrupt detected shutting down...")
        ai.cleanup()
        print("Shutting down server...")
        local_server.stop_server()

    except Exception as e: #if there is an exception stop everything
        print("Unexpecter error occured in main loop, shutting down...")
        local_server.stop_server()
        if detailed_logs:
            print(f"Unexpected error occured in main loop, shutting down: {e}")
            print("Shutting down server...")
            local_server.stop_server()

#if this file is executed directly it will run the main funtion
if __name__ == "__main__":
    asyncio.run(main())