
#this code uses the pyvts librarie to make the plugin simple, shorter, and easier to read

import os #lets me control windows, used to delete, write, and read the auth token
import pyvts #python library especifically made to work with vtube studio api
import asyncio #library that lets me use the async and await syntax, vital for web requests (api requests basically :V)


#avatar control class
class VtubeControll:
    #initialize
    def __init__(self,detailed_logs: bool = True):
     #identifies the plugin so that it shows the plugin name and developer in Vtube Studio
     self.vts = pyvts.vts(
          plugin_info={
             "plugin_name": "NousSoul",
             "developer": "Tagb",
             "authentication_token_path": "Data/noussoul_auth_token.txt" #token is stored in a txt
          }
     )
     self.hotkeys = {} #cache for hotkeys which will serve for emotions
     self.detailed_logs = detailed_logs
     print("Plugin starto!") #starts plugin

    #initializes the function of the authentication and hotkey fetch
    async def initialize(self):
        await self.auth_connect()
        await self.hotkey_fetch() #Comment out this function, because hotkey triggers stops lypsync for some models, if you dont mind it then leave it as is :P

    #function for the authentication of the plugin
    async def auth_connect(self):
     print('Trying to connect to Vtube Studio API...')
     await self.vts.connect() #tries to connect to vtube studio api
     print('Connected!')

     try:
         token_path = "Data/noussoul_auth_token.txt" #variable to not write the path over and over
        
         #always try to authenticate if token exists
         if os.path.exists(token_path):
             print("Found existing token, attempting authentication...")

             #reads the token in "read " mode
             with open(token_path, 'r') as f:
                 auth_token = f.read().strip() #variable that's used to read the token
            
             #calls the api with the token data
             auth_response = await self.vts.request({
                 "apiName": "VTubeStudioPublicAPI",
                 "apiVersion": "1.0",
                 "messageType": "AuthenticationRequest",
                 "requestID": "auth_request",
                 "data": {
                     "pluginName": "NousSoul",
                     "pluginDeveloper": "Tagb",
                     "authenticationToken": auth_token #variable I made earlier that reads the token
                 }
             })
            
             #checks if authentication is successfull if not it deletes the last token and tries to make a new one
             if (auth_response.get('messageType') == 'AuthenticationResponse' and 
                 auth_response['data']['authenticated']): #checks vtube studio response to the api call, detects if it says 'authenticate'
                 print("Authentication successful!") #prints succsesfull authentication
                 return
             else:
                 #if auth response was not 'authenticated' then the token is probably expired or corrupted
                 #deletes the token
                 print("Existing token invalid, requesting new one...")
                 os.remove(token_path)
        
         #if token does not exists or was deleted, then request new auth via vtube studio
         print("Requesting new authentication...")
         print("Please accept the plugin authorization popup in VTube Studio!")

         #calls the api and requests a new token
         token_response = await self.vts.request({ 
             "apiName": "VTubeStudioPublicAPI",
             "apiVersion": "1.0",
              "messageType": "AuthenticationTokenRequest", #this and the line below request the token
             "requestID": "auth_token_request",
             "data": {
                 "pluginName": "NousSoul",
                 "pluginDeveloper": "Tagb"
             }
         })
        
         if token_response.get('messageType') == 'APIError': #looks in vtubes api response and checks if there's an 'APIError'
             raise RuntimeError(f"Token request failed: {token_response['data']['message']}") #if there is then stop code execution and raise error
         
         #stores the token response in a variable
         auth_token = token_response['data']['authenticationToken'] 
         
         #creates a file with the token response that we stored earlier
         with open(token_path, 'w') as f :
             f.write(auth_token)
        
         #authenticate with new token
         auth_response = await self.vts.request({ #calls the api for an authentication request of the new token
             "apiName": "VTubeStudioPublicAPI",
             "apiVersion": "1.0",
             "messageType": "AuthenticationRequest", #it calls it right here
             "requestID": "auth_request",
             "data": {
                 "pluginName": "NousSoul",
                 "pluginDeveloper": "Tagb",
                 "authenticationToken": auth_token
             }
         })

         #does the same thing as the first time we checked the auth response
         if (auth_response.get('messageType') == 'AuthenticationResponse' and  #calls the api response and checks the data if it says 'authenticated'
             auth_response['data']['authenticated']):
             print("New authentication successful!") #prints that the new auth was successful
         else:
             raise RuntimeError("Authentication failed")#if it went wrong, stop code execution and raise error
         
     #if the execution of the code had an error then stop code execution and raise an error
     except Exception as e:
         print(f"Authentication error: {e}")
         raise #raises error

    #function that requests the models hotkeys
    async def hotkey_fetch(self):
        try:
            #calls vtube studio api to request hotkeys  
            response = await self.vts.request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "messageType": "HotkeysInCurrentModelRequest", #requests hoykeys here
                "requestID": "fetch_hotkeys"
            })
            print("Hotkeys fetched")
            if self.detailed_logs:
                print("="*60)
                print("Full API response from VTS:") 
                print(response) #prints the full response data form the previous api call for debugging purposes
                print("="*60)

            #if there is no data in response raise an error
            if "data" not in response:
                raise RuntimeError("No 'data' in response. This might be an error message.")
            
            #if there is no 'availableHotkeys' in repsonse data then raise an error
            if "availableHotkeys" not in response["data"]:
                raise RuntimeError("'data' received but no 'availableHotkeys'. Is the model properly set up?")
            
            #puts hotkeys in a dictionary (this is where out handy cache I made earlier comes in)
            self.hotkeys = {
                hotkey["name"]: hotkey["hotkeyID"]
                for hotkey in response["data"]["availableHotkeys"]
            }
            if self.detailed_logs:
                print("="*60)
                print(f"Hotkeys fetched: \n{list(self.hotkeys.keys())}") #prints the hotkey dictionary
                print("="*60)

        #if hotkeys fetch gone wrong then raise error and proceed without hotkeys
        except Exception as e:
            print(f"Error fetching hotkeys: {e}")
            print("Make sure you have a model loaded in VTube Studio with configured hotkeys")
            #just continue without hotkeys
            self.hotkeys = {}
        if self.detailed_logs:
            print("="*60)
            print("Hotkeys fetched:", list(self.hotkeys.keys())) #prints the empty hotkey list
            print("="*60)
        if not self.hotkeys: #if hotkeys were not found then print the error message
         print("WARNING: No hotkeys found! Make sure your VTube Studio model has hotkeys configured.")

    #fuinction detects ai response and triggers corresponding hotkey
    async def trigger_hotkey(self, name):
     if self.detailed_logs:    
        print(f"Attempting to trigger hotkey: {name}") #prints the name of the hotkey
        print("="*60)
        print(f"Available hotkeys: \n{list(self.hotkeys.keys())}") #prints the available hotkeys that were grabbes form the model
        print("="*60)

     #if a hotkey name that is triggered is not found in the model then print error message
     if name not in self.hotkeys:
         if self.detailed_logs:
            print(f"Hotkey '{name}' not found!")
         return
    
     try:
         hotkey_id = self.hotkeys[name] #stores hotkey name in a variable
         if self.detailed_logs:
            print(f"Triggering hotkey ID: {hotkey_id}")
        
         response = await self.vts.request({ #makes the api call to trigger the hotkey
             "apiName": "VTubeStudioPublicAPI",
             "apiVersion": "1.0",
             "messageType": "HotkeyTriggerRequest", #requests here
             "requestID": "trigger_hotkey",
             "data": {
                 "hotkeyID": hotkey_id #the variable where I stored the hotkey name
             }
         })
         if self.detailed_logs:
            print("="*60)
            print(f"Hotkey trigger response: \n{response}") #prints the response of vtube studio api after trying to trigger hotkey
            print("="*60)

     #if error during api call, programn asummes connection is lost and tries to reconnect    
     except Exception as e: 
        print(f"Connection lost, attempting to reconnect...")
        try:
            await self.auth_connect()  #calls the connect function for reconnection
            await self.hotkey_fetch()  #calls the hotkey fetch funcion to get the hotkeys again
            
            #makes the api call to trigger the hotkey
            hotkey_id = self.hotkeys[name] #store hotkey name in variable
            response = await self.vts.request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "messageType": "HotkeyTriggerRequest", #hotkey requests is here
                "requestID": "trigger_hotkey",
                "data": {
                    "hotkeyID": hotkey_id #use variable here
                }
            })
            if self.detailed_logs:
                print("="*60)
                print(f"Hotkey triggered after reconnection: \n{response}") #prints that it triggered the hotkey after a reconnect and prints vtube studio's response
                print("="*60)
            print("Conected.")
        #if reconnect code gone wrong then print error    
        except Exception as reconnect_error:
            print(f"Failed to reconnect and trigger hotkey '{name}': {reconnect_error}")

    def analyze_dominant_emotion(self, text: str):
        try:
            # Define emotions and their keywords
            happy_words = ["great", "happy", "yay", "joy", "awesome", "excited", "wonderful", "good", "fantastic", "amazing", "love", "perfect","hi","hello","absolutely"]
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
                print(f"error in analyzing dominant emotion: {e}")

#if this file is executed directly it will run the main funtion         
if __name__ == "__main__":
    async def main():
        vts = VtubeControll()
        await vts.initialize()
    asyncio.run(main())


#---------------------MEMOS---------------------
"""
pyvts is a wrapper that facilitates api calls.
it returns and sends all data in json

Generic vts api call:
response = await self.vts.request({
    "apiName": "VTubeStudioPublicAPI",      #always this value
    "apiVersion": "1.0",                    #always this value  
    "messageType": "SpecificRequestType",   #changes based on what you want to do
    "requestID": "unique_identifier",       #any string to identify this request
    "data": {                              #request-specific data
        #parameters specific to the messageType
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