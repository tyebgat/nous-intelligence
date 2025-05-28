from ast import main
import pyvts 
import asyncio

#avatar control class
class VtubeControll:
    #initialize
    def __init__(self):
     def initialize(self):
        self.info = {
            "pluginName": "NousSoul",
            "pluginDeveloper": "Tagb"
        }
        self.vts = pyvts.vts()() #easier to write
        self.hotkeys = {} #cache for hotkeys which will serve for emotions

     #connects and authenticates the api
     async def auth_connect(self):
         await self.vts.connect()
         await self.vts.request_authenticate_token()
         await self.vts.authenticate()
         print("Plugin authenticated and connected!") #runs when its authenticated
         await self.vts.fetch_hotkeys()

     #requests the hotkeys from the model
     async def hotkey_fetch(self):
         response = await self.vts.request_hk_current_model() #grabs the hotkey data

         #loop that puts the hotkey data ina  nice dictionary
         self.hotkeys = {}
         for hotkey in response["data"]["availableHotkeys"]:
          key = hotkey["name"]
          value = hotkey["hotkeyID"]
          self.hotkeys[key] = value

     #triggers the hotkey
     async def trigger_hotkey(self, name):
         if name not in self.hotkeys:
             print(f"Hotkey '{name}' not found.")
             return
         await self.vts.trigger_hotkey(self.hotkeys[name])
         print(f"Triggered hotkey: {name}")

     #automatically triggers the hotkey
     def emotion_auto(text):
         if "angry" in text.lower():
             return "Angry"
         if "sad" in text.lower():
             return "Sad"
         if "great" or "happy" or "yay" in text.lower():
             return "Happy"
         return "Neutral"
     


    
#if this file is executed directly it will run the main funtion         
if __name__ == "__main__":
    async def main():
     vts = VtubeControll()
     await vts.initialize()
    asyncio.run(main())