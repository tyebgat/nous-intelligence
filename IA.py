#all of the import libraries duh
import openai #well... its opena ai
import speech_recognition as sr #self explanatory I think
from gtts import gTTS #goolge tts free :)
from elevenlabs import generate, save, set_api_key, voices #shitty elevenlab paid config libraries
import sounddevice as sd #sounddevice important in a function
import soundfile as sf #library to generate the sound file

from dotenv import load_dotenv #for the env.txt to put the api keys into
from os import getenv, path #gets the system envorenment variable
from json import load, dump, dumps, JSONDecodeError

#this code uses classes, because its prob the best way to do this and looks very cool
#If you want to understand this watch this video https://www.youtube.com/watch?v=u4Ryk0YuW6A

#class of the AI this time IA as the name in spanish
class IA:
    #initializacion that puts placeholders on all the modifiable variables
    def __init__(self) -> None:
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

        #speech recognition using open ai "whisper" or google 
        self.update_user_input(user_input_service=user_input_service, stt_duration=stt_duration)
        self.mic = sr.Microphone(device_index=mic_index)
        self.recogniser = sr.Recognizer()
        
        #calls all of the open ai chat bot functions
        openai.api_key = getenv("OPENAI_API_KEY")
        self.update_chatbot(service = chatbot_service, model = chatbot_model, temperature = chatbot_temperature, personality_file = personality_file)
        self.__load_chatbot_data()
        
        #calls the tts functions
        self.update_tts(service=tts_service, output_device=output_device, voice=tts_voice, model=tts_model)

   #here you define which service you are using for the speech recognition "whisper" is open ai service 
    def update_user_input(self, user_input_service:str = 'whisper', stt_duration:float = 0.5) -> None:
        if user_input_service:
            self.user_input_service = user_input_service #puts the default speech recognitizion which is none
        elif self.user_input_service is None: #puts open ai's speech recognition if user_input_service is set to none
            self.user_input_service = 'whisper' #set to 'google' or 'console' depending in which user input you want

       #magic code that adjust for ambience noise
        if stt_duration:
            self.stt_duration = stt_duration
        elif self.stt_duration is None:
            self.stt_duration = 0.5 #don't really know how this value works itf its any different from 0.5 there are problems so don't touch it XD

   #defines the specific of the open ai's chatbot functions, modify these depending on your open ai model api
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

    #here you specify the service fot the text to speech
    #"None" means they'll use the default values
    def update_tts(self, service:str = 'google', output_device = None, voice:str = None, model:str = None) -> None:
        
        #google tts, free but robotic and doesnt sound good
        if service:
            self.tts_service = service
        elif self.tts_service is None:
            self.tts_service = 'google'

       #calls the eleven lab api from the env.txt
        set_api_key("your_api_key_here") #CHANGE THIS TO set_api_key(getenv('ELEVENLABS_API_KEY')) IF YOURE NOT DEBUGGING

       #configs for the levenlabs voice
        if voice:
            self.tts_voice = voice
        elif self.tts_voice is None:
            self.tts_voice = 'Elli'

        if model:
            self.tts_model = model
        elif self.tts_model is None:
            self.tts_model = 'eleven_monolingual_v1'

        #the output device where the tts will send its audio, needs vb audio cable
        #sd stands for Sound Device
        if output_device is not None:
            try:
                sd.check_output_settings(output_device)  #checks output settings
                sd.default.samplerate = 44100 #sample rate in hz ex: 44100 is 44khz 
                sd.default.device = output_device #sets the default device (should be the vb cable)
            except sd.PortAudioError:
                #error
                print("Invalid output device! Make sure you've launched VB-Cable.\n",
                       "Check that you've choosed the correct output_device in initialize method.\n", 
                       "From the list below, select device that starts with 'CABLE Input' and set output_device to it's id in list.\n",
                       "If you still have this error try every device that starts with 'CABLE Input'. If it doesn't help please create GitHub issue.")
                print(sd.query_devices()) 
                raise

   #gets and lists all audio devices
    def get_audio_devices(self):
        return sd.query_devices() 
    
    #gets user input and turns into a string to send it the chatbot from desired service 
    #"None" means they'll use the default values (look up in the code for them)
    def get_user_input(self, service:str = None, stt_duration:float = None) -> str:
        service = self.user_input_service if service is None else service
        stt_duration = self.stt_duration if stt_duration is None else stt_duration

        #lists of services
        supported_stt_services = ['whisper', 'google']
        supported_text_services = ['console']
        
        #checks the supported services, if there aren'y any stt services then it uses the console
        result = ""
        if service in supported_stt_services:
            result = self.__recognise_speech(service, duration=stt_duration)
        elif service in supported_text_services:
            result = self.__get_text_input(service)
        else:
            #error
            raise ValueError(f"{service} servise doesn't supported. Please, use one of the following services: {supported_stt_services + supported_text_services}")
        
        #returns the console prompt or the speech recognition turned into a string
        return result
    
    #the chatgpt response
    #"None" means they'll use the default values (look up in the code for them)
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
        else:
            raise ValueError(f"{service} servise doesn't supported. Please, use one of the following services: {supported_chatbot_services}")
        
        #returns chatgpt response
        return result
    
    #text to speech settings 
    #"None" means they'll use the default settings
    def tts_say(self, text:str, service:str = None, voice:str = None, model:str = None) -> None:
        service = self.tts_service if service is None else service
        voice = self.tts_voice if voice is None else voice
        model = self.tts_model if model is None else model

        supported_tts_services = ['google', 'elevenlabs', 'console']

        #if the service is not in supported_tts_services it throws and error
        if service not  in supported_tts_services:
            raise ValueError(f"{service} servise doesn't supported. Please, use one of the following services: {supported_tts_services}")
        
        #checks the service of the output
        if service == 'google':
            gTTS(text=text, lang='en', slow=False, lang_check=False).save('output.mp3') #you can put the output in whatever audio extension you want
        elif service == 'elevenlabs': #chooses the elevenlabs sevice which was configured earlier
            self.__elevenlabs_generate(text=text, voice=voice, model=model)

        #prints the output to console
        elif service == 'console':
            print('\n\33[7m' + "Epic Assistant:" + '\33[0m' + f' {text}')
            return

        data, samplerate = sf.read('output.mp3') #reads the audio fale generated
        sd.play(data, samplerate) #plays the audio file
        sd.wait() #wait for playback to finish

    #little function that puts in play the user input and the chatgpt response
    def conversation_cycle(self) -> dict:
        input = self.get_user_input()

        response = self.get_chatbot_response(input)

        self.tts_say(response) #pass the response through the tts functions
        
        return dict(user = input, assistant = response) #returns everything in a dictionary
    
    #get chatgptn response
    def __get_openai_response(self, prompt:str, model:str, temperature:float) -> str:
        self.__add_message('user', prompt) #adds the users message to history
        messages = self.context + self.message_history #combines the users prompts with the context (the personality file)

        #creates a chat in open ai chatgpt api 
        response = openai.create_chat.create(
            model=model,
            messages=messages,
            temperature=temperature, 
        )
        response = response.choices[0].message["content"] #extracts the content from the reply

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
        with open('speech.wav', 'wb') as file:
            file.write(audio.get_wav_data())
            audio_file = open('speech.wav', 'rb')
            transcript = openai.Audio.transcribe(model="whisper-1", file=audio_file)
        return transcript['text']


#main function, initializes the ai
def main():
    ai = IA()
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

