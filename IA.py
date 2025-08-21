import asyncio #asynchronous lirbary that lets every IO task be in sync
import speech_recognition as sr #handles speech recognition
from gtts import gTTS #google's text to speech
import sounddevice as sd #library that allows audio playback to a selected device
import soundfile as sf #library that enables creation of audio file
from VtubeS_Plugin import VtubeControll #My vtube studio plugin :3
import os #os library path to check existence of files
from json import load, dump, JSONDecodeError #Library used for saving and loading chat history
from dotenv import load_dotenv #library to load the .env file
from openai import OpenAI #open ai library
from os import getenv #library to open the .env file
import keyboard
import time

class Nous:
    def __init__(self, vts: VtubeControll = None) -> None:
        #chatgpt personlaity
        self.context = [
            {
                "role": "system",
                "content": "You are nous, a virtual assistant with a friendly tone. you are a woman. Answer only in small sentences. You love technology and often make jokes about it. you are enthusiastic but sometimes sarcastic"
            }
        ]
        #variable initialization
        self.is_speaking = False
        self.vts = vts #calls the vts plugin
        self.chatbot_service = "openai"
        self.user_input_service = "speech"
        self.mic = None #mic for speech recognition, None means it will use default device
        self.recogniser = sr.Recognizer()
        self.message_history = []
        self.cable_device_id = None
        self.last_audio_duration = 0

    def initialize(self, mic_index: int = None) -> None:
        self.debug_audio_devices() #prints all available audio devices for debuggin purposes
        self.mic = sr.Microphone(device_index=mic_index)  #micrphone where audio will be played
        self.cable_device_id = self.get_cable_device_id() #gets cable device id
        if self.cable_device_id is not None:
            print(f"VB Cable device set to id: {self.cable_device_id}") #prints cable device id
        else:
            print("No VB cable found, lypsinc may not work.")
        load_dotenv()
        self.load_chatbot_data() #loads chatbot history if it exists

    def debug_audio_devices(self):
        devices = sd.query_devices() #gets a lists of all audio devices
        print("\n=== ALL AUDIO DEVICES ===")
        #loops stores the index of each device in i, printing the following information of each audio device
        for i, device in enumerate(devices):
            print(f"[{i}] {device['name']}")
            print(f"    Max input channels: {device['max_input_channels']}")
            print(f"    Max output channels: {device['max_output_channels']}")
            print(f"    Default sample rate: {device['default_samplerate']}")
            print()

    def get_cable_device_id(self):
        devices = sd.query_devices()
        #same loop logic as the past function
        #except this one checks if the name matches with cable input audio device
        for i, device in enumerate(devices):
            name = str(device['name']).lower()
            #checks the name output and sample rate to identify the audio cable
            if (device['max_output_channels'] > 0 and
                'cable input' in name and
                'vb-audio virtual cable' in name and
                device['default_samplerate'] == 44100.0):
                print(f"Found VB Cable Input: [{i}] {device['name']}")
                return i #returns i AKA the audio device inidex/id
        return None

    async def get_user_input(self) -> str:
        if self.user_input_service == "console": #input from console
            def get_input_blocking():
                try:
                    print('\033[s', end='') #save cursor position
                    user_input = input('\n\33[7m' + "User: " + '\33[0m')
                    print('\033[u', end='') #restore cursor position
                    return user_input #returns input from conole
                except Exception as e:
                    print(f"console input error: {e}")
                    return ""
            return await asyncio.to_thread(get_input_blocking)
        elif self.user_input_service == "speech":
            def get_speech_blocking():
                print("-----Press space to start listening.----")
                while True:
                    if keyboard.is_pressed(' '):
                        print("listening for 10 seconds...")
                        break
                    else:
                        time.sleep(0.1)
                #'with' is a fancy way of doing 'source = sr.Microphone()'
                #what 'with' allows me to do is end the hassle of closing the variable manually (source.open_stream()/source.close_stream())
                with self.mic as source: #here its used to assigned the open mic to a variable called source
                    self.recogniser.adjust_for_ambient_noise(source, duration=0.5) #function from sr library we pass the audio through here to reduce noise
                    try:
                        audio = self.recogniser.listen(source, timeout=10)
                        try:
                            text = self.recogniser.recognize_google(audio)
                            print(f"text captured: {text}")
                            return text
                        except sr.UnknownValueError:
                            print("could not understand audio. putting default response...")
                            print("default response: hello!")
                            return "hello!"
                        except sr.RequestError as e:
                            print(F"request error from google: {e} \n putting default response...")
                            print("default response: hello!")
                            return "hello!"
                    except sr.WaitTimeoutError:
                        print("timed out, no speech detected. putting default response...")
                        print("default response: hello!")
                        return "hello!"
            return await asyncio.to_thread(get_speech_blocking)
        else:
            print(f"unknown input service: {self.user_input_service}")
            return ""

    def get_chatbot_response(self, prompt: str) -> str:
        if self.chatbot_service == "openai":
            try:
                client = OpenAI(api_key=getenv("OPENAI_API_KEY")) #calls api key
                self.add_message('user', prompt)
                messages = self.context + self.message_history #chatgpt personality plus the chatbot history
                response_obj =  client.chat.completions.create( #create chat with openai function and store it in a variable
                    model = "gpt-4o-mini",
                    messages=messages,
                    temperature=0.5
                )
                chatgpt_response = response_obj.choices[0].message.content #in chatgpt response, it gets the first response in 'content'
                self.add_message('assistant', chatgpt_response)
                self.update_message_history()
                return chatgpt_response
            except Exception as e:
                print(f"Opeai api error: {e}")
                return "Api error."

        elif self.chatbot_service == "test": #test answer
            dummy_response = "Testing tts, functions great!"
            self.add_message('user', prompt)
            self.add_message('assistant',dummy_response)
            self.update_message_history()
            return dummy_response
        else:
            print(f"unknown chatbot service. chatbot_services {self.chatbot_service}")
            return "Unknown service."
        
    async def tts_say(self, text: str) -> None:
        #chatgpt response or test response in console
        print('\n\33[7m' + "Epic Assistant:" + '\33[0m' + f' {text}')
        self.is_speaking = True
        try:
            #generate tts with response from chatgpt or test reponse
            gTTS(text=text, lang='en', slow=False, lang_check=False).save('output.wav')
        except Exception as e:
            print(f"Error generating TTS: {e}")
            self.is_speaking = False
            return 
        
        if not os.path.exists('output.wav'): #error if the file output is not found
            print("error: output.wav file not created!")
            self.is_speaking = False
            return 

        try:
            #stores the two things sf reads return, data: raw audio data, samplerate: samplerate
            data, samplerate = sf.read('output.wav')
            self.last_audio_duration = len(data) / samplerate #formula for calculating audio duration 

            if self.cable_device_id is not None:
                import threading
                def play_default(): #plays to default device
                    sd.play(data, samplerate)
                    sd.wait() #waits for audio to finish
                def play_cable(): #prints to virtual cable
                    sd.play(data, samplerate, device=self.cable_device_id) #uses our function to find the deivce id and plays it to that device
                    sd.wait() #waits for audio to finish
                #calls threading
                t1 = threading.Thread(target=play_default)
                t2 = threading.Thread(target=play_cable)
                #starts threads
                t1.start()
                t2.start()
                #ends threads
                t1.join()
                t2.join()
            else: #if cable device is not found then just play it to the default device
                sd.play(data, samplerate)
                sd.wait()
        except Exception as e:
            print(f"Error playing audio: {e}")
        finally:
            self.is_speaking =False

    async def conversation_cycle(self):
        while True:
            user_input =  await self.get_user_input() #calls user input
            if not user_input:
                return ""
            response =  self.get_chatbot_response(user_input) #gets chatgpt response or test response

            if self.vts:
                try:
                    dominant_emotion = self.vts.analyze_dominant_emotion(response) #gets dominant emotion form chatgpt response
                    await self.vts.trigger_hotkey(dominant_emotion) #triggers the hotkey corresponding to dominant emotion
                except Exception as e:
                    print(f"Emotion analysis error: {e}")

            await self.tts_say(response) #waits for tts to finish

            if self.vts:
                try:
                    await self.vts.trigger_hotkey("Neutral") #after tts is finish turn clear hotkeys
                except Exception as e:
                    print(f"Error resetting to Neutral: {e}")

    def add_message(self, role: str, content: str) -> None: #this only saves to ram
        self.message_history.append({'role': role, 'content': content}) #adds messaages in history as a dictionary

    def load_chatbot_data(self) -> None: #creates a file with add_message() adds stuff to it 
        if os.path.isfile('./message_history.txt'): #checks if file exists
            try:
                with open('message_history.txt', 'r') as file: #loads file
                    self.message_history = load(file)
            except JSONDecodeError:
                pass #if file si corrupted then just start over fresh

    def update_message_history(self) -> None: 
        with open('message_history.txt', 'w') as file: #opens in write mode
            dump(self.message_history, file) #function from json library, saves the ptyhon dicitonary as a json


def main():
    ai = Nous()
    ai.user_input_service = "console"
    ai.chatbot_service = "test"
    ai.initialize()
    while True:
        asyncio.run(ai.conversation_cycle())

if __name__ == "__main__":
    main()


#------------MEMOS----------------------

"""Help in understanding some function:
in get_chatbot_response: response obj stores chatgpt api response, which is something like this:
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": { ... },
  "model": "gpt-4o-mini"
}
"""

"""
In tts_say funciton at the beginning sf.read function returns something like this:
(array([0.1, -0.2, 0.3, -0.1, ...]), 44100)
these are two different values, which corresponds to the variable they are assigned to in the function.
first is 'data' which holds the raw audio data [0.1, -0.2, 0.3, -0.1, ...]
the other one is 'samplerate' which holeds the samplerate
You can also do it like this:
#result = sf.read
#data = result[0]        # Get first item (audio data)
#samplerate = result[1]  # Get second item (sample rate)
here we point the result variable to each value that sf.read gives us, put python lets us put it all in one line like this
#data, samplerate = sf.read
"""