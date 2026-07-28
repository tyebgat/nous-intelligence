#local imports
from json import load, dump, JSONDecodeError, loads
from openai import OpenAI
import os
from os import getenv
import sys
import time
import threading
from paths import BASE_PATH

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'
class ChatBot:
    def __init__(self, chat_bot_service: str = "openai",openai_model: str = None, detailed_logs: bool = False, model_path: str = "", remember_conversation: bool = False) -> None:
        self.openai_model = openai_model
        self.detailed_logs = detailed_logs
        self.chatbot_service = chat_bot_service
        self.model_path = model_path
        self.remember_conversation = remember_conversation
        self.message_history = []
        self.context = None
        self._spinner_active = False

    def _start_spinner(self, label="Thinking"):
        self._spinner_active = True
        chars = ['-', '\\', '|', '/']
        def spin():
            i = 0
            while self._spinner_active:
                sys.stdout.write(f"\r{YELLOW}{label} {chars[i % len(chars)]}{RESET}")
                sys.stdout.flush()
                time.sleep(0.1)
                i += 1
            sys.stdout.write(f"\r{YELLOW}{label} done.{RESET}\n")
            sys.stdout.flush()
        self._spinner_thread = threading.Thread(target=spin, daemon=True)
        self._spinner_thread.start()

    def _stop_spinner(self):
        self._spinner_active = False
        if hasattr(self, '_spinner_thread'):
            self._spinner_thread.join()

    def load_chatbot_personality(self) -> list:
        with open(os.path.join(BASE_PATH, "personality.txt"), "r") as personality:
            text = personality.read()
        return [{"role": "system", "content": text}]
    
    def initialize(self) -> None:
        self.context = self.load_chatbot_personality()
        self.load_chatbot_data()

    def get_chatbot_response(self, prompt: str) -> str:
        #-----------------------------
        #Open AI response 
        #------------------------------
        if self.chatbot_service == "openai":
            try:
                client = OpenAI(api_key=getenv("OPENAI_API_KEY"))
                self._add_message('user', prompt)
                messages = self.context + self.message_history
                self._start_spinner()
                response_obj = client.chat.completions.create(
                    model=self.openai_model,
                    messages=messages,
                    temperature=0.5
                )
                self._stop_spinner()
                chatgpt_response = response_obj.choices[0].message.content
                self._add_message('assistant', chatgpt_response)
                self._update_message_history()
                return chatgpt_response
            except Exception as e:
                self._stop_spinner()
                print(f"{RED}OpenAI API error: {e}{RESET}")
                return "Api error."
        #-----------------------------
        #Local LLM Implementation
        #------------------------------
        elif self.chatbot_service == "local":
            try:
                client = OpenAI(base_url="http://localhost:8080/v1", api_key="not-needed-locally")
                self._add_message('user', prompt)
                messages = self.context + self.message_history

                self._start_spinner()
                response_obj = client.chat.completions.create(
                    model="local-model",
                    messages=messages,
                    temperature=0.7,
                )
                self._stop_spinner()

                local_model_response = response_obj.choices[0].message.content
                self._add_message('assistant', local_model_response)
                self._update_message_history()
                return local_model_response
            except Exception as e:
                self._stop_spinner()
                print(f"{RED}An error has ocurred on local llm: {e}{RESET}")
                return "Local model error"
        #-----------------------------
        #Dummy response
        #------------------------------
        elif self.chatbot_service == "test":
            dummy_response = "Testing tts, functions great!"
            self._add_message('user', prompt)
            self._add_message('assistant', dummy_response)
            self._update_message_history()
            return dummy_response
        else:
            print(f"{ORANGE}unknown chatbot service. chatbot_services {self.chatbot_service}{RESET}")

    def _add_message(self, role: str, content: str) -> None:
        self.message_history.append({'role': role, 'content': content})

    def load_chatbot_data(self) -> None:
        if not self.remember_conversation:
            self.message_history = []
            if os.path.isfile(os.path.join(BASE_PATH, 'Data', 'message_history.txt')):
                with open(os.path.join(BASE_PATH, 'Data', 'message_history.txt'), 'w') as file:
                    file.write('')
            return
        if os.path.isfile(os.path.join(BASE_PATH, 'Data', 'message_history.txt')):
            try:
                with open(os.path.join(BASE_PATH, 'Data', 'message_history.txt'), 'r') as file:
                    self.message_history = load(file)
            except JSONDecodeError:
                pass

    def _update_message_history(self) -> None:
        if not self.remember_conversation:
            return
        with open(os.path.join(BASE_PATH, 'Data', 'message_history.txt'), 'w') as file:
            dump(self.message_history, file)
