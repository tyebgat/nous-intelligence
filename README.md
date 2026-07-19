# **Nous Intelligence**

Nous Intelligence is a fully customizable AI that can connect to a Vtube Studio model, you can either use cloud services or run it with local models.

## Table of Contents 
- [Requirements](#requirements)
- [How to Install](#how-to-install)
- [Configurations](#configuration)
- [Vtube Studio Configuration](#vtube-studio-configuration)
- [Common Problems](#common-problems)
  
## **REQUIREMENTS:**

- Vb virtual audio cable

- Vtube Studio (optional)

- Python 3.11

- An OpenAi API key (optional)

- Huggin Face account (optional)


## **How to install:**
- make sure you have installed Vb virtual audio cable
- put your OPEN AI API key in the .env file.
- For PocketTTS service, add your Hugging face token to the .env file. Get one at https://huggingface.co/settings/tokens and accpet the terms at https://huggingface.co/kyutai/pocket-tts.

If you do not have a Hugging face account, create one on https://huggingface.co/. and go to profile > settings > Access Tokens > Create new token > read or write > create token > copy the value and paste it in .env

### Normal way

- Download the latest .zip on the releases page.
- Unzip it and run the .exe

### Dev Install

Either clone the repo or download the source code from the realese page.

- Install the required libraries with command: 
```
pip install -r requirements.txt
```

- Install local TTS services (optional if you are not going to use them.)
```
pip install -r requirements-pockettts.txt
pip install -r requirements-omnivoice.txt
```

> Tip:
> requirements.txt is located in the Data folder, make sure you either launch the terminal from there or cd onto the folder.

- launch main.py from terminal by typying: 
```
python main.py
```

> IMPORTANT:
> The program will use the default recording device, so please set your prefferd mic to default before launching.

---

## **System Requirements**

Running on cloud services: Nothing / Barely anything
Running all local: have atleast 6gb of ram free at all times, this will depend on the size of the local model you chose, larger model will consume more ram.

---

## **Configuration**

---

### **Personalities**

There are two text files on the program "personality.txt" and "openai-TTS-instructions.txt". 

Edit the personality.txt with however you want the AI to act.

Edit the openai-TTS-instructions only if you are using the openai TTS service. This is where you can say in which language to have an accent and how you want it to speak.

---

### **Voice Cloning**

Only available by Using "pockettts" as the tts service and settings "voice_cloning" to true. To voice clone you need a "reference.wav" file of atleast 5 seconds, and drop it into the `"data"` folder.

---

### **Wake Word**

Wake word is so you can just say a phrase and the AI will start listening, like "hey siri" or "hey jarvis" the program already comes with the model "hey jarvis" for testing. If you want a custom wake word then you'll have to create your own open wake word .onnx model.

**How do I create my own open wake word model?**

Easy way is to use a cloud service to train your model like https://openwakeword.com/ which does all the training in their computers instead of yours, this is by far the easiest way to do it, but this is a paid solution.

For local and free solution I recommend using https://github.com/livekit/livekit-wakeword you need python and basic knowledge on how to run commands on the terminal, but it is way simpler than traditional means. The only downside is that you need atleast 20gb of space for the training data, but you can delete it once done.

---

### **Chatbot Settings**

| Setting | Type | Description |
|---------|------|-------------|
| `user_input_service` | `"speech"` \| `"console"` \| `"wake_word"` | `"speech"`: Uses Google speech recognition with push to talk.    `"console"`: Uses console input to send messages to the AI.      `"wake_word"`: Listens for wake word to and then listens until silence. (requires an openwakeword.onnx model, "hey jarvis" model included in the repo)|
| `chatbot_service` | `"openai"` \| `"local"` \| `"test"` | `"openai"`: Uses an OpenAI model (API key required). `"local"`: Runs a local Llama server with a GGUF model (free, but heavier on PC). `"test"`: Prints a predetermined message every time. |
| `remember_conversation` | `true` \| `false` | `true`: Stores past messages in a .txt and loads them on boot. `false`: Wipes message history on boot (helps reduce tokens with OpenAI). |
| `model_dir` | string | Directory where the GGUF model is stored. Only used with `"local"` chatbot service. |

---

### **Wake Word Settings**

| Setting | Type | Description |
|---------|------|-------------|
| `wake_word_model` | string | Path to the OpenWakeWord ONNX model file. |
| `wake_word_threshold` | float (0.0 - 1.0) | Confidence threshold for wake word detection. Lower values trigger more easily but increase false positives. Higher values need clearer enunciation. Recommended: `0.5` casual, `0.7` noisy environments. |
| `wake_word_confirm_sound` | `true` \| `false` | Plays a confirmation sound when the wake word is detected. |

---

### **Speech to Text Settings**

| Setting | Type | Description |
|---------|------|-------------|
| `stt_service` | `"whisper"` \| `"google"` | `"whisper"`: Local offline Whisper STT (requires model download on first run). `"google"`: Google Speech Recognition (online, requires internet). |
| `stt_device` | `"cpu"` \| `"cuda"` | Device to run Whisper on. `"cpu"`: Uses your processor (slower but works everywhere). `"cuda"`: Uses NVIDIA GPU (faster, requires CUDA). |
| `stt_compute_type` | `"int8"` \| `"float16"` \| `"float32"` | Precision for Whisper inference. `"int8"`: Smallest and fastest, slight quality loss. `"float16"`: Good balance (GPU recommended). `"float32"`: Full precision, slowest, best quality. Use `"int8"` on CPU for best performance. |
| `stt_language` | string | ISO 639-1 language code for speech recognition (en, es, etc). |
| `silence_duration` | float | Seconds of silence before STT considers the user finished speaking. |

---

### **Text to Speech Settings**

| Setting | Type | Description |
|---------|------|-------------|
| `tts_service` | `"gtts"` \| `"openai"` \| `"omnivoice"` \| `"pockettts"` |`"gtts"`: Google TTS (free). `"openai"`: OpenAI TTS (API key required). `"pockettts"`: Local Pocket TTS with voice cloning support (great for cpu). `"omnivoice"`: Best sounding, voice design support, slowest best run on CUDA. |
| `tts_language` | string | ISO 639-1 language code (en, es, ja, zh, etc). Refer to your tts service docs for supported languages. For OpenAI, specify in "openai-TTS-instructions.txt". |
| `tts_voice` | string | Voice name for the selected TTS service. For Pocket TTS, also used as fallback when voice cloning is unavailable. |
| `tts_speed` | float | Speed multiplier for TTS (default: 1.0). |
| `voice_cloning` | `true` \| `false` | Pocket TTS only. `true`: Uses Data/reference.wav for voice cloning. `false`: Uses the built-in voice from `tts_voice`. |
| `voice_design` | `true` \| `false` | omnivoice only. Support for the voice desing, edit the text in Data/omnivoice-desing.txt.

---

### **Open AI Settings**

| Setting | Type | Description |
|---------|------|-------------|
| `openai_model` | string | Choose the model from the OpenAI site. |
| `openai_tts_model` | string | Choose the TTS model from the OpenAI site. |
| `openai_tts_voice` | string | Pick a voice for the TTS. Refer to the TTS model docs for available voices. |

---

### **General Settings**

| Setting | Type | Description |
|---------|------|-------------|
| `app_language` | string | Changes the conversation cycle language (not logs yet). |

---

### **Log Settings**

| Setting | Type | Description |
|---------|------|-------------|
| `logs` | `true` \| `false` | Prints detailed logs with full API responses for debugging. |
| `print_audio_devices` | `true` \| `false` | Toggles print out of audio devices for debugging (to find Virtual Audio Cable). |
| `show_ollama_server_logs` | `true` \| `false` | Only used with `"local"` chatbot service. Shows Llama server logs in the same console. |

---

### **Settings File Example**

This configuration is stored in `settings.json` on the project's root:

```json
{
    "_comment_chatbot": "----CHATBOT SETTINGS-----",
    "user_input_service": "console",
    "chatbot_service": "local",
    "chatbot_name": "NOUS",
    "remember_conversation": false,
    "model_dir": "models/llama/Llama-3.2-3B-Instruct-Q4_K_M.gguf",

    "_comment_wake": "------WAKE WORD SETTINGS-------",
    "wake_word_model": "models/openwakeword/hey_jarvis_v0.1.onnx",
    "wake_word_threshold": 0.5,
    "wake_word_confirm_sound": true,

    "_comment_stt": "------SPEECH TO TEXT SETTINGS-------",
    "stt_service": "whisper",
    "stt_device": "cpu",
    "stt_compute_type": "int8",
    "stt_language": "es",
    "silence_duration": 1,

    "_comment_tts": "------TEXT TO SPEECH SETTING-------",
    "tts_service": "pockettts",
    "tts_language": "es",
    "tts_voice": "af_heart",
    "tts_speed": 1,
    "voice_cloning": true,
    "voice_design": false,

    "_comment_omnivoice": "------OMNIVOICE TTS SETTINGS-------",
    "omnivoice_device": "cuda",

    "_comment_openai": "---OPEN AI SETTINGS---",
    "openai_model": "gpt-4o-mini",
    "openai_tts_model": "gpt-4o-mini-tts",
    "openai_tts_voice": "marin",

    "_comment_general": "------GENERAL SETTINGS-------",
    "app_language": "english",

    "_comment_logs": "------LOGS SETTINGS--------",
    "logs": true,
    "print_audio_devices": false,
    "show_ollama_server_logs": true
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
 
