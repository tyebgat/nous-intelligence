import asyncio #library that lets me use the async and await syntax, vital for web requests (api requests basically :V)
from IA import Nous #imports nous class from the IA script
from VtubeS_Plugin import VtubeControll #imports VtubeCOnbtroll class from the plugin script
from Face_detectecion import FaceDetectionVTuber #imports face detection script

token_path='noussoul_auth_token.txt' #store token path in a variable for ease of use

async def main():
    print('Starting Vtube Studio Plugin...')
    vts = VtubeControll() #Creates object to use the vtube studio plugin

    #crash prevention
    try:
        print('Intializing Plugin...')
        await vts.initialize() #initializes the vtube studio plugin
        print('done.')
    #if gone wrong then print out an error
    except Exception as e:
        print(f"Failed to initialize or authenticate: {e}")

    ai = Nous(vts=vts)
    ai.user_input_service = "console"
    ai.chatbot_service = "openai"
    print("Initializing nous...")
    ai.initialize(mic_index=None)
    print("Nous initialized.")

    print("Initializing face detection...")
    fvts = FaceDetectionVTuber(ai=ai)
    fvts.list_cameras()
    if not fvts.initialize_camera(camera_index=0):
        print("Failed to initialized camera. Check on index which devices are acttive.")
        return
    print("camera iniialized")

    print("starting both systems...")

    try:
        fvts_task = asyncio.create_task(fvts.start_detection())
        ai_task = asyncio.create_task(ai.conversation_cycle())

        await asyncio.gather(fvts_task, ai_task, return_exceptions=True)
    except Exception as e:
        print(f"Unexpected error occured in main loop, shutting down: {e}")
        fvts.stop_detection()
        print("gracefull shut down.")
        

#if this file is executed directly it will run the main funtion
if __name__ == "__main__":
   asyncio.run(main())