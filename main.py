import asyncio
from IA import IA
from VtubeS_Plugin import VtubeControll

async def main():
    vts = VtubeControll()
    await vts.initialize() #starts up the plugin

    ai = IA(vts=vts)

    ai.initialize(user_input_service='console',
                     stt_duration = None,
                     mic_index = None,

                    chatbot_service='test',
                    chatbot_model = None,
                    chatbot_temperature = None,
                    personality_file = None,

                    tts_service='google', 
                    output_device=8,
                    tts_voice=None,
                    tts_model = None
                    )

    while True:
        IA.conversation_cycle()

#if this file is executed directly it will run the main funtion
if __name__ == "__main__":
   asyncio.run(main())