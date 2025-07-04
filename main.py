import asyncio #library that lets me use the async and await syntax, vital for web requests (api requests basically :V)
from IA import nous #imports nous class from the IA script
from VtubeS_Plugin import VtubeControll #imports VtubeCOnbtroll class from the plugin script

token_path='noussoul_auth_token.txt' #store token path in a variable for ease of use

async def main():
    print('Starting Vtube Studio Plugin...')

    """mensaje para mis querido compañeros del grupo de la feria, ya que no estare el viernes,
    El codigo esta diseñado para q se corra ya asi con los parametros que le tengo puesto.
    SI corren esto con una computadora donde vtube studio no esta instalado entonces no va haber conectividad con el mismo.
    Pero aun funcionarian el chat de prueba coin la IA y hara la creacion del output de audio y lo tocara por el speaker.
    Ya que virtual cable no esta instalado en ninunga maquina escolar solo tocara audio del dispositivo de audio que este
    seleccionado en windows."""
    
    vts = VtubeControll() #Creates object to use the vtube studio plugin

    #crash prevention
    try:
        print('Intializing Plugin...')
        await vts.initialize() #initializes the vtube studio plugin
        print('done.')
    #if gone wrong then print out an error
    except Exception as e:
        print(f"Failed to initialize or authenticate: {e}")


    ai = nous(vts=vts)

    ai.initialize(user_input_service='console',
                    stt_duration = None,
                    mic_index = None,

                    chatbot_service='test',
                    chatbot_model = None,
                    chatbot_temperature = None,
                    personality_file = None,

                    tts_service='google', 
                        output_device=None, #DO NOT TOUCH THIS unless auto detection is somehow messing up
                    tts_voice=None,
                    tts_model = None
                )
    print("AI initialized. Starting conversation loop...\n")
    while True:
        await ai.conversation_cycle()

#if this file is executed directly it will run the main funtion
if __name__ == "__main__":
   asyncio.run(main())