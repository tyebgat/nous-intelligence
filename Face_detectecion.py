import cv2
import asyncio
import threading
import time
from typing import Optional
from IA import Nous

class FaceDetectionVTuber:
    def __init__(self, ai: Nous = None):
        self.ai = ai
        self.camera = None
        self.face_cascade = None
        self.is_running = False
        self.face_detected = False
        self.last_face_time = 0
        self.detection_cooldown = 3.0  # Seconds to wait before detecting again

        self.face_detection_messages = [
            "Oh, hello there! I can see you!",
            "Hey! Someone's here!",
            "Hi there! Nice to see a face!",
            "Well well, look who showed up!",
            "Oh my, a human appeared!",
            "Greetings! I detect your presence!"
        ]
        self.current_message_index = 0

    def initialize_camera(self, camera_index: int = 0) -> bool:
        """Initialize the webcam and face detection"""
        try:
            print(f"Initializing camera {camera_index}...")
            self.camera = cv2.VideoCapture(camera_index)

            if not self.camera.isOpened():
                print("Error: Could not open camera")
                return False

            # Load the face detection classifier
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )

            if self.face_cascade.empty():
                print("Error: Could not load face cascade classifier")
                return False

            print("Camera and face detection initialized successfully!")
            return True

        except Exception as e:
            print(f"Error initializing camera: {e}")
            return False

    def detect_faces(self, frame):
        """Detect faces in the current frame"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        return faces

    def get_face_detection_message(self) -> str:
        """Get the next face detection message"""
        message = self.face_detection_messages[self.current_message_index]
        self.current_message_index = (self.current_message_index + 1) % len(self.face_detection_messages)
        return message

    async def handle_face_detection(self):
        """Handle what happens when a face is detected"""
        current_time = time.time()

        if current_time - self.last_face_time < self.detection_cooldown:
            return
        
        # Check if AI is currently speaking or getting input to avoid interruption
        # Added .ai check to prevent AttributeError if self.ai is None
        if self.ai and self.ai.is_speaking == True:
            print("AI is speaking or getting input, skipping face detection message...")
            return

        print("Face detected! Preparing message...")

        self.last_face_time = current_time
        message = self.get_face_detection_message()

        print(f"Face detected! Saying: {message}")
        # Say the message if Nous is available
        if self.ai:
            await self.ai.tts_say(message)
        else:
            print("AI (Nous) not available to say message.")

    def camera_loop(self):
        """Main camera loop running in a separate thread"""
        while self.is_running and self.camera.isOpened():
            ret, frame = self.camera.read()

            if not ret:
                print("Error: Could not read frame from camera")
                break

            # Detect faces
            faces = self.detect_faces(frame)
            current_face_detected = len(faces) > 0

            if current_face_detected and not self.face_detected and len(faces) == 1:
                self.face_detected = True
                asyncio.run_coroutine_threadsafe(
                    self.handle_face_detection(),
                    self.loop
                )
            elif not current_face_detected and self.face_detected:
                self.face_detected = False
                print("Face no longer detected")

            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)

            cv2.imshow('VTuber Face Detection', frame)

            if cv2.waitKey(1) & 0xFF == 27:
                print("esc pressed in camera windows, shuttin down...")
                break

            time.sleep(0.1)
        print("Camera loop exited")
        self.stop_detection()

    async def start_detection(self):
        """Start the face detection system"""
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
        """Stop the face detection system"""
        if not self.is_running:
            return
        print("Stopping face detection...")
        self.is_running = False
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()

    def list_cameras(self):
        """List available cameras for debugging"""
        print("Available cameras:")
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"Camera {i}: Available")
                cap.release()
            else:
                print(f"Camera {i}: Not available")


# Example usage only initializes camera
async def main():
    face_vtuber = FaceDetectionVTuber()
    face_vtuber.list_cameras()

    if not face_vtuber.initialize_camera(camera_index=0):
        print("Failed to initialize camera. Exiting...")
        return

    await face_vtuber.start_detection()


if __name__ == "__main__":
    asyncio.run(main())
