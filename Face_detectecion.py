import cv2 #Open cv library used for face detection
import asyncio #to sycn everything
import threading #to run the camera loop in a separate thread
import time #used to apply cooldown, basically a simple ver of asyncio
from IA import Nous #imports ai script to send messages to 
from VtubeS_Plugin import VtubeControll

class FaceDetectionVTuber:
    def __init__(self, ai: Nous = None, vts: VtubeControll = None, tts_language: str = "english", detailed_logs = False):
        self.face_message_active = False
        self.vts = vts
        self.detailed_logs = detailed_logs
        self.tts_language = tts_language
        self.ai = ai
        self.camera = None
        self.face_cascade = None
        self.is_running = False
        self.face_detected = False
        self.last_face_time = 0
        self.detection_cooldown = 3.0  #seconds to wait before detecting again
        if self.tts_language == "english":
            self.face_detection_messages = [
                "Oh, hello there! I can see you!",
                "Hey! Someone's here!",
                "Hi there! Nice to see a face!",
                "Well well, look who showed up!",
                "Oh my, a human appeared!",
                "Greetings! I detect your presence!"
            ]
        elif self.tts_language == "spanish":
            self.face_detection_messages = [
                "Oh, hola!",
                "Hey! alguien esta aqui!",
                "hola! que bueno verte!"
            ]
        self.current_message_index = 0

    def initialize_camera(self, camera_index: int = 0) -> bool:
        try:
            print(f"Initializing camera {camera_index}...")
            self.camera = cv2.VideoCapture(camera_index) #starts video capture at index 0 (default device)

            if not self.camera.isOpened(): #checks if camera is opened
                print("Error: Could not open camera")
                return False

            self.face_cascade = cv2.CascadeClassifier( #loads open cv built in face detecor
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )

            if self.face_cascade.empty(): #if it cant find the face detection file
                print("Error: Could not load face cascade classifier")
                return False

            print("Camera and face detection initialized successfully!")
            return True

        except Exception as e:
            print(f"Error initializing camera: {e}")
            return False

    def detect_faces(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) #converts every frame to grayscale
        faces = self.face_cascade.detectMultiScale( #functions that detects faces in an image
            gray,
            scaleFactor=1.01, #how much the image size is reduces at each scale
            minNeighbors=20, #minimun 'neighbor' rectangle to keep a detection
            minSize=(90, 90) #minimun face size
        )
        return faces #returns a list of rectanges (x, y, w, h) where faces were detected

    def get_face_detection_message(self) -> str:
        message = self.face_detection_messages[self.current_message_index] #from the list of premade messages it grabs the message that matches index number
        #go to each message index in order, reset when you get to the last message
        self.current_message_index = (self.current_message_index + 1) % len(self.face_detection_messages)
        return message

    async def handle_face_detection(self):
        current_time = time.time() #returns the current time

        if current_time - self.last_face_time < self.detection_cooldown: #cooldown to prevent spam of print messages
            return
        
        #check if AI is currently speaking
        if self.ai and self.ai.is_speaking == True:
            print("AI is speaking or getting input, skipping face detection message...")
            return

        print("Face detected! Preparing message...")

        self.last_face_time = current_time #updates the variable with the current time
        message = self.get_face_detection_message() #gets the face detection message

        print(f"Face detected! Saying: {message}")
        #cehcks if nous exists
        if self.ai:
            self.face_message_active = True
            await self.ai.tts_say(message) #send detection message to nous tts
            self.face_message_active = False
        else:
            print("AI (Nous) not available to say message.")
            self.face_message_active = False

    def camera_loop(self): #main camera loop
        while self.is_running and self.camera.isOpened(): #check if is_running and camera is opened are true
            #self.camera.read() returns two  values
            #one is the frame (ret) and the other is the whole image in color (frame)
            ret, frame = self.camera.read() #reads the current frame

            if not ret: #cehcks the current frame
                print("Error: Could not read frame from camera")
                break

            faces = self.detect_faces(frame) #detects the faces
            current_face_detected = len(faces) > 0 #gets the number of current faces detected

            if current_face_detected and not self.face_detected: #if there is more than one face detected
                self.face_detected = True
                asyncio.run_coroutine_threadsafe( #allows for async operation on a separate thread
                    self.handle_face_detection(), #runs the face detection
                    self.loop #gets the async thread loop
                )
            elif not current_face_detected and self.face_detected: #if face is not detected
                self.face_detected = False
                if self.detailed_logs:
                    print("Face no longer detected")

            for (x, y, w, h) in faces: #draws a rectangle on detected face
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)

            cv2.imshow('VTuber Face Detection', frame) #shows camera feed in a different window

            if cv2.waitKey(1) & 0xFF == 27: #checks if esc key is pressed
                print("esc pressed in camera windows, shuttin down...")
                break

            time.sleep(0.1) #small delay before exiting loop
        print("Camera loop exited")
        self.stop_detection()

    async def start_detection(self):
        if not self.camera or not self.face_cascade: #if camera or the face detection reference
            print("Camera not initialized! Call initialize_camera() first.")
            return

        print("Starting face detection...")
        print("Press 'esc' in the camera window to quit")

        self.is_running = True #check for camera running
        self.loop = asyncio.get_running_loop() #getws asyncio loop

        camera_thread = threading.Thread(target=self.camera_loop) #starts camera loop in a thread
        camera_thread.daemon = True #run in background thread
        camera_thread.start() #start thread

        try: #loop that checks if camera is running
            while self.is_running:
                await asyncio.sleep(0.1)
                if not camera_thread.is_alive(): #checks if camera exists
                    break
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop_detection() #stop detection if loop breaks

    def stop_detection(self):
        if not self.is_running: #checks if camera is running
            return
        print("Stopping face detection...")
        self.is_running = False #sets check to false
        if self.camera:
            self.camera.release() #releases the camera
        cv2.destroyAllWindows() #exits the camrea feed window

    def list_cameras(self): #print all available camera
        print("Available cameras:")
        for i in range(5): #prints the firs 5 cameras
            cap = cv2.VideoCapture(i)
            if cap.isOpened(): #checks if camera is available
                print(f"Camera {i}: Available")
                cap.release()
            else:
                print(f"Camera {i}: Not available")


async def main():
    face_vtuber = FaceDetectionVTuber()
    face_vtuber.list_cameras()

    if not face_vtuber.initialize_camera(camera_index=0):
        print("Failed to initialize camera. Exiting...")
        return

    await face_vtuber.start_detection()


if __name__ == "__main__":
    asyncio.run(main())
