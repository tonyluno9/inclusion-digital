import mediapipe as mp
print("Step 1: import mediapipe")
try:
    import mediapipe.solutions.hands as mp_hands
    import mediapipe.solutions.drawing_utils as mp_drawing
    print("Success with direct import")
except (ImportError, AttributeError) as e:
    print(f"Failed direct import: {e}")
    try:
        from mediapipe.python.solutions import hands as mp_hands
        from mediapipe.python.solutions import drawing_utils as mp_drawing
        print("Success with python.solutions import")
    except (ImportError, AttributeError) as e2:
        print(f"Failed python.solutions import: {e2}")
        if hasattr(mp, 'solutions'):
            print("mp has solutions, trying access")
            mp_hands = mp.solutions.hands
            mp_drawing = mp.solutions.drawing_utils
            print("Success with mp.solutions access")
        else:
            print("mp has NO solutions")
