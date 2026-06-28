import os
import pyvts
import asyncio

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

class VtubeControll:

    def __init__(self, detailed_logs: bool = True):
        self.vts = pyvts.vts(
            plugin_info={
                "plugin_name": "NousSoul",
                "developer": "Tagb",
                "authentication_token_path": "Data/noussoul_auth_token.txt"
            }
        )
        self.hotkeys = {}
        self.detailed_logs = detailed_logs
        print(f"{GREEN}Plugin starto!{RESET}")

    async def initialize(self):
        await self.auth_connect()
        await self.hotkey_fetch()

    async def auth_connect(self):
        print(f'{YELLOW}Trying to connect to Vtube Studio API...{RESET}')
        await self.vts.connect()
        print(f'{GREEN}Connected!{RESET}')

        try:
            token_path = "Data/noussoul_auth_token.txt"

            if os.path.exists(token_path):
                print(f"{YELLOW}Found existing token, attempting authentication...{RESET}")

                with open(token_path, 'r') as f:
                    auth_token = f.read().strip()

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
                    print(f"{GREEN}Authentication successful!{RESET}")
                    return
                else:
                    print(f"{ORANGE}Existing token invalid, requesting new one...{RESET}")
                    os.remove(token_path)

            print(f"{YELLOW}Requesting new authentication...{RESET}")
            print(f"{YELLOW}Please accept the plugin authorization popup in VTube Studio!{RESET}")

            token_response = await self.vts.request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "messageType": "AuthenticationTokenRequest",
                "requestID": "auth_token_request",
                "data": {
                    "pluginName": "NousSoul",
                    "pluginDeveloper": "Tagb"
                }
            })

            if token_response.get('messageType') == 'APIError':
                raise RuntimeError(f"{ORANGE}Token request failed: {token_response['data']['message']}{RESET}")

            auth_token = token_response['data']['authenticationToken']

            with open(token_path, 'w') as f:
                f.write(auth_token)

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
                print(f"{GREEN}New authentication successful!{RESET}")
            else:
                raise RuntimeError("Authentication failed")

        except Exception as e:
            print(f"{RED}Authentication error: {e}{RESET}")
            raise

    async def hotkey_fetch(self):
        try:
            response = await self.vts.request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "messageType": "HotkeysInCurrentModelRequest",
                "requestID": "fetch_hotkeys"
            })
            print(f"{GREEN}Hotkeys fetched{RESET}")
            if self.detailed_logs:
                print("=" * 60)
                print("Full API response from VTS:")
                print(response)
                print("=" * 60)

            if "data" not in response:
                raise RuntimeError(f"{ORANGE}No 'data' in response. This might be an error message.{RESET}")

            if "availableHotkeys" not in response["data"]:
                raise RuntimeError(f"{ORANGE}'data' received but no 'availableHotkeys'. Is the model properly set up?{RESET}")

            self.hotkeys = {
                hotkey["name"]: hotkey["hotkeyID"]
                for hotkey in response["data"]["availableHotkeys"]
            }
            if self.detailed_logs:
                print("=" * 60)
                print(f"Hotkeys fetched: \n{list(self.hotkeys.keys())}")
                print("=" * 60)

        except Exception as e:
            print(f"{RED}Error fetching hotkeys: {e}{RESET}")
            print(f"{ORANGE}Make sure you have a model loaded in VTube Studio with configured hotkeys{RESET}")
            self.hotkeys = {}

        if self.detailed_logs:
            print("=" * 60)
            print("Hotkeys fetched:", list(self.hotkeys.keys()))
            print("=" * 60)

        if not self.hotkeys:
            print(f"{ORANGE}WARNING: No hotkeys found! Make sure your VTube Studio model has hotkeys configured.{RESET}")

    async def trigger_hotkey(self, name):
        if self.detailed_logs:
            print(f"{YELLOW}Attempting to trigger hotkey: {name}{RESET}")
            print("=" * 60)
            print(f"Available hotkeys: \n{list(self.hotkeys.keys())}")
            print("=" * 60)

        if name not in self.hotkeys:
            if self.detailed_logs:
                print(f"{ORANGE}Hotkey '{name}' not found!{RESET}")
            return

        try:
            hotkey_id = self.hotkeys[name]
            if self.detailed_logs:
                print(f"{YELLOW}Triggering hotkey ID: {hotkey_id}{RESET}")

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
                print("=" * 60)
                print(f"Hotkey trigger response: \n{response}")
                print("=" * 60)

        except Exception as e:
            print(f"{ORANGE}Connection lost, attempting to reconnect...{RESET}")
            try:
                await self.auth_connect()
                await self.hotkey_fetch()

                hotkey_id = self.hotkeys[name]
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
                    print("=" * 60)
                    print(f"Hotkey triggered after reconnection: \n{response}")
                    print("=" * 60)
                print(f"{GREEN}Conected.{RESET}")
            except Exception as reconnect_error:
                print(f"{RED}Failed to reconnect and trigger hotkey '{name}': {reconnect_error}{RESET}")

    def analyze_dominant_emotion(self, text: str):
        try:
            happy_words = ["great", "happy", "yay", "joy", "awesome", "excited", "wonderful", "good", "fantastic", "amazing", "love", "perfect", "hi", "hello", "absolutely"]
            sad_words = ["sad", "cry", "depressed", "upset", "terrible", "awful", "disappointed", "sorry"]
            angry_words = ["angry", "mad", "furious", "annoyed", "hate", "stupid", "ridiculous", "frustrated"]
            surprised_words = ["surprised", "wow", "shocked", "incredible", "unbelievable", "whoa"]

            text_lower = text.lower()
            words = text_lower.split()
            clean_words = [word.strip('.,!?;:"()[]') for word in words]

            happy_count = sum(1 for word in clean_words if word in happy_words)
            sad_count = sum(1 for word in clean_words if word in sad_words)
            angry_count = sum(1 for word in clean_words if word in angry_words)
            surprised_count = sum(1 for word in clean_words if word in surprised_words)

            if self.detailed_logs:
                print(f"Emotion counts - Happy: {happy_count}, Sad: {sad_count}, Angry: {angry_count}, Surprised: {surprised_count}")

            counts = [happy_count, sad_count, angry_count, surprised_count]
            emotions = ["Happy", "Sad", "Angry", "Surprised"]

            max_count = max(counts)
            if max_count == 0:
                return "Neutral"

            dominant_emotion = emotions[counts.index(max_count)]
            if self.detailed_logs:
                print(f"Dominant emotion: {dominant_emotion}")
            return dominant_emotion

        except Exception as e:
            if self.detailed_logs:
                print(f"{ORANGE}error in analyzing dominant emotion: {e}{RESET}")

if __name__ == "__main__":
    async def main():
        vts = VtubeControll()
        await vts.initialize()
    asyncio.run(main())
