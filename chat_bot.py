#local imports
from json import load, dump, JSONDecodeError, loads
from openai import OpenAI
import os
from os import getenv
import re
import sys
import time
import threading
from paths import BASE_PATH

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

# emotions the avatar can express; the LLM must pick exactly one per reply
EMOTIONS = ["Happy", "Sad", "Angry", "Surprised", "Neutral"]

# strict schema: the API rejects/repairs anything that doesn't match,
# so the format is guaranteed instead of hoped for (works in any language)
EMOTION_SCHEMA = {
    "name": "emotional_reply",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "emotion": {
                "type": "string",
                "enum": EMOTIONS,
                "description": "The dominant emotional tone of the response text"
            },
            "response": {
                "type": "string",
                "description": "The reply text itself, without any emotion tags or metadata"
            }
        },
        "required": ["emotion", "response"],
        "additionalProperties": False
    }
}

JSON_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")

# belt and braces: strips leaked "[Happy]" style prefixes from any reply text,
# whatever path produced it
LEAKED_TAG_RE = re.compile(
    r"^\s*[\[\(]?\s*(happy|sad|angry|surprised|neutral)\s*[\]\):]?\s*[:,]?\s*",
    flags=re.IGNORECASE
)


def strip_leaked_tags(text: str) -> str:
    return LEAKED_TAG_RE.sub("", text).strip() or text


def parse_emotional_response(raw: str) -> tuple[str, str | None]:
    """Extracts (clean_text, emotion) from a structured reply.

    Returns (cleaned_raw, None) whenever parsing fails so callers can fall
    back to the keyword analyzer instead of dropping the reply.
    """
    if not raw:
        return raw, None

    text = JSON_CODE_FENCE_RE.sub("", raw.strip()).strip()
    try:
        data = loads(text)
    except JSONDecodeError:
        return strip_leaked_tags(raw), None

    if not isinstance(data, dict):
        return strip_leaked_tags(raw), None

    response_text = data.get("response")
    emotion = data.get("emotion")

    if not isinstance(response_text, str) or not response_text.strip():
        return strip_leaked_tags(raw), None
    if emotion not in EMOTIONS:
        emotion = None

    return strip_leaked_tags(response_text), emotion

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

    def get_chatbot_response(self, prompt: str) -> tuple[str, str | None]:
        """Returns (clean_reply_text, emotion) where emotion is one of EMOTIONS
        or None when structured output couldn't be parsed."""
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
                    temperature=0.5,
                    response_format={
                        "type": "json_schema",
                        "json_schema": EMOTION_SCHEMA
                    }
                )
                self._stop_spinner()
                raw_response = response_obj.choices[0].message.content
                chatgpt_response, emotion = parse_emotional_response(raw_response)
                if emotion is None and self.detailed_logs:
                    print(f"{ORANGE}Structured reply unparseable, falling back to keyword analyzer: {raw_response!r}{RESET}")
                self._add_message('assistant', chatgpt_response)
                self._update_message_history()
                return chatgpt_response, emotion
            except Exception as e:
                self._stop_spinner()
                print(f"{RED}OpenAI API error: {e}{RESET}")
                return "Api error.", None
        #-----------------------------
        #Local LLM Implementation
        #------------------------------
        elif self.chatbot_service == "local":
            try:
                client = OpenAI(base_url="http://localhost:8080/v1", api_key="not-needed-locally")
                self._add_message('user', prompt)
                messages = self.context + self.message_history

                self._start_spinner()
                try:
                    # llama.cpp server converts json_schema into a GBNF grammar,
                    # constraining every token to valid structured output
                    response_obj = client.chat.completions.create(
                        model="local-model",
                        messages=messages,
                        temperature=0.7,
                        response_format={
                            "type": "json_schema",
                            "json_schema": EMOTION_SCHEMA
                        }
                    )
                except Exception:
                    # older llama.cpp builds may only know the plain json type
                    response_obj = client.chat.completions.create(
                        model="local-model",
                        messages=messages,
                        temperature=0.7,
                        response_format={"type": "json_object"}
                    )
                self._stop_spinner()

                raw_response = response_obj.choices[0].message.content
                local_model_response, emotion = parse_emotional_response(raw_response)
                if emotion is None and self.detailed_logs:
                    print(f"{ORANGE}Structured reply unparseable, falling back to keyword analyzer: {raw_response!r}{RESET}")
                self._add_message('assistant', local_model_response)
                self._update_message_history()
                return local_model_response, emotion
            except Exception as e:
                self._stop_spinner()
                print(f"{RED}An error has ocurred on local llm: {e}{RESET}")
                return "Local model error", None
        #-----------------------------
        #Dummy response
        #------------------------------
        elif self.chatbot_service == "test":
            dummy_response = "Testing tts, functions great!"
            self._add_message('user', prompt)
            self._add_message('assistant', dummy_response)
            self._update_message_history()
            return dummy_response, "Happy"
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
