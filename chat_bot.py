#local imports
from json import load, dump, JSONDecodeError
from openai import OpenAI
import os
from os import getenv

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'
class ChatBot:
    def __init__(self, chat_bot_language: str = "english", chat_bot_service: str = "openai", detailed_logs: bool = False, model_path: str = "", remember_conversation: bool = False) -> None:
        self.detailed_logs = detailed_logs
        self.chat_bot_language = chat_bot_language
        self.chatbot_service = chat_bot_service
        self.model_path = model_path
        self.remember_conversation = remember_conversation
        #--- chatbot language set --- 
        if self.chat_bot_language == "english":
            self.context = [
                {
                    "role": "system",
                    "content": "You are nous, a virtual assistant with a friendly and sarcastic tone, treat the user like old friends joking around. you are a woman. Answer only in small sentences. You love technology and often make jokes about it. you are enthusiastic but sometimes sarcastic. Always reply in english, no matter the language. Do not use emojis or format the text in your response."
                }
            ]
        elif self.chat_bot_language == "spanish":
            self.context = [
                {
                    "role": "system",
                    "content": "You are nous, a virtual assistant with a friendly and sarcastic tone, treat the user like old friends joking around. you are a woman. Answer only in small sentences. You love technology and often make jokes about it. you are enthusiastic but sometimes sarcastic. Always reply in spanish, no matter the language. Do not use emojis or format the text in your response."
                }
            ]
        else: 
            print(f"{ORANGE}Chat bot can only be either 'english' or 'spanish' you have entered an unsupported language{RESET}")
        
        self.message_history = []

    def get_chatbot_response(self, prompt: str) -> str:
        #-----------------------------
        #Open AI response 
        #------------------------------
        if self.chatbot_service == "openai":
            try:
                client = OpenAI(api_key=getenv("OPENAI_API_KEY")) #calls api key
                self._add_message('user', prompt)
                messages = self.context + self.message_history #chatgpt personality plus the chatbot history
                response_obj =  client.chat.completions.create( #create chat with openai function and store it in a variable
                    model = "gpt-4o-mini",
                    messages=messages,
                    temperature=0.5
                )
                chatgpt_response = response_obj.choices[0].message.content #in chatgpt response, it gets the first response in 'content'
                self._add_message('assistant', chatgpt_response)
                self._update_message_history()
                return chatgpt_response
            except Exception as e:
                print(f"{RED}Opeai api error: {e}{RESET}")
                return "Api error."
        #-----------------------------
        #Local LLM Implementation
        #------------------------------
        elif self.chatbot_service == "local":
            try:
                client = OpenAI(base_url="http://localhost:8080/v1", api_key="not-needed-locally")
                self._add_message('user', prompt)
                messages = self.context + self.message_history
                response_obj = client.chat.completions.create(
                    model = "local-model",
                    messages= messages,
                    temperature=0.7
                )
                local_model_response = response_obj.choices[0].message.content
                self._add_message('asistant', local_model_response)
                self._update_message_history()
                return local_model_response
            except Exception as e:
                print(f"{RED}An error has ocurred on local llm: {e}{RESET}")
                return "Local model error"
        #-----------------------------
        #Dummy response
        #------------------------------
        elif self.chatbot_service == "test": #test answer
            dummy_response = "Testing tts, functions great!"
            self._add_message('user', prompt)
            self._add_message('assistant',dummy_response)
            self._update_message_history()
            return dummy_response
        else:
            print(f"{ORANGE}unknown chatbot service. chatbot_services {self.chatbot_service}{RESET}")

    def _add_message(self, role: str, content: str) -> None: #this only saves to ram
        self.message_history.append({'role': role, 'content': content}) #adds messaages in history as a dictionary

    def load_chatbot_data(self) -> None:
        if self.remember_conversation:
            self.message_history = []
            return
        if os.path.isfile('Data/message_history.txt'):
            try:
                with open('Data/message_history.txt', 'r') as file:
                    self.message_history = load(file)
            except JSONDecodeError:
                pass

    def _update_message_history(self) -> None:
        if self.remember_conversation:
            return
        with open('Data/message_history.txt', 'w') as file:
            dump(self.message_history, file)

#---cool kids dont need a main function---
