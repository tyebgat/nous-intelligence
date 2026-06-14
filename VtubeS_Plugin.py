# this code uses the pyvts librarie to make the plugin simple, shorter, and easier to read
import os       # lets me control windows, used to delete, write, and read the auth token
import pyvts    # python library especifically made to work with vtube studio api
import asyncio  # library that lets me use the async and await syntax, vital for web requests (api requests basically :V)

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

# avatar control class
class VtubeControll:

    # initialize
    def __init__(self, detailed_logs: bool = True):
        # identifies the plugin so that it shows the plugin name and developer in Vtube Studio
        self.vts = pyvts.vts(
            plugin_info={
                "plugin_name": "NousSoul",
                "developer": "Tagb",
                "authentication_token_path": "Data/noussoul_auth_token.txt"  # token is stored in a txt
            }
        )
        self.hotkeys = {}  # cache for hotkeys which will serve for emotions
        self.detailed_logs = detailed_logs
        print(f"{GREEN}Plugin starto!{RESET}")

    # initializes the function of the authentication and hotkey fetch
    async def initialize(self):
        await self.auth_connect()
        await self.hotkey_fetch()  # Comment out this function, because hotkey triggers stops lypsync for some models, if you dont mind it then leave it as is :P

    # function for the authentication of the plugin
    async def auth_connect(self):
        print(f'{YELLOW}Trying to connect to Vtube Studio API...{RESET}')
        await self.vts.connect()
        print(f'{GREEN}Connected!{RESET}')

        try:
            token_path = "Data/noussoul_auth_token.txt"  # variable to not write the path over and over

            # always try to authenticate if token exists
            if os.path.exists(token_path):
                print(f"{YELLOW}Found existing token, attempting authentication...{RESET}")

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
                    print(f"{GREEN}Authentication successful!{RESET}")
                    return
                else:
                    # if auth response was not 'authenticated' then the token is probably expired or corrupted
                    print(f"{ORANGE}Existing token invalid, requesting new one...{RESET}")
                    os.remove(token_path)

            # if token does not exist or was deleted, request new auth via vtube studio
            print(f"{YELLOW}Requesting new authentication...{RESET}")
            print(f"{YELLOW}Please accept the plugin authorization popup in VTube Studio!{RESET}")

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
                print(f"{GREEN}New authentication successful!{RESET}")
            else:
                raise RuntimeError("Authentication failed")

        except Exception as e:
            print(f"{RED}Authentication error: {e}{RESET}")
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
            print(f"{GREEN}Hotkeys fetched{RESET}")
            if self.detailed_logs:
                print("=" * 60)
                print("Full API response from VTS:")
                print(response)  # prints the full response data for debugging purposes
                print("=" * 60)

            if "data" not in response:
                raise RuntimeError(f"{ORANGE}No 'data' in response. This might be an error message.{RESET}")

            if "availableHotkeys" not in response["data"]:
                raise RuntimeError(f"{ORANGE}'data' received but no 'availableHotkeys'. Is the model properly set up?{RESET}")

            # puts hotkeys in a dictionary (this is where the cache comes in)
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

    # function detects ai response and triggers corresponding hotkey
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
            # Define emotions and their keywords
            happy_words = ["great", "happy", "yay", "joy", "awesome", "excited", "wonderful", "good", "fantastic", "amazing", "love", "perfect", "hi", "hello", "absolutely"]
            sad_words = ["sad", "cry", "depressed", "upset", "terrible", "awful", "disappointed", "sorry"]
            angry_words = ["angry", "mad", "furious", "annoyed", "hate", "stupid", "ridiculous", "frustrated"]
            surprised_words = ["surprised", "wow", "shocked", "incredible", "unbelievable", "whoa"]

            # Convert text to lowercase and clean it
            text_lower = text.lower()
            words = text_lower.split()
            clean_words = [word.strip('.,!?;:"()[]') for word in words]

            # Count each emotion
            happy_count = sum(1 for word in clean_words if word in happy_words)
            sad_count = sum(1 for word in clean_words if word in sad_words)
            angry_count = sum(1 for word in clean_words if word in angry_words)
            surprised_count = sum(1 for word in clean_words if word in surprised_words)

            if self.detailed_logs:
                print(f"Emotion counts - Happy: {happy_count}, Sad: {sad_count}, Angry: {angry_count}, Surprised: {surprised_count}")

            # Find the highest count
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


# if this file is executed directly it will run the main function
if __name__ == "__main__":
    async def main():
        vts = VtubeControll()
        await vts.initialize()
    asyncio.run(main())


# ---------------------MEMOS---------------------
"""
pyvts is a wrapper that facilitates api calls.
it returns and sends all data in json

Generic vts api call:
response = await self.vts.request({
    "apiName": "VTubeStudioPublicAPI",      # always this value
    "apiVersion": "1.0",                    # always this value
    "messageType": "SpecificRequestType",   # changes based on what you want to do
    "requestID": "unique_identifier",       # any string to identify this request
    "data": {                               # request-specific data
        # parameters specific to the messageType
    }
})

To understand some of the function like the token auth logic, note that the response from vts api is this:
{
    "apiName": "VTubeStudioPublicAPI",
    "apiVersion": "1.0",
    "timestamp": 1234567890,
    "messageType": "AuthenticationResponse",
    "requestID": "auth_request",
    "data": {
        "authenticated": true,
        "reason": "Token valid."
    }
}

and the comprehension dictionary in hotkey fetch, it makes a dictionary with a for loop out of vts response which is like this:
{
    "data": {
        "availableHotkeys": [
            {
                "name": "Happy",
                "hotkeyID": "abc123",
                "description": "Happy expression",
                "file": "happy.exp3.json"
            },
            {
                "name": "Sad",
                "hotkeyID": "def456",
                "description": "Sad expression",
                "file": "sad.exp3.json"
            },
            {
                "name": "Angry",
                "hotkeyID": "ghi789",
                "description": "Angry expression",
                "file": "angry.exp3.json"
            },
            {
                "name": "Surprised",
                "hotkeyID": "jkl012",
                "description": "Surprised expression",
                "file": "surprised.exp3.json"
            }
        ]
    }
}
"""