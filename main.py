import asyncio #library that lets me use the async and await syntax, vital for web requests (api requests basically :V)
from IA import Nous #imports nous class from the IA script
from VtubeS_Plugin import VtubeControll #imports VtubeCOnbtroll class from the plugin script
from Face_detectecion import FaceDetectionVTuber #imports face detection script
import json #to load settings

token_path='noussoul_auth_token.txt' #store token path in a variable for ease of use

async def main():
    #opens the json setting
    try:
        #=====GET JSON CONFIGURATION========
        with open("settings.json", 'r') as f:
            print("loading settings from json....")
            config = json.load(f)
            user_input_service = config.get("user_input_service", "console") #gets user input
            chatbot_service = config.get("chatbot_service", "openai") #gets chatbor service
            tts_language = config.get("tts_language", "english") #gets tts language
            detailed_logs = config.get("detailed_logs", True)
            face_detection = config.get("face_detection", False)
            print_audio_devices = config.get("print_audio_devices", False)
            if detailed_logs:
                print("==================SETTINGS===================")
                print(json.dumps(config, indent=4))
                print("="*60)
    except FileNotFoundError: #if file is not found use default settings
        #======JSON DEFAULT SETTINGS=======
        print("file not found using default settings...")
        user_input_service = "console"
        chatbot_service = "test"
        tts_language = "english"
        detailed_logs = True
        face_detection = False
        print_audio_devices = False
    
        print('Starting Vtube Studio Plugin...')
    vts = VtubeControll(detailed_logs=detailed_logs) #Creates object to use the vtube studio plugin

    #crash prevention
    try:
        print('Intializing Plugin...')
        await vts.initialize() #initializes the vtube studio plugin
        print('done.')
    #if gone wrong then print out an error
    except Exception as e:
        print(f"Failed to initialize or authenticate: {e}")

    ai = Nous(vts=vts, tts_language=tts_language, detailed_logs=detailed_logs, print_audio_devices=print_audio_devices) #decalring nous class

    #set the input and chatbot service to the ones in the json file
    ai.user_input_service = user_input_service
    ai.chatbot_service = chatbot_service

    print("Initializing nous...")
    ai.initialize(mic_index=None) #initializes nous
    print("Nous initialized.")

    if face_detection:
        print("Initializing face detection...")
        fvts = FaceDetectionVTuber(ai=ai, tts_language=tts_language, detailed_logs=detailed_logs) #decalres the face detection class
        if detailed_logs:
            fvts.list_cameras() #gets the list of
        if not fvts.initialize_camera(camera_index=0): #initializes on index 0 (default device)
            print("Failed to initialized camera. Check on index which devices are acttive.")
            return
        print("camera iniialized")
    
    if not  face_detection:
        print("starting only conversation cycle.")
        print("="*60)

    if face_detection:
        print("starting both systems...")
        print("="*60)
        try:
            #creates tasks for both face and conversation loops
            fvts_task = asyncio.create_task(fvts.start_detection())
            ai_task = asyncio.create_task(ai.conversation_cycle())

            await asyncio.gather(fvts_task, ai_task, return_exceptions=True) #awaits them both at the same time
        except Exception as e: #if there is an exception stop everything
            print("Unexpected error occured shutting down...")
            if detailed_logs:
                print(f"Unexpected error occured in main loop, shutting down: {e}")
            fvts.stop_detection()
            print("gracefull shut down.")
    elif not face_detection:
        try:
            #creates tasks for both face and conversation loops
            ai_task = asyncio.create_task(ai.conversation_cycle())

            await ai_task #awaits them both at the same time
        except Exception as e: #if there is an exception stop everything
            print("Unexpecter error occured in main loop, shutting down...")
            if detailed_logs:
                print(f"Unexpected error occured in main loop, shutting down: {e}")

#if this file is executed directly it will run the main funtion
if __name__ == "__main__":
   asyncio.run(main())