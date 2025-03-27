import os
import logging
from flask import Flask, render_template, abort, jsonify, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from markupsafe import Markup
from config import SQLALCHEMY_DATABASE_URI, db
from decimal import Decimal
import json
import nltk
import re
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from sentiment_analysis import analyze_sentiment
from improvement_tips import generate_improvement_tip
from issue_extraction import extract_issues
from datetime import datetime, timedelta
from matching_module import calculate_dynamic_score, match_tutor 
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_apscheduler import APScheduler
from werkzeug.utils import secure_filename

from models import Tutor, Student, Subject, TutorSubject, TutorReview, TutorAvailableSlot, Session, SessionFeedback, StudentSubject, StudentAvailableSlot, StudentLearningPath, seed_data

analyzer = SentimentIntensityAnalyzer()

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key_here'

db.init_app(app)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

def get_current_time():
    return datetime.now()


# --------------------------
# Create tables and seed data
# --------------------------
with app.app_context():
    db.create_all()  
    seed_data()       

# ------------------------
# Helper Functions
# ------------------------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def update_past_sessions():
    """Update any 'Scheduled' sessions whose scheduled_time is in the past to 'Completed'."""
    current_time = get_current_time()
    past_sessions = Session.query.filter(
        Session.session_status=='Scheduled',
        Session.scheduled_time <= current_time
    ).all()
    for s in past_sessions:
        s.session_status = 'Completed'
    db.session.commit()

def remove_expired_available_slots():
    """Automatically delete expired tutor slots from the database."""
    with app.app_context():
        current_datetime = get_current_time()
        expired_slots = TutorAvailableSlot.query.filter(
            (TutorAvailableSlot.available_date < current_datetime.date()) |
            ((TutorAvailableSlot.available_date == current_datetime.date()) &
             (TutorAvailableSlot.end_time <= current_datetime.time()))
        ).all()
        if expired_slots:
            for slot in expired_slots:
                db.session.delete(slot)
            db.session.commit()
        print(f"Expired tutor slots removed at {current_datetime}")

scheduler.add_job(id='remove_expired_slots', func=remove_expired_available_slots, trigger='interval', minutes=30)

# ------------------------
# Routes (unchanged)
# ------------------------

@app.route('/')
def home():
    return render_template('landing-page.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard-student')
def dashboard_student():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    update_past_sessions()
    student_id = session['student_id']
    student = Student.query.get(student_id)
    if not student:
        abort(404)
    sessions = Session.query.filter_by(student_id=student_id).all()
    completed_sessions = [s for s in sessions if s.session_status == 'Completed']
    recommended_tutor_ids = {s.tutor_id for s in completed_sessions}
    recommended_tutors = Tutor.query.filter(Tutor.tutor_id.in_(recommended_tutor_ids)).all()
    current_time = get_current_time()
    upcoming_sessions = Session.query.filter(
        Session.student_id == student_id,
        Session.session_status == 'Scheduled',
        Session.scheduled_time > current_time
    ).order_by(Session.scheduled_time).all()
    for s in upcoming_sessions:
        s.end_time = s.scheduled_time + timedelta(hours=1)
    total_sessions = len(completed_sessions)
    return render_template(
        'dashboard-student.html',
        student=student,
        student_id=student_id,
        recommended_tutors=recommended_tutors,
        total_sessions=total_sessions,
        upcoming_sessions=upcoming_sessions
    )

@app.route('/student/settings')
def student_profile_settings():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    student_id = session['student_id']
    student = Student.query.get(student_id)
    if not student:
        abort(404)
    all_subjects = Subject.query.order_by(Subject.subject_name).all()
    student_subjects = StudentSubject.query.filter_by(student_id=student_id).all()
    student_subject_ids = [ss.subject_id for ss in student_subjects]
    all_languages = [ "Afrikaans", "Albanian", "Amharic", "Arabic", "Armenian", "Azerbaijani", "Basque",
                      "Belarusian", "Bengali", "Bosnian", "Bulgarian", "Burmese", "Catalan", "Cebuano",
                      "Chichewa", "Chinese (Simplified)", "Chinese (Traditional)", "Corsican", "Croatian", "Czech",
                      "Danish", "Dutch", "English", "Esperanto", "Estonian", "Filipino", "Finnish", "French",
                      "Frisian", "Galician", "Georgian", "German", "Greek", "Gujarati", "Haitian Creole", "Hausa",
                      "Hawaiian", "Hebrew", "Hindi", "Hmong", "Hungarian", "Icelandic", "Igbo", "Indonesian",
                      "Irish", "Italian", "Japanese", "Javanese", "Kannada", "Kazakh", "Khmer", "Kinyarwanda",
                      "Korean", "Kurdish (Kurmanji)", "Kyrgyz", "Lao", "Latin", "Latvian", "Lithuanian",
                      "Luxembourgish", "Macedonian", "Malagasy", "Malay", "Malayalam", "Maltese", "Maori",
                      "Marathi", "Mongolian", "Nepali", "Norwegian", "Odia (Oriya)", "Pashto", "Persian", "Polish",
                      "Portuguese", "Punjabi", "Romanian", "Russian", "Samoan", "Scots Gaelic", "Serbian",
                      "Sesotho", "Shona", "Sindhi", "Sinhala", "Slovak", "Slovenian", "Somali", "Spanish", "Sundanese",
                      "Swahili", "Swedish", "Tajik", "Tamil", "Tatar", "Telugu", "Thai", "Turkish", "Turkmen",
                      "Ukrainian", "Urdu", "Uyghur", "Uzbek", "Vietnamese", "Welsh", "Xhosa", "Yiddish", "Yoruba",
                      "Zulu" ]
    return render_template('student-profile-setting.html',
                           student=student,
                           student_id=student_id,
                           all_subjects=all_subjects,
                           student_subject_ids=student_subject_ids,
                           all_languages=all_languages)

