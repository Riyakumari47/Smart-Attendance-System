from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session
)

from datetime import datetime, timedelta
from functools import wraps

from database import (
    init_db,
    get_student_by_id,
    get_all_students,
    delete_student_db,
    create_lecture,
    get_lecture_by_id,
    get_all_lectures,
    start_attendance_session,
    update_attendance_verification,
    finalize_attendance,
    get_all_logs,
    get_dashboard_stats,
    get_weekly_attendance,
    get_recent_attendance
)

from face_engine import recognize_face

from face_register import (
    register_student_details,
    process_face_sample,
    finalize_student_registration
)


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = "smart_attendance_secret_key_change_in_production"

init_db()


# =========================================================
# TEACHER / SUBJECT MAPPING
# =========================================================

TEACHER_MAP = {

    "E18982": {
        "name": "Ravi Raj Sir",
        "subjects": [
            "Data Mining",
            "Data Mining Lab"
        ]
    },

    "R350": {
        "name": "Prerna",
        "subjects": [
            "Software Engineering"
        ]
    },

    "E19512": {
        "name": "Kishan Ahuja",
        "subjects": [
            "Python",
            "Python Lab"
        ]
    },

    "E20257": {
        "name": "Amit Kumar Singh",
        "subjects": [
            "Minor Project",
            "Leadership & Time Management"
        ]
    },

    # Admin
    "Riya": {
        "name": "Admin",
        "subjects": [
            "ALL"
        ]
    }
}


# =========================================================
# ATTENDANCE TIMETABLE
# =========================================================

ATTENDANCE_TIMETABLE = [

    # =====================================================
    # TUESDAY
    # =====================================================

    {
        "day": "Tuesday",
        "subject": "Data Mining",
        "start": "11:25",
        "end": "12:10"
    },

    {
        "day": "Tuesday",
        "subject": "Software Engineering",
        "start": "12:10",
        "end": "12:55"
    },

    {
        "day": "Tuesday",
        "subject": "Minor Project",
        "start": "13:40",
        "end": "14:25"
    },

    {
        "day": "Tuesday",
        "subject": "Python Lab",
        "start": "14:25",
        "end": "15:10"
    },

    {
        "day": "Tuesday",
        "subject": "Python Lab",
        "start": "15:10",
        "end": "15:55"
    },


    # =====================================================
    # WEDNESDAY
    # =====================================================

    {
        "day": "Wednesday",
        "subject": "Data Mining",
        "start": "10:40",
        "end": "11:25"
    },

    {
        "day": "Wednesday",
        "subject": "Software Engineering",
        "start": "11:25",
        "end": "12:10"
    },

    {
        "day": "Wednesday",
        "subject": "Python",
        "start": "12:55",
        "end": "13:40"
    },

    {
        "day": "Wednesday",
        "subject": "Minor Project",
        "start": "13:40",
        "end": "14:25"
    },

    {
        "day": "Wednesday",
        "subject": "Data Mining Lab",
        "start": "14:25",
        "end": "15:10"
    },

    {
        "day": "Wednesday",
        "subject": "Data Mining Lab",
        "start": "15:10",
        "end": "15:55"
    },


    # =====================================================
    # THURSDAY
    # =====================================================

    {
        "day": "Thursday",
        "subject": "Python",
        "start": "09:55",
        "end": "10:40"
    },

    {
        "day": "Thursday",
        "subject": "Python Lab",
        "start": "12:55",
        "end": "14:25"
    },


    # =====================================================
    # FRIDAY
    # =====================================================

    {
        "day": "Friday",
        "subject": "Data Mining",
        "start": "09:55",
        "end": "10:40"
    },

    {
        "day": "Friday",
        "subject": "Leadership & Time Management",
        "start": "10:40",
        "end": "11:25"
    },

    {
        "day": "Friday",
        "subject": "Software Engineering",
        "start": "11:25",
        "end": "12:10"
    },

    {
        "day": "Friday",
        "subject": "Entrepreneurship",
        "start": "12:10",
        "end": "12:55"
    },

    {
        "day": "Friday",
        "subject": "Data Mining Lab",
        "start": "14:25",
        "end": "15:10"
    },

    {
        "day": "Friday",
        "subject": "Data Mining Lab",
        "start": "15:10",
        "end": "15:55"
    }
]


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def row_to_dict(row):

    if row is None:
        return None

    try:
        return dict(row)
    except Exception:
        return row


def rows_to_dicts(rows):

    return [
        row_to_dict(row)
        for row in rows
    ]


