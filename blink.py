import cv2
import numpy as np
import dlib
import os
import sys
from scipy.spatial import distance as dist

# Find the correct path whether running as script or exe
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

model_path = os.path.join(base_path, 'shape_predictor_68_face_landmarks.dat')

# Load once at startup
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(model_path)

def get_eye_points(landmarks, start, end):
    return [(landmarks.part(i).x, landmarks.part(i).y) for i in range(start, end)]

def eye_aspect_ratio(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

# Track consecutive low-EAR frames per session
blink_frame_counter = 0
BLINK_FRAMES_REQUIRED = 1  
EAR_THRESHOLD = 0.15  # Stricter threshold — less sensitive to movement

def detect_blink(image_bytes):
    global blink_frame_counter

    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = detector(gray)
    if len(faces) == 0:
        blink_frame_counter = 0
        return {'blink': False, 'face': False}

    for face in faces:
        landmarks = predictor(gray, face)
        left_eye = get_eye_points(landmarks, 36, 42)
        right_eye = get_eye_points(landmarks, 42, 48)
        avg_ear = (eye_aspect_ratio(left_eye) + eye_aspect_ratio(right_eye)) / 2.0

        if avg_ear < EAR_THRESHOLD:
            blink_frame_counter += 1
        else:
            blink_frame_counter = 0

        confirmed = blink_frame_counter >= BLINK_FRAMES_REQUIRED

        if confirmed:
            blink_frame_counter = 0  # Reset after confirmed blink

        return {
            'blink': confirmed,
            'face': True,
            'ear': round(avg_ear, 3),
            'frames': blink_frame_counter
        }

    return {'blink': False, 'face': True}

def reset_blink_counter():
    global blink_frame_counter
    blink_frame_counter = 0