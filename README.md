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

- Vtube Studio

- An OpenAi API key


## **How to install:**
- make sure you have installed Vb virtual audio cable
- download the lates release
- extract the .rar file into the path of your choosing
- Launch main.exe

> IMPORTANT:
> The program will use the default recording device, so please set your prefferd mic to default before launching.

## **Configuration**

There are 3 categories of configuration. Chatbot settings, general settings and log settings.

- **Chatbot Settings:**
     - "user_input_service":changes what user input is being used. Either 'speech' or 'console'.
       - 'speech': User google speech recognition to send messages to the AI with push to talk.
       - 'console': Uses console input to send messages to tha AI.
     - "chatbot_service":changes what chabot service to use. either 'openai' or 'test'
       - 'openai': Uses the OpenAI API default model is 4o-mini (API Key is required).
       - 'test': Just prints out a predetermined message everytime.

- **General Settings:**
     - "tts_language": Changes Google tts. Either 'spanish' or 'english'.
     - "face_detection": Toggles Face Detection. False = Off, True = On.

- **Log Settings:**
     - "detailed_logs": prints a more detailed version of the logs with full API responses for debugging. False = Off, True = On.
     - "print_audio_devices": Toggle the print out of audio devices used in debugging to see which one is the Virtual audio cable. False = Off, True = On.
  

This configuration are stored in 'settings.json' on the projects root:
``` python
{
    "_comment": "----CHATBOT SETTINGS-----",
    "user_input_service": "console",
    "chatbot_service": "openai",

    "_comment1": "------GENERAL SETTINGS-------",
    "tts_language": "english",
    "face_detection": true,

    "_comment2": "------LOGS SETTINGS--------",
    "detailed_logs": true,
    "print_audio_devices": false
}
```

For example, if I want to use 'speech' as the user input, and 'test' as the chatbot service I would do:
``` python
{
    "_comment": "----CHATBOT SETTINGS-----",
    "user_input_service": "speech",
    "chatbot_service": "test",

    "_comment1": "------GENERAL SETTINGS-------",
    "tts_language": "english",
    "face_detection": true,

    "_comment2": "------LOGS SETTINGS--------",
    "detailed_logs": true,
    "print_audio_devices": false
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
 