def calculate_lecture_duration_seconds(lecture):

    try:

        start_text = str(
            lecture["start_time"]
        ).strip()

        end_text = str(
            lecture["end_time"]
        ).strip()

        start_dt = datetime.strptime(
            start_text,
            "%H:%M"
        )

        end_dt = datetime.strptime(
            end_text,
            "%H:%M"
        )

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        return (
            end_dt - start_dt
        ).total_seconds()

    except Exception:

        return 0


def calculate_required_seconds(lecture):

    duration_seconds = (
        calculate_lecture_duration_seconds(
            lecture
        )
    )

    try:

        required_percentage = float(
            lecture["required_percentage"]
            or 90
        )

    except Exception:

        required_percentage = 90.0

    required_percentage = max(
        0,
        min(
            100,
            required_percentage
        )
    )

    return (
        duration_seconds
        * required_percentage
        / 100
    )


# =========================================================
# TEACHER AUTHORIZATION HELPERS
# =========================================================

def get_logged_in_teacher():

    username = session.get("user")

    if not username:
        return None

    teacher = TEACHER_MAP.get(
        username
    )

    if not teacher:
        return None

    return {
        "username": username,
        "name": teacher.get(
            "name",
            username
        ),
        "subjects": teacher.get(
            "subjects",
            []
        )
    }


def teacher_can_access_subject(subject_name):

    teacher = get_logged_in_teacher()

    if not teacher:
        return False

    allowed_subjects = teacher.get(
        "subjects",
        []
    )

    if "ALL" in allowed_subjects:
        return True

    if not subject_name:
        return False

    subject_name = str(
        subject_name
    ).strip().lower()

    return subject_name in {
        str(subject).strip().lower()
        for subject in allowed_subjects
    }


def teacher_can_access_lecture(lecture):

    if not lecture:
        return False

    try:

        lecture_name = lecture[
            "lecture_name"
        ]

    except Exception:

        return False

    return teacher_can_access_subject(
        lecture_name
    )


# =========================================================
# IMPORTANT:
# AUTOMATICALLY CREATE ALL TIMETABLE LECTURES
# =========================================================

def ensure_timetable_lectures():

    """
    Makes sure every lecture from ATTENDANCE_TIMETABLE
    exists in the database.

    This is the main fix for the empty lecture dropdown.
    """

    try:

        existing_lectures = get_all_lectures()

        existing_keys = set()

        for lecture in existing_lectures:

            lecture_name = str(
                lecture["lecture_name"]
            ).strip().lower()

            start_time = str(
                lecture["start_time"]
            ).strip()

            end_time = str(
                lecture["end_time"]
            ).strip()

            key = (
                lecture_name,
                start_time,
                end_time
            )

            existing_keys.add(key)


        # -------------------------------------------------
        # Create missing timetable lectures
        # -------------------------------------------------

        for item in ATTENDANCE_TIMETABLE:

            lecture_name = str(
                item["subject"]
            ).strip()

            start_time = str(
                item["start"]
            ).strip()

            end_time = str(
                item["end"]
            ).strip()

            key = (
                lecture_name.lower(),
                start_time,
                end_time
            )

            # Already exists
            if key in existing_keys:
                continue


            try:

                result = create_lecture(
                    lecture_name,
                    start_time,
                    end_time,
                    90
                )

                existing_keys.add(key)

                print(
                    "[TIMETABLE] Lecture created:",
                    lecture_name,
                    start_time,
                    "-",
                    end_time,
                    "ID:",
                    result
                )

            except Exception as lecture_error:

                print(
                    "[TIMETABLE] Could not create:",
                    lecture_name,
                    "| Error:",
                    lecture_error
                )


    except Exception as e:

        print(
            "[TIMETABLE] Setup error:",
            e
        )


# =========================================================
# GET TEACHER LECTURES
# =========================================================

def get_teacher_lectures():

    # VERY IMPORTANT:
    # Create timetable lectures before reading them.
    ensure_timetable_lectures()


    # Read fresh data AFTER creation
    all_lectures = get_all_lectures()

    teacher = get_logged_in_teacher()


    if not teacher:
        return []


    subjects = teacher.get(
        "subjects",
        []
    )


    # -----------------------------------------------------
    # ADMIN
    # -----------------------------------------------------

    if "ALL" in subjects:

        return all_lectures


    # -----------------------------------------------------
    # TEACHER SUBJECT FILTER
    # -----------------------------------------------------

    allowed_subjects = {
        str(subject).strip().lower()
        for subject in subjects
    }


    filtered = []


    for lecture in all_lectures:

        lecture_name = str(
            lecture["lecture_name"]
        ).strip().lower()


        if lecture_name in allowed_subjects:

            filtered.append(
                lecture
            )


    return filtered


