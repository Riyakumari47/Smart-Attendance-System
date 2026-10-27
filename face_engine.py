import os
import re
import base64
import pickle
import cv2
import numpy as np
import face_recognition

# =========================================================
# CONFIGURATION & STORAGE PATHS
# =========================================================
ENCODINGS_FILE = "database/encodings.pkl"
FACES_DIR = "static/faces"

os.makedirs(FACES_DIR, exist_ok=True)
os.makedirs("database", exist_ok=True)


def base64_to_cv2(base64_string):
    """Base64 string ko OpenCV image array me decode karta hai."""
    try:
        image_data = re.sub(r"^data:image/.+;base64,", "", base64_string)
        decoded_data = base64.b64decode(image_data)
        np_arr = np.frombuffer(decoded_data, np.uint8)
        return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"[FaceEngine Error] Base64 decoding failed: {e}")
        return None


def load_encodings():
    """Disk se saved face encodings pickle file load karta hai."""
    if os.path.exists(ENCODINGS_FILE):
        try:
            with open(ENCODINGS_FILE, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"[FaceEngine Error] Encodings loading failed: {e}")
    return {"encodings": [], "ids": []}


def save_encodings(data):
    """Face encodings list ko disk par save karta hai."""
    try:
        with open(ENCODINGS_FILE, "wb") as f:
            pickle.dump(data, f)
        return True
    except Exception as e:
        print(f"[FaceEngine Error] Encodings saving failed: {e}")
        return False


def save_face_sample(student_id, base64_img, index):
    """Camera sample frame se face verify karke dataset me save karta hai."""
    image = base64_to_cv2(base64_img)
    if image is None:
        return False, "Invalid image payload."

    rgb_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb_img)

    if not locations:
        return False, "Face not detected. Stand clearly in frame."

    student_dir = os.path.join(FACES_DIR, str(student_id))
    os.makedirs(student_dir, exist_ok=True)

    img_path = os.path.join(student_dir, f"sample_{index}.jpg")
    cv2.imwrite(img_path, image)
    return True, f"Sample {index} captured successfully."


def train_face_embeddings(student_id):
    """Captured samples se face features extract karke trained database update karta hai."""
    student_dir = os.path.join(FACES_DIR, str(student_id))
    if not os.path.exists(student_dir):
        return False, "No face samples found for this student."

    data = load_encodings()
    samples_processed = 0

    for file_name in os.listdir(student_dir):
        if file_name.endswith((".jpg", ".jpeg", ".png")):
            img_path = os.path.join(student_dir, file_name)
            image = face_recognition.load_image_file(img_path)
            encodings = face_recognition.face_encodings(image)

            if encodings:
                data["encodings"].append(encodings[0])
                data["ids"].append(str(student_id))
                samples_processed += 1

    if samples_processed > 0:
        save_encodings(data)
        return True, f"Model successfully trained with {samples_processed} samples."

    return False, "Failed to extract features from samples."


def recognize_face(base64_img, tolerance=0.48):
    """Live camera frame ko trained face database se match karta hai."""
    image = base64_to_cv2(base64_img)
    if image is None:
        return {"success": False, "message": "Invalid image frame."}

    # Frame resize for rapid real-time processing
    small_frame = cv2.resize(image, (0, 0), fx=0.25, fy=0.25)
    rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_small)
    face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

    data = load_encodings()

    if not data["encodings"]:
        return {"success": True, "recognized": False, "message": "No face data trained yet."}

    for encoding in face_encodings:
        matches = face_recognition.compare_faces(data["encodings"], encoding, tolerance=tolerance)
        distances = face_recognition.face_distance(data["encodings"], encoding)

        if len(distances) > 0:
            best_match_index = np.argmin(distances)
            if matches[best_match_index]:
                matched_id = data["ids"][best_match_index]
                confidence = round((1 - distances[best_match_index]) * 100, 2)

                return {
                    "success": True,
                    "recognized": True,
                    "student_id": matched_id,
                    "confidence": f"{confidence}%"
                }

    return {"success": True, "recognized": False, "message": "Scanning for face match..."}