@app.route('/api/student/update', methods=['POST'])
def update_student_profile():
    if 'student_id' not in session:
        return jsonify({"msg": "Not logged in"}), 401
    student_id = session['student_id']
    student = Student.query.get(student_id)
    if not student:
        return jsonify({"msg": "Student not found"}), 404

    student.name = request.form.get("name", student.name)
    student.email = request.form.get("email", student.email)
    student.about_me = request.form.get("about_me", student.about_me)
    student.preferred_language = request.form.get("preferred_language", student.preferred_language)
    student.preferred_learning_style = request.form.get("preferred_learning_style", student.preferred_learning_style)
    if "budget" in request.form:
        student.budget = request.form.get("budget")

    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"student_{student_id}_" + file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            student.profile_pic_url = f"/static/uploads/{filename}"

    subjects_list = request.form.getlist("subjects")
    if subjects_list:
        StudentSubject.query.filter_by(student_id=student_id).delete()
        for subject_id in subjects_list:
            new_assoc = StudentSubject(student_id=student_id, subject_id=subject_id)
            db.session.add(new_assoc)
    try:
        db.session.commit()
        return jsonify({"msg": "Profile updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating student profile: {e}")
        return jsonify({"msg": "Failed to update profile", "error": str(e)}), 500

# ---------- Tutor Routes ----------

@app.template_filter('from_json')
def from_json_filter(s):
    try:
        return json.loads(s)
    except Exception:
        return []

@app.route('/tutor/settings')
def tutor_profile_settings():
    if 'tutor_id' not in session:
        return redirect(url_for('login'))
    tutor_id = session['tutor_id']
    tutor = Tutor.query.get(tutor_id)
    if not tutor:
        abort(404)
    
    remove_expired_available_slots()
    all_subjects = Subject.query.order_by(Subject.subject_name).all()
    all_languages = [ "Afrikaans", "Albanian", "Amharic", "Arabic", "Armenian", "Azerbaijani", "Basque", "Belarusian", "Bengali",
                      "Bosnian", "Bulgarian", "Burmese", "Catalan", "Cebuano", "Chichewa", "Chinese (Simplified)", "Chinese (Traditional)",
                      "Corsican", "Croatian", "Czech", "Danish", "Dutch", "English", "Esperanto", "Estonian", "Filipino", "Finnish",
                      "French", "Frisian", "Galician", "Georgian", "German", "Greek", "Gujarati", "Haitian Creole", "Hausa",
                      "Hawaiian", "Hebrew", "Hindi", "Hmong", "Hungarian", "Icelandic", "Igbo", "Indonesian", "Irish", "Italian",
                      "Japanese", "Javanese", "Kannada", "Kazakh", "Khmer", "Kinyarwanda", "Korean", "Kurdish (Kurmanji)", "Kyrgyz",
                      "Lao", "Latin", "Latvian", "Lithuanian", "Luxembourgish", "Macedonian", "Malagasy", "Malay", "Malayalam",
                      "Maltese", "Maori", "Marathi", "Mongolian", "Nepali", "Norwegian", "Odia (Oriya)", "Pashto", "Persian", "Polish",
                      "Portuguese", "Punjabi", "Romanian", "Russian", "Samoan", "Scots Gaelic", "Serbian", "Sesotho", "Shona",
                      "Sindhi", "Sinhala", "Slovak", "Slovenian", "Somali", "Spanish", "Sundanese", "Swahili", "Swedish", "Tajik",
                      "Tamil", "Tatar", "Telugu", "Thai", "Turkish", "Turkmen", "Ukrainian", "Urdu", "Uyghur", "Uzbek", "Vietnamese",
                      "Welsh", "Xhosa", "Yiddish", "Yoruba", "Zulu" ]
    tutor_subjects = TutorSubject.query.filter_by(tutor_id=tutor_id).all()
    tutor_subject_ids = [ts.subject_id for ts in tutor_subjects]
    return render_template(
        'tutor-profile-setting.html',
        tutor=tutor,
        tutor_id=tutor_id,
        all_subjects=all_subjects,
        tutor_subject_ids=tutor_subject_ids,
        all_languages=all_languages
    )

@app.route('/api/tutor/update', methods=['POST'])
def update_tutor_profile():
    if 'tutor_id' not in session:
        return jsonify({"msg": "Not logged in"}), 401
    tutor_id = session['tutor_id']
    tutor = Tutor.query.get(tutor_id)

    if not tutor:
        return jsonify({"msg": "Tutor not found"}), 404
    
    tutor.name = request.form.get('name', tutor.name)
    tutor.email = request.form.get('email', tutor.email)
    tutor.preferred_language = request.form.get("preferred_language", tutor.preferred_language)
    tutor.teaching_style = request.form.get("teaching_style", tutor.teaching_style)
    tutor.expertise = request.form.get("expertise", tutor.expertise)

    degrees = request.form.getlist("degree_type[]") 
    fields = request.form.getlist("degree_field[]") 
    text_qualifications = request.form.get("qualifications_text", "").strip() 
    existing_qualifications = tutor.qualifications 
    try:
        qualifications_list = json.loads(existing_qualifications) if existing_qualifications else []
        if not isinstance(qualifications_list, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        if existing_qualifications:
            qualifications_list = []
            for line in existing_qualifications.split("\n"):  
                match = re.match(r"^(BSc|MSc|PhD)\s+(.+)$", line.strip(), re.IGNORECASE)
                if match:
                    degree_type, degree_field = match.groups()
                    qualifications_list.append({"degree_type": degree_type, "degree_field": degree_field})
        else:
            qualifications_list = []
    new_qualifications = []
    if degrees and fields and len(degrees) == len(fields):
        for i in range(len(degrees)):
            new_entry = {"degree_type": degrees[i], "degree_field": fields[i]}
            if new_entry not in qualifications_list: 
                new_qualifications.append(new_entry)
    if text_qualifications:
        for line in text_qualifications.split("\n"):  
            match = re.match(r"^(BSc|MSc|PhD)\s+(.+)$", line.strip(), re.IGNORECASE)
            if match:
                degree_type, degree_field = match.groups()
                text_entry = {"degree_type": degree_type, "degree_field": degree_field}
                if text_entry not in qualifications_list:
                    new_qualifications.append(text_entry)
    qualifications_list.extend(new_qualifications) 
    tutor.qualifications = json.dumps(qualifications_list) 
    subject_ids = request.form.getlist("subjects[]")
    remove_expired_available_slots()
    if subject_ids:
        TutorSubject.query.filter_by(tutor_id=tutor_id).delete()
        for sid in subject_ids:
            new_subj = TutorSubject(tutor_id=tutor_id, subject_id=sid)
            db.session.add(new_subj)
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"tutor_{tutor_id}_" + file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            tutor.profile_pic_url = f"/static/uploads/{filename}"
    available_dates = request.form.getlist('available_date[]')
    start_times = request.form.getlist('start_time[]')
    end_times = request.form.getlist('end_time[]')
    if available_dates and start_times and end_times:
        TutorAvailableSlot.query.filter_by(tutor_id=tutor_id).delete()
        for date_str, start_str, end_str in zip(available_dates, start_times, end_times):
            try:
                available_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_time = datetime.strptime(start_str, '%H:%M').time()
                end_time = datetime.strptime(end_str, '%H:%M').time()
                new_slot = TutorAvailableSlot(
                    tutor_id=tutor_id,
                    available_date=available_date,
                    start_time=start_time,
                    end_time=end_time
                )
                db.session.add(new_slot)
            except Exception:
                continue
    try:
        db.session.commit()
        return jsonify({"msg": "Profile updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Failed to update profile", "error": str(e)}), 500

@app.route('/dashboard/tutor')
def dashboard_tutor():
    if 'tutor_id' not in session:
        return redirect(url_for('login'))
    update_past_sessions()
    tutor_id = session['tutor_id']
    tutor = Tutor.query.get(tutor_id)
    if not tutor:
        abort(404)
    db.session.refresh(tutor)
    current_time = get_current_time()
    upcoming_sessions = Session.query.filter(
        Session.tutor_id == tutor_id,
        Session.session_status == 'Scheduled',
        Session.scheduled_time > current_time
    ).order_by(Session.scheduled_time).all()
    for s in upcoming_sessions:
        s.end_time = s.scheduled_time + timedelta(hours=1)
    session_feedbacks = (
        db.session.query(SessionFeedback, Session, Student)
        .join(Session, Session.session_id == SessionFeedback.session_id)
        .join(Student, Student.student_id == Session.student_id)
        .filter(Session.tutor_id == tutor_id)
        .order_by(SessionFeedback.feedback_id.desc())
        .all()
    )
    session_reviews = []
    for fb, sess, stud in session_feedbacks:
        review_dict = {
            "review_id": fb.feedback_id,
            "student_profile_pic": stud.profile_pic_url or '/static/images/default-profile-picture.png',
            "student_name": stud.name,
            "comment": fb.student_feedback or "No review available.",
            "rating": fb.star_rating,
            "sentiment": fb.feedback_sentiment or "N/A",
            "date_posted": sess.scheduled_time
        }
        session_reviews.append(review_dict)
    tutor_reviews_query = TutorReview.query.filter_by(tutor_id=tutor_id).order_by(TutorReview.review_id.desc()).all()
    tutor_reviews = []
    for tr in tutor_reviews_query:
        review_dict = {
            "review_id": tr.review_id,
            "student_profile_pic": '/static/images/default-profile-picture.png',
            "student_name": tr.student_name,
            "comment": tr.comment or "No review available.",
            "rating": tr.rating,
            "sentiment": "N/A",
            "date_posted": None
        }
        tutor_reviews.append(review_dict)
    reviews = session_reviews + tutor_reviews
    reviews = sorted(reviews, key=lambda r: r["review_id"], reverse=True)
    review_count = tutor.review_count
    star_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for review in reviews:
        try:
            rating = int(round(float(review["rating"])))
            if rating in star_counts:
                star_counts[rating] += 1
        except Exception:
            continue
    if review_count > 0:
        star_percentages = {star: round((count / review_count) * 100) for star, count in star_counts.items()}
        average_star_rating = round(sum(float(review["rating"]) for review in reviews) / review_count, 2)
    else:
        star_percentages = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        average_star_rating = "N/A"
    return render_template(
        'dashboard-tutor.html',
        tutor=tutor,
        reviews=reviews,
        tutor_id=tutor_id,
        upcoming_sessions=upcoming_sessions,
        star_percentages=star_percentages,
        review_count=review_count,
        average_star_rating=average_star_rating
    )

@app.route('/landing-page')
def landing_page():
    return render_template('landing-page.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    required_fields = ['name', 'email', 'password', 'userType']
    for field in required_fields:
        if not data.get(field):
            return jsonify({"msg": f"Missing required field: {field}"}), 400
    name = data.get('name').strip()
    email = data.get('email').strip()
    password = data.get('password')
    user_type = data.get('userType').strip().lower()
    if "@" not in email or "." not in email:
        return jsonify({"msg": "Invalid email address."}), 400
    if user_type not in ['tutor', 'student']:
        return jsonify({"msg": "Invalid user type."}), 400
    if user_type == 'tutor':
        if Tutor.query.filter_by(email=email).first():
            return jsonify({"msg": "Tutor with that email already exists."}), 400
    else:
        if Student.query.filter_by(email=email).first():
            return jsonify({"msg": "Student with that email already exists."}), 400
    hashed_password = generate_password_hash(password)
    try:
        if user_type == 'tutor':
            new_user = Tutor(
                name=name,
                email=email,
                password=hashed_password,
                preferred_language="English",
                teaching_style="Read/Write",
                completed_sessions=0
            )
        else:
            new_user = Student(
                name=name,
                email=email,
                password=hashed_password,
                preferred_learning_style="Read/Write",
                preferred_language="English"
            )
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error during signup: {e}")
        return jsonify({"msg": "Signup failed", "error": str(e)}), 500
    if user_type == 'tutor':
        return jsonify({"msg": "Tutor signup successful", "tutor_id": new_user.tutor_id}), 201
    else:
        return jsonify({"msg": "Student signup successful", "student_id": new_user.student_id}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"msg": "No input data provided"}), 400
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({"msg": "Missing email or password"}), 400
    tutor = Tutor.query.filter_by(email=email).first()
    student = Student.query.filter_by(email=email).first()
    if tutor and check_password_hash(tutor.password, password):
        session.clear()
        session['tutor_id'] = tutor.tutor_id
        return jsonify({
            "msg": "Login successful",
            "role": "tutor",
            "tutor_id": tutor.tutor_id,
            "firstLogin": tutor.completed_sessions == 0
        }), 200
    elif student and check_password_hash(student.password, password):
        session.clear()
        session['student_id'] = student.student_id
        return jsonify({
            "msg": "Login successful",
            "role": "student",
            "student_id": student.student_id,
            "firstLogin": len(student.sessions) == 0
        }), 200
    else:
        return jsonify({"msg": "Invalid credentials"}), 401

@app.route('/signup-page')
def signup_page():
    return render_template('sign-up-page.html')

@app.route('/signup-student-page')
def signup_student_page():
    return render_template('signup-student-page.html')

@app.route('/login-page')
def login_page():
    return render_template('login-page.html')

# ---------- AI Feedback System Routes ----------

@app.route("/analyze-feedback", methods=["POST"])
def analyze_feedback():
    data = request.form
    session_id = data.get("session_id")
    tutor_id = data.get("tutor_id")
    student_feedback = data.get("student_feedback")
    star_rating = data.get("star_rating")
    if not session_id or not tutor_id or not student_feedback or star_rating is None:
        return jsonify({"error": "Missing required fields"}), 400

    sentiment_result = analyze_sentiment(student_feedback)
    sentiment_label = sentiment_result.get("label", "")
    sentiment_label = sentiment_label.capitalize() 
    if sentiment_label not in ["Positive", "Neutral", "Negative"]:
        sentiment_label = "Neutral"

    issues = extract_issues(student_feedback)
    improvement_tip = generate_improvement_tip(issues)
    issues_str = ", ".join([issue["issue"] for issue in issues])
    new_feedback = SessionFeedback(
        session_id=session_id,
        student_feedback=student_feedback,
        star_rating=star_rating,
        feedback_sentiment=sentiment_label,
        feedback_issues=issues_str,
        improvement_tip=improvement_tip
    )
    try:
        db.session.add(new_feedback)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to add feedback: {str(e)}"}), 500

    try:
        avg_rating = db.session.query(db.func.avg(SessionFeedback.star_rating))\
                    .join(Session, Session.session_id == SessionFeedback.session_id)\
                    .filter(Session.tutor_id == tutor_id).scalar()
        tutor = Tutor.query.get(tutor_id)
        tutor.average_star_rating = avg_rating
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating tutor average rating: {e}")
    return jsonify({
        "sentiment": sentiment_label,
        "issues": issues,
        "improvement_tip": improvement_tip
    }), 200

@app.route('/call_feedback')
def call_feedback():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    session_id = request.args.get('session_id')
    if not session_id:
        abort(400, description="Missing session id")
    tutoring_session = Session.query.get(session_id)
    if not tutoring_session:
        abort(404, description="Session not found")
    student = Student.query.get(session['student_id'])
    return render_template("call-feedback.html", session=tutoring_session, student=student)

def get_rating(review):
    return review.get("star_rating", review.get("rating"))

@app.route('/session_feedback')
def session_feedback():
    if 'tutor_id' not in session:
        return redirect(url_for('login'))
    tutor_id = session['tutor_id']
    tutor = Tutor.query.get(tutor_id)
    if not tutor:
        abort(404)
    session_feedbacks = (
        db.session.query(SessionFeedback, Session, Student)
        .join(Session, Session.session_id == SessionFeedback.session_id)
        .join(Student, Student.student_id == Session.student_id)
        .filter(Session.tutor_id == tutor_id)
        .order_by(SessionFeedback.feedback_id.desc())
        .all()
    )
    session_reviews = []
    for fb, sess, stud in session_feedbacks:
        review_dict = {
            "review_id": fb.feedback_id,
            "profile_pic_url": stud.profile_pic_url or '/static/images/default-profile-picture.png',
            "student_name": stud.name,
            "date_posted": sess.scheduled_time,
            "sentiment": fb.feedback_sentiment or "N/A",
            "comment": fb.student_feedback or "No review available.",
            "star_rating": fb.star_rating,
            "improvement_tip": fb.improvement_tip or "No improvement tip available"
        }
        session_reviews.append(review_dict)
    tutor_reviews_query = TutorReview.query.filter_by(tutor_id=tutor_id).order_by(TutorReview.review_id.desc()).all()
    tutor_reviews = []
    for tr in tutor_reviews_query:
        review_dict = {
            "review_id": tr.review_id,
            "profile_pic_url": '/static/images/default-profile-picture.png',
            "student_name": tr.student_name,
            "comment": tr.comment or "No review available.",
            "star_rating": tr.rating, 
            "sentiment": "N/A",
            "date_posted": None,
            "improvement_tip": "No improvement tip available"
        }
        tutor_reviews.append(review_dict)
    
    all_reviews = session_reviews + tutor_reviews
    all_reviews = sorted(all_reviews, key=lambda r: r["review_id"], reverse=True)
    review_count = tutor.review_count
    star_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for review in all_reviews:
        try:
            rating = int(round(float(review["star_rating"])))
            if rating in star_counts:
                star_counts[rating] += 1
        except Exception:
            continue
    if review_count > 0:
        star_percentages = {star: round((count / review_count) * 100) for star, count in star_counts.items()}
        average_star_rating = round(sum(float(review["star_rating"]) for review in all_reviews) / review_count, 2)
    else:
        star_percentages = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        average_star_rating = "N/A"
    if review_count > 0:
        most_recent = all_reviews[0]
        recent_review = {
            "profile_pic_url": most_recent.get("profile_pic_url", "/static/images/default-profile-picture.png"),
            "student_name": most_recent.get("student_name", "N/A"),
            "date_posted": most_recent.get("date_posted").strftime("%d %b %Y") if most_recent.get("date_posted") else "N/A",
            "sentiment": most_recent.get("sentiment", "N/A"),
            "comment": most_recent.get("comment", "No review available."),
            "star_rating": most_recent.get("star_rating", 0)
        }
        improvement_tip = most_recent.get("improvement_tip", "No improvement tip available")
    else:
        recent_review = None
        improvement_tip = "No improvement tip available"
    current_time = get_current_time()
    upcoming_sessions = Session.query.filter(
        Session.tutor_id == tutor_id,
        Session.session_status == 'Scheduled',
        Session.scheduled_time > current_time
    ).order_by(Session.scheduled_time).all()
    for s in upcoming_sessions:
        s.end_time = s.scheduled_time + timedelta(hours=1)
    return render_template(
        'review-feedback.html',
        tutor=tutor,
        recent_review=recent_review,
        improvement_tip=improvement_tip,
        star_percentages=star_percentages,
        review_count=review_count,
        average_star_rating=average_star_rating,
        upcoming_sessions=upcoming_sessions
    )

@app.route('/api/sentiment_breakdown', methods=['GET'])
def sentiment_breakdown():
    if 'tutor_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    tutor_id = session['tutor_id']
    session_feedbacks = (
        db.session.query(SessionFeedback.feedback_sentiment)
        .join(Session, Session.session_id == SessionFeedback.session_id)
        .filter(Session.tutor_id == tutor_id)
        .all()
    )
    tutor_reviews = TutorReview.query.filter(TutorReview.tutor_id == tutor_id).all()
    counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
    for (sentiment,) in session_feedbacks:
        sentiment = (sentiment or "Neutral").capitalize()
        if sentiment not in ["Positive", "Neutral", "Negative"]:
            sentiment = "Neutral"
        counts[sentiment] += 1
    for review in tutor_reviews:
        sentiment = (review.sentiment or "Neutral").capitalize()
        if sentiment not in ["Positive", "Neutral", "Negative"]:
            sentiment = "Neutral"
        counts[sentiment] += 1
    return jsonify([
        {"value": counts["Positive"], "name": "Positive"},
        {"value": counts["Neutral"], "name": "Neutral"},
        {"value": counts["Negative"], "name": "Negative"}
    ])

@app.route('/tutor/feedback')
def tutor_feedback():
    if 'tutor_id' not in session:
        return redirect(url_for('login'))
    tutor_id = session['tutor_id']
    tutor = Tutor.query.get(tutor_id)
    if not tutor:
        abort(404)
    session_feedback_entries = db.session.query(
        SessionFeedback.feedback_id,
        Student.name.label("student_name"),
        Student.profile_pic_url.label("reviewer_logo"),
        SessionFeedback.student_feedback.label("comment"),
        SessionFeedback.star_rating.label("rating"),
        SessionFeedback.feedback_sentiment.label("sentiment")
    ).join(Session, Session.session_id == SessionFeedback.session_id
    ).join(Student, Student.student_id == Session.student_id
    ).filter(Session.tutor_id == tutor_id
    ).order_by(SessionFeedback.feedback_id.desc()).all()
    session_reviews = []
    for entry in session_feedback_entries:
        session_reviews.append({
            "review_id": entry.feedback_id,
            "student_name": entry.student_name,
            "reviewer_logo": entry.reviewer_logo or '/static/images/default-profile-picture.png',
            "comment": entry.comment or "No review available.",
            "rating": entry.rating,
            "sentiment": entry.sentiment or "N/A"
        })
    tutor_reviews_entries = db.session.query(
        TutorReview.review_id,
        TutorReview.student_name,
        db.literal('/static/images/default-profile-picture.png').label("reviewer_logo"),
        TutorReview.comment.label("comment"),
        TutorReview.rating.label("rating"),
        db.literal("N/A").label("sentiment")
    ).filter(TutorReview.tutor_id == tutor_id
    ).order_by(TutorReview.review_id.desc()).all()
    tutor_reviews = []
    for entry in tutor_reviews_entries:
        tutor_reviews.append({
            "review_id": entry.review_id,
            "student_name": entry.student_name,
            "reviewer_logo": entry.reviewer_logo,
            "comment": entry.comment or "No review available.",
            "rating": entry.rating,
            "sentiment": entry.sentiment
        })
    
    reviews = session_reviews + tutor_reviews
    reviews = sorted(reviews, key=lambda r: r["review_id"], reverse=True)
    return render_template('feedback.html', tutor=tutor, tutor_id=tutor_id, reviews=reviews)

def load_weights():
    with open("/Users/fatima/Downloads/tutoreal/weights.json", "r") as f:
        return json.load(f)

@app.route('/find-a-tutor')
def find_a_tutor():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    student_id = session['student_id']
    student = db.session.get(Student, student_id)
    query = request.args.get('q', '').strip()
    all_languages = [ "Afrikaans", "Albanian", "Amharic", "Arabic", "Armenian", "Azerbaijani", "Basque", "Belarusian",
                      "Bengali", "Bosnian", "Bulgarian", "Burmese", "Catalan", "Cebuano", "Chichewa", "Chinese (Simplified)",
                      "Chinese (Traditional)", "Corsican", "Croatian", "Czech", "Danish", "Dutch", "English", "Esperanto",
                      "Estonian", "Filipino", "Finnish", "French", "Frisian", "Galician", "Georgian", "German", "Greek",
                      "Gujarati", "Haitian Creole", "Hausa", "Hawaiian", "Hebrew", "Hindi", "Hmong", "Hungarian",
                      "Icelandic", "Igbo", "Indonesian", "Irish", "Italian", "Japanese", "Javanese", "Kannada", "Kazakh",
                      "Khmer", "Kinyarwanda", "Korean", "Kurdish (Kurmanji)", "Kyrgyz", "Lao", "Latin", "Latvian",
                      "Lithuanian", "Luxembourgish", "Macedonian", "Malagasy", "Malay", "Malayalam", "Maltese", "Maori",
                      "Marathi", "Mongolian", "Nepali", "Norwegian", "Odia (Oriya)", "Pashto", "Persian", "Polish",
                      "Portuguese", "Punjabi", "Romanian", "Russian", "Samoan", "Scots Gaelic", "Serbian", "Sesotho",
                      "Shona", "Sindhi", "Sinhala", "Slovak", "Slovenian", "Somali", "Spanish", "Sundanese", "Swahili",
                      "Swedish", "Tajik", "Tamil", "Tatar", "Telugu", "Thai", "Turkish", "Turkmen", "Ukrainian",
                      "Urdu", "Uyghur", "Uzbek", "Vietnamese", "Welsh", "Xhosa", "Yiddish", "Yoruba", "Zulu" ]
    if query:
        tutors = (db.session.query(Tutor)
                  .outerjoin(TutorSubject)
                  .outerjoin(Subject)
                  .filter(
                      (Tutor.name.ilike(f'%{query}%')) |
                      (Subject.subject_name.ilike(f'%{query}%')) |
                      (Tutor.expertise.ilike(f'%{query}%'))
                  )
                  .distinct()
                  .all()
                 )
    else:
        student_subjects = StudentSubject.query.filter_by(student_id=student_id).all()
        subject_ids = [ss.subject_id for ss in student_subjects]
        tutors = (Tutor.query
                  .join(TutorSubject)
                  .filter(TutorSubject.subject_id.in_(subject_ids))
                  .all())
    weights = load_weights()
    total_weight = sum(weights.values())
    current_date = get_current_time().date()
    for tutor in tutors:
        available = False
        if tutor.available_slots:
            available = any(slot.available_date >= current_date for slot in tutor.available_slots)
        tutor_data = {
            'tutor_id': tutor.tutor_id,
            'average_star_rating': float(tutor.average_star_rating or 0),
            'price': float(tutor.hourly_rate or 0),
            'preferred_language': tutor.preferred_language,
            'teaching_style': tutor.teaching_style,
        }
        student_budget = float(student.budget or 0)
        score = calculate_dynamic_score(
            tutor_data,
            available,
            student_budget,
            student.preferred_language,
            student.preferred_learning_style,
            weights
        )
        tutor.match_percentage = round((score / total_weight) * 100) if total_weight > 0 else 0
        print(f"Tutor {tutor.name} match percentage: {tutor.match_percentage}")
    return render_template('find-a-tutor.html', student=student, tutors=tutors, student_id=student_id, all_languages=all_languages)

@app.route('/match-tutor', methods=['GET'])
def match_tutor_page():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    student_id = session['student_id']
    student = db.session.get(Student, student_id)
    subject = request.args.get('subject')
    desired_date = request.args.get('desired_date')
    budget = request.args.get('budget', type=float)
    language = request.args.get('language')
    learning_style = request.args.get('learning_style')
    if not all([subject, desired_date, budget, language, learning_style]):
        abort(400, description="Missing one or more required fields: subject, desired_date, budget, language, learning_style.")
    try:
        desired_date_obj = datetime.strptime(desired_date, '%d-%m-%Y').date()
    except ValueError:
        abort(400, description="Invalid date format. Expected DD-MM-YYYY.")
    all_languages = [ "Afrikaans", "Albanian", "Amharic", "Arabic", "Armenian", "Azerbaijani", "Basque", "Belarusian",
                      "Bengali", "Bosnian", "Bulgarian", "Burmese", "Catalan", "Cebuano", "Chichewa", "Chinese (Simplified)",
                      "Chinese (Traditional)", "Corsican", "Croatian", "Czech", "Danish", "Dutch", "English", "Esperanto",
                      "Estonian", "Filipino", "Finnish", "French", "Frisian", "Galician", "Georgian", "German", "Greek",
                      "Gujarati", "Haitian Creole", "Hausa", "Hawaiian", "Hebrew", "Hindi", "Hmong", "Hungarian",
                      "Icelandic", "Igbo", "Indonesian", "Irish", "Italian", "Japanese", "Javanese", "Kannada", "Kazakh",
                      "Khmer", "Kinyarwanda", "Korean", "Kurdish (Kurmanji)", "Kyrgyz", "Lao", "Latin", "Latvian",
                      "Lithuanian", "Luxembourgish", "Macedonian", "Malagasy", "Malay", "Malayalam", "Maltese", "Maori",
                      "Marathi", "Mongolian", "Nepali", "Norwegian", "Odia (Oriya)", "Pashto", "Persian", "Polish",
                      "Portuguese", "Punjabi", "Romanian", "Russian", "Samoan", "Scots Gaelic", "Serbian", "Sesotho",
                      "Shona", "Sindhi", "Sinhala", "Slovak", "Slovenian", "Somali", "Spanish", "Sundanese", "Swahili",
                      "Swedish", "Tajik", "Tamil", "Tatar", "Telugu", "Thai", "Turkish", "Turkmen", "Ukrainian",
                      "Urdu", "Uyghur", "Uzbek", "Vietnamese", "Welsh", "Xhosa", "Yiddish", "Yoruba", "Zulu" ]
    engine = db.get_engine()
    conn = engine.raw_connection()
    cursor = conn.cursor()
    weights = load_weights()
    top_tutor, learning_path = match_tutor(subject, desired_date, budget, language, learning_style, weights, cursor)
    cursor.close()
    conn.close()
    if top_tutor is None:
        abort(404, description="No matching tutor found.")
    score = top_tutor.get('score', 0)
    return render_template(
        'match-tutor.html',
        subject=subject,
        student=student,
        student_id=student_id,
        matched_tutor=top_tutor,
        score=score,
        learning_path=learning_path,
        all_languages=all_languages
    )

@app.route('/tutor')
def tutor_profile():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    if 'view_tutor_id' not in session:
        abort(400, description="Tutor not selected.")
    tutor_id = session['view_tutor_id']
    tutor = Tutor.query.options(
        db.joinedload(Tutor.subjects),
        db.joinedload(Tutor.tutor_subjects_assoc),
        db.joinedload(Tutor.reviews),
        db.joinedload(Tutor.available_slots)
    ).get(tutor_id)
    if not tutor:
        abort(404)
    tutor_reviews = TutorReview.query.filter_by(tutor_id=tutor_id).order_by(TutorReview.review_id.desc()).all()
    session_feedbacks = (
        db.session.query(SessionFeedback, Session, Student)
        .join(Session, Session.session_id == SessionFeedback.session_id)
        .join(Student, Student.student_id == Session.student_id)
        .filter(Session.tutor_id == tutor_id)
        .order_by(SessionFeedback.feedback_id.desc())
        .all()
    )
    reviews = []
    for review in tutor_reviews:
        reviews.append({
            "review_id": review.review_id,
            "student_name": review.student_name,
            "profile_pic_url": "/static/images/default-profile-picture.png",
            "comment": review.comment or "No review available.",
            "rating": review.rating,
            "sentiment": "N/A",
            "date_posted": None
        })
    for feedback, tutoring_session, student in session_feedbacks:
        reviews.append({
            "review_id": feedback.feedback_id,
            "student_name": student.name,
            "profile_pic_url": student.profile_pic_url or "/static/images/default-profile-picture.png",
            "comment": feedback.student_feedback or "No review available.",
            "rating": feedback.star_rating,
            "sentiment": feedback.feedback_sentiment or "N/A",
            "date_posted": tutoring_session.scheduled_time.strftime('%d %b %Y') if tutoring_session.scheduled_time else "N/A"
        })
    reviews_sorted = sorted(reviews, key=lambda r: r["review_id"], reverse=True)
    tutor.last_two_reviews = reviews_sorted[:2]
    student_id = session['student_id']
    student = db.session.get(Student, student_id)
    return render_template('tutor-profile-page.html', tutor=tutor, student=student, student_id=student_id, reviews=reviews_sorted)

@app.route('/set_view_tutor/<int:tutor_id>')
def set_view_tutor(tutor_id):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    session['view_tutor_id'] = tutor_id
    return redirect(url_for('tutor_profile'))

# ---------- API Routes ----------

@app.route("/sessions/student", methods=["GET"])
def get_sessions_for_student():
    if 'student_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    student_id = session['student_id']
    sessions = Session.query.filter_by(student_id=student_id).order_by(Session.scheduled_time).all()
    rows = []
    for s in sessions:
        rows.append({
            "session_id": s.session_id,
            "student_id": s.student_id,
            "tutor_id": s.tutor_id,
            "tutor_name": s.tutor.name,
            "subject_id": s.subject_id,
            "subject_name": s.subject.subject_name,
            "scheduled_time": s.scheduled_time.isoformat(),
            "session_status": s.session_status
        })
    return jsonify(rows), 200

@app.route("/sessions/tutor", methods=["GET"])
def get_sessions_for_tutor():
    if 'tutor_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    tutor_id = session['tutor_id']
    sessions = Session.query.filter_by(tutor_id=tutor_id).order_by(Session.scheduled_time).all()
    rows = []
    for s in sessions:
        rows.append({
            "session_id": s.session_id,
            "student_id": s.student_id,
            "student_name": s.student.name,
            "tutor_id": s.tutor_id,
            "subject_id": s.subject_id,
            "subject_name": s.subject.subject_name,
            "scheduled_time": s.scheduled_time.isoformat(),
            "session_status": s.session_status
        })
    return jsonify(rows), 200

@app.route('/api/booking-page/<int:tutor_id>', methods=['GET'])
def api_booking_page(tutor_id):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    tutor = Tutor.query.get(tutor_id)
    if not tutor:
        abort(404)
    student_id = session['student_id']
    student = db.session.get(Student, student_id)
    subjects = tutor.subjects    
    tutor_subjects = tutor.tutor_subjects_assoc
    remove_expired_available_slots()
    available_slots = TutorAvailableSlot.query.filter_by(tutor_id=tutor_id).all()
    available_slots_serialized = [
        {
            "slot_id": slot.slot_id,
            "available_date": slot.available_date.isoformat(),
            "start_time": slot.start_time.strftime("%H:%M:%S"),
            "end_time": slot.end_time.strftime("%H:%M:%S")
        }
        for slot in available_slots
    ]
    return render_template(
        'booking-page.html',
        tutor=tutor,
        student=student,
        student_id=student_id,
        tutor_subjects=tutor_subjects,
        available_slots=available_slots_serialized,
        total_price=0,
        tax=0
    )

@app.route('/booking-confirmation/<int:session_id>')
def booking_confirmation(session_id):
    session_obj = Session.query.get(session_id)
    if not session_obj:
        abort(404)
    student_id = session['student_id']
    student = db.session.get(Student, student_id)
    tutor_id = session_obj.tutor_id
    tutor = db.session.get(Tutor, tutor_id)
    return render_template('book-confirmation.html', session=session_obj, student_id=student_id, student=student, tutor_id=tutor_id, tutor=tutor)

@app.route('/book_session', methods=['POST'])
def book_session():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    student_id = session['student_id']
    tutor_id = request.form.get('tutor_id')
    subject_id = request.form.get('subject_id')
    selected_date = request.form.get('selected_date')
    selected_time = request.form.get('selected_time')
    scheduled_slot = selected_date + " " + selected_time
    if not all([tutor_id, subject_id, scheduled_slot]):
        return render_template('booking-error.html', message="Missing required fields."), 400
    try:
        tutor_id = int(tutor_id)
        subject_id = int(subject_id)
    except ValueError:
        return render_template('booking-error.html', message="Invalid input types."), 400
    try:
        date_str, time_str = scheduled_slot.split()
        slot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if len(time_str.split(':')) == 3:
            slot_time = datetime.strptime(time_str, "%H:%M:%S").time()
        else:
            slot_time = datetime.strptime(time_str, "%H:%M").time()
    except Exception:
        return render_template('booking-error.html', message="Invalid scheduled slot format."), 400

    available_slot = TutorAvailableSlot.query.filter_by(
        tutor_id=tutor_id, available_date=slot_date, start_time=slot_time
    ).first()
    if not available_slot:
        return render_template('booking-error.html', message="Selected time slot is not available."), 400

    tutor_subject = TutorSubject.query.filter_by(tutor_id=tutor_id, subject_id=subject_id).first()
    if not tutor_subject:
        return render_template('booking-error.html', message="Tutor does not offer this subject."), 400

    scheduled_datetime = datetime.combine(slot_date, slot_time)
    new_session = Session(
        student_id=student_id,
        tutor_id=tutor_id,
        subject_id=subject_id,
        scheduled_time=scheduled_datetime,
        session_status='Scheduled'
    )
    try:
        db.session.add(new_session)
        tutor = Tutor.query.get(tutor_id)
        session_price = Decimal(str(tutor_subject.price))
        if tutor.earnings is None:
            tutor.earnings = session_price
        else:
            tutor.earnings = Decimal(str(tutor.earnings)) + session_price

        logging.info(f"Updated earnings for tutor {tutor_id}: {tutor.earnings}")

        db.session.delete(available_slot)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return render_template('booking-error.html', message="Booking failed. Please try again."), 500

    return redirect(url_for('booking_confirmation', session_id=new_session.session_id))

@app.route('/api/student_sessions', methods=["GET"])
def api_student_sessions():
    if 'student_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    student_id = session['student_id']
    sessions = Session.query.filter_by(student_id=student_id).order_by(Session.scheduled_time).all()
    sessions_data = []
    for s in sessions:
        sessions_data.append({
            "session_id": s.session_id,
            "tutor_name": s.tutor.name,
            "tutor_pic": s.tutor.profile_pic_url,
            "session_status": s.session_status,
            "subject_name": s.subject.subject_name,
            "scheduled_date": s.scheduled_time.strftime('%d %b %Y'),
            "scheduled_time": s.scheduled_time.strftime('%I:%M %p'),
            "description": s.description
        })
    return jsonify(sessions_data)

@app.route('/session/<int:session_id>/call')
def session_call(session_id):
    if 'student_id' not in session and 'tutor_id' not in session:
        return redirect(url_for('login'))
    tutoring_session = Session.query.get(session_id)
    if not tutoring_session:
        abort(404)
    if 'student_id' in session:
        if session['student_id'] != tutoring_session.student_id:
            abort(403)
        user_role = 'student'
        username = tutoring_session.student.name
    elif 'tutor_id' in session:
        if session['tutor_id'] != tutoring_session.tutor_id:
            abort(403)
        user_role = 'tutor'
        username = tutoring_session.tutor.name
    return render_template("call_page.html", session=tutoring_session, role=user_role, username=username)

@app.route('/api/student_reminders', methods=["GET"])
def api_student_reminders():
    if 'student_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    student_id = session['student_id']
    student = Student.query.get(student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404
    sessions = Session.query.filter_by(student_id=student_id).all()
    current_time = get_current_time()
    reminders = []
    for s in sessions:
        if s.session_status == 'Scheduled' and 0 <= (s.scheduled_time - current_time).total_seconds() <= 3600:
            minutes_left = int((s.scheduled_time - current_time).total_seconds() // 60)
            reminders.append({
                "message": f"Your '{s.subject.subject_name}' session starts in {minutes_left} minutes.",
                "tutor_name": s.tutor.name,
                "time": s.scheduled_time.strftime('%I:%M %p'),
                "date": s.scheduled_time.strftime('%b %d %Y')
            })
    return jsonify(reminders)

@app.route('/student-session-view')
def student_session_view():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    student_id = session['student_id']
    student = db.session.get(Student, student_id)
    return render_template('student_session.html', student=student, student_id=student_id)

@app.route('/tutor-session-view')
def tutor_session_view():
    if 'tutor_id' not in session:
        return redirect(url_for('login'))
    tutor_id = session['tutor_id']
    tutor = Tutor.query.get(tutor_id)
    return render_template('tutor_session.html', tutor_id=tutor_id, tutor=tutor)

@app.route('/booking-page/<int:tutor_id>', methods=['GET', 'POST'])
def booking_page(tutor_id):
    tutor = Tutor.query.get(tutor_id)
    if not tutor:
        abort(404)
    if request.method == 'POST':
        return jsonify({"status": "success", "message": f"Booking confirmed for tutor {tutor.name}!"})
    return render_template('booking-page.html', tutor=tutor)

@app.route('/api/upcoming_sessions_dates')
def upcoming_sessions_dates():
    student_id = request.args.get('student_id', type=int, default=1)
    upcoming_sessions = Session.query.filter(
        Session.student_id == student_id,
        Session.session_status == 'Scheduled',
        Session.scheduled_time > get_current_time()
    ).all()
    unique_dates = {s.scheduled_time.date().isoformat() for s in upcoming_sessions}
    return jsonify(list(unique_dates))

@app.route('/api/available_slots')
def available_slots():
    tutor_id = request.args.get('tutor_id', type=int)
    if tutor_id:
        slots = TutorAvailableSlot.query.filter_by(tutor_id=tutor_id).all()
    else:
        slots = []
    dates = [slot.available_date.isoformat() for slot in slots]
    return jsonify(dates)

@app.route('/api/get_user_booked_dates')
def get_user_booked_dates():
    if 'student_id' in session:
        student_id = session['student_id']
        upcoming_sessions = Session.query.filter(
            Session.student_id == student_id,
            Session.session_status == 'Scheduled',
            Session.scheduled_time > get_current_time()
        ).all()
    elif 'tutor_id' in session:
        tutor_id = session['tutor_id']
        upcoming_sessions = Session.query.filter(
            Session.tutor_id == tutor_id,
            Session.session_status == 'Scheduled',
            Session.scheduled_time > get_current_time()
        ).all()
    else:
        return jsonify({"error": "Unauthorized"}), 401
    unique_dates = {s.scheduled_time.date().isoformat() for s in upcoming_sessions}
    return jsonify(list(unique_dates))

@app.route('/join_session/<int:session_id>')
def join_session(session_id):
    return f"Joining session {session_id}"

# -----------------------------------------------------------------------------
# Socket.IO Events
# -----------------------------------------------------------------------------

@socketio.on("join")
def on_join(data):
    username = data.get("username")
    session_id = data.get("session_id")
    if username and session_id:
        join_room(session_id)
        logging.info(f"{username} joined session {session_id}")

@socketio.on("offer")
def on_offer(data):
    session_id = data.get("session_id")
    if session_id:
        emit("offer", data, room=session_id, include_self=False)

@socketio.on("answer")
def on_answer(data):
    session_id = data.get("session_id")
    if session_id:
        emit("answer", data, room=session_id, include_self=False)

@socketio.on("ice-candidate")
def on_ice_candidate(data):
    session_id = data.get("session_id")
    if session_id:
        emit("ice-candidate", data, room=session_id, include_self=False)

@socketio.on("sendMessage")
def on_send_message(data):
    session_id = data.get("session_id")
    if session_id:
        emit("receiveMessage", data, room=session_id)

@socketio.on("draw")
def on_draw(data):
    session_id = data.get("session_id")
    if session_id:
        emit("draw", data, room=session_id, include_self=False)

@socketio.on("leave")
def on_leave(data):
    session_id = data.get("session_id")
    username = data.get("username")
    if username and session_id:
        leave_room(session_id)
        logging.info(f"{username} left session {session_id}")

@socketio.on("disconnect")
def on_disconnect():
    logging.info(f"Client disconnected: SID {request.sid}")

if __name__ == '__main__':
    socketio.run(app, host="127.0.0.1", port=5001, debug=True)
