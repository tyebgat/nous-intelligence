# nous-intelligence
Ai assistant with vtuber capabilities powered by chatgpt

## Table of Contents 
- [Requirements](#requirements)
- [Hot to Install](#how-to-install)
- [Configuraions](#configuration)
- [Vtube Studio Configuration](#vtube-studio-configuration)
- [Common Problems](#common-problems)
  
## **REQUIREMENTS:**

- Vb virtual audio cable

- Vtube Studio (optional)

- Python 3.11

- An OpenAi API key (optional)


## **How to install:**
- make sure you have installed Vb virtual audio cable
- put you OPEN AI API key in the .env file.

### Normal way

- Download the latest .zip on the releases page.
- Unzip it and run the .exe


### Dev Install

Either clone the repo or download the source code from the realese page.

- Install the required libraries with command: 
```
pip install -r requirements.txt
```
> Tip:
> requirements.txt is located in the Data folder, make sure you either launch the terminal from there or cd onto the folder.

- launch main.py from terminal by typying: 
```
python main.py
```

> IMPORTANT:
> The program will use the default recording device, so please set your prefferd mic to default before launching.

## **Configuration**

### **Personalities**
There are two text files on the program "personality.txt" and "openai-TTS-instructions.txt". 

Edit the personality.txt with however you want the AI to act.

Edit the openai-TTS-instructions only if you are using the openai TTS service. This is where you can say in which language to have an accent and how you want it to speak.

### **Chatbot Settings:**
- "user_input_service": changes what user input is being used. Either 'speech' or 'console'.
     - 'speech': User google speech recognition to send messages to the AI with push to talk.
     - 'console': Uses console input to send messages to tha AI.

- "chatbot_service": changes what chabot service to use. either 'openai' or 'test'
     - 'openai': Uses the open ai model of your choice. (API Key is required).
     - 'local': Creates a llama server with the binary included in the program and then loads a gguf model. It is completely free but your pc will have to run the AI by itself the larger the model you choose the heavier on the pc.
     - 'test': Just prints out a predetermined message everytime.

- "remmeber_conversation" : changes the behaviour of the message history.
     - 'true' : Will store all of your past messages on a .txt and will load them when the program is executed.
     - 'false' : Will wipe the message history upon boot up. This can be helpful to reduce tokens if you are using openai.

- "model_dir" : directory where the gguf model is stored. Only used when running with chatbot_service local. Put the directory of where you put your gguf models.

### **Text to Speech Settings**
- "tts_service": changes the service of tts you want to use.
     - 'gtts' : uses google tts completely free.
     - 'openai' : uses an openai tts_model of your choice (API key is required).
- "tts_language" : changes the accent of the tts via language codes of ISO 639-1 (en, es, ja, zh etc...) refer to the gtts docs to the supported languages. If you want to change the openai accent language then specify it on the "openai-TTS-instructions.txt".

### **Open AI Settings**
- "openai_model" : Choose the model you want from the openAI site.
- "openai_tts_model" : Choose the tts model from the openAI site.
- "openai_tts_voice" : Pick a voice for the tts. Refer to the tts model you are using for your available voices.

### **General Settings:**
- "app_language": Changes the conversation cycle language (not logs yet).

### **Log Settings:**
- "logs": prints a more detailed version of the logs with full API responses for debugging. False = Off, True = On.
- "print_audio_devices": Toggle the print out of audio devices used in debugging to see which one is the Virtual audio cable. False = Off, True = On.  
- "show_ollama_server_logs": Only used when using the "local" chatbot service. Shows the logs of the llama server on the same console.

This configuration are stored in 'settings.json' on the projects root:
``` python
{
    "_comment": "----CHATBOT SETTINGS-----",
    "user_input_service": "console",
    "chatbot_service": "local",
    "remember_conversation": true,
    "model_dir": "models/llama-3.2-1b-instruct-q4_k_m.gguf",

    "_comment1": "------TEXT TO SPEECH SETTING-------",
    "tts_service": "google",
    "tts_language": "en",

    "_comment1.1": "---OPEN AI SETTINGS",
    "openai_model": "gpt-4o-mini",
    "openai_tts_model": "gpt-4o-mini-tts",
    "openai_tts_voice": "ash",

    "_comment2": "------GENERAL SETTINGS-------",
    "app_language": "english",

    "_comment3": "------LOGS SETTINGS--------",
    "logs": true,
    "print_audio_devices": false,
    "show_ollama_server_logs": false
}
```

## **Vtube Studio Configuration**

Select the model of your choice

Go to configuration (gear icon) and scroll down until you see the slider "START API (allow plugin)" and tick it to blue.

![image](https://github.com/user-attachments/assets/3bc1dde3-000e-4c75-9c45-0476dc317383)

make sure its running on port 8001

Scroll down even more until Microphone settings, tick the slider "Use Microphone" to blue and use micrpohne "CABLE Output (VB-Audio Virtual Cable)"

Set volume gain and frequency gain to 100

![image](https://github.com/user-attachments/assets/43424cd3-1a06-4528-b9fb-b60e95f67972)

Go to model settings and scroll down until you the parameter for mouth open and set input as "VoiceVolume"

![image](https://github.com/user-attachments/assets/d1941b2a-5eed-49ab-b007-76fff5cec6f0)

Scroll down a little until you find the parameter mouth smile and set it to "VoiceFrequencyPlusMouthSmile"

![image](https://github.com/user-attachments/assets/5ecac5dd-bb34-4141-9800-7ac5997dfa78)

Go to hotkey settinngs and edit the names of 4 hotkeys of your preferrence to: "Happy" "Sad" "Angry" "Surprised"

![image](https://github.com/user-attachments/assets/4cfcadab-8539-4ecb-8498-e8357219522c)

![image](https://github.com/user-attachments/assets/7ab75a14-9b0e-4f0e-8c28-6574e7f63bbe)

etc..

model should be setup now.


## **Common problems:**

If lypsync is not working it's probably because there is no audio signal going to CABLE Output. 
 Fix this by going into windows sound settings > playback > CABLE Input > Properites > Advanced > "Give Exclusiver mode applications priority" should be ticked off.
 
 ![image](https://github.com/user-attachments/assets/06163191-1136-4051-aed0-d2c807c7b087)

 ![image](https://github.com/user-attachments/assets/0ca08be1-9819-48ff-8e38-e37cac7410dc)

Click Apply > click ok.
-Lypsync should be working now.
 
