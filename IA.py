#all of the import libraries duh
import asyncio #this is for the web requests and api calls, basically for the vtube studio plugin
import openai #well... its opena ai
from openai import OpenAI # more ai
import speech_recognition as sr #self explanatory I think
from gtts import gTTS #goolge tts free :)
from elevenlabs import generate, save, set_api_key, voices #shitty elevenlab paid config libraries
import sounddevice as sd #sounddevice important in a function
import soundfile as sf #library to generate the sound file

from VtubeS_Plugin import VtubeControll #my vtube plugin
from dotenv import load_dotenv #for the env.txt to put the api keys into
from os import getenv, path #gets the system envorenment variable
from json import load, dump, dumps, JSONDecodeError

#this code uses classes, because its prob the best way to do this and looks very cool
#If you want to understand this watch this video https://www.youtube.com/watch?v=u4Ryk0YuW6A

#class of the AI this time IA as the name in spanish
class nous:
    #initializacion that puts placeholders on all the modifiable variables
    def __init__(self, vts: VtubeControll=None) -> None: #vts argument is used for the vtube studio plugin in main.py
        self.vts = vts 
        self.mic = None
        self.recogniser = None

        self.user_input_service = None
        self.stt_duration = None #stt is Speech To Text which is the speec recognizion

        self.chatbot_service = None
        self.chatbot_model = None
        self.chatbot_temperature = None
        self.chatbot_personality_file = None

        self.message_history = []
        self.context = []

        self.tts_service = None
        self.tts_voice = None
        self.tts_model = None

    #defines all of the variables, the function that calls all of the api keys from the env.txt
    def initialize(self, user_input_service:str = None, stt_duration:float = None, mic_index:int = None,
                    chatbot_service:str = None, chatbot_model:str = None, chatbot_temperature:float = None, personality_file:str = None,
                    tts_service:str = None, output_device = None, tts_voice:str = None, tts_model:str = None) -> None:
        load_dotenv() #loads the env.txt file with the api keys

        #function that prints out all audio device, used for debuggin 
        self.debug_audio_devices()

        #speech recognition using open ai "whisper" or google 
        self.update_user_input(user_input_service=user_input_service, stt_duration=stt_duration)
        self.mic = sr.Microphone(device_index=mic_index)
        self.recogniser = sr.Recognizer()
        
        #calls all of the open ai chat bot functions
        openai.api_key = getenv("OPENAI_API_KEY")
        self.update_chatbot(service = chatbot_service, model = chatbot_model, temperature = chatbot_temperature, personality_file = personality_file)
        self.__load_chatbot_data()
        
        #calls the tts function
        self.update_tts(service=tts_service, output_device=output_device, voice=tts_voice, model=tts_model)

    #debug function that prints out all of audio devices
    def debug_audio_devices(self):
     """Debug all audio devices"""
     devices = sd.query_devices() #gets the list of audio devices
     print("\n=== ALL AUDIO DEVICES ===")
     for i, device in enumerate(devices): #enumerates thge audio devices
         print(f"[{i}] {device['name']}")
         print(f"    Max input channels: {device['max_input_channels']}")
         print(f"    Max output channels: {device['max_output_channels']}")
         print(f"    Default sample rate: {device['default_samplerate']}")
         print()   
   
   #updates and configures chat gpt stt 'whisper'
    def update_user_input(self, user_input_service:str = 'whisper', stt_duration:float = 0.5) -> None:
        #if user input is none then automatically put whisper
        if user_input_service:
            self.user_input_service = user_input_service 
        elif self.user_input_service is None: 
            self.user_input_service = 'whisper' 

       #magic code that adjust for ambience noise
        if stt_duration:
            self.stt_duration = stt_duration
        elif self.stt_duration is None:
            self.stt_duration = 0.5 #don't really know how this value works itf its any different from 0.5 there are problems so don't touch it XD

   #defines the specific of the open ai's chatbot functions, only modify the chatgpt model
   #the variable "temperature" if to determine the model randomness, everything else is self explanatory
    def update_chatbot(self, service:str = 'openai', model:str = 'gpt-3.5-turbo', temperature:float = 0.5, personality_file:str = 'personality.txt') -> None:
        
        #chat bot service
        if service:
            self.chatbot_service = service
        elif self.chatbot_service is None:
            self.chatbot_service = 'openai'

        #open ai model, change depending on what model you're paying the api key. 
        if model:
            self.chatbot_model = model
        elif self.chatbot_model is None:
            self.chatbot_model = 'gpt-3.5-turbo'

        #temperature, randomness in responses. 
        if temperature:
            self.chatbot_temperature = temperature
        elif self.chatbot_temperature is None:
            self.chatbot_temperature = 0.5

        #the personality file.
        if personality_file:
            self.chatbot_personality_file = personality_file
        elif self.chatbot_personality_file is None:
            self.chatbot_personality_file = 'personality.txt'

    #finds the vb virtual audio cable 
    def get_cable_device_id(self):
     """FIND THE CABLE OUTPUT FOR VTUBE LYPSYCN"""
     devices = sd.query_devices()

     #llok for cable input with 44100 sample rate
     for i, device in enumerate(devices): #enumerates the audio devices
         device_name = str(device['name']).lower() #converts audio devices to a string and puts it in lower case 
         #if audio devices are more than 0 then check if a 'cable input' or 'vb-audio virtual cable' exists
         if (device['max_output_channels'] > 0 and 
             'cable input' in device_name and 
             'vb-audio virtual cable' in device_name and
             device['default_samplerate'] == 44100.0):
             print(f"Found VB Cable Input: [{i}] {device['name']}") #prints that audio device name
             return i #return the cable input ID
    #print error if cable input not found
     print("Warning: No VB Cable Input found.")
     return None
    
    #function that updates the text to speech, chacks which service the user is using
    def update_tts(self, service:str = 'google', output_device = None, voice:str = None, model:str = None) -> None:
        
        #If service is set to none then automatically use google tts
        if service:
            self.tts_service = service
        elif self.tts_service is None:
            self.tts_service = 'google'

       #if service is elevenlabs then use 
        if service == 'elevenlabs':
            elevenlabs_api = getenv('ELEVENLABS_API_KEY')
            if elevenlabs_api:
                set_api_key(elevenlabs_api)
            else:
                print("WARNING: No api for elevenlabs.")

       #configs for the levenlabs voice
        if voice:
            self.tts_voice = voice
        elif self.tts_voice is None:
            self.tts_voice = 'Elli'

        if model:
            self.tts_model = model
        elif self.tts_model is None:
            self.tts_model = 'eleven_monolingual_v1'

        #find and set the vb cable device
        self.cable_device_id = self.get_cable_device_id() #gets the cable device id from the funtcion I made to detect it
        if self.cable_device_id is not None: #if cable device actually has an id then print it
             print(f"VB Cable decive set to id: {self.cable_device_id}")
        #if there is no cable device then print an error
        else:
             print("ERROR: No VB Cable found, lyp sync wont work.")
    
   #gets and lists all audio devices
    def get_audio_devices(self): #honestly im pretty sure this functin is unnecesary, but the code functions so im not gonna touch it and wreck it 
        return sd.query_devices() 
    
    #gets user input and turns into a string to send it the chatbot from desired service 
    #"None" means they'll use the default values
    def get_user_input(self, service:str = None, stt_duration:float = None) -> str:
        #this are the variables used in initialize, if set to none it uses the default values
        service = self.user_input_service if service is None else service
        stt_duration = self.stt_duration if stt_duration is None else stt_duration

        #lists of services
        supported_stt_services = ['whisper', 'google']
        supported_text_services = ['console']
        
        #checks the supported services, if there aren't any stt services then it uses the console
        result = "" 
        #self variables with double underscore like self.__recognise_speech are only meant to be used inside the class not called from the outside
        #this self variables are functions that are defined later in the code around line 365
        if service in supported_stt_services:
            result = self.__recognise_speech(service, duration=stt_duration)
        elif service in supported_text_services:
            result = self.__get_text_input(service)
        #if user inputted wrong or unsopported the raise an error
        else:
            raise ValueError(f"{service} servise doesn't supported. Please, use one of the following services: {supported_stt_services + supported_text_services}")
        
        #returns the console prompt or the speech recognition turned into a string
        return result
    
    #the chatgpt response
    #"None" means they'll use the default values
    def get_chatbot_response(self, prompt:str, service:str = None, model:str = None, temperature:float = None) -> str:
        service = self.chatbot_service if service is None else service
        model = self.chatbot_model if model is None else model
        temperature = self.chatbot_temperature if temperature is None else temperature

        supported_chatbot_services = ['openai', 'test']

        #checks which chatbot service there is, if openai api key isn't activated then it will just put out the test response
        result = ""
        if service == 'openai':
            result = self.__get_openai_response(prompt, model=model, temperature=temperature)
        elif service == 'test':
            result = "Test answer from the very great assistant!" #test answer
        #if user inputted wrong or unsopported the raise an error
        else:
            raise ValueError(f"{service} servise doesn't supported. Please, use one of the following services: {supported_chatbot_services}")
        
        #returns chatgpt response
        return result
    
    #text to speech settings 
    #"None" means they'll use the default settings
    async def tts_say(self, text:str, service:str = None, voice:str = None, model:str = None) -> None:
        service = self.tts_service if service is None else service
        voice = self.tts_voice if voice is None else voice
        model = self.tts_model if model is None else model

        supported_tts_services = ['google', 'elevenlabs', 'console'] #supported tts services

        #if the service is not in supported_tts_services it throws and error
        if service not  in supported_tts_services:
            raise ValueError(f"{service} servise doesn't supported. Please, use one of the following services: {supported_tts_services}")
        
        #print to console first 
        print('\n\33[7m' + "Epic Assistant:" + '\33[0m' + f' {text}')

        #checks the service of the output
        try:
         if service == 'google':
             gTTS(text=text, lang='en', slow=False, lang_check=False).save('output.wav') #you can put the output in whatever audio extension you want
             print('\n\33[7m' + "Epic Assistant:" + '\33[0m' + f' {text}') #prints gtts response in console
         elif service == 'elevenlabs': #chooses the elevenlabs sevice which was configured earlier
             self.__elevenlabs_generate(text=text, voice=voice, model=model)
        except Exception as e:
             print(f"Error generating tts: {e}")
             return

        #error checks!
        if not path.exists('output.wav'): #if output was not created then print error
            print("ERROR output.wav file was not created!")
            return
        
        print(f"File size: {path.getsize('output.wav')}") #print file size of audio output that was created

        #tries reading the audio file
        try:
            print("reading audio file...")
            data, samplerate = sf.read('output.wav') #make this variables read the output file
            print(f"Audio loaded: {len(data)} samples at {samplerate}Hz") #counts  the sample and hz and then prints it 

            #resamples if audio is not 44100
            if samplerate!=44100:
                print("resampling audio")
                import librosa #library used for resampling audio
                data = librosa.resample(data, orig_sr=samplerate, target_sr=44100)
                samplerate=44100

            #if cable device has an id (which we set earlier in the code) then play in default speaker and in cable input
            if self.cable_device_id is not None:
                print(f"Playing to both default and VB Cable device: {self.cable_device_id}")
                
                #play to both devices simultaneously using threading
                import threading #library used for... you guessed it! threading!

                #function that plays on the default device
                def play_to_default(): 
                    sd.play(data, samplerate)
                    sd.wait() #waits for audio to finish

                #function that plays to the cable input
                def play_to_cable():
                    sd.play(data, samplerate, device=self.cable_device_id)
                    sd.wait() #waits for audio to finish
                    print("Audio sent to VB Cable Vtube studio should detect it.")
                
                #start both threads
                thread1 = threading.Thread(target=play_to_default) #run play on defualt device function in 1 thread
                thread2 = threading.Thread(target=play_to_cable) #run play on cable input on another thread
                
                #start both threads
                thread1.start()
                thread2.start()
                
                #wait for both threads to complete
                thread1.join()
                thread2.join()
            #if cable input doesnt have an id then just play on the default device
            else:
                print("No VB Cable found, playing to default only")
                sd.play(data, samplerate)
                sd.wait() #waits for audio to finish playing

            print("Audio playback completed")

        #if code execution gone wrong then print an error
        except Exception as e:
            print(f"Error playing audio. Are your sounds alright?: {e}")

    #little function that puts in play the user input and the chatgpt response
    async def conversation_cycle(self) -> dict:
        input = self.get_user_input()
        response = self.get_chatbot_response(input)
        
        #trigger emotion immediatly when response is generated
        if self.vts:
            try:
                emotion = self.vts.emotion_auto(response) #calls the emotion auto function in vts plugin
                print(f"Detected emtotion: '{emotion}'")
                if emotion != "Neutral":
                    await self.vts.trigger_hotkey(emotion)
            #if there is an error in triggering a hotkey then print it
            except Exception as e:
                print(f"Vtube studio error: {e}")
        await self.tts_say(response) #wait for chatgpt response to finish
    
    #get chatgptn response
    def __get_openai_response(self, prompt:str, model:str, temperature:float) -> str:
        self.__add_message('user', prompt) #adds the users message to history
        messages = self.context + self.message_history #combines the users prompts with the context (the personality file)

        #creates a chat in open ai chatgpt api 
        client = OpenAI(api_key= getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature, 
        )
        response = response.choices[0].message.content #extracts the content from the reply

        self.__add_message('assistant', response) #adds chatgpt response to the message history
        self.__update_message_history() #updates the history

        return response #returns the response generated by chatgpt
    
    #this marks if the message is from the user or chatgpt
    def __add_message(self, role:str, content:str) -> None:
        self.message_history.append({'role': role, 'content': content})

    #loads the personality file, this is where the os lib is used
    def __load_chatbot_data(self, file_name:str = None) -> None:
        file_name = self.chatbot_personality_file if file_name is None else file_name #makes the personality.txt file the default one

        #opens the persnality file in read mode
        with open(file_name, 'r') as file:
            personality = file.read()
        self.context = [{'role': 'system', 'content': personality}] #stores it so cahtgpt can read the previous conversation

        #if a message history file exists, open it and continue the convo
        if path.isfile('./message_history.txt'):
            with open('message_history.txt', 'r') as file:
                try:
                    self.message_history = load(file)
                except JSONDecodeError:
                    pass
    
    #creates a .txt out of the message history 'w' is write mode
    def __update_message_history(self) -> None:
        with open('message_history.txt', 'w') as file:
                dump(self.message_history, file)

    #if the user input is set to console show this prompt and get input
    def __get_text_input(self, service:str) -> str:
        user_input = ""
        if service == 'console':
            user_input = input('\n\33[42m' + "User:" + '\33[0m' + " ")
        return user_input
    
    #generate audio output from elevenlabd 
    def __elevenlabs_generate(self, text:str, voice:str, model:str, filename:str='output.mp3'): #set to preffered audio extension
        audio = generate(
                 text=text,
                 voice=voice,
                 model=model
                )
        save(audio, filename)

    #turn the audio to text
    def __recognise_speech(self, service:str, duration:float) -> str:
        with self.mic as source: #opens mic
            print('(Start listening)')
            self.recogniser.adjust_for_ambient_noise(source, duration=duration) #adjust ambient noise
            audio = self.recogniser.listen(source) #record mic
            print('(Stop listening)') 

            #passes the audio to be transcribe by either whisper or google
            result = ""
            try:
                if service == 'whisper':
                    result = self.__whisper_sr(audio)
                elif service == 'google':
                    result = self.recogniser.recognize_google(audio)
            except Exception as e:
                print(f"Exeption: {e}")
        return result
    
    #amkes whisper open the audio and transcribes it into text
    def __whisper_sr(self, audio) -> str:
     try:
         with open('speech.wav', 'wb') as file:
             file.write(audio.get_wav_data())
    
         client = OpenAI(api_key=getenv("OPENAI_API_KEY"))
    
         with open('speech.wav', 'rb') as audio_file:
             transcript = client.audio.transcriptions.create(
             model="whisper-1", 
             file=audio_file
            )
             return transcript.text
     except Exception as e:
         print(f"Error in Whisper transcription: {e}")
         return ""


#main function, initializes the ai
def main():
    ai = nous()
    ai.initialize(user_input_service='console', 
                 chatbot_service='test', 
                 tts_service='google', output_device=8)
    
    #starts the conversation cycle
    ai.conversation_cycle()

    #loop to repeat convo
    while True:
       ai.conversation_cycle()

#if this file is executed directly it will run the main funtion
if __name__ == "__main__":
    main()

