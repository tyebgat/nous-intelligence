# nous-intelligence
Ai assistant with vtuber capabilities powered by chatgpt

THIS PROJECT ONLY WORKS WITH PYTHON 3.11!!!!

THIS PROJECT IS STILL UNDER DEVELOPMENT AND NOT YET REALESED PLEASE DO NOT TRY TO USE IT
--------------------------------------------------------------------------------------
**REQUIREMENTS:**

-Vb virtual audio cable

-Python 3.11

-Vtube Studio

---------------------------------------------------------------------------------------
**How to install:**
--------------------
-download code as zip and extract onto a folder

-Go to either your visual studio or local windows terminal

-Check your version of python with comman: python --version 

-If it shows python 3.11 or 3.12 you are good to go, if not then uninstall your current python  version and install python 3.11

-Go to the file directory that you have the porject folder with cmd (EX: C\Users\exUser\desktop\example_project_folder) using the command: cd your_directory_here

-Install the required libraries with command: pip install -r requirements.txt

-launch main.py from terminal by typying: python main.py

-Program should launch without error.

https://github.com/user-attachments/assets/805fde38-ef2e-4681-b4c1-8bbff890419b

----------------------------------------------------------------------------------------
**Vtube Studio Configuration**
------------------------------
-Select the model of your choice

-Go to configuration (gear icon) and scroll down until you see the slider "START API (allow plugin)" and tick it to blue.

![image](https://github.com/user-attachments/assets/3bc1dde3-000e-4c75-9c45-0476dc317383)

make sure its running on port 8001

-Scroll down even more until Microphone settings, tick the slider "Use Microphone" to blue and use micrpohne "CABLE Output (VB-Audio Virtual Cable)"

-Set volume gain and frequency gain to 100

![image](https://github.com/user-attachments/assets/43424cd3-1a06-4528-b9fb-b60e95f67972)

-Go to model settings and scroll down until you the parameter for mouth open and set input as "VoiceVolume"

![image](https://github.com/user-attachments/assets/d1941b2a-5eed-49ab-b007-76fff5cec6f0)

-Scroll down a little until you find the parameter mouth smile and set it to "VoiceFrequencyPlusMouthSmile"

![image](https://github.com/user-attachments/assets/5ecac5dd-bb34-4141-9800-7ac5997dfa78)

-Go to hotkey settinngs and edit the names of 4 hotkeys of your preferrence to: "Happy" "Sad" "Angry" "Surprised"

![image](https://github.com/user-attachments/assets/4cfcadab-8539-4ecb-8498-e8357219522c)

![image](https://github.com/user-attachments/assets/7ab75a14-9b0e-4f0e-8c28-6574e7f63bbe)

etc..

model should be setup now.

-----------------------------------------------------------------------------------------------------------
**Common problems:**
--------------------
-If lypsync is not working it's probably because there is no audio signal going to CABLE Output. 
 Fix this by going into windows sound settings > playback > CABLE Input > Properites > Advanced > "Give Exclusiver mode applications priority" should be ticked off.
 
 ![image](https://github.com/user-attachments/assets/06163191-1136-4051-aed0-d2c807c7b087)

 ![image](https://github.com/user-attachments/assets/0ca08be1-9819-48ff-8e38-e37cac7410dc)

-Click Apply > click ok.
-Lypsync should be working now.
 