# =========================================================
# LOGIN PROTECTION
# =========================================================

def login_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "user" not in session:

            return redirect(
                url_for("login")
            )

        return function(
            *args,
            **kwargs
        )

    return decorated_function


# =========================================================
# TEMPLATE CONTEXT
# =========================================================

@app.context_processor
def inject_endpoints():

    return {
        "endpoints": [
            rule.endpoint
            for rule in app.url_map.iter_rules()
        ]
    }


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    if "user" in session:

        return redirect(
            url_for("dashboard")
        )

    return redirect(
        url_for("login")
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()


        # =================================================
        # ADMIN LOGIN
        # =================================================

        if (
            username == "Riya"
            and
            password == "10178"
        ):

            session.clear()

            session["user"] = username

            session["teacher_name"] = "Admin"

            session["teacher_subjects"] = [
                "ALL"
            ]

            return redirect(
                url_for("dashboard")
            )


        # =================================================
        # TEACHER LOGIN
        # =================================================

        if (
            username in TEACHER_MAP
            and
            username != "Riya"
            and
            password == "10178"
        ):

            teacher = TEACHER_MAP[
                username
            ]

            session.clear()

            session["user"] = username

            session["teacher_name"] = (
                teacher["name"]
            )

            session["teacher_subjects"] = (
                teacher["subjects"]
            )

            return redirect(
                url_for("dashboard")
            )


        error = (
            "Invalid Username or Password!"
        )


    return render_template(
        "login.html",
        error=error
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    stats = get_dashboard_stats()

    weekly_data = get_weekly_attendance()

    recent_data = get_recent_attendance(
        10
    )

    lectures = get_all_lectures()

    return render_template(
        "dashboard.html",
        stats=stats,
        weekly_data=weekly_data,
        recent_data=recent_data,
        lectures=lectures
    )


# =========================================================
# ATTENDANCE PAGE
# =========================================================

@app.route("/attendance")
@login_required
def attendance():

    # -----------------------------------------------------
    # Ensure DB has timetable lectures first.
    # -----------------------------------------------------

    ensure_timetable_lectures()


    # -----------------------------------------------------
    # Get ONLY current teacher's lectures
    # -----------------------------------------------------

    lectures = get_teacher_lectures()


    current_day = datetime.now().strftime(
        "%A"
    )


    teacher = get_logged_in_teacher()


    teacher_name = (
        teacher["name"]
        if teacher
        else session.get(
            "teacher_name",
            "Admin"
        )
    )


    teacher_subjects = (
        teacher["subjects"]
        if teacher
        else []
    )


    return render_template(
        "attendance.html",
        lectures=lectures,
        current_day=current_day,
        teacher_name=teacher_name,
        teacher_subjects=teacher_subjects,
        attendance_timetable=(
            ATTENDANCE_TIMETABLE
        )
    )


# =========================================================
# STUDENTS
# =========================================================

@app.route("/students")
@login_required
def students():

    all_students = get_all_students()

    return render_template(
        "student.html",
        students=all_students
    )


# =========================================================
# EDIT STUDENT
# =========================================================

@app.route(
    "/students/edit/<student_id>"
)
@login_required
def edit_student(student_id):

    student = get_student_by_id(
        student_id
    )

    if not student:

        return redirect(
            url_for("students")
        )

    return render_template(
        "edit_student.html",
        student=student
    )


# =========================================================
# DELETE STUDENT
# =========================================================

@app.route(
    "/students/delete/<student_id>",
    methods=["POST"]
)
@login_required
def delete_student(student_id):

    try:

        success = delete_student_db(
            student_id
        )

        if request.is_json:

            return jsonify({
                "success": success
            })

        return redirect(
            url_for("students")
        )

    except Exception as e:

        if request.is_json:

            return jsonify({
                "success": False,
                "message": str(e)
            }), 500

        return redirect(
            url_for("students")
        )


# =========================================================
# ADD STUDENT
# =========================================================

@app.route(
    "/add-student",
    methods=["GET", "POST"]
)
@login_required
def add_student():

    # =====================================================
    # GET
    # =====================================================

    if request.method == "GET":

        student_id = request.args.get(
            "student_id",
            ""
        ).strip()


        # =================================================
        # CAPTURE PAGE
        # =================================================

        if student_id:

            student = get_student_by_id(
                str(student_id)
            )

            if not student:

                return render_template(
                    "add_student.html",
                    student=None,
                    student_id="",
                    error="Student not found.",
                    success=None,
                    registration=False
                )

            return render_template(
                "add_student.html",
                student=student,
                student_id=str(
                    student_id
                ),
                error=None,
                success=None,
                registration=True
            )


        # =================================================
        # NORMAL ADD FORM
        # =================================================

        return render_template(
            "add_student.html",
            student=None,
            student_id="",
            error=None,
            success=None,
            registration=False
        )


    # =====================================================
    # POST
    # =====================================================

    s_id = request.form.get(
        "student_id",
        ""
    ).strip()

    name = request.form.get(
        "name",
        ""
    ).strip()


    # =====================================================
    # VALIDATION
    # =====================================================

    if not s_id:

        return render_template(
            "add_student.html",
            student=None,
            student_id="",
            error="UID is required.",
            success=None,
            registration=False
        )


    if not name:

        return render_template(
            "add_student.html",
            student=None,
            student_id=s_id,
            error="Student name is required.",
            success=None,
            registration=False
        )


    # =====================================================
    # DUPLICATE CHECK
    # =====================================================

    try:

        existing_student = get_student_by_id(
            str(s_id)
        )

        if existing_student:

            return render_template(
                "add_student.html",
                student=existing_student,
                student_id=str(s_id),
                error=(
                    "A student with this UID "
                    "already exists."
                ),
                success=None,
                registration=False
            )

    except Exception:

        pass


    # =====================================================
    # REGISTER STUDENT
    # =====================================================

    try:

        roll_no = s_id

        result = register_student_details(
            s_id,
            name,
            roll_no
        )


        if isinstance(
            result,
            tuple
        ):

            success_flag, message = result

        else:

            success_flag = bool(
                result
            )

            message = ""


        if not success_flag:

            return render_template(
                "add_student.html",
                student=None,
                student_id=s_id,
                error=(
                    message
                    or
                    "Unable to register student."
                ),
                success=None,
                registration=False
            )


        return redirect(
            url_for(
                "add_student",
                student_id=str(s_id)
            )
        )


    except Exception as e:

        return render_template(
            "add_student.html",
            student=None,
            student_id=s_id,
            error=str(e),
            success=None,
            registration=False
        )


# =========================================================
# ADD STUDENT PAGE ALIAS
# =========================================================

@app.route(
    "/add-student-page",
    methods=["GET", "POST"]
)
@login_required
def add_student_page():

    if request.method == "POST":

        return add_student()

    return redirect(
        url_for("add_student")
    )


# =========================================================
# HISTORY
# =========================================================

@app.route("/history")
@login_required
def history():

    logs = get_all_logs()

    current_date = datetime.now().strftime(
        "%Y-%m-%d"
    )

    return render_template(
        "history.html",
        logs=logs,
        current_date=current_date
    )


# =========================================================
# REPORTS
# =========================================================

@app.route("/reports")
@login_required
def reports():

    logs = get_all_logs()

    stats = get_dashboard_stats()

    return render_template(
        "report.html",
        logs=logs,
        stats=stats
    )


# =========================================================
# LECTURES PAGE
# =========================================================

@app.route("/lectures")
@login_required
def lectures():

    ensure_timetable_lectures()

    all_lectures = get_all_lectures()

    return render_template(
        "lectures.html",
        lectures=all_lectures
    )


# =========================================================
# CREATE LECTURE
# =========================================================

@app.route(
    "/lectures/create",
    methods=["POST"]
)
@login_required
def create_lecture_api():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )

        lecture_name = str(
            data.get(
                "lecture_name",
                ""
            )
        ).strip()

        start_time = str(
            data.get(
                "start_time",
                ""
            )
        ).strip()

        end_time = str(
            data.get(
                "end_time",
                ""
            )
        ).strip()

        required_percentage = data.get(
            "required_percentage",
            75
        )


        if not lecture_name:

            return jsonify({
                "success": False,
                "message": "Lecture name is required."
            }), 400


        if not start_time:

            return jsonify({
                "success": False,
                "message": "Start time is required."
            }), 400


        if not end_time:

            return jsonify({
                "success": False,
                "message": "End time is required."
            }), 400


        try:

            required_percentage = float(
                required_percentage
            )

        except Exception:

            return jsonify({
                "success": False,
                "message": (
                    "Invalid required percentage."
                )
            }), 400


        if (
            required_percentage < 0
            or
            required_percentage > 100
        ):

            return jsonify({
                "success": False,
                "message": (
                    "Percentage must be between 0 and 100."
                )
            }), 400


        result = create_lecture(
            lecture_name,
            start_time,
            end_time,
            required_percentage
        )


        if isinstance(
            result,
            tuple
        ):

            success, message = result

        else:

            success = result is not None

            message = (
                "Lecture created successfully."
                if success
                else
                "Failed to create lecture."
            )


        response = {
            "success": success,
            "message": message
        }


        if success:

            if isinstance(result, tuple):

                if len(result) > 0:
                    response["lecture_id"] = result[0]

            else:

                response["lecture_id"] = result


        return jsonify(
            response
        )


    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# GET LECTURE
# =========================================================

@app.route(
    "/lectures/<int:lecture_id>",
    methods=["GET"]
)
@login_required
def get_lecture_api(lecture_id):

    try:

        lecture = get_lecture_by_id(
            lecture_id
        )


        if not lecture:

            return jsonify({
                "success": False,
                "message": "Lecture not found."
            }), 404


        if not teacher_can_access_lecture(
            lecture
        ):

            return jsonify({
                "success": False,
                "message": (
                    "You are not authorized "
                    "to access this lecture."
                )
            }), 403


        return jsonify({
            "success": True,
            "lecture": row_to_dict(
                lecture
            )
        })


    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# FACE REGISTRATION
# =========================================================

@app.route(
    "/register-face",
    methods=["POST"],
    endpoint="register_face"
)
@login_required
def register_face_api():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )

        student_id = data.get(
            "student_id"
        )

        image_base64 = data.get(
            "image"
        )

        index = data.get(
            "index"
        )


        if not student_id:

            return jsonify({
                "success": False,
                "message": "Student ID is required."
            }), 400


        if not image_base64:

            return jsonify({
                "success": False,
                "message": "No image data received."
            }), 400


        student = get_student_by_id(
            str(student_id)
        )


        if not student:

            return jsonify({
                "success": False,
                "message": "Student record not found."
            }), 404


        result = process_face_sample(
            str(student_id),
            image_base64,
            index
        )


        if isinstance(
            result,
            tuple
        ):

            success, message = result

        else:

            success = bool(result)
            message = ""


        return jsonify({
            "success": success,
            "message": message
        })


    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# FINISH FACE REGISTRATION
