
#this code uses the pyvts librarie to make the plugin simple, shorter, and easier to read

from ast import main
import pyvts 
import asyncio

#avatar control class
class VtubeControll:
    #initialize
    def __init__(self):
     #identifies the plugin so that it shows the plugin name and developer in Vtube Studio
     self.vts = pyvts.vts(
          plugin_info={
             "plugin_name": "NousSoul",
             "developer": "Tagb",
             "authentication_token_path": "./noussoul_auth_token.txt"
          }
     )
     self.hotkeys = {} #cache for hotkeys which will serve for emotions
     print("Plugin starto!") #runs when its authenticated

    #connects and authenticates the api
    async def initialize(self):
        await self.auth_connect()
        await self.hotkey_fetch()
         
    async def auth_connect(self):
        await self.vts.connect()
        await self.vts.request_authenticate_token()
        await self.vts.authenticate()

    #requests the hotkeys from the model
    async def hotkey_fetch(self):
        response = await self.vts.request_hk_current_model() #grabs the hotkey data

        #loop that puts the hotkey data ina  nice dictionary
        self.hotkeys = {
        hotkey["name"]: hotkey["hotkeyID"]
        for hotkey in response["data"]["availableHotkeys"]
        }

    #triggers the hotkey
    async def trigger_hotkey(self, name):
        if name not in self.hotkeys:
            print(f"Hotkey '{name}' not found.")
            return
        await self.vts.trigger_hotkey(self.hotkeys[name])
        print(f"Triggered hotkey: {name}")

    #automatically detects emotion
    def emotion_auto(self, text):
        if "angry" in text.lower():
            return "Angry"
        if "sad" in text.lower():
            return "Sad"
        if any(word in text.lower() for word in ["great", "happy", "yay"]):
            return "Happy"
        return "Neutral"
     


    
#if this file is executed directly it will run the main funtion         
if __name__ == "__main__":
    async def main():
     vtsp = VtubeControll()
     await vtsp.initialize()
    asyncio.run(main())