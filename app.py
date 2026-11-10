   
from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date


app = Flask(__name__)
app.secret_key = "skillbridge_secret_key"


# DATABASE CONNECTION
def get_db_connection():
    conn = sqlite3.connect("skillbridge.db")
    conn.row_factory = sqlite3.Row
    return conn


# CREATE DATABASE TABLES
def create_table():
    conn = get_db_connection()

    # Students Table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            college TEXT NOT NULL,
            department TEXT NOT NULL,
            year TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Student Skills Table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS student_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER UNIQUE,
            teach_skills TEXT NOT NULL,
            learn_skills TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # Learning Requests Table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learning_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sender_id, receiver_id),
            FOREIGN KEY(sender_id) REFERENCES students(id),
            FOREIGN KEY(receiver_id) REFERENCES students(id)
        )
    """)

    # PRIVATE CHAT MESSAGES TABLE
    # Correct location: inside create_table()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES students(id),
            FOREIGN KEY(receiver_id) REFERENCES students(id)
        )
    """)

    # SKILL EXCHANGE SESSIONS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            session_time TEXT NOT NULL,
            meeting_details TEXT,
            status TEXT DEFAULT 'Scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES students(id),
            FOREIGN KEY (receiver_id) REFERENCES students(id)
        )
    """)

    conn.commit()
    conn.close()


# HOME PAGE
@app.route("/")
def home():
    return render_template("index.html")


# STUDENT REGISTRATION
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip().lower()
        college = request.form["college"].strip()
        department = request.form["department"]
        year = request.form["year"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()

        try:
            conn.execute("""
                INSERT INTO students
                (full_name, email, college, department, year, password)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                full_name,
                email,
                college,
                department,
                year,
                hashed_password
            ))

            conn.commit()

            flash(
                "Registration successful! Please login.",
                "success"
            )

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            flash(
                "Email already registered. Please use another email.",
                "error"
            )

        finally:
            conn.close()

    return render_template("register.html")


# STUDENT LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db_connection()

        student = conn.execute("""
            SELECT *
            FROM students
            WHERE email = ?
        """, (email,)).fetchone()

        conn.close()

        if student and check_password_hash(
            student["password"], password
        ):

            session["student_id"] = student["id"]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# STUDENT DASHBOARD
@app.route("/dashboard")
def dashboard():

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (session["student_id"],)).fetchone()

    conn.close()

    if student is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        student=student
    )


# SAVE STUDENT SKILLS
@app.route("/skills", methods=["GET", "POST"])
def skills():

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    if request.method == "POST":

        teach_skills = request.form["teach_skills"]
        learn_skills = request.form["learn_skills"]

        conn.execute("""
            INSERT INTO student_skills
            (student_id, teach_skills, learn_skills)
            VALUES (?, ?, ?)

            ON CONFLICT(student_id)
            DO UPDATE SET
                teach_skills = excluded.teach_skills,
                learn_skills = excluded.learn_skills
        """, (
            session["student_id"],
            teach_skills,
            learn_skills
        ))

        conn.commit()
        conn.close()

        flash(
            "Your skills saved successfully!",
            "success"
        )

        return redirect(url_for("skills"))

    conn.close()

    return render_template("skills.html")


# FIND MATCHING STUDENTS
@app.route("/matches")
def matches():

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    student_matches = conn.execute("""
        SELECT
            students.id AS student_id,
            students.full_name,
            students.college,
            students.department,
            students.year,
            student_skills.teach_skills,
            student_skills.learn_skills

        FROM student_skills AS mine

        JOIN student_skills
        ON student_skills.teach_skills = mine.learn_skills
        AND student_skills.learn_skills = mine.teach_skills

        JOIN students
        ON students.id = student_skills.student_id

        WHERE mine.student_id = ?
        AND student_skills.student_id != ?

    """, (
        session["student_id"],
        session["student_id"]
    )).fetchall()

    conn.close()

    return render_template(
        "matches.html",
        matches=student_matches
    )


