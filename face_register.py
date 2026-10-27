import os
from database import add_student_db, get_student_by_id
from face_engine import save_face_sample, train_face_embeddings

def register_student_details(student_id, name, roll_no):
    """Database me student ki basic info save karta hai."""
    if not student_id or not name or not roll_no:
        return False, "All fields (Student ID, Name, Roll No) are required."
    
    success = add_student_db(str(student_id), name, str(roll_no))
    if success:
        return True, "Student details registered successfully."
    return False, "Failed to register student details in database."


def process_face_sample(student_id, base64_image, sample_index):
    """Face image sample ko disk par save karta hai."""
    if not student_id or not base64_image:
        return False, "Missing student ID or image payload."

    success, message = save_face_sample(student_id, base64_image, sample_index)
    return success, message


def finalize_student_registration(student_id):
    """Finalize registration by training face encodings for the student."""
    success, message = train_face_embeddings(student_id)
    return success, message