# =========================================================

@app.route(
    "/finish-registration/<student_id>",
    endpoint="finish_registration"
)
@login_required
def finish_registration_route(student_id):

    student = None

    try:

        student = get_student_by_id(
            str(student_id)
        )


        if not student:

            if request.args.get(
                "json"
            ) == "1":

                return jsonify({
                    "success": False,
                    "message": (
                        "Student record not found."
                    )
                }), 404


            return redirect(
                url_for("add_student")
            )


        result = finalize_student_registration(
            str(student_id)
        )


        if isinstance(
            result,
            tuple
        ):

            success, message = result

        else:

            success = bool(result)
            message = ""


        if request.args.get(
            "json"
        ) == "1":

            return jsonify({
                "success": success,
                "message": message
            })


        if success:

            return redirect(
                url_for("dashboard")
            )


        return render_template(
            "add_student.html",
            student=student,
            student_id=str(
                student_id
            ),
            error=(
                message
                or
                "Face training failed."
            ),
            success=None,
            registration=True
        )


    except Exception as e:

        if request.args.get(
            "json"
        ) == "1":

            return jsonify({
                "success": False,
                "message": str(e)
            }), 500


        return render_template(
            "add_student.html",
            student=student,
            student_id=str(
                student_id
            ),
            error=str(e),
            success=None,
            registration=True
        )


