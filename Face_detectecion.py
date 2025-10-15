import cv2 #Open cv library used for face detection
import asyncio #to sycn everything
import threading #to run the camera loop in a separate thread
import time #used to apply cooldown, basically a simple ver of asyncio
from IA import Nous #imports ai script to send messages to 
import os
from VtubeS_Plugin import VtubeControll

class FaceDetectionVTuber:
    def __init__(self, ai: Nous = None, tts_language: str = "english", detailed_logs = False):
        self.face_message_active = False
        self.detailed_logs = detailed_logs
        self.tts_language = tts_language
        self.ai = ai
        self.camera = None
        self.face_cascade = None
        self.is_running = False
        self.face_detected = False
        self.last_face_time = 0
        self.detection_cooldown = 3.0  #seconds to wait before detecting again
        self.detection_hold_time = 5.0 #seconds for face to be detected
        self.face_detection_start = 3.0 #timestamp
        self.face_message_sent = False #check
        self.last_message = ""  # Track last message for avoiding duplicates
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
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            cascade_path = os.path.join(script_dir, 'Data', 'haarcascade_frontalface_default.xml')

            self.face_cascade = cv2.CascadeClassifier(cascade_path)

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
        current_time = time.time()

        if current_time - self.last_face_time < self.detection_cooldown:
            if self.detailed_logs:
                print("Skipping face detection - cooldown active")
            return
        
        if self.ai and self.ai.is_speaking:
            if self.detailed_logs:
                print("AI is speaking, skipping face detection message")
            return

        if self.detailed_logs:
            print("Face detected! Getting message...")

        self.last_face_time = current_time
        message = self.get_face_detection_message()
        
        if self.detailed_logs:
            print(f"Sending message to TTS: {message}")
        
        if self.ai:
            try:
                self.face_message_active = True
                if self.detailed_logs:
                    print("Calling AI TTS...")
                await self.ai.tts_say(message)
                if self.detailed_logs:
                    print("TTS complete")
            except Exception as e:
                print(f"Error in TTS: {e}")
            finally:
                self.face_message_active = False
        else:
            print("AI (Nous) not available to say message.")
            self.face_message_active = False

    def camera_loop(self): #main camera loop
        while self.is_running and self.camera.isOpened():
            ret, frame = self.camera.read()

            if not ret:
                print("Error: Could not read frame from camera")
                break

            faces = self.detect_faces(frame)
            current_face_detected = len(faces) > 0

            if current_face_detected:
                if not self.face_detected:
                    self.face_detected = True
                    self.face_detection_start = time.time()
                    self.face_message_sent = False
                    if self.detailed_logs:
                        print("Face detected - starting timer...")
                else:
                    if (not self.face_message_sent
                        and time.time() - self.face_detection_start >= self.detection_hold_time):
                        if self.detailed_logs:
                            print("Face held - creating coroutine...")
                        self.face_message_sent = True
                        try:
                            asyncio.run_coroutine_threadsafe(
                                self.handle_face_detection(),
                                self.loop
                            ).result(timeout=5)  # Add timeout to prevent hanging
                        except Exception as e:
                            if self.detailed_logs:
                                print(f"Error in face detection coroutine: {e}")
            else:
                if self.face_detected:
                    self.face_detected = False
                    self.face_detection_start = 0.0
                    self.face_message_sent = False
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
        if not self.camera or not self.face_cascade:
            print("Camera not initialized! Call initialize_camera() first.")
            return

        print("Starting face detection...")
        print("Press 'esc' in the camera window to quit")

        self.is_running = True
        self.loop = asyncio.get_running_loop()

        camera_thread = threading.Thread(target=self.camera_loop)
        camera_thread.daemon = True
        camera_thread.start()

        try:
            while self.is_running:
                await asyncio.sleep(0.1)
                if not camera_thread.is_alive():
                    break
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop_detection()

    def stop_detection(self):
        if not self.is_running:
            return
        print("Stopping face detection...")
        self.is_running = False
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()

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
