import mediapipe as mp
print(f"MediaPipe version: {mp.__version__}")
try:
    import mediapipe.solutions.hands as mp_hands
    print("Successfully imported hands solution")
except Exception as e:
    print(f"Failed to import hands solution: {e}")