# =========================================================
# LEGACY FINISH REGISTRATION ROUTE
# =========================================================

@app.route(
    "/finish-registration-api/<student_id>"
)
@login_required
def finish_registration_legacy(student_id):

    return finish_registration_route(
        student_id
    )


# =========================================================
# FACE RECOGNITION
# =========================================================

@app.route(
    "/recognize-face",
    methods=["POST"]
)
@login_required
def recognize_face_api():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )

        image_base64 = data.get(
            "image"
        )


        if not image_base64:

            return jsonify({
                "success": False,
                "recognized": False,
                "message": (
                    "No frame data received."
                )
            }), 400


        lecture_id = data.get(
            "lecture_id"
        )


        if lecture_id is None:

            lecture_id = data.get(
                "id"
            )


        if lecture_id is None:

            return jsonify({
                "success": False,
                "recognized": False,
                "message": (
                    "Please select a lecture first."
                )
            }), 400


        try:

            lecture_id = int(
                lecture_id
            )

        except Exception:

            return jsonify({
                "success": False,
                "recognized": False,
                "message": (
                    "Invalid lecture ID."
                )
            }), 400


        lecture = get_lecture_by_id(
            lecture_id
        )


        if not lecture:

            return jsonify({
                "success": False,
                "recognized": False,
                "message": (
                    "Selected lecture not found."
                )
            }), 404


        if not teacher_can_access_lecture(
            lecture
        ):

            return jsonify({
                "success": False,
                "recognized": False,
                "message": (
                    "You are not authorized "
                    "for this lecture."
                )
            }), 403


        result = recognize_face(
            image_base64
        )


        if not result.get(
            "success"
        ):

            return jsonify(
                result
            )


        if not result.get(
            "recognized"
        ):

            return jsonify(
                result
            )


        student_id = result.get(
            "student_id"
        )


        if not student_id:

            return jsonify({
                "success": False,
                "recognized": False,
                "message": (
                    "Recognized face has no student ID."
                )
            })


        student_info = get_student_by_id(
            str(student_id)
        )


        if not student_info:

            return jsonify({
                "success": False,
                "recognized": False,
                "message": (
                    "Student record not found."
                )
            })


        current_session = session.get(
            "attendance_session"
        )


        if not isinstance(
            current_session,
            dict
        ):

            current_session = {}


        current_lecture_id = (
            current_session.get(
                "lecture_id"
            )
        )


        if (
            current_lecture_id is None
            or
            int(current_lecture_id)
            !=
            lecture_id
        ):

            current_session = {

                "lecture_id": lecture_id,

                "student_id": None,

                "attendance_id": None,

                "started_at": (
                    datetime.now().isoformat()
                )

            }

            session[
                "attendance_session"
            ] = current_session


        return jsonify({

            "success": True,

            "recognized": True,

            "student_id": str(
                student_id
            ),

            "name": student_info[
                "name"
            ],

            "roll_no": student_info[
                "roll_no"
            ],

            "confidence": result.get(
                "confidence",
                0
            ),

            "lecture_id": lecture_id,

            "lecture_name": lecture[
                "lecture_name"
            ],

            "attendance_marked": False,

            "message": (
                "Student recognized. "
                "Attendance verification in progress."
            )

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "recognized": False,

            "message": str(e)

        }), 500


