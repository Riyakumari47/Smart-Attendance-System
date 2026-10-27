import sqlite3
from datetime import datetime, date
import os

# =========================================================
# DATABASE CONFIGURATION
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_NAME = os.path.join(DB_DIR, "attendance.db")

os.makedirs(DB_DIR, exist_ok=True)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # -------------------------
    # STUDENTS TABLE
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -------------------------
    # LECTURES TABLE
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lectures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lecture_name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            required_percentage REAL DEFAULT 90,
            status TEXT DEFAULT 'Scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -------------------------
    # ATTENDANCE TABLE
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id TEXT NOT NULL,

            lecture_id INTEGER,

            date TEXT NOT NULL,

            first_seen TEXT,

            last_seen TEXT,

            verified_seconds REAL DEFAULT 0,

            required_seconds REAL DEFAULT 0,

            verification_count INTEGER DEFAULT 0,

            status TEXT DEFAULT 'In Progress',

            finalized INTEGER DEFAULT 0,

            final_time TEXT,

            FOREIGN KEY (student_id)
                REFERENCES students(student_id)
                ON DELETE CASCADE,

            FOREIGN KEY (lecture_id)
                REFERENCES lectures(id)
                ON DELETE SET NULL
        )
    """)

    conn.commit()

    # ---------------------------------------------------------
    # BACKWARD COMPATIBILITY
    # Existing database may already have the old columns.
    # Add missing columns safely.
    # ---------------------------------------------------------

    existing_columns = []

    cursor.execute("PRAGMA table_info(attendance)")
    columns = cursor.fetchall()

    for column in columns:
        existing_columns.append(column["name"])

    new_columns = {
        "lecture_id": "INTEGER",
        "first_seen": "TEXT",
        "last_seen": "TEXT",
        "verified_seconds": "REAL DEFAULT 0",
        "required_seconds": "REAL DEFAULT 0",
        "verification_count": "INTEGER DEFAULT 0",
        "finalized": "INTEGER DEFAULT 0",
        "final_time": "TEXT"
    }

    for column_name, column_type in new_columns.items():

        if column_name not in existing_columns:

            try:
                cursor.execute(
                    f"ALTER TABLE attendance ADD COLUMN "
                    f"{column_name} {column_type}"
                )
            except sqlite3.OperationalError:
                pass

    conn.commit()
    conn.close()


# =========================================================
# STUDENT FUNCTIONS
# =========================================================

def add_student_db(student_id, name, roll_no):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO students
            (student_id, name, roll_no)
            VALUES (?, ?, ?)
        """, (
            str(student_id),
            name.strip(),
            roll_no.strip()
        ))

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        return False

    finally:

        conn.close()


def get_student_by_id(student_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM students
        WHERE student_id = ?
    """, (str(student_id),))

    student = cursor.fetchone()

    conn.close()

    return student


def get_all_students():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM students
        ORDER BY id DESC
    """)

    students = cursor.fetchall()

    conn.close()

    return students


def delete_student_db(student_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM students
        WHERE student_id = ?
    """, (str(student_id),))

    conn.commit()

    deleted = cursor.rowcount > 0

    conn.close()

    return deleted


# =========================================================
# LECTURE FUNCTIONS
# =========================================================

def create_lecture(
    lecture_name,
    start_time,
    end_time,
    required_percentage=90
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO lectures
        (
            lecture_name,
            start_time,
            end_time,
            required_percentage,
            status
        )
        VALUES (?, ?, ?, ?, 'Scheduled')
    """, (
        lecture_name,
        start_time,
        end_time,
        float(required_percentage)
    ))

    conn.commit()

    lecture_id = cursor.lastrowid

    conn.close()

    return lecture_id

def get_all_lectures():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM lectures
        ORDER BY id DESC
    """)

    lectures = cursor.fetchall()

    conn.close()

    return lectures
    
def get_lecture_by_id(lecture_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM lectures
        WHERE id = ?
    """, (lecture_id,))

    lecture = cursor.fetchone()

    conn.close()

    return lecture


# =========================================================
# ATTENDANCE SESSION
# =========================================================

def start_attendance_session(
    student_id,
    lecture_id,
    required_seconds
):

    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now()

    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")

    # Check if record already exists
    cursor.execute("""
        SELECT *
        FROM attendance
        WHERE student_id = ?
        AND lecture_id = ?
        AND date = ?
    """, (
        str(student_id),
        lecture_id,
        today
    ))

    record = cursor.fetchone()

    if record:

        conn.close()

        return record["id"]

    cursor.execute("""
        INSERT INTO attendance
        (
            student_id,
            lecture_id,
            date,
            first_seen,
            last_seen,
            verified_seconds,
            required_seconds,
            verification_count,
            status,
            finalized
        )
        VALUES (?, ?, ?, ?, ?, 0, ?, 1, 'In Progress', 0)
    """, (
        str(student_id),
        lecture_id,
        today,
        current_time,
        current_time,
        float(required_seconds)
    ))

    conn.commit()

    attendance_id = cursor.lastrowid

    conn.close()

    return attendance_id


# =========================================================
# UPDATE VERIFIED ATTENDANCE
# =========================================================

def update_attendance_verification(
    student_id,
    lecture_id,
    verified_seconds
):

    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")

    cursor.execute("""
        SELECT *
        FROM attendance
        WHERE student_id = ?
        AND lecture_id = ?
        AND date = ?
    """, (
        str(student_id),
        lecture_id,
        today
    ))

    record = cursor.fetchone()

    if not record:

        conn.close()

        return None

    new_seconds = max(
        float(record["verified_seconds"] or 0),
        float(verified_seconds)
    )

    cursor.execute("""
        UPDATE attendance
        SET
            last_seen = ?,
            verified_seconds = ?,
            verification_count =
                COALESCE(verification_count, 0) + 1
        WHERE id = ?
    """, (
        current_time,
        new_seconds,
        record["id"]
    ))

    conn.commit()

    cursor.execute("""
        SELECT *
        FROM attendance
        WHERE id = ?
    """, (record["id"],))

    updated = cursor.fetchone()

    conn.close()

    return updated


# =========================================================
# FINALIZE ATTENDANCE
# =========================================================

def finalize_attendance(
    student_id,
    lecture_id
):

    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")

    cursor.execute("""
        SELECT *
        FROM attendance
        WHERE student_id = ?
        AND lecture_id = ?
        AND date = ?
    """, (
        str(student_id),
        lecture_id,
        today
    ))

    record = cursor.fetchone()

    if not record:

        conn.close()

        return None

    verified = float(record["verified_seconds"] or 0)
    required = float(record["required_seconds"] or 0)

    # Student is Present only when required duration is achieved.
    if required > 0 and verified >= required:

        status = "Present"

    else:

        status = "Absent"

    cursor.execute("""
        UPDATE attendance
        SET
            status = ?,
            finalized = 1,
            final_time = ?
        WHERE id = ?
    """, (
        status,
        current_time,
        record["id"]
    ))

    conn.commit()

    cursor.execute("""
        SELECT *
        FROM attendance
        WHERE id = ?
    """, (record["id"],))

    updated = cursor.fetchone()

    conn.close()

    return updated


# =========================================================
# OLD COMPATIBILITY FUNCTION
# =========================================================

def mark_attendance_db(student_id):

    """
    Old function kept so existing code does not immediately break.

    IMPORTANT:
    This function no longer directly creates Present attendance.
    Attendance should be created through a lecture session.
    """

    student = get_student_by_id(student_id)

    if not student:

        return False

    return True


# =========================================================
# ATTENDANCE LOGS
# =========================================================

def get_all_logs():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            a.id,
            a.student_id,
            s.name,
            s.roll_no,
            a.lecture_id,
            l.lecture_name,
            a.date,
            a.first_seen,
            a.last_seen,
            a.verified_seconds,
            a.required_seconds,
            a.verification_count,
            a.status,
            a.finalized,
            a.final_time
        FROM attendance a

        LEFT JOIN students s
            ON a.student_id = s.student_id

        LEFT JOIN lectures l
            ON a.lecture_id = l.id

        ORDER BY
            a.date DESC,
            a.id DESC
    """)

    logs = cursor.fetchall()

    conn.close()

    return logs


# =========================================================
# DASHBOARD STATISTICS
# =========================================================

def get_dashboard_stats():

    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    # Total students
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM students
    """)

    total_students = cursor.fetchone()["total"]

    # Present today
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM attendance
        WHERE date = ?
        AND status = 'Present'
    """, (today,))

    present_today = cursor.fetchone()["total"]

    # Absent today
    cursor.execute("""
        SELECT COUNT(*)
        FROM attendance
        WHERE date = ?
        AND status = 'Absent'
    """, (today,))

    absent_today = cursor.fetchone()[0]

    # Attendance percentage
    if total_students > 0:

        attendance_percentage = round(
            (present_today / total_students) * 100,
            1
        )

    else:

        attendance_percentage = 0

    conn.close()

    return {
        "total_students": total_students,
        "present_today": present_today,
        "absent_today": absent_today,
        "attendance_percentage": attendance_percentage
    }


# =========================================================
# WEEKLY ATTENDANCE
# =========================================================

def get_weekly_attendance():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            date,
            SUM(
                CASE
                    WHEN status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present,
            SUM(
                CASE
                    WHEN status = 'Absent'
                    THEN 1
                    ELSE 0
                END
            ) AS absent
        FROM attendance
        GROUP BY date
        ORDER BY date DESC
        LIMIT 7
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# RECENT ATTENDANCE
# =========================================================

def get_recent_attendance(limit=10):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            a.*,
            s.name,
            s.roll_no
        FROM attendance a

        LEFT JOIN students s
            ON a.student_id = s.student_id

        ORDER BY
            a.id DESC

        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# INITIALIZE DATABASE
# =========================================================

init_db()