import cv2
from modules.hand_detector import HandDetector
from modules.face_detector import FaceDetector
import numpy as np

def debug_capture():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Camera not opened")
        return
    
    detector = HandDetector()
    face_detector = FaceDetector()
    
    ret, frame = cap.read()
    if not ret:
        print("Failed to read frame")
        return
        
    frame = cv2.flip(frame, 1)
    frame, hands = detector.process(frame)
    frame, face, emotion = face_detector.process(frame)
    
    print(f"Hands non-zero sum: {sum(hands)}")
    print(f"Face non-zero sum: {sum(face)}")
    print(f"Emotion detected: {emotion}")
    
    cv2.imwrite("debug_capture.jpg", frame)
    print("Saved debug_capture.jpg")
    
    cap.release()

if __name__ == "__main__":
    debug_capture()