# =========================================================
# ATTENDANCE SESSION - START
# =========================================================

@app.route(
    "/attendance/start",
    methods=["POST"]
)
@login_required
def attendance_start():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )

        lecture_id = data.get(
            "lecture_id"
        )


        if lecture_id is None:

            lecture_id = data.get(
                "id"
            )


        if lecture_id is None:

            return jsonify({
                "success": False,
                "message": (
                    "Lecture ID is required."
                )
            }), 400


        try:

            lecture_id = int(
                lecture_id
            )

        except Exception:

            return jsonify({
                "success": False,
                "message": (
                    "Invalid lecture ID."
                )
            }), 400


        lecture = get_lecture_by_id(
            lecture_id
        )


        if not lecture:

            return jsonify({
                "success": False,
                "message": (
                    "Lecture not found."
                )
            }), 404


        if not teacher_can_access_lecture(
            lecture
        ):

            return jsonify({
                "success": False,
                "message": (
                    "You are not authorized "
                    "for this lecture."
                )
            }), 403


        student_id = data.get(
            "student_id"
        )


        if not student_id:

            session[
                "attendance_session"
            ] = {

                "lecture_id": lecture_id,

                "student_id": None,

                "attendance_id": None,

                "started_at": (
                    datetime.now().isoformat()
                )

            }


            return jsonify({

                "success": True,

                "message": (
                    "Attendance scanner session started."
                ),

                "lecture_id": lecture_id,

                "student_id": None,

                "required_seconds": (
                    calculate_required_seconds(
                        lecture
                    )
                )

            })


        student_id = str(
            student_id
        ).strip()


        student = get_student_by_id(
            student_id
        )


        if not student:

            return jsonify({
                "success": False,
                "message": (
                    "Student not found."
                )
            }), 404


        required_seconds = (
            calculate_required_seconds(
                lecture
            )
        )


        required_percentage = float(
            lecture[
                "required_percentage"
            ]
            or
            90
        )


        attendance_id = (
            start_attendance_session(
                student_id,
                lecture_id,
                required_seconds
            )
        )


        existing_session = session.get(
            "attendance_session",
            {}
        )


        started_at = (
            existing_session.get(
                "started_at"
            )
            if isinstance(
                existing_session,
                dict
            )
            else None
        )


        if not started_at:

            started_at = (
                datetime.now().isoformat()
            )


        session[
            "attendance_session"
        ] = {

            "lecture_id": lecture_id,

            "student_id": student_id,

            "attendance_id": attendance_id,

            "started_at": started_at

        }


        return jsonify({

            "success": True,

            "message": (
                "Attendance session started."
            ),

            "lecture_id": lecture_id,

            "student_id": student_id,

            "attendance_id": attendance_id,

            "required_seconds": (
                required_seconds
            ),

            "required_percentage": (
                required_percentage
            )

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500


# =========================================================
# ATTENDANCE VERIFICATION
# =========================================================

@app.route(
    "/attendance/verify",
    methods=["POST"]
)
@login_required
def attendance_verify():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )


        current_session = session.get(
            "attendance_session"
        )


        if not current_session:

            return jsonify({
                "success": False,
                "message": (
                    "No attendance session is active."
                )
            }), 400


        lecture_id = current_session.get(
            "lecture_id"
        )


        if not lecture_id:

            return jsonify({
                "success": False,
                "message": (
                    "Invalid attendance session."
                )
            }), 400


        try:

            lecture_id = int(
                lecture_id
            )

        except Exception:

            return jsonify({
                "success": False,
                "message": (
                    "Invalid lecture ID."
                )
            }), 400


        lecture = get_lecture_by_id(
            lecture_id
        )


        if not lecture:

            return jsonify({
                "success": False,
                "message": (
                    "Lecture not found."
                )
            }), 404


        if not teacher_can_access_lecture(
            lecture
        ):

            return jsonify({
                "success": False,
                "message": (
                    "You are not authorized "
                    "for this lecture."
                )
            }), 403


        student_id = data.get(
            "student_id"
        )


        if not student_id:

            student_id = (
                current_session.get(
                    "student_id"
                )
            )


        if not student_id:

            return jsonify({
                "success": False,
                "message": (
                    "Student ID is required."
                )
            }), 400


        student_id = str(
            student_id
        ).strip()


        session_student_id = (
            current_session.get(
                "student_id"
            )
        )


        if (
            session_student_id
            and
            str(session_student_id)
            !=
            student_id
        ):

            return jsonify({
                "success": False,
                "message": (
                    "Student does not match "
                    "active attendance session."
                )
            }), 400


        student = get_student_by_id(
            student_id
        )


        if not student:

            return jsonify({
                "success": False,
                "message": (
                    "Student not found."
                )
            }), 404


        verified_seconds = data.get(
            "verified_seconds"
        )


        if verified_seconds is None:

            verified_seconds = data.get(
                "seconds",
                0
            )


        try:

            verified_seconds = float(
                verified_seconds
            )

        except Exception:

            verified_seconds = 0


        verified_seconds = max(
            0,
            verified_seconds
        )


        result = (
            update_attendance_verification(
                student_id,
                lecture_id,
                verified_seconds
            )
        )


        if result is None:

            return jsonify({
                "success": False,
                "message": (
                    "Attendance record not found. "
                    "Start the attendance session first."
                )
            }), 404


        return jsonify({

            "success": True,

            "student_id": student_id,

            "lecture_id": lecture_id,

            "name": student[
                "name"
            ],

            "roll_no": student[
                "roll_no"
            ],

            "verified_seconds": float(
                result[
                    "verified_seconds"
                ]
                or
                0
            ),

            "verification_count": int(
                result[
                    "verification_count"
                ]
                or
                0
            ),

            "message": (
                "Attendance verification updated."
            )

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500


# =========================================================
# ATTENDANCE FINALIZE
# =========================================================

@app.route(
    "/attendance/finalize",
    methods=["POST"]
)
@login_required
def attendance_finalize():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )


        current_session = session.get(
            "attendance_session"
        )


        if not current_session:

            return jsonify({
                "success": False,
                "message": (
                    "No attendance session is active."
                )
            }), 400


        lecture_id = data.get(
            "lecture_id"
        )


        if lecture_id is None:

            lecture_id = (
                current_session.get(
                    "lecture_id"
                )
            )


        if lecture_id is None:

            return jsonify({
                "success": False,
                "message": (
                    "Lecture ID is required."
                )
            }), 400


        try:

            lecture_id = int(
                lecture_id
            )

        except Exception:

            return jsonify({
                "success": False,
                "message": (
                    "Invalid lecture ID."
                )
            }), 400


        lecture = get_lecture_by_id(
            lecture_id
        )


        if not lecture:

            return jsonify({
                "success": False,
                "message": (
                    "Lecture not found."
                )
            }), 404


        if not teacher_can_access_lecture(
            lecture
        ):

            return jsonify({
                "success": False,
                "message": (
                    "You are not authorized "
                    "for this lecture."
                )
            }), 403


        student_id = data.get(
            "student_id"
        )


        if not student_id:

            student_id = (
                current_session.get(
                    "student_id"
                )
            )


        if not student_id:

            return jsonify({
                "success": False,
                "message": (
                    "Student ID is required."
                )
            }), 400


        student_id = str(
            student_id
        ).strip()


        session_lecture_id = (
            current_session.get(
                "lecture_id"
            )
        )


        session_student_id = (
            current_session.get(
                "student_id"
            )
        )


        if (
            session_lecture_id
            and
            int(session_lecture_id)
            !=
            lecture_id
        ):

            return jsonify({
                "success": False,
                "message": (
                    "Lecture does not match "
                    "active attendance session."
                )
            }), 400


        if (
            session_student_id
            and
            str(session_student_id)
            !=
            student_id
        ):

            return jsonify({
                "success": False,
                "message": (
                    "Student does not match "
                    "active attendance session."
                )
            }), 400


        result = finalize_attendance(
            student_id,
            lecture_id
        )


        if result is None:

            return jsonify({
                "success": False,
                "message": (
                    "Attendance record not found."
                )
            }), 404


        status = result[
            "status"
        ]


        verified_seconds = float(
            result[
                "verified_seconds"
            ]
            or
            0
        )


        required_seconds = float(
            result[
                "required_seconds"
            ]
            or
            0
        )


        session.pop(
            "attendance_session",
            None
        )


        return jsonify({

            "success": True,

            "student_id": student_id,

            "lecture_id": lecture_id,

            "status": status,

            "verified_seconds": (
                verified_seconds
            ),

            "required_seconds": (
                required_seconds
            ),

            "finalized": True,

            "message": (
                "Attendance marked as "
                + status
                + "."
            )

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500


# =========================================================
# ATTENDANCE STATUS
# =========================================================

@app.route(
    "/attendance/status",
    methods=["GET"]
)
@login_required
def attendance_status():

    current_session = session.get(
        "attendance_session"
    )


    if not current_session:

        return jsonify({

            "success": True,

            "active": False,

            "message": (
                "No attendance session is active."
            )

        })


    lecture_id = current_session.get(
        "lecture_id"
    )


    lecture = None


    if lecture_id:

        try:

            lecture = get_lecture_by_id(
                lecture_id
            )

        except Exception:

            lecture = None


    if lecture and not teacher_can_access_lecture(
        lecture
    ):

        session.pop(
            "attendance_session",
            None
        )

        return jsonify({

            "success": True,

            "active": False,

            "message": (
                "Attendance session is not "
                "authorized for this teacher."
            )

        })


    return jsonify({

        "success": True,

        "active": True,

        "lecture_id": lecture_id,

        "student_id": current_session.get(
            "student_id"
        ),

        "attendance_id": current_session.get(
            "attendance_id"
        ),

        "lecture": (
            row_to_dict(lecture)
            if lecture
            else None
        ),

        "started_at": (
            current_session.get(
                "started_at"
            )
        )

    })


# =========================================================
# DASHBOARD API
# =========================================================

@app.route(
    "/api/dashboard",
    methods=["GET"]
)
@login_required
def dashboard_api():

    try:

        stats = get_dashboard_stats()

        weekly_data = get_weekly_attendance()

        recent_data = get_recent_attendance(
            10
        )


        return jsonify({

            "success": True,

            "stats": stats,

            "weekly_data": (
                rows_to_dicts(
                    weekly_data
                )
            ),

            "recent_data": (
                rows_to_dicts(
                    recent_data
                )
            )

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route(
    "/api/health",
    methods=["GET"]
)
def health_check():

    return jsonify({

        "success": True,

        "status": "online",

        "service": (
            "Smart Attendance System"
        ),

        "time": (
            datetime.now().isoformat()
        )

    })


# =========================================================
# 404 HANDLER
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({

            "success": False,

            "message": (
                "API endpoint not found."
            ),

            "path": request.path

        }), 404


    return render_template(
        "404.html"
    ), 404


# =========================================================
# 500 HANDLER
# =========================================================

@app.errorhandler(500)
def internal_server_error(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({

            "success": False,

            "message": (
                "Internal server error."
            )

        }), 500


    return render_template(
        "500.html"
    ), 500


# =========================================================
# APPLICATION START
# =========================================================

if __name__ == "__main__":

    # -----------------------------------------------------
    # Create timetable lectures when application starts.
    # -----------------------------------------------------

    ensure_timetable_lectures()


    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )