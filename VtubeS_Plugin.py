import os  
import pyvts  
import asyncio  
import re
import unicodedata
from paths import BASE_PATH

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

# avatar control class
class VtubeControll:

    # initialize
    def __init__(self, detailed_logs: bool = True, log_callback=None):
        # identifies the plugin so that it shows the plugin name and developer in Vtube Studio
        self.vts = pyvts.vts(
            plugin_info={
                "plugin_name": "NousSoul",
                "developer": "Tagb",
                "authentication_token_path": os.path.join(BASE_PATH, "Data", "noussoul_auth_token.txt")  # token is stored in a txt
            }
        )
        self.hotkeys = {}  # cache for hotkeys which will serve for emotions
        self._hotkey_aliases = {}  # lowercase/normalized name -> exact hotkey name
        self.detailed_logs = detailed_logs
        self._log = log_callback or print
        self._log(f"{GREEN}Plugin starto!{RESET}")

    # initializes the function of the authentication and hotkey fetch
    async def initialize(self):
        await self.auth_connect()
        await self.hotkey_fetch()  # Comment out this function, because hotkey triggers stops lypsync for some models, if you dont mind it then leave it as is :P

    # function for the authentication of the plugin
    async def auth_connect(self):
        self._log(f'{YELLOW}Trying to connect to Vtube Studio API...{RESET}')
        await self.vts.connect()
        self._log(f'{GREEN}Connected!{RESET}')

        try:
            token_path = os.path.join(BASE_PATH, "Data", "noussoul_auth_token.txt")  # variable to not write the path over and over

            # always try to authenticate if token exists
            if os.path.exists(token_path):
                self._log(f"{YELLOW}Found existing token, attempting authentication...{RESET}")

                # reads the token in "read" mode
                with open(token_path, 'r') as f:
                    auth_token = f.read().strip()  # variable that's used to read the token

                # calls the api with the token data
                auth_response = await self.vts.request({
                    "apiName": "VTubeStudioPublicAPI",
                    "apiVersion": "1.0",
                    "messageType": "AuthenticationRequest",
                    "requestID": "auth_request",
                    "data": {
                        "pluginName": "NousSoul",
                        "pluginDeveloper": "Tagb",
                        "authenticationToken": auth_token  # variable I made earlier that reads the token
                    }
                })

                # checks if authentication is successfull; if not, deletes the last token and tries to make a new one
                if (auth_response.get('messageType') == 'AuthenticationResponse' and
                        auth_response['data']['authenticated']):  # checks vtube studio response, detects if it says 'authenticate'
                    self._log(f"{GREEN}Authentication successful!{RESET}")
                    return
                else:
                    # if auth response was not 'authenticated' then the token is probably expired or corrupted
                    self._log(f"{ORANGE}Existing token invalid, requesting new one...{RESET}")
                    os.remove(token_path)

            # if token does not exist or was deleted, request new auth via vtube studio
            self._log(f"{YELLOW}Requesting new authentication...{RESET}")
            self._log(f"{YELLOW}Please accept the plugin authorization popup in VTube Studio!{RESET}")

            # calls the api and requests a new token
            token_response = await self.vts.request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "messageType": "AuthenticationTokenRequest",  # this and the line below request the token
                "requestID": "auth_token_request",
                "data": {
                    "pluginName": "NousSoul",
                    "pluginDeveloper": "Tagb"
                }
            })

            if token_response.get('messageType') == 'APIError':  # looks in vtubes api response and checks if there's an 'APIError'
                raise RuntimeError(f"{ORANGE}Token request failed: {token_response['data']['message']}{RESET}")

            # stores the token response in a variable
            auth_token = token_response['data']['authenticationToken']

            # creates a file with the token response that we stored earlier
            with open(token_path, 'w') as f:
                f.write(auth_token)

            # authenticate with new token
            auth_response = await self.vts.request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "messageType": "AuthenticationRequest",
                "requestID": "auth_request",
                "data": {
                    "pluginName": "NousSoul",
                    "pluginDeveloper": "Tagb",
                    "authenticationToken": auth_token
                }
            })

            if (auth_response.get('messageType') == 'AuthenticationResponse' and
                    auth_response['data']['authenticated']):
                self._log(f"{GREEN}New authentication successful!{RESET}")
            else:
                raise RuntimeError("Authentication failed")

        except Exception as e:
            self._log(f"{RED}Authentication error: {e}{RESET}")
            raise

    # function that requests the models hotkeys
    async def hotkey_fetch(self):
        try:
            # calls vtube studio api to request hotkeys
            response = await self.vts.request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "messageType": "HotkeysInCurrentModelRequest",  # requests hotkeys here
                "requestID": "fetch_hotkeys"
            })
            self._log(f"{GREEN}Hotkeys fetched{RESET}")
            if self.detailed_logs:
                self._log("=" * 60)
                self._log("Full API response from VTS:")
                self._log(response)  # prints the full response data for debugging purposes
                self._log("=" * 60)

            if "data" not in response:
                raise RuntimeError(f"{ORANGE}No 'data' in response. This might be an error message.{RESET}")

            if "availableHotkeys" not in response["data"]:
                raise RuntimeError(f"{ORANGE}'data' received but no 'availableHotkeys'. Is the model properly set up?{RESET}")

            # puts hotkeys in a dictionary (this is where the cache comes in)
            self.hotkeys = {
                hotkey["name"]: hotkey["hotkeyID"]
                for hotkey in response["data"]["availableHotkeys"]
            }
            # normalized aliases so "happy", "Happy Face" etc. all resolve
            self._hotkey_aliases = {
                self._normalize_hotkey_name(name): name
                for name in self.hotkeys
            }
            if self.detailed_logs:
                self._log("=" * 60)
                self._log(f"Hotkeys fetched: \n{list(self.hotkeys.keys())}")
                self._log("=" * 60)

        except Exception as e:
            self._log(f"{RED}Error fetching hotkeys: {e}{RESET}")
            self._log(f"{ORANGE}Make sure you have a model loaded in VTube Studio with configured hotkeys{RESET}")
            self.hotkeys = {}
            self._hotkey_aliases = {}

        if self.detailed_logs:
            self._log("=" * 60)
            self._log(f"Hotkeys fetched: {list(self.hotkeys.keys())}")
            self._log("=" * 60)

        if not self.hotkeys:
            self._log(f"{ORANGE}WARNING: No hotkeys found! Make sure your VTube Studio model has hotkeys configured.{RESET}")

    @staticmethod
    def _normalize_hotkey_name(name: str) -> str:
        # strips accents/spaces/punctuation and lowercases, so lookups are forgiving
        text = unicodedata.normalize("NFKD", str(name))
        text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9]", "", text.lower())

    def resolve_emotion(self, emotion) -> "str | None":
        """Maps an emotion label to an actual hotkey name (case/spacing insensitive)."""
        if not emotion:
            return None
        key = self._normalize_hotkey_name(emotion)
        if not key:
            return None
        if key in self._hotkey_aliases:
            return self._hotkey_aliases[key]
        # substring pass: emotion "Happy" should still hit hotkeys like "Happy Face"
        for normalized, original in self._hotkey_aliases.items():
            if key in normalized or normalized in key:
                return original
        return None

    # function detects ai response and triggers corresponding hotkey
    async def trigger_hotkey(self, name):
        resolved = self.resolve_emotion(name) or name
        if self.detailed_logs:
            self._log(f"{YELLOW}Attempting to trigger hotkey: {name}{RESET}")
            self._log("=" * 60)
            self._log(f"Available hotkeys: \n{list(self.hotkeys.keys())}")
            self._log("=" * 60)

        if resolved not in self.hotkeys:
            if self.detailed_logs:
                self._log(f"{ORANGE}Hotkey '{name}' not found!{RESET}")
            return

        try:
            hotkey_id = self.hotkeys[resolved]
            if self.detailed_logs:
                self._log(f"{YELLOW}Triggering hotkey ID: {hotkey_id}{RESET}")

            response = await self.vts.request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "messageType": "HotkeyTriggerRequest",
                "requestID": "trigger_hotkey",
                "data": {
                    "hotkeyID": hotkey_id
                }
            })
            if self.detailed_logs:
                self._log("=" * 60)
                self._log(f"Hotkey trigger response: \n{response}")
                self._log("=" * 60)

        except Exception as e:
            self._log(f"{ORANGE}Connection lost, attempting to reconnect...{RESET}")
            try:
                await self.auth_connect()
                await self.hotkey_fetch()

                resolved = self.resolve_emotion(name) or name
                hotkey_id = self.hotkeys[resolved]
                response = await self.vts.request({
                    "apiName": "VTubeStudioPublicAPI",
                    "apiVersion": "1.0",
                    "messageType": "HotkeyTriggerRequest",
                    "requestID": "trigger_hotkey",
                    "data": {
                        "hotkeyID": hotkey_id
                    }
                })
                if self.detailed_logs:
                    self._log("=" * 60)
                    self._log(f"Hotkey triggered after reconnection: \n{response}")
                    self._log("=" * 60)
                self._log(f"{GREEN}Conected.{RESET}")
            except Exception as reconnect_error:
                self._log(f"{RED}Failed to reconnect and trigger hotkey '{name}': {reconnect_error}{RESET}")

    def analyze_dominant_emotion(self, text: str):
        """Fallback analyzer used only when structured output failed.

        Combines language-independent signals (emoji, punctuation, caps)
        with a multilingual keyword list, since plain English keywords
        alone are useless for any other language.
        """
        try:
            if not text or not text.strip():
                return "Neutral"

            # language-independent signals first: emoji work in every language
            emoji_emotions = {
                "😀": "Happy", "😃": "Happy", "😄": "Happy", "😁": "Happy",
                "😊": "Happy", "🙂": "Happy", "😂": "Happy", "🤣": "Happy",
                "😍": "Happy", "🥰": "Happy", "😎": "Happy", "🎉": "Happy",
                "👍": "Happy", "❤": "Happy", "💖": "Happy", "✨": "Happy",
                "😢": "Sad", "😭": "Sad", "😞": "Sad", "😔": "Sad",
                "💔": "Sad", "☹": "Sad", "🙁": "Sad", "😰": "Sad", "😥": "Sad",
                "😠": "Angry", "😡": "Angry", "🤬": "Angry", "😤": "Angry",
                "💢": "Angry", "👎": "Angry", "🙄": "Angry", "😒": "Angry",
                "😲": "Surprised", "😮": "Surprised", "😯": "Surprised",
                "🤯": "Surprised", "😱": "Surprised", "😳": "Surprised",
                "‼": "Surprised", "❓": "Surprised", "⁉": "Surprised",
            }
            for emoji, emotion in emoji_emotions.items():
                if emoji in text:
                    return emotion

            # multilingual keywords (english + common translations)
            keyword_groups = {
                "Happy": ["happy", "great", "yay", "joy", "awesome", "excited",
                          "wonderful", "good", "fantastic", "amazing", "love",
                          "perfect", "hello", "hi", "feliz", "alegre", "genial",
                          "increíble", "contento", "heureux", "joie", "génial",
                          "super", "bonjour", "glücklich", "freude", "toll",
                          "hallo", "うれしい", "嬉しい", "楽しい",
                          "开心", "高兴", "快乐", "счастлив", "рад",
                          "سعيد", "رائع", "فرحان"],
                "Sad": ["sad", "cry", "depressed", "upset", "terrible", "awful",
                        "disappointed", "sorry", "triste", "lo siento",
                        "malheureux", "désolé", "traurig", "entschuldigung",
                        "悲しい", "伤心", "难过", "груст",
                        "حزين", "آسف", "للأسف"],
                "Angry": ["angry", "mad", "furious", "annoyed", "hate", "stupid",
                          "ridiculous", "frustrated", "enojado", "furioso",
                          "odio", "estúpido", "colère", "haine", "wütend",
                          "hass", "怒り", "怒って", "生气", "愤怒", "зл",
                          "غاضب", "أكره", "فضيع"],
                "Surprised": ["surprised", "wow", "shocked", "incredible",
                              "unbelievable", "whoa", "sorpresa", "asombroso",
                              "incroyable", "waouh", "überrascht", "unglaublich",
                              "びっくり", "すごい", "惊讶", "难以置信", "удивлен", "вау",
                              "مذهل", "لا يصدق"],
            }

            text_lower = text.lower()

            def count_keyword(keyword: str) -> int:
                # word boundaries for latin-script words ("hi" must not match "this"),
                # plain containment for CJK/Cyrillic/Arabic runs without separators
                if re.fullmatch(r"[a-zà-ÿ0-9]+", keyword):
                    return len(re.findall(rf"\b{re.escape(keyword)}\b", text_lower))
                return text_lower.count(keyword)

            counts = {
                emotion: sum(count_keyword(kw) for kw in keywords)
                for emotion, keywords in keyword_groups.items()
            }

            # punctuation/caps signals, also language-independent
            exclaims = text.count("!")
            question_marks = text.count("?")
            letters = [char for char in text if char.isalpha()]
            caps_ratio = (sum(1 for char in letters if char.isupper()) / len(letters)) if letters else 0
            if len(letters) >= 6 and caps_ratio > 0.7:
                # shouting in caps reads as anger and cancels cheerful bangs
                counts["Angry"] += 2
                counts["Surprised"] += 1
                counts["Happy"] -= min(exclaims, 2)
            elif exclaims:
                counts["Happy"] += min(exclaims, 2)
            if question_marks >= 1 and exclaims == 0 and max(counts.values()) == 0:
                counts["Surprised"] += 1

            if self.detailed_logs:
                self._log(f"Emotion counts - {counts} (excl: {exclaims}, caps: {caps_ratio:.0%})")

            dominant = max(counts, key=counts.get)
            if counts[dominant] == 0:
                return "Neutral"

            if self.detailed_logs:
                self._log(f"Dominant emotion: {dominant}")
            return dominant

        except Exception as e:
            if self.detailed_logs:
                self._log(f"{ORANGE}error in analyzing dominant emotion: {e}{RESET}")
            return "Neutral"

# if this file is executed directly it will run the main function
if __name__ == "__main__":
    async def main():
        vts = VtubeControll()
        await vts.initialize()
    asyncio.run(main())
