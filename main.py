import asyncio #library that lets me use the async and await syntax, vital for web requests (api requests basically :V)
from IA import Nous #imports nous class from the IA script
from VtubeS_Plugin import VtubeControll #imports VtubeCOnbtroll class from the plugin script

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
    ai.chatbot_service = "test"
    ai.initialize()

    print("ai initialized starting conversation cycle...\n")
    while True:
        await ai.conversation_cycle()


#if this file is executed directly it will run the main funtion
if __name__ == "__main__":
   asyncio.run(main())