# SEND LEARNING REQUEST
@app.route("/send-request/<int:receiver_id>", methods=["POST"])
def send_request(receiver_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    sender_id = session["student_id"]

    if sender_id == receiver_id:

        flash(
            "You cannot send a request to yourself.",
            "error"
        )

        return redirect(url_for("matches"))

    conn = get_db_connection()

    receiver = conn.execute("""
        SELECT id
        FROM students
        WHERE id = ?
    """, (receiver_id,)).fetchone()

    if receiver is None:

        conn.close()

        flash("Student not found.", "error")

        return redirect(url_for("matches"))

    # Verify Reciprocal Skill Match
    valid_match = conn.execute("""
        SELECT 1

        FROM student_skills AS mine

        JOIN student_skills AS theirs
        ON theirs.teach_skills = mine.learn_skills
        AND theirs.learn_skills = mine.teach_skills

        WHERE mine.student_id = ?
        AND theirs.student_id = ?

    """, (sender_id, receiver_id)).fetchone()

    if valid_match is None:

        conn.close()

        flash(
            "This student is not a valid skill match.",
            "error"
        )

        return redirect(url_for("matches"))

    try:

        conn.execute("""
            INSERT INTO learning_requests
            (sender_id, receiver_id)
            VALUES (?, ?)
        """, (sender_id, receiver_id))

        conn.commit()

        flash(
            "Learning request sent successfully!",
            "success"
        )

    except sqlite3.IntegrityError:

        flash(
            "You have already sent a request to this student.",
            "error"
        )

    finally:
        conn.close()

    return redirect(url_for("matches"))


# VIEW RECEIVED LEARNING REQUESTS
@app.route("/received-requests")
def received_requests():

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    received = conn.execute("""
        SELECT
            learning_requests.id AS request_id,
            learning_requests.status,
            learning_requests.created_at,
            students.full_name,
            students.college,
            students.department,
            students.year,
            student_skills.teach_skills,
            student_skills.learn_skills

        FROM learning_requests

        JOIN students
        ON students.id = learning_requests.sender_id

        LEFT JOIN student_skills
        ON student_skills.student_id = students.id

        WHERE learning_requests.receiver_id = ?

        ORDER BY learning_requests.created_at DESC

    """, (session["student_id"],)).fetchall()

    conn.close()

    return render_template(
        "received_requests.html",
        received=received
    )


# ACCEPT LEARNING REQUEST
@app.route("/accept-request/<int:request_id>", methods=["POST"])
def accept_request(request_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    result = conn.execute("""
        UPDATE learning_requests

        SET status = 'Accepted'

        WHERE id = ?
        AND receiver_id = ?
        AND status = 'Pending'

    """, (
        request_id,
        session["student_id"]
    ))

    conn.commit()
    conn.close()

    if result.rowcount > 0:

        flash(
            "Learning request accepted successfully!",
            "success"
        )

    else:

        flash(
            "Request not found or already processed.",
            "error"
        )

    return redirect(url_for("received_requests"))


# REJECT LEARNING REQUEST
@app.route("/reject-request/<int:request_id>", methods=["POST"])
def reject_request(request_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    result = conn.execute("""
        UPDATE learning_requests

        SET status = 'Rejected'

        WHERE id = ?
        AND receiver_id = ?
        AND status = 'Pending'

    """, (
        request_id,
        session["student_id"]
    ))

    conn.commit()
    conn.close()

    if result.rowcount > 0:

        flash(
            "Learning request rejected.",
            "success"
        )

    else:

        flash(
            "Request not found or already processed.",
            "error"
        )

    return redirect(url_for("received_requests"))


# ACCEPTED STUDENTS / CONNECTIONS
@app.route("/connections")
def connections():

    if "student_id" not in session:
        return redirect(url_for("login"))

    current_id = session["student_id"]

    conn = get_db_connection()

    accepted = conn.execute("""
        SELECT
            students.id,
            students.full_name,
            students.email,
            students.college,
            students.department,
            students.year

        FROM learning_requests

        JOIN students
        ON students.id = learning_requests.sender_id

        WHERE learning_requests.receiver_id = ?
        AND learning_requests.status = 'Accepted'

        UNION

        SELECT
            students.id,
            students.full_name,
            students.email,
            students.college,
            students.department,
            students.year

        FROM learning_requests

        JOIN students
        ON students.id = learning_requests.receiver_id

        WHERE learning_requests.sender_id = ?
        AND learning_requests.status = 'Accepted'

    """, (current_id, current_id)).fetchall()

    conn.close()

    return render_template(
        "connections.html",
        connections=accepted
    )


# PRIVATE CHAT
@app.route("/chat/<int:peer_id>", methods=["GET", "POST"])
def chat(peer_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    current_id = session["student_id"]

    conn = get_db_connection()

    # Check Accepted Connection
    connection = conn.execute("""
        SELECT id

        FROM learning_requests

        WHERE status = 'Accepted'

        AND (
            (sender_id = ? AND receiver_id = ?)
            OR
            (sender_id = ? AND receiver_id = ?)
        )

    """, (
        current_id,
        peer_id,
        peer_id,
        current_id
    )).fetchone()

    if connection is None:

        conn.close()

        flash(
            "Chat is available only with accepted connections.",
            "error"
        )

        return redirect(url_for("connections"))

    # Get Chat Partner
    peer = conn.execute("""
        SELECT id, full_name

        FROM students

        WHERE id = ?

    """, (peer_id,)).fetchone()

    if peer is None:

        conn.close()

        flash("Student not found.", "error")

        return redirect(url_for("connections"))

    # SEND MESSAGE
    if request.method == "POST":

        message = request.form.get(
            "message", ""
        ).strip()

        if message:

            conn.execute("""
                INSERT INTO messages
                (sender_id, receiver_id, message)

                VALUES (?, ?, ?)

            """, (
                current_id,
                peer_id,
                message
            ))

            conn.commit()

        conn.close()

        return redirect(
            url_for("chat", peer_id=peer_id)
        )

    # DISPLAY CONVERSATION
    messages = conn.execute("""
        SELECT
            messages.*,
            students.full_name AS sender_name

        FROM messages

        JOIN students
        ON students.id = messages.sender_id

        WHERE
            (
                messages.sender_id = ?
                AND messages.receiver_id = ?
            )

            OR

            (
                messages.sender_id = ?
                AND messages.receiver_id = ?
            )

        ORDER BY
            messages.created_at ASC,
            messages.id ASC

    """, (
        current_id,
        peer_id,
        peer_id,
        current_id
    )).fetchall()

    conn.close()

    return render_template(
        "chat.html",
        peer=peer,
        messages=messages,
        current_id=current_id
    )
    # SCHEDULE SKILL EXCHANGE SESSION
@app.route("/schedule-session/<int:peer_id>", methods=["GET", "POST"])
def schedule_session(peer_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    current_id = session["student_id"]
    conn = get_db_connection()

    # Check accepted connection
    connection = conn.execute("""
        SELECT id
        FROM learning_requests
        WHERE status = 'Accepted'
        AND (
            (sender_id = ? AND receiver_id = ?)
            OR
            (sender_id = ? AND receiver_id = ?)
        )
    """, (current_id, peer_id, peer_id, current_id)).fetchone()

    if connection is None:
        conn.close()
        flash("You can schedule sessions only with accepted connections.", "error")
        return redirect(url_for("connections"))

    # Get student details
    peer = conn.execute("""
        SELECT id, full_name
        FROM students
        WHERE id = ?
    """, (peer_id,)).fetchone()

    if peer is None:
        conn.close()
        flash("Student not found.", "error")
        return redirect(url_for("connections"))

    if request.method == "POST":

        session_date = request.form.get("session_date", "").strip()
        session_time = request.form.get("session_time", "").strip()
        meeting_details = request.form.get("meeting_details", "").strip()

        if not session_date or not session_time:
            flash("Please select session date and time.", "error")
            conn.close()
            return redirect(url_for("schedule_session", peer_id=peer_id))

        conn.execute("""
            INSERT INTO sessions
            (sender_id, receiver_id, session_date, session_time, meeting_details)
            VALUES (?, ?, ?, ?, ?)
        """, (
            current_id,
            peer_id,
            session_date,
            session_time,
            meeting_details
        ))

        conn.commit()
        conn.close()

        flash("Session scheduled successfully!", "success")
        return redirect(url_for("my_sessions"))

    conn.close()

    return render_template(
        "schedule_session.html",
        peer=peer,
        today=date.today().isoformat()
    )


# VIEW MY SCHEDULED SESSIONS
# VIEW MY SCHEDULED SESSIONS
@app.route("/my-sessions")
def my_sessions():

    if "student_id" not in session:
        return redirect(url_for("login"))

    current_id = session["student_id"]
    conn = get_db_connection()

    # Automatically mark past scheduled sessions as completed
    conn.execute("""
        UPDATE sessions
        SET status = 'Completed'
        WHERE session_date < ?
        AND status = 'Scheduled'
        AND (sender_id = ? OR receiver_id = ?)
    """, (date.today().isoformat(), current_id, current_id))

    conn.commit()

    all_sessions = conn.execute("""
        SELECT
            sessions.*,
            sender.full_name AS sender_name,
            receiver.full_name AS receiver_name
        FROM sessions
        JOIN students AS sender
            ON sender.id = sessions.sender_id
        JOIN students AS receiver
            ON receiver.id = sessions.receiver_id
        WHERE sessions.sender_id = ?
           OR sessions.receiver_id = ?
        ORDER BY sessions.session_date ASC,
                 sessions.session_time ASC
    """, (current_id, current_id)).fetchall()

    upcoming_sessions = [
        item for item in all_sessions
        if item["status"] == "Scheduled"
    ]

    completed_sessions = [
        item for item in all_sessions
        if item["status"] == "Completed"
    ]

    cancelled_sessions = [
        item for item in all_sessions
        if item["status"] == "Cancelled"
    ]

    conn.close()

    return render_template(
        "my_sessions.html",
        upcoming_sessions=upcoming_sessions,
        completed_sessions=completed_sessions,
        cancelled_sessions=cancelled_sessions,
        current_id=current_id
    )
    
# CANCEL SCHEDULED SESSION
@app.route("/cancel-session/<int:session_id>", methods=["POST"])
def cancel_session(session_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    current_id = session["student_id"]
    conn = get_db_connection()

    existing = conn.execute("""
        SELECT id, status
        FROM sessions
        WHERE id = ?
        AND (sender_id = ? OR receiver_id = ?)
    """, (session_id, current_id, current_id)).fetchone()

    if existing is None:
        conn.close()
        flash("Session not found.", "error")
        return redirect(url_for("my_sessions"))

    if existing["status"] != "Scheduled":
        conn.close()
        flash("Only scheduled sessions can be cancelled.", "error")
        return redirect(url_for("my_sessions"))

    conn.execute("""
        UPDATE sessions
        SET status = 'Cancelled'
        WHERE id = ?
    """, (session_id,))

    conn.commit()
    conn.close()

    flash("Session cancelled successfully!", "success")
    return redirect(url_for("my_sessions"))

# RESCHEDULE SKILL EXCHANGE SESSION
@app.route("/reschedule-session/<int:session_id>", methods=["GET", "POST"])
def reschedule_session(session_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    current_id = session["student_id"]
    conn = get_db_connection()

    item = conn.execute("""
        SELECT *
        FROM sessions
        WHERE id = ?
        AND (sender_id = ? OR receiver_id = ?)
    """, (session_id, current_id, current_id)).fetchone()

    if item is None:
        conn.close()
        flash("Session not found.", "error")
        return redirect(url_for("my_sessions"))

    if item["status"] != "Scheduled":
        conn.close()
        flash("Only scheduled sessions can be rescheduled.", "error")
        return redirect(url_for("my_sessions"))

    if request.method == "POST":

        new_date = request.form.get("session_date", "").strip()
        new_time = request.form.get("session_time", "").strip()
        new_details = request.form.get("meeting_details", "").strip()

        if not new_date or not new_time:
            conn.close()
            flash("Please select date and time.", "error")
            return redirect(url_for("reschedule_session", session_id=session_id))

        if new_date < date.today().isoformat():
            conn.close()
            flash("Please select a valid future date.", "error")
            return redirect(url_for("reschedule_session", session_id=session_id))

        conn.execute("""
            UPDATE sessions
            SET session_date = ?,
                session_time = ?,
                meeting_details = ?
            WHERE id = ?
        """, (new_date, new_time, new_details, session_id))

        conn.commit()
        conn.close()

        flash("Session rescheduled successfully!", "success")
        return redirect(url_for("my_sessions"))

    conn.close()

    return render_template(
        "reschedule_session.html",
        item=item,
        today=date.today().isoformat()
    )
    
# MARK SESSION AS COMPLETED
@app.route("/complete-session/<int:session_id>", methods=["POST"])
def complete_session(session_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    current_id = session["student_id"]
    conn = get_db_connection()

    item = conn.execute("""
        SELECT *
        FROM sessions
        WHERE id = ?
        AND (sender_id = ? OR receiver_id = ?)
    """, (session_id, current_id, current_id)).fetchone()

    if item is None:
        conn.close()
        flash("Session not found.", "error")
        return redirect(url_for("my_sessions"))

    if item["status"] != "Scheduled":
        conn.close()
        flash("This session cannot be completed.", "error")
        return redirect(url_for("my_sessions"))

    if item["session_date"] > date.today().isoformat():
        conn.close()
        flash("You cannot complete a future session.", "error")
        return redirect(url_for("my_sessions"))

    conn.execute("""
        UPDATE sessions
        SET status = 'Completed'
        WHERE id = ?
    """, (session_id,))

    conn.commit()
    conn.close()

    flash("Session marked as completed!", "success")
    return redirect(url_for("my_sessions"))





# LOGOUT
@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have logged out successfully.",
        "success"
    )

    return redirect(url_for("login"))


# RUN APPLICATION
if __name__ == "__main__":

    create_table()

    app.run(host="0.0.0.0", port=5000, debug=False)