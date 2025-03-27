import datetime as dt
from config import db
from sqlalchemy import event, DDL
import json
from markupsafe import Markup
from datetime import timedelta, datetime
from nltk.sentiment.vader import SentimentIntensityAnalyzer

def get_current_time():
    return datetime.now()

analyzer = SentimentIntensityAnalyzer()

# ----------------------------
# TABLE MODELS
# ----------------------------

class Subject(db.Model):
    __tablename__ = 'Subjects'
    subject_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject_name = db.Column(db.String(255), nullable=False)
    prerequisite_id = db.Column(db.Integer, db.ForeignKey('Subjects.subject_id'), nullable=True)
    
    # Self-referential relationship for prerequisites
    prerequisite = db.relationship('Subject', remote_side=[subject_id], backref='dependent_subjects')
    # The sessions that use this subject will be accessible via the backref from Session (see below).

class Tutor(db.Model):
    __tablename__ = 'Tutors'
    tutor_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    profile_pic_url = db.Column(db.String(255), default='/static/images/default-profile-picture.png')
    preferred_language = db.Column(db.String(50), nullable=False)
    teaching_style = db.Column(db.Enum('Read/Write', 'Auditory', 'Visual'), nullable=False)
    average_star_rating = db.Column(db.Numeric(3,2))
    completed_sessions = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    earnings = db.Column(db.Numeric(10,2))
    qualifications = db.Column(db.Text)
    expertise = db.Column(db.Text)
    password = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text)

    # Many-to-many relationship with Subject through TutorSubjects
    subjects = db.relationship(
        'Subject', secondary='TutorSubjects',
        backref='tutors', overlaps="subject"
    )
    tutor_subjects_assoc = db.relationship(
        'TutorSubject',
        lazy=True, overlaps="subjects,tutors"
    )
    reviews = db.relationship(
        'TutorReview', backref='tutor',
        lazy=True, order_by="TutorReview.review_id.desc()"
    )
    available_slots = db.relationship(
        'TutorAvailableSlot', backref='tutor',
        lazy=True
    )
    sessions = db.relationship(
        'Session',
        backref=db.backref('tutor', cascade="all, delete-orphan", single_parent=True),
        lazy=True
    )

    @property
    def subjects_list(self):
        return [subject.subject_name for subject in self.subjects]

    @property
    def expertise_list(self):
        try:
            parsed = json.loads(self.expertise)
            if isinstance(parsed, list):
                return ", ".join(parsed)
            return str(parsed)
        except Exception:
            return self.expertise

    @property
    def qualifications_list(self):
        try:
            parsed = json.loads(self.qualifications)
            if isinstance(parsed, list):
                return Markup("<br>".join(parsed))
            return str(parsed)
        except Exception:
            return self.qualifications

    @property
    def review_count(self):
        session_review_count = (
            SessionFeedback.query
            .join(Session, SessionFeedback.session_id == Session.session_id)
            .filter(Session.tutor_id == self.tutor_id)
            .count()
        )
        tutor_review_count = (
            TutorReview.query
            .filter(TutorReview.tutor_id == self.tutor_id)
            .count()
        )
        return session_review_count + tutor_review_count

    @property
    def hourly_rate(self):
        if self.tutor_subjects_assoc:
            return min(float(ts.price) for ts in self.tutor_subjects_assoc)
        return None

    @property
    def next_available_slot(self):
        current_date = get_current_time().date()
        upcoming = [slot for slot in self.available_slots if slot.available_date >= current_date]
        if upcoming:
            upcoming.sort(key=lambda s: (s.available_date, s.start_time))
            return upcoming[0].available_date.strftime('%b %d') + ", " + upcoming[0].start_time.strftime('%I:%M %p')
        return "Not available"

class Student(db.Model):
    __tablename__ = 'Students'
    student_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    profile_pic_url = db.Column(db.String(255), default='/static/images/default-profile-picture.png')
    preferred_language = db.Column(db.String(50), nullable=False)
    preferred_learning_style = db.Column(db.Enum('Read/Write', 'Auditory', 'Visual'), nullable=False)
    budget = db.Column(db.Numeric(10, 2))
    about_me = db.Column(db.Text)
    password = db.Column(db.String(255), nullable=False)
    
    # Relationships for Student
    sessions = db.relationship('Session', backref='student', lazy=True)
    available_slots = db.relationship('StudentAvailableSlot', backref='student', lazy=True)
    learning_paths = db.relationship('StudentLearningPath', backref='student', lazy=True)

class TutorSubject(db.Model):
    __tablename__ = 'TutorSubjects'
    tutor_id = db.Column(db.Integer, db.ForeignKey('Tutors.tutor_id'), primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('Subjects.subject_id'), primary_key=True)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=50.00)
    
    # Optional explicit relationships
    tutor = db.relationship('Tutor', backref=db.backref('tutor_subjects', lazy=True))
    subject = db.relationship('Subject', backref=db.backref('tutor_subjects', lazy=True))

class TutorAvailableSlot(db.Model):
    __tablename__ = 'TutorAvailableSlots'
    slot_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey('Tutors.tutor_id'))
    available_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    @property
    def date(self):
        return self.available_date.strftime('%b %d, %Y')
    
    @property
    def time(self):
        return f"{self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}"

class TutorReview(db.Model):
    __tablename__ = 'TutorReviews'
    review_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey('Tutors.tutor_id'))
    student_name = db.Column(db.String(255))
    rating = db.Column(db.Numeric(3, 2))
    comment = db.Column(db.Text)

    @property
    def sentiment(self):
        if self.comment:
            scores = analyzer.polarity_scores(self.comment)
            compound = scores['compound']
            if compound >= 0.05:
                return "Positive"
            elif compound <= -0.05:
                return "Negative"
            else:
                return "Neutral"
        return "Neutral"

class Session(db.Model):
    __tablename__ = 'Sessions'
    session_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('Students.student_id'), nullable=False)
    tutor_id = db.Column(db.Integer, db.ForeignKey('Tutors.tutor_id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('Subjects.subject_id'), nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    session_status = db.Column(db.Enum('Scheduled', 'Completed', 'Canceled'), nullable=False)

    # Relationship to Subject so that session.subject is available in templates.
    subject = db.relationship('Subject', backref='sessions')
    # The relationships to Student and Tutor are available via the backrefs defined in those models.

    @property
    def description(self):
        return f"Learn advanced {self.subject.subject_name} techniques"

class SessionFeedback(db.Model):
    __tablename__ = 'SessionFeedback'
    feedback_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('Sessions.session_id'))
    student_feedback = db.Column(db.Text)
    star_rating = db.Column(db.Integer, nullable=False)
    feedback_sentiment = db.Column(db.String(20))
    feedback_issues = db.Column(db.Text)
    improvement_tip = db.Column(db.Text)

    # Relationship to Session so that you can access the session from feedback
    session = db.relationship('Session', backref='feedbacks')

class StudentSubject(db.Model):
    __tablename__ = 'StudentSubjects'
    student_id = db.Column(db.Integer, db.ForeignKey('Students.student_id'), primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('Subjects.subject_id'), primary_key=True)

class StudentAvailableSlot(db.Model):
    __tablename__ = 'StudentAvailableSlots'
    slot_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('Students.student_id'))
    available_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    @property
    def date(self):
        return self.available_date.strftime('%b %d, %Y')
    
    @property
    def time(self):
        return f"{self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}"

class StudentLearningPath(db.Model):
    __tablename__ = 'StudentLearningPaths'
    learning_path_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('Students.student_id'))
    learning_item = db.Column(db.String(255))  # Added to capture the learning item
    step_order = db.Column(db.Integer)

# ----------------------------
# SEED DATA FUNCTION
# ----------------------------

def seed_data():
    """
    Inserts initial seed data into the database, replicating all the INSERT
    statements from the provided SQL file.
    """

    db.drop_all()
    db.create_all()

    # --- INSERT BASE SUBJECTS ---
    subjects = {}

    # First group of subjects
    subject_data1 = [
        ("Linear Algebra", None),
        ("General Chemistry", None),
        ("Python Programming", None),
        ("Database Systems", None),
        ("Classical Mechanics", None),
        ("Basic Cooking Techniques", None),
        ("Calculus 1", None),
        ("Linear Regression", None)
    ]
    for name, prereq in subject_data1:
        subj = Subject(subject_name=name, prerequisite_id=prereq)
        db.session.add(subj)
        db.session.flush()  # so that subject_id is assigned
        subjects[name] = subj
    db.session.commit()

    # Second group of subjects – note the use of subqueries in SQL is replaced here by using the inserted objects
    subject_data2 = [
        ("Calculus 2", subjects["Calculus 1"].subject_id),
        ("Organic Chemistry", subjects["General Chemistry"].subject_id),
        ("Physics", None),
        ("Programming", None),
        ("Data Structures", None),
        ("Algorithms", None),
        ("Statistics", None),
        ("Machine Learning", None),  # to be updated after insertion
        ("Deep Learning", None),       # to be updated after insertion
        ("Data Structures and Algorithms", None)
    ]
    for name, prereq in subject_data2:
        subj = Subject(subject_name=name, prerequisite_id=prereq)
        db.session.add(subj)
        db.session.flush()
        subjects[name] = subj
    # Now update prerequisites for Machine Learning and Deep Learning
    subjects["Machine Learning"].prerequisite_id = subjects["Data Structures"].subject_id
    subjects["Deep Learning"].prerequisite_id = subjects["Machine Learning"].subject_id
    db.session.commit()

    # --- INSERT TUTOR DATA and RELATED INFORMATION ---
    tutors = {}

    # Tutor 1
    t1 = Tutor(
        name="Alice Johnson",
        preferred_language="English",
        teaching_style="Visual",
        average_star_rating=4.3,
        completed_sessions=120,
        email="alice.johnson@example.com",
        earnings=0.00,
        qualifications="MSc Mathematics",
        expertise="Linear Regression, Calculus",
        bio=("I am Alice Johnson, a dedicated Visual tutor with an MSc in Mathematics. I specialize in "
             "Linear Regression and Calculus and have completed 120 sessions helping students master complex "
             "mathematical concepts."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t1)
    db.session.commit()
    tutors[1] = t1
    # TutorSubjects for Tutor 1
    ts1 = TutorSubject(tutor_id=t1.tutor_id, subject_id=subjects["Linear Regression"].subject_id, price=40.00)
    ts2 = TutorSubject(tutor_id=t1.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=45.00)
    db.session.add_all([ts1, ts2])
    db.session.commit()
    # TutorAvailableSlots for Tutor 1
    tas1 = [
        TutorAvailableSlot(tutor_id=t1.tutor_id, available_date=dt.date(2025, 4, 21),
                           start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t1.tutor_id, available_date=dt.date(2025, 4, 22),
                           start_time=dt.time(8, 15, 0), end_time=dt.time(9, 15, 0)),
        TutorAvailableSlot(tutor_id=t1.tutor_id, available_date=dt.date(2025, 4, 23),
                           start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t1.tutor_id, available_date=dt.date(2025, 4, 25),
                           start_time=dt.time(14, 45, 0), end_time=dt.time(15, 45, 0))
    ]
    db.session.add_all(tas1)
    db.session.commit()

    # Tutor 2
    t2 = Tutor(
        name="Bob Smith",
        preferred_language="Spanish",
        teaching_style="Auditory",
        average_star_rating=3.7,
        completed_sessions=95,
        email="bob.smith@example.com",
        earnings=0.00,
        qualifications="BSc Chemistry",
        expertise="Organic Chemistry, Physics",
        bio=("I am Bob Smith, an Auditory tutor with a BSc in Chemistry. I specialize in Organic Chemistry and Physics "
             "and have conducted 95 sessions supporting students in scientific learning."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t2)
    db.session.commit()
    tutors[2] = t2
    ts2 = [
        TutorSubject(tutor_id=t2.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=50.00),
        TutorSubject(tutor_id=t2.tutor_id, subject_id=subjects["Physics"].subject_id, price=55.00)
    ]
    db.session.add_all(ts2)
    db.session.commit()
    tas2 = [
        TutorAvailableSlot(tutor_id=t2.tutor_id, available_date=dt.datetime(2025, 4, 21),
                           start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t2.tutor_id, available_date=dt.datetime(2025, 4, 22),
                           start_time=dt.time(9, 30, 0), end_time=dt.time(10, 30, 0)),
        TutorAvailableSlot(tutor_id=t2.tutor_id, available_date=dt.datetime(2025, 4, 26),
                           start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0)),
        TutorAvailableSlot(tutor_id=t2.tutor_id, available_date=dt.datetime(2025, 4, 28),
                           start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(tas2)
    db.session.commit()

    # Tutor 3
    t3 = Tutor(
        name="Charlie Davis",
        preferred_language="English",
        teaching_style="Read/Write",
        average_star_rating=4.8,
        completed_sessions=200,
        email="charlie.davis@example.com",
        earnings=0.00,
        qualifications="PhD Computer Science",
        expertise="Programming, Data Structures",
        bio=("I am Charlie Davis, a Read/Write tutor holding a PhD in Computer Science. With expertise in Programming "
             "and Data Structures and 200 completed sessions, I empower students with deep technical skills."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t3)
    db.session.commit()
    tutors[3] = t3
    ts3 = [
        TutorSubject(tutor_id=t3.tutor_id, subject_id=subjects["Programming"].subject_id, price=35.00),
        TutorSubject(tutor_id=t3.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=40.00)
    ]
    db.session.add_all(ts3)
    db.session.commit()
    tas3 = [
        TutorAvailableSlot(tutor_id=t3.tutor_id, available_date=dt.datetime(2025, 4, 21),
                           start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t3.tutor_id, available_date=dt.datetime(2025, 4, 25),
                           start_time=dt.time(10, 45, 0), end_time=dt.time(11, 45, 0)),
        TutorAvailableSlot(tutor_id=t3.tutor_id, available_date=dt.datetime(2025, 4, 27),
                           start_time=dt.time(13, 15, 0), end_time=dt.time(14, 15, 0)),
        TutorAvailableSlot(tutor_id=t3.tutor_id, available_date=dt.datetime(2025, 4, 29),
                           start_time=dt.time(16, 30, 0), end_time=dt.time(17, 30, 0))
    ]
    db.session.add_all(tas3)
    db.session.commit()

    # Tutor 4
    t4 = Tutor(
        name="Diana Evans",
        preferred_language="French",
        teaching_style="Visual",
        average_star_rating=4.1,
        completed_sessions=150,
        email="diana.evans@example.com",
        earnings=0.00,
        qualifications="MSc Computer Science",
        expertise="Algorithms, Machine Learning",
        bio=("I am Diana Evans, a Visual tutor with an MSc in Computer Science. I specialize in Algorithms and Machine Learning "
             "and have successfully conducted 150 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t4)
    db.session.commit()
    tutors[4] = t4
    ts4 = [
        TutorSubject(tutor_id=t4.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=45.00),
        TutorSubject(tutor_id=t4.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=50.00)
    ]
    db.session.add_all(ts4)
    db.session.commit()
    tas4 = [
        TutorAvailableSlot(tutor_id=t4.tutor_id, available_date=dt.datetime(2025, 4, 21),
                           start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t4.tutor_id, available_date=dt.datetime(2025, 4, 27),
                           start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t4.tutor_id, available_date=dt.datetime(2025, 4, 29),
                           start_time=dt.time(12, 45, 0), end_time=dt.time(13, 45, 0)),
        TutorAvailableSlot(tutor_id=t4.tutor_id, available_date=dt.datetime(2025, 5, 1),
                           start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(tas4)
    db.session.commit()

    # Tutor 5
    t5 = Tutor(
        name="Edward Miller",
        preferred_language="German",
        teaching_style="Auditory",
        average_star_rating=3.9,
        completed_sessions=110,
        email="edward.miller@example.com",
        earnings=0.00,
        qualifications="BSc Mathematics",
        expertise="Statistics, Calculus 1",
        bio=("I am Edward Miller, an Auditory tutor with a BSc in Mathematics. I excel in teaching Statistics and Calculus 1, "
             "backed by 110 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t5)
    db.session.commit()
    tutors[5] = t5
    ts5 = [
        TutorSubject(tutor_id=t5.tutor_id, subject_id=subjects["Statistics"].subject_id, price=40.00),
        TutorSubject(tutor_id=t5.tutor_id, subject_id=subjects["Calculus 1"].subject_id, price=35.00)
    ]
    db.session.add_all(ts5)
    db.session.commit()
    tas5 = [
        TutorAvailableSlot(tutor_id=t5.tutor_id, available_date=dt.datetime(2025, 4, 21),
                           start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t5.tutor_id, available_date=dt.datetime(2025, 4, 30),
                           start_time=dt.time(9, 45, 0), end_time=dt.time(10, 45, 0)),
        TutorAvailableSlot(tutor_id=t5.tutor_id, available_date=dt.datetime(2025, 4, 23),
                           start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0)),
        TutorAvailableSlot(tutor_id=t5.tutor_id, available_date=dt.datetime(2025, 4, 25),
                           start_time=dt.time(14, 30, 0), end_time=dt.time(15, 30, 0))
    ]
    db.session.add_all(tas5)
    db.session.commit()

    # Tutor 6
    t6 = Tutor(
        name="Fiona Garcia",
        preferred_language="English",
        teaching_style="Read/Write",
        average_star_rating=4.5,
        completed_sessions=130,
        email="fiona.garcia@example.com",
        earnings=0.00,
        qualifications="MSc Statistics",
        expertise="Linear Regression, Statistics",
        bio=("I am Fiona Garcia, a Read/Write tutor with an MSc in Statistics. I focus on Linear Regression and Statistics, "
             "and I have 130 successful sessions under my belt."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t6)
    db.session.commit()
    tutors[6] = t6
    ts6 = [
        TutorSubject(tutor_id=t6.tutor_id, subject_id=subjects["Linear Regression"].subject_id, price=42.00),
        TutorSubject(tutor_id=t6.tutor_id, subject_id=subjects["Statistics"].subject_id, price=38.00)
    ]
    db.session.add_all(ts6)
    db.session.commit()
    tas6 = [
        TutorAvailableSlot(tutor_id=t6.tutor_id, available_date=dt.datetime(2025, 4, 21),
                           start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t6.tutor_id, available_date=dt.datetime(2025, 4, 22),
                           start_time=dt.time(10, 15, 0), end_time=dt.time(11, 15, 0)),
        TutorAvailableSlot(tutor_id=t6.tutor_id, available_date=dt.datetime(2025, 4, 24),
                           start_time=dt.time(13, 30, 0), end_time=dt.time(14, 30, 0)),
        TutorAvailableSlot(tutor_id=t6.tutor_id, available_date=dt.datetime(2025, 4, 26),
                           start_time=dt.time(16, 0, 0), end_time=dt.time(17, 0, 0))
    ]
    db.session.add_all(tas6)
    db.session.commit()

    import datetime

    # Tutor 7
    t7 = Tutor(
        name="George Harris",
        preferred_language="Arabic",
        teaching_style="Visual",
        average_star_rating=3.6,
        completed_sessions=85,
        email="george.harris@example.com",
        earnings=0.00,
        qualifications="BSc Physics",
        expertise="Organic Chemistry, Physics",
        bio=("I am George Harris, a Visual tutor with a BSc in Physics. I bring expertise in Organic Chemistry and Physics, "
            "with 85 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t7)
    db.session.commit()
    tutors[7] = t7
    ts7 = [
        TutorSubject(tutor_id=t7.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=48.00),
        TutorSubject(tutor_id=t7.tutor_id, subject_id=subjects["Physics"].subject_id, price=52.00)
    ]
    db.session.add_all(ts7)
    db.session.commit()
    tas7 = [
        TutorAvailableSlot(tutor_id=t7.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t7.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0)),
        TutorAvailableSlot(tutor_id=t7.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0)),
        TutorAvailableSlot(tutor_id=t7.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(15, 30, 0), end_time=dt.time(16, 30, 0))
    ]
    db.session.add_all(tas7)
    db.session.commit()

    # Tutor 8
    t8 = Tutor(
        name="Hannah Lee",
        preferred_language="English",
        teaching_style="Auditory",
        average_star_rating=4.7,
        completed_sessions=175,
        email="hannah.lee@example.com",
        earnings=0.00,
        qualifications="BA Computer Science",
        expertise="Programming, Algorithms",
        bio=("I am Hannah Lee, an Auditory tutor with a BA in Computer Science. I specialize in Programming and Algorithms "
            "and have 175 sessions of experience."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t8)
    db.session.commit()
    tutors[8] = t8
    ts8 = [
        TutorSubject(tutor_id=t8.tutor_id, subject_id=subjects["Programming"].subject_id, price=37.00),
        TutorSubject(tutor_id=t8.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=42.00)
    ]
    db.session.add_all(ts8)
    db.session.commit()
    tas8 = [
        TutorAvailableSlot(tutor_id=t8.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t8.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(10, 45, 0), end_time=dt.time(11, 45, 0)),
        TutorAvailableSlot(tutor_id=t8.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(12, 15, 0), end_time=dt.time(13, 15, 0)),
        TutorAvailableSlot(tutor_id=t8.tutor_id, available_date=dt.datetime(2025, 5, 1), start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(tas8)
    db.session.commit()

    # Tutor 9
    t9 = Tutor(
        name="Ian Walker",
        preferred_language="Spanish",
        teaching_style="Read/Write",
        average_star_rating=4.2,
        completed_sessions=140,
        email="ian.walker@example.com",
        earnings=0.00,
        qualifications="BSc Computer Science",
        expertise="Data Structures, Machine Learning",
        bio=("I am Ian Walker, a Read/Write tutor holding a BSc in Computer Science. My expertise in Data Structures and "
            "Machine Learning is backed by 140 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t9)
    db.session.commit()
    tutors[9] = t9
    ts9 = [
        TutorSubject(tutor_id=t9.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=40.00),
        TutorSubject(tutor_id=t9.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=45.00)
    ]
    db.session.add_all(ts9)
    db.session.commit()
    tas9 = [
        TutorAvailableSlot(tutor_id=t9.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t9.tutor_id, available_date=dt.datetime(2025, 4, 30), start_time=dt.time(8, 45, 0), end_time=dt.time(9, 45, 0)),
        TutorAvailableSlot(tutor_id=t9.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0)),
        TutorAvailableSlot(tutor_id=t9.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(16, 0, 0), end_time=dt.time(17, 0, 0))
    ]
    db.session.add_all(tas9)
    db.session.commit()

    # Tutor 10
    t10 = Tutor(
        name="Julia Scott",
        preferred_language="French",
        teaching_style="Visual",
        average_star_rating=4.0,
        completed_sessions=100,
        email="julia.scott@example.com",
        earnings=0.00,
        qualifications="MSc Mathematics",
        expertise="Calculus 2, Linear Regression",
        bio=("I am Julia Scott, a Visual tutor with an MSc in Mathematics. I specialize in Calculus 2 and Linear Regression, "
            "having completed 100 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t10)
    db.session.commit()
    tutors[10] = t10
    ts10 = [
        TutorSubject(tutor_id=t10.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=44.00),
        TutorSubject(tutor_id=t10.tutor_id, subject_id=subjects["Linear Regression"].subject_id, price=40.00)
    ]
    db.session.add_all(ts10)
    db.session.commit()
    tas10 = [
        TutorAvailableSlot(tutor_id=t10.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t10.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(8, 30, 0), end_time=dt.time(9, 30, 0)),
        TutorAvailableSlot(tutor_id=t10.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(10, 0, 0), end_time=dt.time(11, 0, 0)),
        TutorAvailableSlot(tutor_id=t10.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(tas10)
    db.session.commit()

    # Tutor 11
    t11 = Tutor(
        name="Kevin Adams",
        preferred_language="English",
        teaching_style="Auditory",
        average_star_rating=3.8,
        completed_sessions=90,
        email="kevin.adams@example.com",
        earnings=0.00,
        qualifications="BSc Chemistry",
        expertise="Organic Chemistry, Statistics",
        bio=("I am Kevin Adams, an Auditory tutor with a BSc in Chemistry. I focus on Organic Chemistry and Statistics, "
            "with 90 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t11)
    db.session.commit()
    tutors[11] = t11
    ts11 = [
        TutorSubject(tutor_id=t11.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=43.00),
        TutorSubject(tutor_id=t11.tutor_id, subject_id=subjects["Statistics"].subject_id, price=39.00)
    ]
    db.session.add_all(ts11)
    db.session.commit()
    tas11 = [
        TutorAvailableSlot(tutor_id=t11.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t11.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(10, 15, 0), end_time=dt.time(11, 15, 0)),
        TutorAvailableSlot(tutor_id=t11.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(13, 30, 0), end_time=dt.time(14, 30, 0)),
        TutorAvailableSlot(tutor_id=t11.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(tas11)
    db.session.commit()

    # Tutor 12
    t12 = Tutor(
        name="Laura Perez",
        preferred_language="Spanish",
        teaching_style="Read/Write",
        average_star_rating=4.6,
        completed_sessions=160,
        email="laura.perez@example.com",
        earnings=0.00,
        qualifications="MSc Computer Science",
        expertise="Programming, Calculus 2",
        bio=("I am Laura Perez, a Read/Write tutor with an MSc in Computer Science. I specialize in Programming and Calculus 2, "
            "supported by 160 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t12)
    db.session.commit()
    tutors[12] = t12
    ts12 = [
        TutorSubject(tutor_id=t12.tutor_id, subject_id=subjects["Programming"].subject_id, price=38.00),
        TutorSubject(tutor_id=t12.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=42.00)
    ]
    db.session.add_all(ts12)
    db.session.commit()
    tas12 = [
        TutorAvailableSlot(tutor_id=t12.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t12.tutor_id, available_date=dt.datetime(2025, 4, 22), start_time=dt.time(8, 45, 0), end_time=dt.time(9, 45, 0)),
        TutorAvailableSlot(tutor_id=t12.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t12.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(tas12)
    db.session.commit()

    # Tutor 13
    t13 = Tutor(
        name="Michael Brown",
        preferred_language="English",
        teaching_style="Visual",
        average_star_rating=4.4,
        completed_sessions=145,
        email="michael.brown@example.com",
        earnings=0.00,
        qualifications="PhD Physics",
        expertise="Physics, Machine Learning",
        bio=("I am Michael Brown, a Visual tutor holding a PhD in Physics. With expertise in Physics and Machine Learning and "
            "145 completed sessions, I help students excel in science."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t13)
    db.session.commit()
    tutors[13] = t13
    ts13 = [
        TutorSubject(tutor_id=t13.tutor_id, subject_id=subjects["Physics"].subject_id, price=46.00),
        TutorSubject(tutor_id=t13.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=50.00)
    ]
    db.session.add_all(ts13)
    db.session.commit()
    tas13 = [
        TutorAvailableSlot(tutor_id=t13.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t13.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t13.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(12, 15, 0), end_time=dt.time(13, 15, 0)),
        TutorAvailableSlot(tutor_id=t13.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(15, 30, 0), end_time=dt.time(16, 30, 0))
    ]
    db.session.add_all(tas13)
    db.session.commit()

    # Tutor 14
    t14 = Tutor(
        name="Natalie Wilson",
        preferred_language="French",
        teaching_style="Auditory",
        average_star_rating=4.9,
        completed_sessions=210,
        email="natalie.wilson@example.com",
        earnings=0.00,
        qualifications="MSc Computer Science",
        expertise="Data Structures, Algorithms",
        bio=("I am Natalie Wilson, an Auditory tutor with an MSc in Computer Science. I excel in Data Structures and Algorithms, "
            "having completed 210 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t14)
    db.session.commit()
    tutors[14] = t14
    ts14 = [
        TutorSubject(tutor_id=t14.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=47.00),
        TutorSubject(tutor_id=t14.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=45.00)
    ]
    db.session.add_all(ts14)
    db.session.commit()
    tas14 = [
        TutorAvailableSlot(tutor_id=t14.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t14.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(9, 15, 0), end_time=dt.time(10, 15, 0)),
        TutorAvailableSlot(tutor_id=t14.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(11, 45, 0), end_time=dt.time(12, 45, 0)),
        TutorAvailableSlot(tutor_id=t14.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(14, 30, 0), end_time=dt.time(15, 30, 0))
    ]
    db.session.add_all(tas14)
    db.session.commit()

    # Tutor 15
    t15 = Tutor(
        name="Oliver Martinez",
        preferred_language="German",
        teaching_style="Read/Write",
        average_star_rating=3.5,
        completed_sessions=80,
        email="oliver.martinez@example.com",
        earnings=0.00,
        qualifications="BSc Mathematics",
        expertise="Statistics, Programming",
        bio=("I am Oliver Martinez, a Read/Write tutor with a BSc in Mathematics. I specialize in Statistics and Programming "
            "and have completed 80 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t15)
    db.session.commit()
    tutors[15] = t15
    ts15 = [
        TutorSubject(tutor_id=t15.tutor_id, subject_id=subjects["Statistics"].subject_id, price=40.00),
        TutorSubject(tutor_id=t15.tutor_id, subject_id=subjects["Programming"].subject_id, price=42.00)
    ]
    db.session.add_all(ts15)
    db.session.commit()
    tas15 = [
        TutorAvailableSlot(tutor_id=t15.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t15.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(10, 0, 0), end_time=dt.time(11, 0, 0)),
        TutorAvailableSlot(tutor_id=t15.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(13, 30, 0), end_time=dt.time(14, 30, 0)),
        TutorAvailableSlot(tutor_id=t15.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(15, 45, 0), end_time=dt.time(16, 45, 0))
    ]
    db.session.add_all(tas15)
    db.session.commit()

    # Tutor 16
    t16 = Tutor(
        name="Patricia Robinson",
        preferred_language="Arabic",
        teaching_style="Visual",
        average_star_rating=4.2,
        completed_sessions=115,
        email="patricia.robinson@example.com",
        earnings=0.00,
        qualifications="MBA",
        expertise="Linear Regression, Organic Chemistry",
        bio=("I am Patricia Robinson, a Visual tutor with an MBA. I focus on Linear Regression and Organic Chemistry, "
            "with 115 completed sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t16)
    db.session.commit()
    tutors[16] = t16
    ts16 = [
        TutorSubject(tutor_id=t16.tutor_id, subject_id=subjects["Linear Regression"].subject_id, price=41.00),
        TutorSubject(tutor_id=t16.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=43.00)
    ]
    db.session.add_all(ts16)
    db.session.commit()
    tas16 = [
        TutorAvailableSlot(tutor_id=t16.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t16.tutor_id, available_date=dt.datetime(2025, 4, 30), start_time=dt.time(12, 0, 0), end_time=dt.time(13, 0, 0)),
        TutorAvailableSlot(tutor_id=t16.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t16.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(14, 15, 0), end_time=dt.time(15, 15, 0))
    ]
    db.session.add_all(tas16)
    db.session.commit()

    # Tutor 17
    t17 = Tutor(
        name="Quentin Clark",
        preferred_language="English",
        teaching_style="Auditory",
        average_star_rating=3.9,
        completed_sessions=105,
        email="quentin.clark@example.com",
        earnings=0.00,
        qualifications="BSc Mathematics",
        expertise="Calculus, Physics",
        bio=("I am Quentin Clark, an Auditory tutor with a BSc in Mathematics. I specialize in Calculus and Physics and "
            "have completed 105 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t17)
    db.session.commit()
    tutors[17] = t17
    ts17 = [
        TutorSubject(tutor_id=t17.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=43.00),
        TutorSubject(tutor_id=t17.tutor_id, subject_id=subjects["Physics"].subject_id, price=44.00)
    ]
    db.session.add_all(ts17)
    db.session.commit()
    tas17 = [
        TutorAvailableSlot(tutor_id=t17.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t17.tutor_id, available_date=dt.datetime(2025, 4, 22), start_time=dt.time(10, 0, 0), end_time=dt.time(11, 0, 0)),
        TutorAvailableSlot(tutor_id=t17.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(12, 15, 0), end_time=dt.time(13, 15, 0)),
        TutorAvailableSlot(tutor_id=t17.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(15, 30, 0), end_time=dt.time(16, 30, 0))
    ]
    db.session.add_all(tas17)
    db.session.commit()

    # Tutor 18
    t18 = Tutor(
        name="Rachel Lewis",
        preferred_language="Spanish",
        teaching_style="Read/Write",
        average_star_rating=4.8,
        completed_sessions=190,
        email="rachel.lewis@example.com",
        earnings=0.00,
        qualifications="BSc Chemistry",
        expertise="Programming, Machine Learning",
        bio=("I am Rachel Lewis, a Read/Write tutor with a BSc in Chemistry. My expertise in Programming and Machine Learning "
            "is backed by 190 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t18)
    db.session.commit()
    tutors[18] = t18
    ts18 = [
        TutorSubject(tutor_id=t18.tutor_id, subject_id=subjects["Programming"].subject_id, price=39.00),
        TutorSubject(tutor_id=t18.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=47.00)
    ]
    db.session.add_all(ts18)
    db.session.commit()
    tas18 = [
        TutorAvailableSlot(tutor_id=t18.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t18.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(9, 15, 0), end_time=dt.time(10, 15, 0)),
        TutorAvailableSlot(tutor_id=t18.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0)),
        TutorAvailableSlot(tutor_id=t18.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(tas18)
    db.session.commit()

    # Tutor 19
    t19 = Tutor(
        name="Steven Young",
        preferred_language="French",
        teaching_style="Visual",
        average_star_rating=4.0,
        completed_sessions=125,
        email="steven.young@example.com",
        earnings=0.00,
        qualifications="BSc Physics",
        expertise="Data Structures, Algorithms",
        bio=("I am Steven Young, a Visual tutor holding a BSc in Physics. I specialize in Data Structures and Algorithms, "
            "with 125 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t19)
    db.session.commit()
    tutors[19] = t19
    ts19 = [
        TutorSubject(tutor_id=t19.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=42.00),
        TutorSubject(tutor_id=t19.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=45.00)
    ]
    db.session.add_all(ts19)
    db.session.commit()
    tas19 = [
        TutorAvailableSlot(tutor_id=t19.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t19.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(10, 0, 0), end_time=dt.time(11, 0, 0)),
        TutorAvailableSlot(tutor_id=t19.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0)),
        TutorAvailableSlot(tutor_id=t19.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(tas19)
    db.session.commit()

    # Tutor 20
    t20 = Tutor(
        name="Teresa King",
        preferred_language="German",
        teaching_style="Auditory",
        average_star_rating=3.7,
        completed_sessions=95,
        email="teresa.king@example.com",
        earnings=0.00,
        qualifications="BSc Chemistry",
        expertise="Organic Chemistry, Statistics",
        bio=("I am Teresa King, an Auditory tutor with a BSc in Chemistry. I focus on Organic Chemistry and Statistics, "
            "supported by 95 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t20)
    db.session.commit()
    tutors[20] = t20
    ts20 = [
        TutorSubject(tutor_id=t20.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=44.00),
        TutorSubject(tutor_id=t20.tutor_id, subject_id=subjects["Statistics"].subject_id, price=40.00)
    ]
    db.session.add_all(ts20)
    db.session.commit()
    tas20 = [
        TutorAvailableSlot(tutor_id=t20.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t20.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(8, 30, 0), end_time=dt.time(9, 30, 0)),
        TutorAvailableSlot(tutor_id=t20.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0)),
        TutorAvailableSlot(tutor_id=t20.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(14, 45, 0), end_time=dt.time(15, 45, 0))
    ]
    db.session.add_all(tas20)
    db.session.commit()

    # Tutor 21
    t21 = Tutor(
        name="Umar Patel",
        preferred_language="Arabic",
        teaching_style="Read/Write",
        average_star_rating=4.3,
        completed_sessions=135,
        email="umar.patel@example.com",
        earnings=0.00,
        qualifications="MBA",
        expertise="Linear Regression, Calculus 1",
        bio=("I am Umar Patel, a Read/Write tutor with an MBA. I specialize in Linear Regression and Calculus 1, "
            "having completed 135 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t21)
    db.session.commit()
    tutors[21] = t21
    ts21 = [
        TutorSubject(tutor_id=t21.tutor_id, subject_id=subjects["Linear Regression"].subject_id, price=40.00),
        TutorSubject(tutor_id=t21.tutor_id, subject_id=subjects["Calculus 1"].subject_id, price=38.00)
    ]
    db.session.add_all(ts21)
    db.session.commit()
    tas21 = [
        TutorAvailableSlot(tutor_id=t21.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t21.tutor_id, available_date=dt.datetime(2025, 4, 30), start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0)),
        TutorAvailableSlot(tutor_id=t21.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0)),
        TutorAvailableSlot(tutor_id=t21.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(tas21)
    db.session.commit()

    # Tutor 22
    t22 = Tutor(
        name="Victoria Wright",
        preferred_language="English",
        teaching_style="Visual",
        average_star_rating=4.5,
        completed_sessions=150,
        email="victoria.wright@example.com",
        earnings=0.00,
        qualifications="MSc Computer Science",
        expertise="Programming, Data Structures",
        bio=("I am Victoria Wright, a Visual tutor with an MSc in Computer Science. I excel in Programming and Data Structures "
            "with 150 completed sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t22)
    db.session.commit()
    tutors[22] = t22
    ts22 = [
        TutorSubject(tutor_id=t22.tutor_id, subject_id=subjects["Programming"].subject_id, price=41.00),
        TutorSubject(tutor_id=t22.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=45.00)
    ]
    db.session.add_all(ts22)
    db.session.commit()
    tas22 = [
        TutorAvailableSlot(tutor_id=t22.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t22.tutor_id, available_date=dt.datetime(2025, 4, 22), start_time=dt.time(9, 15, 0), end_time=dt.time(10, 15, 0)),
        TutorAvailableSlot(tutor_id=t22.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0)),
        TutorAvailableSlot(tutor_id=t22.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(14, 30, 0), end_time=dt.time(15, 30, 0))
    ]
    db.session.add_all(tas22)
    db.session.commit()

    # Tutor 23
    t23 = Tutor(
        name="Walter Baker",
        preferred_language="Spanish",
        teaching_style="Auditory",
        average_star_rating=4.1,
        completed_sessions=110,
        email="walter.baker@example.com",
        earnings=0.00,
        qualifications="BSc Mathematics",
        expertise="Algorithms, Machine Learning",
        bio=("I am Walter Baker, an Auditory tutor with a BSc in Mathematics. I specialize in Algorithms and Machine Learning "
            "and have conducted 110 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t23)
    db.session.commit()
    tutors[23] = t23
    ts23 = [
        TutorSubject(tutor_id=t23.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=42.00),
        TutorSubject(tutor_id=t23.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=44.00)
    ]
    db.session.add_all(ts23)
    db.session.commit()
    tas23 = [
        TutorAvailableSlot(tutor_id=t23.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t23.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t23.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(13, 0, 0), end_time=dt.time(14, 0, 0)),
        TutorAvailableSlot(tutor_id=t23.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(15, 45, 0), end_time=dt.time(16, 45, 0))
    ]
    db.session.add_all(tas23)
    db.session.commit()

    # Tutor 24
    t24 = Tutor(
        name="Xenia Gonzalez",
        preferred_language="French",
        teaching_style="Read/Write",
        average_star_rating=4.7,
        completed_sessions=160,
        email="xenia.gonzalez@example.com",
        earnings=0.00,
        qualifications="MSc Chemistry",
        expertise="Statistics, Calculus 2",
        bio=("I am Xenia Gonzalez, a Read/Write tutor with an MSc in Chemistry. I focus on Statistics and Calculus 2, backed by 160 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t24)
    db.session.commit()
    tutors[24] = t24
    ts24 = [
        TutorSubject(tutor_id=t24.tutor_id, subject_id=subjects["Statistics"].subject_id, price=40.00),
        TutorSubject(tutor_id=t24.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=42.00)
    ]
    db.session.add_all(ts24)
    db.session.commit()
    tas24 = [
        TutorAvailableSlot(tutor_id=t24.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t24.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(8, 45, 0), end_time=dt.time(9, 45, 0)),
        TutorAvailableSlot(tutor_id=t24.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t24.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(13, 15, 0), end_time=dt.time(14, 15, 0))
    ]
    db.session.add_all(tas24)
    db.session.commit()

    # Tutor 25
    t25 = Tutor(
        name="Yvonne Rivera",
        preferred_language="German",
        teaching_style="Visual",
        average_star_rating=3.8,
        completed_sessions=90,
        email="yvonne.rivera@example.com",
        earnings=0.00,
        qualifications="BSc Engineering",
        expertise="Organic Chemistry, Physics",
        bio=("I am Yvonne Rivera, a Visual tutor with a BSc in Engineering. I specialize in Organic Chemistry and Physics, "
            "with 90 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t25)
    db.session.commit()
    tutors[25] = t25
    ts25 = [
        TutorSubject(tutor_id=t25.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=45.00),
        TutorSubject(tutor_id=t25.tutor_id, subject_id=subjects["Physics"].subject_id, price=47.00)
    ]
    db.session.add_all(ts25)
    db.session.commit()
    tas25 = [
        TutorAvailableSlot(tutor_id=t25.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t25.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(13, 15, 0), end_time=dt.time(14, 15, 0)),
        TutorAvailableSlot(tutor_id=t25.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0)),
        TutorAvailableSlot(tutor_id=t25.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(16, 30, 0), end_time=dt.time(17, 30, 0))
    ]
    db.session.add_all(tas25)
    db.session.commit()

    # Tutor 26
    t26 = Tutor(
        name="Zachary Cooper",
        preferred_language="Arabic",
        teaching_style="Auditory",
        average_star_rating=4.6,
        completed_sessions=170,
        email="zachary.cooper@example.com",
        earnings=0.00,
        qualifications="MBA",
        expertise="Programming, Algorithms",
        bio=("I am Zachary Cooper, an Auditory tutor with a MBA. I specialize in Programming and Algorithms, and I have conducted 170 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t26)
    db.session.commit()
    tutors[26] = t26
    ts26 = [
        TutorSubject(tutor_id=t26.tutor_id, subject_id=subjects["Programming"].subject_id, price=42.00),
        TutorSubject(tutor_id=t26.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=45.00)
    ]
    db.session.add_all(ts26)
    db.session.commit()
    tas26 = [
        TutorAvailableSlot(tutor_id=t26.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t26.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0)),
        TutorAvailableSlot(tutor_id=t26.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0)),
        TutorAvailableSlot(tutor_id=t26.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(15, 30, 0), end_time=dt.time(16, 30, 0))
    ]
    db.session.add_all(tas26)
    db.session.commit()

    # Tutor 27
    t27 = Tutor(
        name="Aaron Reed",
        preferred_language="English",
        teaching_style="Read/Write",
        average_star_rating=4.2,
        completed_sessions=130,
        email="aaron.reed@example.com",
        earnings=0.00,
        qualifications="BSc Mathematics",
        expertise="Data Structures, Machine Learning",
        bio=("I am Aaron Reed, a Read/Write tutor with a BSc in Mathematics. My expertise in Data Structures and Machine Learning "
            "is supported by 130 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t27)
    db.session.commit()
    tutors[27] = t27
    ts27 = [
        TutorSubject(tutor_id=t27.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=40.00),
        TutorSubject(tutor_id=t27.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=45.00)
    ]
    db.session.add_all(ts27)
    db.session.commit()
    tas27 = [
        TutorAvailableSlot(tutor_id=t27.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t27.tutor_id, available_date=dt.datetime(2025, 4, 30), start_time=dt.time(8, 30, 0), end_time=dt.time(9, 30, 0)),
        TutorAvailableSlot(tutor_id=t27.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0)),
        TutorAvailableSlot(tutor_id=t27.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(14, 30, 0), end_time=dt.time(15, 30, 0))
    ]
    db.session.add_all(tas27)
    db.session.commit()

    # Tutor 28
    t28 = Tutor(
        name="Bethany Cox",
        preferred_language="Spanish",
        teaching_style="Visual",
        average_star_rating=4.4,
        completed_sessions=140,
        email="bethany.cox@example.com",
        earnings=0.00,
        qualifications="BA Computer Science",
        expertise="Calculus 2, Linear Regression",
        bio=("I am Bethany Cox, a Visual tutor with a BA in Computer Science. I specialize in Calculus 2 and Linear Regression, "
            "having completed 140 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t28)
    db.session.commit()
    tutors[28] = t28
    ts28 = [
        TutorSubject(tutor_id=t28.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=44.00),
        TutorSubject(tutor_id=t28.tutor_id, subject_id=subjects["Linear Regression"].subject_id, price=40.00)
    ]
    db.session.add_all(ts28)
    db.session.commit()
    tas28 = [
        TutorAvailableSlot(tutor_id=t28.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t28.tutor_id, available_date=dt.datetime(2025, 4, 22), start_time=dt.time(10, 45, 0), end_time=dt.time(11, 45, 0)),
        TutorAvailableSlot(tutor_id=t28.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0)),
        TutorAvailableSlot(tutor_id=t28.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(15, 15, 0), end_time=dt.time(16, 15, 0))
    ]
    db.session.add_all(tas28)
    db.session.commit()

    # Tutor 29
    t29 = Tutor(
        name="Caleb Brooks",
        preferred_language="French",
        teaching_style="Auditory",
        average_star_rating=3.6,
        completed_sessions=100,
        email="caleb.brooks@example.com",
        earnings=0.00,
        qualifications="BSc Chemistry",
        expertise="Organic Chemistry, Statistics",
        bio=("I am Caleb Brooks, an Auditory tutor with a BSc in Chemistry. I focus on Organic Chemistry and Statistics with "
            "100 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t29)
    db.session.commit()
    tutors[29] = t29
    ts29 = [
        TutorSubject(tutor_id=t29.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=43.00),
        TutorSubject(tutor_id=t29.tutor_id, subject_id=subjects["Statistics"].subject_id, price=40.00)
    ]
    db.session.add_all(ts29)
    db.session.commit()
    tas29 = [
        TutorAvailableSlot(tutor_id=t29.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t29.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(10, 0, 0), end_time=dt.time(11, 0, 0)),
        TutorAvailableSlot(tutor_id=t29.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(11, 45, 0), end_time=dt.time(12, 45, 0)),
        TutorAvailableSlot(tutor_id=t29.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(14, 30, 0), end_time=dt.time(15, 30, 0))
    ]
    db.session.add_all(tas29)
    db.session.commit()

    # Tutor 30
    t30 = Tutor(
        name="Danielle Ward",
        preferred_language="German",
        teaching_style="Read/Write",
        average_star_rating=4.8,
        completed_sessions=180,
        email="danielle.ward@example.com",
        earnings=0.00,
        qualifications="MSc Computer Science",
        expertise="Programming, Calculus 2",
        bio=("I am Danielle Ward, a Read/Write tutor with an MSc in Computer Science. I excel in Programming and Calculus 2, "
            "and have completed 180 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t30)
    db.session.commit()
    tutors[30] = t30
    ts30 = [
        TutorSubject(tutor_id=t30.tutor_id, subject_id=subjects["Programming"].subject_id, price=38.00),
        TutorSubject(tutor_id=t30.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=42.00)
    ]
    db.session.add_all(ts30)
    db.session.commit()
    tas30 = [
        TutorAvailableSlot(tutor_id=t30.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t30.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(9, 15, 0), end_time=dt.time(10, 15, 0)),
        TutorAvailableSlot(tutor_id=t30.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t30.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(14, 45, 0), end_time=dt.time(15, 45, 0))
    ]
    db.session.add_all(tas30)
    db.session.commit()

    # Tutor 31
    t31 = Tutor(
        name="Ethan Price",
        preferred_language="Arabic",
        teaching_style="Visual",
        average_star_rating=4.0,
        completed_sessions=115,
        email="ethan.price@example.com",
        earnings=0.00,
        qualifications="BSc Engineering",
        expertise="Physics, Machine Learning",
        bio=("I am Ethan Price, a Visual tutor with a BSc in Engineering. I specialize in Physics and Machine Learning, "
            "having completed 115 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t31)
    db.session.commit()
    tutors[31] = t31
    ts31 = [
        TutorSubject(tutor_id=t31.tutor_id, subject_id=subjects["Physics"].subject_id, price=45.00),
        TutorSubject(tutor_id=t31.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=48.00)
    ]
    db.session.add_all(ts31)
    db.session.commit()
    tas31 = [
        TutorAvailableSlot(tutor_id=t31.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t31.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t31.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0)),
        TutorAvailableSlot(tutor_id=t31.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(tas31)
    db.session.commit()

    # Tutor 32
    t32 = Tutor(
        name="Faith Long",
        preferred_language="English",
        teaching_style="Auditory",
        average_star_rating=4.9,
        completed_sessions=205,
        email="faith.long@example.com",
        earnings=0.00,
        qualifications="MSc Computer Science",
        expertise="Data Structures, Algorithms",
        bio=("I am Faith Long, an Auditory tutor with an MSc in Computer Science. I excel in Data Structures and Algorithms "
            "and have successfully completed 205 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t32)
    db.session.commit()
    tutors[32] = t32
    ts32 = [
        TutorSubject(tutor_id=t32.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=41.00),
        TutorSubject(tutor_id=t32.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=44.00)
    ]
    db.session.add_all(ts32)
    db.session.commit()
    tas32 = [
        TutorAvailableSlot(tutor_id=t32.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t32.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(10, 15, 0), end_time=dt.time(11, 15, 0)),
        TutorAvailableSlot(tutor_id=t32.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0)),
        TutorAvailableSlot(tutor_id=t32.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(15, 45, 0), end_time=dt.time(16, 45, 0))
    ]
    db.session.add_all(tas32)
    db.session.commit()

    # Tutor 33
    t33 = Tutor(
        name="Gavin Patterson",
        preferred_language="Spanish",
        teaching_style="Read/Write",
        average_star_rating=3.5,
        completed_sessions=85,
        email="gavin.patterson@example.com",
        earnings=0.00,
        qualifications="BA Economics",
        expertise="Statistics, Programming",
        bio=("I am Gavin Patterson, a Read/Write tutor with a BA in Economics. I specialize in Statistics and Programming, "
            "with 85 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t33)
    db.session.commit()
    tutors[33] = t33
    ts33 = [
        TutorSubject(tutor_id=t33.tutor_id, subject_id=subjects["Statistics"].subject_id, price=40.00),
        TutorSubject(tutor_id=t33.tutor_id, subject_id=subjects["Programming"].subject_id, price=38.00)
    ]
    db.session.add_all(ts33)
    db.session.commit()
    tas33 = [
        TutorAvailableSlot(tutor_id=t33.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t33.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0)),
        TutorAvailableSlot(tutor_id=t33.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(13, 15, 0), end_time=dt.time(14, 15, 0)),
        TutorAvailableSlot(tutor_id=t33.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(16, 0, 0), end_time=dt.time(17, 0, 0))
    ]
    db.session.add_all(tas33)
    db.session.commit()

    # Tutor 34
    t34 = Tutor(
        name="Hailey Hughes",
        preferred_language="French",
        teaching_style="Visual",
        average_star_rating=4.2,
        completed_sessions=125,
        email="hailey.hughes@example.com",
        earnings=0.00,
        qualifications="BSc Mathematics",
        expertise="Linear Regression, Organic Chemistry",
        bio=("I am Hailey Hughes, a Visual tutor with a BSc in Mathematics. I focus on Linear Regression and Organic Chemistry, "
            "and have completed 125 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t34)
    db.session.commit()
    tutors[34] = t34
    ts34 = [
        TutorSubject(tutor_id=t34.tutor_id, subject_id=subjects["Linear Regression"].subject_id, price=42.00),
        TutorSubject(tutor_id=t34.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=44.00)
    ]
    db.session.add_all(ts34)
    db.session.commit()
    tas34 = [
        TutorAvailableSlot(tutor_id=t34.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t34.tutor_id, available_date=dt.datetime(2025, 4, 30), start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0)),
        TutorAvailableSlot(tutor_id=t34.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(10, 45, 0), end_time=dt.time(11, 45, 0)),
        TutorAvailableSlot(tutor_id=t34.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(tas34)
    db.session.commit()

    # Tutor 35
    t35 = Tutor(
        name="Kyle Bennett",
        preferred_language="English",
        teaching_style="Visual",
        average_star_rating=4.0,
        completed_sessions=120,
        email="kyle.bennett@example.com",
        earnings=0.00,
        qualifications="BA Computer Science",
        expertise="Data Structures, Algorithms",
        bio=("I am Kyle Bennett, a Visual tutor with a BA in Computer Science. My expertise in Data Structures and Algorithms is "
            "reflected in my 120 completed sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t35)
    db.session.commit()
    tutors[35] = t35
    ts35 = [
        TutorSubject(tutor_id=t35.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=40.00),
        TutorSubject(tutor_id=t35.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=42.00)
    ]
    db.session.add_all(ts35)
    db.session.commit()
    tas35 = [
        TutorAvailableSlot(tutor_id=t35.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t35.tutor_id, available_date=dt.datetime(2025, 4, 30), start_time=dt.time(13, 0, 0), end_time=dt.time(14, 0, 0)),
        TutorAvailableSlot(tutor_id=t35.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(14, 15, 0), end_time=dt.time(15, 15, 0)),
        TutorAvailableSlot(tutor_id=t35.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(15, 30, 0), end_time=dt.time(16, 30, 0))
    ]
    db.session.add_all(tas35)
    db.session.commit()

    # Tutor 36
    t36 = Tutor(
        name="Bethany Cox",
        preferred_language="Spanish",
        teaching_style="Visual",
        average_star_rating=4.4,
        completed_sessions=140,
        email="bethany.cox2@example.com",
        earnings=0.00,
        qualifications="BSc Information Systems",
        expertise="Calculus 2, Linear Regression",
        bio=("I am Bethany Cox, a Visual tutor with a BSc in Information Systems. I specialize in Calculus 2 and Linear Regression, "
            "with 140 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t36)
    db.session.commit()
    tutors[36] = t36
    ts36 = [
        TutorSubject(tutor_id=t36.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=44.00),
        TutorSubject(tutor_id=t36.tutor_id, subject_id=subjects["Linear Regression"].subject_id, price=40.00)
    ]
    db.session.add_all(ts36)
    db.session.commit()
    tas36 = [
        TutorAvailableSlot(tutor_id=t36.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t36.tutor_id, available_date=dt.datetime(2025, 4, 22), start_time=dt.time(10, 15, 0), end_time=dt.time(11, 15, 0)),
        TutorAvailableSlot(tutor_id=t36.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(11, 45, 0), end_time=dt.time(12, 45, 0)),
        TutorAvailableSlot(tutor_id=t36.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(13, 30, 0), end_time=dt.time(14, 30, 0))
    ]
    db.session.add_all(tas36)
    db.session.commit()

    # Tutor 37
    t37 = Tutor(
        name="Caleb Brooks",
        preferred_language="French",
        teaching_style="Auditory",
        average_star_rating=3.6,
        completed_sessions=100,
        email="caleb.brooks2@example.com",
        earnings=0.00,
        qualifications="BSc Chemistry",
        expertise="Organic Chemistry, Statistics",
        bio=("I am Caleb Brooks, an Auditory tutor with a BSc in Chemistry. I focus on Organic Chemistry and Statistics, "
            "with 100 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t37)
    db.session.commit()
    tutors[37] = t37
    ts37 = [
        TutorSubject(tutor_id=t37.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=43.00),
        TutorSubject(tutor_id=t37.tutor_id, subject_id=subjects["Statistics"].subject_id, price=40.00)
    ]
    db.session.add_all(ts37)
    db.session.commit()
    tas37 = [
        TutorAvailableSlot(tutor_id=t37.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t37.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(10, 0, 0), end_time=dt.time(11, 0, 0)),
        TutorAvailableSlot(tutor_id=t37.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0)),
        TutorAvailableSlot(tutor_id=t37.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(tas37)
    db.session.commit()

    # Tutor 38
    t38 = Tutor(
        name="Danielle Ward",
        preferred_language="German",
        teaching_style="Read/Write",
        average_star_rating=4.8,
        completed_sessions=180,
        email="danielle.ward2@example.com",
        earnings=0.00,
        qualifications="MSc Computer Science",
        expertise="Programming, Calculus 2",
        bio=("I am Danielle Ward, a Read/Write tutor with an MSc in Computer Science. I specialize in Programming and Calculus 2, "
            "and have successfully completed 180 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t38)
    db.session.commit()
    tutors[38] = t38
    ts38 = [
        TutorSubject(tutor_id=t38.tutor_id, subject_id=subjects["Programming"].subject_id, price=38.00),
        TutorSubject(tutor_id=t38.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=42.00)
    ]
    db.session.add_all(ts38)
    db.session.commit()
    tas38 = [
        TutorAvailableSlot(tutor_id=t38.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t38.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(9, 15, 0), end_time=dt.time(10, 15, 0)),
        TutorAvailableSlot(tutor_id=t38.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t38.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(14, 45, 0), end_time=dt.time(15, 45, 0))
    ]
    db.session.add_all(tas38)
    db.session.commit()

    # Tutor 39
    t39 = Tutor(
        name="Nora Perry",
        preferred_language="German",
        teaching_style="Visual",
        average_star_rating=4.5,
        completed_sessions=150,
        email="nora.perry@example.com",
        earnings=0.00,
        qualifications="BSc Mathematics",
        expertise="Programming, Data Structures",
        bio=("I am Nora Perry, a Visual tutor with a BSc in Mathematics. I excel in Programming and Data Structures, "
            "with 150 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t39)
    db.session.commit()
    tutors[39] = t39
    ts39 = [
        TutorSubject(tutor_id=t39.tutor_id, subject_id=subjects["Programming"].subject_id, price=38.00),
        TutorSubject(tutor_id=t39.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=42.00)
    ]
    db.session.add_all(ts39)
    db.session.commit()
    tas39 = [
        TutorAvailableSlot(tutor_id=t39.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t39.tutor_id, available_date=dt.datetime(2025, 4, 22), start_time=dt.time(9, 30, 0), end_time=dt.time(10, 30, 0)),
        TutorAvailableSlot(tutor_id=t39.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(11, 45, 0), end_time=dt.time(12, 45, 0)),
        TutorAvailableSlot(tutor_id=t39.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(14, 30, 0), end_time=dt.time(15, 30, 0))
    ]
    db.session.add_all(tas39)
    db.session.commit()

    # Tutor 40
    t40 = Tutor(
        name="Owen Russell",
        preferred_language="Arabic",
        teaching_style="Auditory",
        average_star_rating=4.1,
        completed_sessions=110,
        email="owen.russell@example.com",
        earnings=0.00,
        qualifications="BA Engineering",
        expertise="Algorithms, Machine Learning",
        bio=("I am Owen Russell, an Auditory tutor with a BA in Engineering. I specialize in Algorithms and Machine Learning, "
            "having completed 110 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t40)
    db.session.commit()
    tutors[40] = t40
    ts40 = [
        TutorSubject(tutor_id=t40.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=43.00),
        TutorSubject(tutor_id=t40.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=45.00)
    ]
    db.session.add_all(ts40)
    db.session.commit()
    tas40 = [
        TutorAvailableSlot(tutor_id=t40.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t40.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(10, 0, 0), end_time=dt.time(11, 0, 0)),
        TutorAvailableSlot(tutor_id=t40.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0)),
        TutorAvailableSlot(tutor_id=t40.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(tas40)
    db.session.commit()

    # Tutor 41
    t41 = Tutor(
        name="Penelope Bryant",
        preferred_language="English",
        teaching_style="Read/Write",
        average_star_rating=4.7,
        completed_sessions=160,
        email="penelope.bryant@example.com",
        earnings=0.00,
        qualifications="MSc Mathematics",
        expertise="Calculus, Data Structures",
        bio=("I am Penelope Bryant, a Read/Write tutor with an MSc in Mathematics. I specialize in Calculus and Data Structures, "
            "with 160 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t41)
    db.session.commit()
    tutors[41] = t41
    ts41 = [
        TutorSubject(tutor_id=t41.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=45.00)
    ]
    db.session.add_all(ts41)
    db.session.commit()
    tas41 = [
        TutorAvailableSlot(tutor_id=t41.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t41.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t41.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0)),
        TutorAvailableSlot(tutor_id=t41.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(14, 30, 0), end_time=dt.time(15, 30, 0))
    ]
    db.session.add_all(tas41)
    db.session.commit()

    # Tutor 42
    t42 = Tutor(
        name="Queen Fisher",
        preferred_language="Spanish",
        teaching_style="Visual",
        average_star_rating=3.8,
        completed_sessions=90,
        email="queen.fisher@example.com",
        earnings=0.00,
        qualifications="BA History",
        expertise="Organic Chemistry, Physics",
        bio=("I am Queen Fisher, a Visual tutor with a BA in History. I focus on Organic Chemistry and Physics, "
            "with 90 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t42)
    db.session.commit()
    tutors[42] = t42
    ts42 = [
        TutorSubject(tutor_id=t42.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=44.00),
        TutorSubject(tutor_id=t42.tutor_id, subject_id=subjects["Physics"].subject_id, price=46.00)
    ]
    db.session.add_all(ts42)
    db.session.commit()
    tas42 = [
        TutorAvailableSlot(tutor_id=t42.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t42.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(10, 15, 0), end_time=dt.time(11, 15, 0)),
        TutorAvailableSlot(tutor_id=t42.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0)),
        TutorAvailableSlot(tutor_id=t42.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(tas42)
    db.session.commit()

    # Tutor 43
    t43 = Tutor(
        name="Rebecca Simmons",
        preferred_language="French",
        teaching_style="Auditory",
        average_star_rating=4.6,
        completed_sessions=170,
        email="rebecca.simmons@example.com",
        earnings=0.00,
        qualifications="BSc English",
        expertise="Programming, Algorithms",
        bio=("I am Rebecca Simmons, an Auditory tutor with a BSc in English. I excel in Programming and Algorithms, "
            "having successfully completed 170 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t43)
    db.session.commit()
    tutors[43] = t43
    ts43 = [
        TutorSubject(tutor_id=t43.tutor_id, subject_id=subjects["Programming"].subject_id, price=39.00),
        TutorSubject(tutor_id=t43.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=42.00)
    ]
    db.session.add_all(ts43)
    db.session.commit()
    tas43 = [
        TutorAvailableSlot(tutor_id=t43.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t43.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0)),
        TutorAvailableSlot(tutor_id=t43.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(13, 45, 0), end_time=dt.time(14, 45, 0)),
        TutorAvailableSlot(tutor_id=t43.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(15, 15, 0), end_time=dt.time(16, 15, 0))
    ]
    db.session.add_all(tas43)
    db.session.commit()

    # Tutor 44
    t44 = Tutor(
        name="Samuel Butler",
        preferred_language="German",
        teaching_style="Read/Write",
        average_star_rating=4.2,
        completed_sessions=135,
        email="samuel.butler@example.com",
        earnings=0.00,
        qualifications="BSc Mathematics",
        expertise="Data Structures, Machine Learning",
        bio=("I am Samuel Butler, a Read/Write tutor with a BSc in Mathematics. I specialize in Data Structures and Machine Learning, "
            "with 135 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t44)
    db.session.commit()
    tutors[44] = t44
    ts44 = [
        TutorSubject(tutor_id=t44.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=40.00),
        TutorSubject(tutor_id=t44.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=45.00)
    ]
    db.session.add_all(ts44)
    db.session.commit()
    tas44 = [
        TutorAvailableSlot(tutor_id=t44.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t44.tutor_id, available_date=dt.datetime(2025, 4, 30), start_time=dt.time(9, 15, 0), end_time=dt.time(10, 15, 0)),
        TutorAvailableSlot(tutor_id=t44.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0)),
        TutorAvailableSlot(tutor_id=t44.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(tas44)
    db.session.commit()

    # Tutor 45
    t45 = Tutor(
        name="Tina Ward",
        preferred_language="Arabic",
        teaching_style="Visual",
        average_star_rating=4.4,
        completed_sessions=140,
        email="tina.ward@example.com",
        earnings=0.00,
        qualifications="BSc Engineering",
        expertise="Calculus 2, Linear Regression",
        bio=("I am Tina Ward, a Visual tutor with a BSc in Engineering. I focus on Calculus 2 and Linear Regression, "
            "having completed 140 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t45)
    db.session.commit()
    tutors[45] = t45
    ts45 = [
        TutorSubject(tutor_id=t45.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=43.00),
        TutorSubject(tutor_id=t45.tutor_id, subject_id=subjects["Physics"].subject_id, price=45.00)
    ]
    db.session.add_all(ts45)
    db.session.commit()
    tas45 = [
        TutorAvailableSlot(tutor_id=t45.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t45.tutor_id, available_date=dt.datetime(2025, 4, 22), start_time=dt.time(9, 45, 0), end_time=dt.time(10, 45, 0)),
        TutorAvailableSlot(tutor_id=t45.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0)),
        TutorAvailableSlot(tutor_id=t45.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(14, 15, 0), end_time=dt.time(15, 15, 0))
    ]
    db.session.add_all(tas45)
    db.session.commit()

    # Tutor 46
    t46 = Tutor(
        name="Ulysses Grant",
        preferred_language="English",
        teaching_style="Auditory",
        average_star_rating=3.6,
        completed_sessions=100,
        email="ulysses.grant@example.com",
        earnings=0.00,
        qualifications="BSc History",
        expertise="Organic Chemistry, Statistics",
        bio=("I am Ulysses Grant, an Auditory tutor with a BSc in History. I specialize in Organic Chemistry and Statistics, "
            "with 100 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t46)
    db.session.commit()
    tutors[46] = t46
    ts46 = [
        TutorSubject(tutor_id=t46.tutor_id, subject_id=subjects["Organic Chemistry"].subject_id, price=44.00),
        TutorSubject(tutor_id=t46.tutor_id, subject_id=subjects["Statistics"].subject_id, price=40.00)
    ]
    db.session.add_all(ts46)
    db.session.commit()
    tas46 = [
        TutorAvailableSlot(tutor_id=t46.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t46.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0)),
        TutorAvailableSlot(tutor_id=t46.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(14, 45, 0), end_time=dt.time(15, 45, 0)),
        TutorAvailableSlot(tutor_id=t46.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(16, 0, 0), end_time=dt.time(17, 0, 0))
    ]
    db.session.add_all(tas46)
    db.session.commit()

    # Tutor 47
    t47 = Tutor(
        name="Violet Diaz",
        preferred_language="Spanish",
        teaching_style="Read/Write",
        average_star_rating=4.8,
        completed_sessions=180,
        email="violet.diaz@example.com",
        earnings=0.00,
        qualifications="BA Art",
        expertise="Programming, Calculus 2",
        bio=("I am Violet Diaz, a Read/Write tutor with a BA in Art. I specialize in Programming and Calculus 2, "
            "with 180 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t47)
    db.session.commit()
    tutors[47] = t47
    ts47 = [
        TutorSubject(tutor_id=t47.tutor_id, subject_id=subjects["Programming"].subject_id, price=39.00),
        TutorSubject(tutor_id=t47.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=42.00)
    ]
    db.session.add_all(ts47)
    db.session.commit()
    tas47 = [
        TutorAvailableSlot(tutor_id=t47.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t47.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(9, 30, 0), end_time=dt.time(10, 30, 0)),
        TutorAvailableSlot(tutor_id=t47.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(11, 45, 0), end_time=dt.time(12, 45, 0)),
        TutorAvailableSlot(tutor_id=t47.tutor_id, available_date=dt.datetime(2025, 4, 28), start_time=dt.time(14, 30, 0), end_time=dt.time(15, 30, 0))
    ]
    db.session.add_all(tas47)
    db.session.commit()

    # Tutor 48
    t48 = Tutor(
        name="Wesley Ortiz",
        preferred_language="French",
        teaching_style="Visual",
        average_star_rating=4.0,
        completed_sessions=115,
        email="wesley.ortiz@example.com",
        earnings=0.00,
        qualifications="BSc Computer Science",
        expertise="Physics, Machine Learning",
        bio=("I am Wesley Ortiz, a Visual tutor with a BSc in Computer Science. I focus on Physics and Machine Learning, "
            "having completed 115 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t48)
    db.session.commit()
    tutors[48] = t48
    ts48 = [
        TutorSubject(tutor_id=t48.tutor_id, subject_id=subjects["Physics"].subject_id, price=45.00),
        TutorSubject(tutor_id=t48.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=47.00)
    ]
    db.session.add_all(ts48)
    db.session.commit()
    tas48 = [
        TutorAvailableSlot(tutor_id=t48.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t48.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(9, 15, 0), end_time=dt.time(10, 15, 0)),
        TutorAvailableSlot(tutor_id=t48.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0)),
        TutorAvailableSlot(tutor_id=t48.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(tas48)
    db.session.commit()

    # Tutor 49
    t49 = Tutor(
        name="Xander Mills",
        preferred_language="German",
        teaching_style="Auditory",
        average_star_rating=4.9,
        completed_sessions=205,
        email="xander.mills@example.com",
        earnings=0.00,
        qualifications="MSc Computer Science",
        expertise="Data Structures, Algorithms",
        bio=("I am Xander Mills, an Auditory tutor with an MSc in Computer Science. I specialize in Data Structures and Algorithms, "
            "with 205 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t49)
    db.session.commit()
    tutors[49] = t49
    ts49 = [
        TutorSubject(tutor_id=t49.tutor_id, subject_id=subjects["Data Structures"].subject_id, price=42.00),
        TutorSubject(tutor_id=t49.tutor_id, subject_id=subjects["Algorithms"].subject_id, price=45.00)
    ]
    db.session.add_all(ts49)
    db.session.commit()
    tas49 = [
        TutorAvailableSlot(tutor_id=t49.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t49.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t49.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(12, 0, 0), end_time=dt.time(13, 0, 0)),
        TutorAvailableSlot(tutor_id=t49.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(15, 15, 0), end_time=dt.time(16, 15, 0))
    ]
    db.session.add_all(tas49)
    db.session.commit()

    # Tutor 50
    t50 = Tutor(
        name="Ethan Mitchell",
        preferred_language="English",
        teaching_style="Visual",
        average_star_rating=4.6,
        completed_sessions=150,
        email="ethan.mitchell@example.com",
        earnings=1200.00,
        qualifications='["PhD in Mathematics", "5 years tutoring experience"]',
        expertise="Calculus, Differential Equations",
        bio=("I am Ethan Mitchell, a Visual tutor with a PhD in Mathematics and 5 years of tutoring experience. I specialize in Calculus and Differential Equations, "
            "and have completed 150 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t50)
    db.session.commit()
    tutors[50] = t50
    ts50 = [
        TutorSubject(tutor_id=t50.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=45.00)
    ]
    db.session.add_all(ts50)
    db.session.commit()
    tas50 = [
        TutorAvailableSlot(tutor_id=t50.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t50.tutor_id, available_date=dt.datetime(2025, 4, 22), start_time=dt.time(10, 0, 0), end_time=dt.time(11, 0, 0)),
        TutorAvailableSlot(tutor_id=t50.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(12, 0, 0), end_time=dt.time(13, 0, 0)),
        TutorAvailableSlot(tutor_id=t50.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(tas50)
    db.session.commit()
    # TutorReviews for Tutor 50
    tr50 = [
        TutorReview(tutor_id=t50.tutor_id, student_name="John Doe", rating=5, comment="Great explanations!"),
        TutorReview(tutor_id=t50.tutor_id, student_name="Emma Davis", rating=1, comment="Very bad.")
    ]
    db.session.add_all(tr50)
    db.session.commit()

    # Tutor 51
    t51 = Tutor(
        name="Sophia Anderson",
        preferred_language="English",
        teaching_style="Visual",
        average_star_rating=4.7,
        completed_sessions=180,
        email="sophia.anderson@example.com",
        earnings=1400.00,
        qualifications='["MSc in Applied Mathematics", "Former University Lecturer"]',
        expertise="Calculus, Algebra",
        bio=("I am Sophia Anderson, a Visual tutor with an MSc in Applied Mathematics and former university lecturer experience. I specialize in Calculus and Algebra, "
            "with 180 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t51)
    db.session.commit()
    tutors[51] = t51
    ts51 = [
        TutorSubject(tutor_id=t51.tutor_id, subject_id=subjects["Calculus 1"].subject_id, price=40.00)
    ]
    db.session.add_all(ts51)
    db.session.commit()
    tas51 = [
        TutorAvailableSlot(tutor_id=t51.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t51.tutor_id, available_date=dt.datetime(2025, 4, 30), start_time=dt.time(9, 30, 0), end_time=dt.time(10, 30, 0)),
        TutorAvailableSlot(tutor_id=t51.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0)),
        TutorAvailableSlot(tutor_id=t51.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(tas51)
    db.session.commit()
    # TutorReview for Tutor 51
    tr51 = [
        TutorReview(tutor_id=t51.tutor_id, student_name="Olivia Turner", rating=4.7, comment="Patient and detailed explanations.")
    ]
    db.session.add_all(tr51)
    db.session.commit()

    # Tutor 52
    t52 = Tutor(
        name="Liam Carter",
        preferred_language="English",
        teaching_style="Visual",
        average_star_rating=4.8,
        completed_sessions=200,
        email="liam.carter@example.com",
        earnings=1600.00,
        qualifications='["MSc in Data Science", "Google ML Certification"]',
        expertise="Machine Learning, Python, AI",
        bio=("I am Liam Carter, a Visual tutor with an MSc in Data Science and Google ML Certification. I specialize in Machine Learning, Python, and AI, "
            "and have completed 200 sessions."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t52)
    db.session.commit()
    tutors[52] = t52
    ts52 = [
        TutorSubject(tutor_id=t52.tutor_id, subject_id=subjects["Machine Learning"].subject_id, price=50.00)
    ]
    db.session.add_all(ts52)
    db.session.commit()
    tas52 = [
        TutorAvailableSlot(tutor_id=t52.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t52.tutor_id, available_date=dt.datetime(2025, 4, 22), start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0)),
        TutorAvailableSlot(tutor_id=t52.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(13, 0, 0), end_time=dt.time(14, 0, 0)),
        TutorAvailableSlot(tutor_id=t52.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(tas52)
    db.session.commit()
    # TutorReview for Tutor 52
    tr52 = [
        TutorReview(tutor_id=t52.tutor_id, student_name="Jane Smith", rating=4.8, comment="Very patient and clear.")
    ]
    db.session.add_all(tr52)
    db.session.commit()

    # Tutor 53
    t53 = Tutor(
        name="Olivia Johnson",
        preferred_language="English",
        teaching_style="Visual",
        average_star_rating=4.9,
        completed_sessions=170,
        email="olivia.johnson@example.com",
        earnings=1800.00,
        qualifications='["PhD in Computer Science", "10 years experience in AI"]',
        expertise="Deep Learning, TensorFlow, CNNs",
        bio=("I am Olivia Johnson, a Visual tutor with a PhD in Computer Science and 10 years of experience in AI. I specialize in Deep Learning, TensorFlow, and CNNs, "
            "with 170 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t53)
    db.session.commit()
    tutors[53] = t53
    ts53 = [
        TutorSubject(tutor_id=t53.tutor_id, subject_id=subjects["Deep Learning"].subject_id, price=60.00)
    ]
    db.session.add_all(ts53)
    db.session.commit()
    tas53 = [
        TutorAvailableSlot(tutor_id=t53.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t53.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(12, 0, 0), end_time=dt.time(13, 0, 0)),
        TutorAvailableSlot(tutor_id=t53.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(9, 30, 0), end_time=dt.time(10, 30, 0)),
        TutorAvailableSlot(tutor_id=t53.tutor_id, available_date=dt.datetime(2025, 4, 27), start_time=dt.time(14, 15, 0), end_time=dt.time(15, 15, 0))
    ]
    db.session.add_all(tas53)
    db.session.commit()
    # TutorReview for Tutor 53
    tr53 = [
        TutorReview(tutor_id=t53.tutor_id, student_name="David Brown", rating=4.7, comment="Super knowledgeable about ML models.")
    ]
    db.session.add_all(tr53)
    db.session.commit()

    # Tutor 54
    t54 = Tutor(
        name="Noah Williams",
        preferred_language="English",
        teaching_style="Visual",
        average_star_rating=2.0,
        completed_sessions=190,
        email="noah.williams@example.com",
        earnings=1500.00,
        qualifications='["BSc in Computer Science", "Competitive Programming Coach"]',
        expertise="Data Structures, Algorithms, Java",
        bio=("I am Noah Williams, a Visual tutor with a BSc in Computer Science and experience as a competitive programming coach. I specialize in Data Structures, Algorithms, and Java, "
            "with 190 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t54)
    db.session.commit()
    tutors[54] = t54
    ts54 = [
        TutorSubject(tutor_id=t54.tutor_id, subject_id=subjects["Data Structures and Algorithms"].subject_id, price=55.00)
    ]
    db.session.add_all(ts54)
    db.session.commit()
    tas54 = [
        TutorAvailableSlot(tutor_id=t54.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t54.tutor_id, available_date=dt.datetime(2025, 4, 24), start_time=dt.time(10, 0, 0), end_time=dt.time(11, 0, 0)),
        TutorAvailableSlot(tutor_id=t54.tutor_id, available_date=dt.datetime(2025, 4, 26), start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0)),
        TutorAvailableSlot(tutor_id=t54.tutor_id, available_date=dt.datetime(2025, 4, 29), start_time=dt.time(9, 30, 0), end_time=dt.time(10, 30, 0))
    ]
    db.session.add_all(tas54)
    db.session.commit()
    # TutorReview for Tutor 54
    tr54 = [
        TutorReview(tutor_id=t54.tutor_id, student_name="Lucas Wright", rating=4.7, comment="Amazing teaching methods for deep learning.")
    ]
    db.session.add_all(tr54)
    db.session.commit()

    # Tutor 55
    t55 = Tutor(
        name="Bethany Cox",
        preferred_language="Spanish",
        teaching_style="Visual",
        average_star_rating=4.4,
        completed_sessions=140,
        email="bethany.cox3@example.com",
        earnings=0.00,
        qualifications="BA Computer Science",
        expertise="Calculus, Data Structures",
        bio=("I am Bethany Cox, a Visual tutor with a BA in Computer Science. I specialize in Calculus and Data Structures, "
            "with 140 sessions completed."),
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78"
    )
    db.session.add(t55)
    db.session.commit()
    tutors[55] = t55
    ts55 = [
        TutorSubject(tutor_id=t55.tutor_id, subject_id=subjects["Calculus 2"].subject_id, price=44.00),
        TutorSubject(tutor_id=t55.tutor_id, subject_id=subjects["Linear Regression"].subject_id, price=40.00)
    ]
    db.session.add_all(ts55)
    db.session.commit()
    tas55 = [
        TutorAvailableSlot(tutor_id=t55.tutor_id, available_date=dt.datetime(2025, 4, 21), start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        TutorAvailableSlot(tutor_id=t55.tutor_id, available_date=dt.datetime(2025, 4, 30), start_time=dt.time(8, 45, 0), end_time=dt.time(9, 45, 0)),
        TutorAvailableSlot(tutor_id=t55.tutor_id, available_date=dt.datetime(2025, 4, 23), start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        TutorAvailableSlot(tutor_id=t55.tutor_id, available_date=dt.datetime(2025, 4, 25), start_time=dt.time(13, 15, 0), end_time=dt.time(14, 15, 0))
    ]
    db.session.add_all(tas55)
    db.session.commit()

    # Inserting into Student table

    students = {}

    # Student 1
    st1 = Student(
        name="Adam Freeman",
        preferred_learning_style="Visual",
        preferred_language="English",
        budget=300.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="adam.freeman@example.com"
    )
    db.session.add(st1)
    db.session.commit()
    students[1] = st1
    ss1 = [
        StudentSubject(student_id=st1.student_id, subject_id=subjects["Calculus 2"].subject_id),
        StudentSubject(student_id=st1.student_id, subject_id=subjects["Physics"].subject_id)
    ]
    db.session.add_all(ss1)
    db.session.commit()
    sas1 = [
        StudentAvailableSlot(student_id=st1.student_id, available_date=dt.datetime(2025, 4, 21),
                              start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st1.student_id, available_date=dt.datetime(2025, 4, 30),
                              start_time=dt.time(8, 20, 0), end_time=dt.time(9, 20, 0)),
        StudentAvailableSlot(student_id=st1.student_id, available_date=dt.datetime(2025, 4, 24),
                              start_time=dt.time(10, 15, 0), end_time=dt.time(11, 15, 0))
    ]
    db.session.add_all(sas1)
    db.session.commit()
    slp1 = StudentLearningPath(student_id=st1.student_id, learning_item="Calculus 1", step_order=1)
    db.session.add(slp1)
    db.session.commit()

    # Student 2
    st2 = Student(
        name="Bella Knight",
        preferred_learning_style="Auditory",
        preferred_language="Spanish",
        budget=450.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="bella.knight@example.com"
    )
    db.session.add(st2)
    db.session.commit()
    students[2] = st2
    ss2 = [
        StudentSubject(student_id=st2.student_id, subject_id=subjects["Programming"].subject_id),
        StudentSubject(student_id=st2.student_id, subject_id=subjects["Data Structures"].subject_id)
    ]
    db.session.add_all(ss2)
    db.session.commit()
    sas2 = [
        StudentAvailableSlot(student_id=st2.student_id, available_date=dt.datetime(2025, 4, 21),
                              start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st2.student_id, available_date=dt.datetime(2025, 4, 22),
                              start_time=dt.time(9, 35, 0), end_time=dt.time(10, 35, 0)),
        StudentAvailableSlot(student_id=st2.student_id, available_date=dt.datetime(2025, 4, 25),
                              start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0))
    ]
    db.session.add_all(sas2)
    db.session.commit()

    # Student 3
    st3 = Student(
        name="Cody Long",
        preferred_learning_style="Visual",
        preferred_language="French",
        budget=500.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="cody.long@example.com"
    )
    db.session.add(st3)
    db.session.commit()
    students[3] = st3
    ss3 = [
        StudentSubject(student_id=st3.student_id, subject_id=subjects["Organic Chemistry"].subject_id),
        StudentSubject(student_id=st3.student_id, subject_id=subjects["Statistics"].subject_id)
    ]
    db.session.add_all(ss3)
    db.session.commit()
    sas3 = [
        StudentAvailableSlot(student_id=st3.student_id, available_date=dt.datetime(2025, 4, 21),
                              start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st3.student_id, available_date=dt.datetime(2025, 4, 23),
                              start_time=dt.time(10, 50, 0), end_time=dt.time(11, 50, 0)),
        StudentAvailableSlot(student_id=st3.student_id, available_date=dt.datetime(2025, 4, 26),
                              start_time=dt.time(14, 20, 0), end_time=dt.time(15, 20, 0))
    ]
    db.session.add_all(sas3)
    db.session.commit()
    slp3 = StudentLearningPath(student_id=st3.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp3)
    db.session.commit()

    # Student 4
    st4 = Student(
        name="Daisy Rivera",
        preferred_learning_style="Read/Write",
        preferred_language="German",
        budget=350.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="daisy.rivera@example.com"
    )
    db.session.add(st4)
    db.session.commit()
    students[4] = st4
    ss4 = [
        StudentSubject(student_id=st4.student_id, subject_id=subjects["Linear Regression"].subject_id),
        StudentSubject(student_id=st4.student_id, subject_id=subjects["Calculus 1"].subject_id)
    ]
    db.session.add_all(ss4)
    db.session.commit()
    sas4 = [
        StudentAvailableSlot(student_id=st4.student_id, available_date=dt.datetime(2025, 4, 21),
                              start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st4.student_id, available_date=dt.datetime(2025, 4, 24),
                              start_time=dt.time(11, 10, 0), end_time=dt.time(12, 10, 0)),
        StudentAvailableSlot(student_id=st4.student_id, available_date=dt.datetime(2025, 4, 27),
                              start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(sas4)
    db.session.commit()

    # Student 5
    st5 = Student(
        name="Evan Stone",
        preferred_learning_style="Auditory",
        preferred_language="Arabic",
        budget=600.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="evan.stone@example.com"
    )
    db.session.add(st5)
    db.session.commit()
    students[5] = st5
    ss5 = [
        StudentSubject(student_id=st5.student_id, subject_id=subjects["Machine Learning"].subject_id),
        StudentSubject(student_id=st5.student_id, subject_id=subjects["Algorithms"].subject_id)
    ]
    db.session.add_all(ss5)
    db.session.commit()
    sas5 = [
        StudentAvailableSlot(student_id=st5.student_id, available_date=dt.datetime(2025, 4, 21),
                              start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st5.student_id, available_date=dt.datetime(2025, 4, 25),
                              start_time=dt.time(13, 20, 0), end_time=dt.time(14, 20, 0)),
        StudentAvailableSlot(student_id=st5.student_id, available_date=dt.datetime(2025, 4, 28),
                              start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(sas5)
    db.session.commit()
    slp5 = StudentLearningPath(student_id=st5.student_id, learning_item="Data Structures", step_order=1)
    db.session.add(slp5)
    db.session.commit()

    # Student 6
    st6 = Student(
        name="Faye Murphy",
        preferred_learning_style="Visual",
        preferred_language="English",
        budget=275.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="faye.murphy@example.com"
    )
    db.session.add(st6)
    db.session.commit()
    students[6] = st6
    ss6 = [
        StudentSubject(student_id=st6.student_id, subject_id=subjects["Data Structures"].subject_id),
        StudentSubject(student_id=st6.student_id, subject_id=subjects["Programming"].subject_id)
    ]
    db.session.add_all(ss6)
    db.session.commit()
    sas6 = [
        StudentAvailableSlot(student_id=st6.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st6.student_id, available_date=dt.datetime(2025, 4, 30),
                            start_time=dt.time(9, 55, 0), end_time=dt.time(10, 55, 0)),
        StudentAvailableSlot(student_id=st6.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(10, 15, 0), end_time=dt.time(11, 15, 0))
    ]
    db.session.add_all(sas6)
    db.session.commit()

    # Student 7
    st7 = Student(
        name="Gavin Ross",
        preferred_learning_style="Read/Write",
        preferred_language="Spanish",
        budget=320.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="gavin.ross@example.com"
    )
    db.session.add(st7)
    db.session.commit()
    students[7] = st7
    ss7 = [
        StudentSubject(student_id=st7.student_id, subject_id=subjects["Physics"].subject_id),
        StudentSubject(student_id=st7.student_id, subject_id=subjects["Organic Chemistry"].subject_id)
    ]
    db.session.add_all(ss7)
    db.session.commit()
    sas7 = [
        StudentAvailableSlot(student_id=st7.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st7.student_id, available_date=dt.datetime(2025, 4, 22),
                            start_time=dt.time(10, 50, 0), end_time=dt.time(11, 50, 0)),
        StudentAvailableSlot(student_id=st7.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(11, 10, 0), end_time=dt.time(12, 10, 0))
    ]
    db.session.add_all(sas7)
    db.session.commit()
    slp7 = StudentLearningPath(student_id=st7.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp7)
    db.session.commit()

    # Student 8
    st8 = Student(
        name="Hazel Ford",
        preferred_learning_style="Auditory",
        preferred_language="French",
        budget=400.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="hazel.ford@example.com"
    )
    db.session.add(st8)
    db.session.commit()
    students[8] = st8
    ss8 = [
        StudentSubject(student_id=st8.student_id, subject_id=subjects["Calculus 1"].subject_id),
        StudentSubject(student_id=st8.student_id, subject_id=subjects["Linear Regression"].subject_id)
    ]
    db.session.add_all(ss8)
    db.session.commit()
    sas8 = [
        StudentAvailableSlot(student_id=st8.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st8.student_id, available_date=dt.datetime(2025, 4, 23),
                            start_time=dt.time(10, 5, 0), end_time=dt.time(11, 5, 0)),
        StudentAvailableSlot(student_id=st8.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(11, 50, 0), end_time=dt.time(12, 50, 0))
    ]
    db.session.add_all(sas8)
    db.session.commit()
    slp8 = StudentLearningPath(student_id=st8.student_id, learning_item="Algebra", step_order=1)
    db.session.add(slp8)
    db.session.commit()

    # Student 9
    st9 = Student(
        name="Isaiah Wood",
        preferred_learning_style="Visual",
        preferred_language="German",
        budget=550.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="isaiah.wood@example.com"
    )
    db.session.add(st9)
    db.session.commit()
    students[9] = st9
    ss9 = [
        StudentSubject(student_id=st9.student_id, subject_id=subjects["Programming"].subject_id),
        StudentSubject(student_id=st9.student_id, subject_id=subjects["Machine Learning"].subject_id)
    ]
    db.session.add_all(ss9)
    db.session.commit()
    sas9 = [
        StudentAvailableSlot(student_id=st9.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st9.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(15, 5, 0), end_time=dt.time(16, 5, 0)),
        StudentAvailableSlot(student_id=st9.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(10, 15, 0), end_time=dt.time(11, 15, 0))
    ]
    db.session.add_all(sas9)
    db.session.commit()
    slp9 = StudentLearningPath(student_id=st9.student_id, learning_item="Data Structures", step_order=1)
    db.session.add(slp9)
    db.session.commit()

    # Student 10
    st10 = Student(
        name="Jasmine Bell",
        preferred_learning_style="Read/Write",
        preferred_language="Arabic",
        budget=480.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="jasmine.bell@example.com"
    )
    db.session.add(st10)
    db.session.commit()
    students[10] = st10
    ss10 = [
        StudentSubject(student_id=st10.student_id, subject_id=subjects["Statistics"].subject_id),
        StudentSubject(student_id=st10.student_id, subject_id=subjects["Data Structures"].subject_id)
    ]
    db.session.add_all(ss10)
    db.session.commit()
    sas10 = [
        StudentAvailableSlot(student_id=st10.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st10.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(9, 10, 0), end_time=dt.time(10, 10, 0)),
        StudentAvailableSlot(student_id=st10.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0))
    ]
    db.session.add_all(sas10)
    db.session.commit()

    # Student 11
    st11 = Student(
        name="Kyle Brooks",
        preferred_learning_style="Auditory",
        preferred_language="English",
        budget=390.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="kyle.brooks@example.com"
    )
    db.session.add(st11)
    db.session.commit()
    students[11] = st11
    ss11 = [
        StudentSubject(student_id=st11.student_id, subject_id=subjects["Organic Chemistry"].subject_id),
        StudentSubject(student_id=st11.student_id, subject_id=subjects["Physics"].subject_id)
    ]
    db.session.add_all(ss11)
    db.session.commit()
    sas11 = [
        StudentAvailableSlot(student_id=st11.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st11.student_id, available_date=dt.datetime(2025, 4, 30),
                            start_time=dt.time(11, 10, 0), end_time=dt.time(12, 10, 0)),
        StudentAvailableSlot(student_id=st11.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0))
    ]
    db.session.add_all(sas11)
    db.session.commit()
    slp11 = StudentLearningPath(student_id=st11.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp11)
    db.session.commit()

    # Student 12
    st12 = Student(
        name="Lola Hayes",
        preferred_learning_style="Visual",
        preferred_language="Spanish",
        budget=310.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="lola.hayes@example.com"
    )
    db.session.add(st12)
    db.session.commit()
    students[12] = st12
    ss12 = [
        StudentSubject(student_id=st12.student_id, subject_id=subjects["Calculus 2"].subject_id),
        StudentSubject(student_id=st12.student_id, subject_id=subjects["Programming"].subject_id)
    ]
    db.session.add_all(ss12)
    db.session.commit()
    sas12 = [
        StudentAvailableSlot(student_id=st12.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st12.student_id, available_date=dt.datetime(2025, 4, 22),
                            start_time=dt.time(10, 50, 0), end_time=dt.time(11, 50, 0)),
        StudentAvailableSlot(student_id=st12.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0))
    ]
    db.session.add_all(sas12)
    db.session.commit()
    slp12 = StudentLearningPath(student_id=st12.student_id, learning_item="Calculus 1", step_order=1)
    db.session.add(slp12)
    db.session.commit()

    # Student 13
    st13 = Student(
        name="Mason Reed",
        preferred_learning_style="Read/Write",
        preferred_language="French",
        budget=525.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="mason.reed@example.com"
    )
    db.session.add(st13)
    db.session.commit()
    students[13] = st13
    ss13 = [
        StudentSubject(student_id=st13.student_id, subject_id=subjects["Data Structures"].subject_id),
        StudentSubject(student_id=st13.student_id, subject_id=subjects["Algorithms"].subject_id)
    ]
    db.session.add_all(ss13)
    db.session.commit()
    sas13 = [
        StudentAvailableSlot(student_id=st13.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st13.student_id, available_date=dt.datetime(2025, 4, 23),
                            start_time=dt.time(12, 5, 0), end_time=dt.time(13, 5, 0)),
        StudentAvailableSlot(student_id=st13.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(14, 30, 0), end_time=dt.time(15, 30, 0))
    ]
    db.session.add_all(sas13)
    db.session.commit()

    # Student 14
    st14 = Student(
        name="Nina Foster",
        preferred_learning_style="Auditory",
        preferred_language="German",
        budget=430.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="nina.foster@example.com"
    )
    db.session.add(st14)
    db.session.commit()
    students[14] = st14
    ss14 = [
        StudentSubject(student_id=st14.student_id, subject_id=subjects["Machine Learning"].subject_id),
        StudentSubject(student_id=st14.student_id, subject_id=subjects["Statistics"].subject_id)
    ]
    db.session.add_all(ss14)
    db.session.commit()
    sas14 = [
        StudentAvailableSlot(student_id=st14.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st14.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(12, 25, 0), end_time=dt.time(13, 25, 0)),
        StudentAvailableSlot(student_id=st14.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(14, 45, 0), end_time=dt.time(15, 45, 0))
    ]
    db.session.add_all(sas14)
    db.session.commit()
    slp14 = StudentLearningPath(student_id=st14.student_id, learning_item="Data Structures", step_order=1)
    db.session.add(slp14)
    db.session.commit()

    # Student 15
    st15 = Student(
        name="Owen Price",
        preferred_learning_style="Visual",
        preferred_language="Arabic",
        budget=365.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="owen.price@example.com"
    )
    db.session.add(st15)
    db.session.commit()
    students[15] = st15
    ss15 = [
        StudentSubject(student_id=st15.student_id, subject_id=subjects["Linear Regression"].subject_id),
        StudentSubject(student_id=st15.student_id, subject_id=subjects["Organic Chemistry"].subject_id)
    ]
    db.session.add_all(ss15)
    db.session.commit()
    sas15 = [
        StudentAvailableSlot(student_id=st15.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st15.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(10, 0, 0), end_time=dt.time(11, 0, 0)),
        StudentAvailableSlot(student_id=st15.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0))
    ]
    db.session.add_all(sas15)
    db.session.commit()
    slp15 = StudentLearningPath(student_id=st15.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp15)
    db.session.commit()

    # Student 16
    st16 = Student(
        name="Paige Hunter",
        preferred_learning_style="Read/Write",
        preferred_language="English",
        budget=295.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="paige.hunter@example.com"
    )
    db.session.add(st16)
    db.session.commit()
    students[16] = st16
    ss16 = [
        StudentSubject(student_id=st16.student_id, subject_id=subjects["Programming"].subject_id),
        StudentSubject(student_id=st16.student_id, subject_id=subjects["Calculus 2"].subject_id)
    ]
    db.session.add_all(ss16)
    db.session.commit()
    sas16 = [
        StudentAvailableSlot(student_id=st16.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st16.student_id, available_date=dt.datetime(2025, 4, 30),
                            start_time=dt.time(11, 10, 0), end_time=dt.time(12, 10, 0)),
        StudentAvailableSlot(student_id=st16.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(12, 45, 0), end_time=dt.time(13, 45, 0))
    ]
    db.session.add_all(sas16)
    db.session.commit()
    slp16 = StudentLearningPath(student_id=st16.student_id, learning_item="Calculus 1", step_order=1)
    db.session.add(slp16)
    db.session.commit()

    # Student 17
    st17 = Student(
        name="Quinn Martin",
        preferred_learning_style="Auditory",
        preferred_language="Spanish",
        budget=410.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="quinn.martin@example.com"
    )
    db.session.add(st17)
    db.session.commit()
    students[17] = st17
    ss17 = [
        StudentSubject(student_id=st17.student_id, subject_id=subjects["Physics"].subject_id),
        StudentSubject(student_id=st17.student_id, subject_id=subjects["Machine Learning"].subject_id)
    ]
    db.session.add_all(ss17)
    db.session.commit()
    sas17 = [
        StudentAvailableSlot(student_id=st17.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st17.student_id, available_date=dt.datetime(2025, 4, 22),
                            start_time=dt.time(14, 5, 0), end_time=dt.time(15, 5, 0)),
        StudentAvailableSlot(student_id=st17.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0))
    ]
    db.session.add_all(sas17)
    db.session.commit()
    slp17 = StudentLearningPath(student_id=st17.student_id, learning_item="Calculus 2", step_order=1)
    db.session.add(slp17)
    db.session.commit()

    # Student 18
    st18 = Student(
        name="Riley Diaz",
        preferred_learning_style="Visual",
        preferred_language="French",
        budget=520.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="riley.diaz@example.com"
    )
    db.session.add(st18)
    db.session.commit()
    students[18] = st18
    ss18 = [
        StudentSubject(student_id=st18.student_id, subject_id=subjects["Data Structures"].subject_id),
        StudentSubject(student_id=st18.student_id, subject_id=subjects["Algorithms"].subject_id)
    ]
    db.session.add_all(ss18)
    db.session.commit()
    sas18 = [
        StudentAvailableSlot(student_id=st18.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st18.student_id, available_date=dt.datetime(2025, 4, 23),
                            start_time=dt.time(16, 20, 0), end_time=dt.time(17, 20, 0)),
        StudentAvailableSlot(student_id=st18.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(10, 5, 0), end_time=dt.time(11, 5, 0))
    ]
    db.session.add_all(sas18)
    db.session.commit()
    slp18 = StudentLearningPath(student_id=st18.student_id, learning_item="Data Structures", step_order=1)
    db.session.add(slp18)
    db.session.commit()

    # Student 19
    st19 = Student(
        name="Sophia Carter",
        preferred_learning_style="Read/Write",
        preferred_language="German",
        budget=350.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="sophia.carter@example.com"
    )
    db.session.add(st19)
    db.session.commit()
    students[19] = st19
    ss19 = [
        StudentSubject(student_id=st19.student_id, subject_id=subjects["Organic Chemistry"].subject_id),
        StudentSubject(student_id=st19.student_id, subject_id=subjects["Statistics"].subject_id)
    ]
    db.session.add_all(ss19)
    db.session.commit()
    sas19 = [
        StudentAvailableSlot(student_id=st19.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st19.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(9, 35, 0), end_time=dt.time(10, 35, 0)),
        StudentAvailableSlot(student_id=st19.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0))
    ]
    db.session.add_all(sas19)
    db.session.commit()
    slp19 = StudentLearningPath(student_id=st19.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp19)
    db.session.commit()

    # Student 20
    st20 = Student(
        name="Tyler Reed",
        preferred_learning_style="Auditory",
        preferred_language="Arabic",
        budget=380.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="tyler.reed@example.com"
    )
    db.session.add(st20)
    db.session.commit()
    students[20] = st20
    ss20 = [
        StudentSubject(student_id=st20.student_id, subject_id=subjects["Calculus 1"].subject_id),
        StudentSubject(student_id=st20.student_id, subject_id=subjects["Linear Regression"].subject_id)
    ]
    db.session.add_all(ss20)
    db.session.commit()
    sas20 = [
        StudentAvailableSlot(student_id=st20.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st20.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(12, 35, 0), end_time=dt.time(13, 35, 0)),
        StudentAvailableSlot(student_id=st20.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(11, 10, 0), end_time=dt.time(12, 10, 0))
    ]
    db.session.add_all(sas20)
    db.session.commit()
    slp20 = StudentLearningPath(student_id=st20.student_id, learning_item="Algebra", step_order=1)
    db.session.add(slp20)
    db.session.commit()

    # Student 21
    st21 = Student(
        name="Uma Stevens",
        preferred_learning_style="Visual",
        preferred_language="English",
        budget=465.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="uma.stevens@example.com"
    )
    db.session.add(st21)
    db.session.commit()
    students[21] = st21
    ss21 = [
        StudentSubject(student_id=st21.student_id, subject_id=subjects["Programming"].subject_id),
        StudentSubject(student_id=st21.student_id, subject_id=subjects["Machine Learning"].subject_id)
    ]
    db.session.add_all(ss21)
    db.session.commit()
    sas21 = [
        StudentAvailableSlot(student_id=st21.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st21.student_id, available_date=dt.datetime(2025, 4, 30),
                            start_time=dt.time(10, 5, 0), end_time=dt.time(11, 5, 0)),
        StudentAvailableSlot(student_id=st21.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(11, 45, 0), end_time=dt.time(12, 45, 0))
    ]
    db.session.add_all(sas21)
    db.session.commit()
    slp21 = StudentLearningPath(student_id=st21.student_id, learning_item="Data Structures", step_order=1)
    db.session.add(slp21)
    db.session.commit()

    # Student 22
    st22 = Student(
        name="Victor Chavez",
        preferred_learning_style="Read/Write",
        preferred_language="Spanish",
        budget=540.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="victor.chavez@example.com"
    )
    db.session.add(st22)
    db.session.commit()
    students[22] = st22
    ss22 = [
        StudentSubject(student_id=st22.student_id, subject_id=subjects["Data Structures"].subject_id),
        StudentSubject(student_id=st22.student_id, subject_id=subjects["Algorithms"].subject_id)
    ]
    db.session.add_all(ss22)
    db.session.commit()
    sas22 = [
        StudentAvailableSlot(student_id=st22.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st22.student_id, available_date=dt.datetime(2025, 4, 22),
                            start_time=dt.time(10, 50, 0), end_time=dt.time(11, 50, 0)),
        StudentAvailableSlot(student_id=st22.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0))
    ]
    db.session.add_all(sas22)
    db.session.commit()

    # Student 23
    st23 = Student(
        name="Wendy Rivera",
        preferred_learning_style="Auditory",
        preferred_language="French",
        budget=330.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="wendy.rivera@example.com"
    )
    db.session.add(st23)
    db.session.commit()
    students[23] = st23
    ss23 = [
        StudentSubject(student_id=st23.student_id, subject_id=subjects["Organic Chemistry"].subject_id),
        StudentSubject(student_id=st23.student_id, subject_id=subjects["Physics"].subject_id)
    ]
    db.session.add_all(ss23)
    db.session.commit()
    sas23 = [
        StudentAvailableSlot(student_id=st23.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st23.student_id, available_date=dt.datetime(2025, 4, 23),
                            start_time=dt.time(13, 50, 0), end_time=dt.time(14, 50, 0)),
        StudentAvailableSlot(student_id=st23.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(10, 5, 0), end_time=dt.time(11, 5, 0))
    ]
    db.session.add_all(sas23)
    db.session.commit()
    slp23 = StudentLearningPath(student_id=st23.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp23)
    db.session.commit()

    # Student 24
    st24 = Student(
        name="Xavier Ortiz",
        preferred_learning_style="Visual",
        preferred_language="German",
        budget=475.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="xavier.ortiz@example.com"
    )
    db.session.add(st24)
    db.session.commit()
    students[24] = st24
    ss24 = [
        StudentSubject(student_id=st24.student_id, subject_id=subjects["Calculus 2"].subject_id),
        StudentSubject(student_id=st24.student_id, subject_id=subjects["Programming"].subject_id)
    ]
    db.session.add_all(ss24)
    db.session.commit()
    sas24 = [
        StudentAvailableSlot(student_id=st24.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st24.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(10, 30, 0), end_time=dt.time(11, 30, 0)),
        StudentAvailableSlot(student_id=st24.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0))
    ]
    db.session.add_all(sas24)
    db.session.commit()
    slp24 = StudentLearningPath(student_id=st24.student_id, learning_item="Calculus 1", step_order=1)
    db.session.add(slp24)
    db.session.commit()

    # Student 25
    st25 = Student(
        name="Yara Morales",
        preferred_learning_style="Read/Write",
        preferred_language="Arabic",
        budget=520.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="yara.morales@example.com"
    )
    db.session.add(st25)
    db.session.commit()
    students[25] = st25
    ss25 = [
        StudentSubject(student_id=st25.student_id, subject_id=subjects["Machine Learning"].subject_id),
        StudentSubject(student_id=st25.student_id, subject_id=subjects["Data Structures"].subject_id)
    ]
    db.session.add_all(ss25)
    db.session.commit()
    sas25 = [
        StudentAvailableSlot(student_id=st25.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st25.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0)),
        StudentAvailableSlot(student_id=st25.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0))
    ]
    db.session.add_all(sas25)
    db.session.commit()
    slp25 = StudentLearningPath(student_id=st25.student_id, learning_item="Data Structures", step_order=1)
    db.session.add(slp25)
    db.session.commit()

    # Student 26
    st26 = Student(
        name="Zack Henderson",
        preferred_learning_style="Auditory",
        preferred_language="English",
        budget=400.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="zack.henderson@example.com"
    )
    db.session.add(st26)
    db.session.commit()
    students[26] = st26
    ss26 = [
        StudentSubject(student_id=st26.student_id, subject_id=subjects["Algorithms"].subject_id),
        StudentSubject(student_id=st26.student_id, subject_id=subjects["Statistics"].subject_id)
    ]
    db.session.add_all(ss26)
    db.session.commit()
    sas26 = [
        StudentAvailableSlot(student_id=st26.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st26.student_id, available_date=dt.datetime(2025, 4, 30),
                            start_time=dt.time(15, 5, 0), end_time=dt.time(16, 5, 0)),
        StudentAvailableSlot(student_id=st26.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(10, 50, 0), end_time=dt.time(11, 50, 0))
    ]
    db.session.add_all(sas26)
    db.session.commit()

    # Student 27
    st27 = Student(
        name="Abby Powell",
        preferred_learning_style="Visual",
        preferred_language="Spanish",
        budget=360.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="abby.powell@example.com"
    )
    db.session.add(st27)
    db.session.commit()
    students[27] = st27
    ss27 = [
        StudentSubject(student_id=st27.student_id, subject_id=subjects["Organic Chemistry"].subject_id),
        StudentSubject(student_id=st27.student_id, subject_id=subjects["Calculus 1"].subject_id)
    ]
    db.session.add_all(ss27)
    db.session.commit()
    sas27 = [
        StudentAvailableSlot(student_id=st27.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st27.student_id, available_date=dt.datetime(2025, 4, 22),
                            start_time=dt.time(12, 5, 0), end_time=dt.time(13, 5, 0)),
        StudentAvailableSlot(student_id=st27.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(11, 10, 0), end_time=dt.time(12, 10, 0))
    ]
    db.session.add_all(sas27)
    db.session.commit()
    slp27 = StudentLearningPath(student_id=st27.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp27)
    db.session.commit()

    # Student 28
    st28 = Student(
        name="Blake Jenkins",
        preferred_learning_style="Read/Write",
        preferred_language="French",
        budget=495.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="blake.jenkins@example.com"
    )
    db.session.add(st28)
    db.session.commit()
    students[28] = st28
    ss28 = [
        StudentSubject(student_id=st28.student_id, subject_id=subjects["Programming"].subject_id),
        StudentSubject(student_id=st28.student_id, subject_id=subjects["Data Structures"].subject_id)
    ]
    db.session.add_all(ss28)
    db.session.commit()
    sas28 = [
        StudentAvailableSlot(student_id=st28.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st28.student_id, available_date=dt.datetime(2025, 4, 23),
                            start_time=dt.time(10, 5, 0), end_time=dt.time(11, 5, 0)),
        StudentAvailableSlot(student_id=st28.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0))
    ]
    db.session.add_all(sas28)
    db.session.commit()

    # Student 29
    st29 = Student(
        name="Casey Riley",
        preferred_learning_style="Auditory",
        preferred_language="German",
        budget=415.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="casey.riley@example.com"
    )
    db.session.add(st29)
    db.session.commit()
    students[29] = st29
    ss29 = [
        StudentSubject(student_id=st29.student_id, subject_id=subjects["Physics"].subject_id),
        StudentSubject(student_id=st29.student_id, subject_id=subjects["Machine Learning"].subject_id)
    ]
    db.session.add_all(ss29)
    db.session.commit()
    sas29 = [
        StudentAvailableSlot(student_id=st29.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st29.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(14, 30, 0), end_time=dt.time(15, 30, 0)),
        StudentAvailableSlot(student_id=st29.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(10, 50, 0), end_time=dt.time(11, 50, 0))
    ]
    db.session.add_all(sas29)
    db.session.commit()
    slp29 = StudentLearningPath(student_id=st29.student_id, learning_item="Calculus 2", step_order=1)
    db.session.add(slp29)
    db.session.commit()

    # Student 30
    st30 = Student(
        name="Derek Alexander",
        preferred_learning_style="Visual",
        preferred_language="Arabic",
        budget=385.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="derek.alexander@example.com"
    )
    db.session.add(st30)
    db.session.commit()
    students[30] = st30
    ss30 = [
        StudentSubject(student_id=st30.student_id, subject_id=subjects["Linear Regression"].subject_id),
        StudentSubject(student_id=st30.student_id, subject_id=subjects["Algorithms"].subject_id)
    ]
    db.session.add_all(ss30)
    db.session.commit()
    sas30 = [
        StudentAvailableSlot(student_id=st30.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st30.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(9, 40, 0), end_time=dt.time(10, 40, 0)),
        StudentAvailableSlot(student_id=st30.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0))
    ]
    db.session.add_all(sas30)
    db.session.commit()
    slp30 = StudentLearningPath(student_id=st30.student_id, learning_item="Algebra", step_order=1)
    db.session.add(slp30)
    db.session.commit()

    # Student 31
    st31 = Student(
        name="Elena Torres",
        preferred_learning_style="Read/Write",
        preferred_language="English",
        budget=430.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="elena.torres@example.com"
    )
    db.session.add(st31)
    db.session.commit()
    students[31] = st31
    ss31 = [
        StudentSubject(student_id=st31.student_id, subject_id=subjects["Data Structures"].subject_id),
        StudentSubject(student_id=st31.student_id, subject_id=subjects["Programming"].subject_id)
    ]
    db.session.add_all(ss31)
    db.session.commit()
    sas31 = [
        StudentAvailableSlot(student_id=st31.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st31.student_id, available_date=dt.datetime(2025, 4, 30),
                            start_time=dt.time(11, 10, 0), end_time=dt.time(12, 10, 0)),
        StudentAvailableSlot(student_id=st31.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0))
    ]
    db.session.add_all(sas31)
    db.session.commit()

    # Student 32
    st32 = Student(
        name="Felix Burns",
        preferred_learning_style="Auditory",
        preferred_language="Spanish",
        budget=375.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="felix.burns@example.com"
    )
    db.session.add(st32)
    db.session.commit()
    students[32] = st32
    ss32 = [
        StudentSubject(student_id=st32.student_id, subject_id=subjects["Organic Chemistry"].subject_id),
        StudentSubject(student_id=st32.student_id, subject_id=subjects["Statistics"].subject_id)
    ]
    db.session.add_all(ss32)
    db.session.commit()
    sas32 = [
        StudentAvailableSlot(student_id=st32.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st32.student_id, available_date=dt.datetime(2025, 4, 22),
                            start_time=dt.time(10, 50, 0), end_time=dt.time(11, 50, 0)),
        StudentAvailableSlot(student_id=st32.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0))
    ]
    db.session.add_all(sas32)
    db.session.commit()
    slp32 = StudentLearningPath(student_id=st32.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp32)
    db.session.commit()

    # Student 33
    st33 = Student(
        name="Gia Freeman",
        preferred_learning_style="Visual",
        preferred_language="French",
        budget=455.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="gia.freeman@example.com"
    )
    db.session.add(st33)
    db.session.commit()
    students[33] = st33
    ss33 = [
        StudentSubject(student_id=st33.student_id, subject_id=subjects["Calculus 1"].subject_id),
        StudentSubject(student_id=st33.student_id, subject_id=subjects["Linear Regression"].subject_id)
    ]
    db.session.add_all(ss33)
    db.session.commit()
    sas33 = [
        StudentAvailableSlot(student_id=st33.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st33.student_id, available_date=dt.datetime(2025, 4, 23),
                            start_time=dt.time(9, 35, 0), end_time=dt.time(10, 35, 0)),
        StudentAvailableSlot(student_id=st33.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0))
    ]
    db.session.add_all(sas33)
    db.session.commit()
    slp33 = StudentLearningPath(student_id=st33.student_id, learning_item="Algebra", step_order=1)
    db.session.add(slp33)
    db.session.commit()

    # Student 34
    st34 = Student(
        name="Hector Arnold",
        preferred_learning_style="Read/Write",
        preferred_language="German",
        budget=490.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="hector.arnold@example.com"
    )
    db.session.add(st34)
    db.session.commit()
    students[34] = st34
    ss34 = [
        StudentSubject(student_id=st34.student_id, subject_id=subjects["Programming"].subject_id),
        StudentSubject(student_id=st34.student_id, subject_id=subjects["Machine Learning"].subject_id)
    ]
    db.session.add_all(ss34)
    db.session.commit()
    sas34 = [
        StudentAvailableSlot(student_id=st34.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st34.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(12, 45, 0), end_time=dt.time(13, 45, 0)),
        StudentAvailableSlot(student_id=st34.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(sas34)
    db.session.commit()
    slp34 = StudentLearningPath(student_id=st34.student_id, learning_item="Data Structures", step_order=1)
    db.session.add(slp34)
    db.session.commit()

    # Student 35
    st35 = Student(
        name="Ivy Goodman",
        preferred_learning_style="Auditory",
        preferred_language="Arabic",
        budget=520.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="ivy.goodman@example.com"
    )
    db.session.add(st35)
    db.session.commit()
    students[35] = st35
    ss35 = [
        StudentSubject(student_id=st35.student_id, subject_id=subjects["Data Structures"].subject_id),
        StudentSubject(student_id=st35.student_id, subject_id=subjects["Algorithms"].subject_id)
    ]
    db.session.add_all(ss35)
    db.session.commit()
    sas35 = [
        StudentAvailableSlot(student_id=st35.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st35.student_id, available_date=dt.datetime(2025, 4, 22),
                            start_time=dt.time(10, 20, 0), end_time=dt.time(11, 20, 0)),
        StudentAvailableSlot(student_id=st35.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(11, 45, 0), end_time=dt.time(12, 45, 0))
    ]
    db.session.add_all(sas35)
    db.session.commit()

    # Student 36
    st36 = Student(
        name="Jonas Klein",
        preferred_learning_style="Visual",
        preferred_language="English",
        budget=360.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="jonas.klein@example.com"
    )
    db.session.add(st36)
    db.session.commit()
    students[36] = st36
    ss36 = [
        StudentSubject(student_id=st36.student_id, subject_id=subjects["Organic Chemistry"].subject_id),
        StudentSubject(student_id=st36.student_id, subject_id=subjects["Physics"].subject_id)
    ]
    db.session.add_all(ss36)
    db.session.commit()
    sas36 = [
        StudentAvailableSlot(student_id=st36.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st36.student_id, available_date=dt.datetime(2025, 4, 30),
                            start_time=dt.time(12, 35, 0), end_time=dt.time(13, 35, 0)),
        StudentAvailableSlot(student_id=st36.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(10, 50, 0), end_time=dt.time(11, 50, 0))
    ]
    db.session.add_all(sas36)
    db.session.commit()
    slp36 = StudentLearningPath(student_id=st36.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp36)
    db.session.commit()

    # Student 37
    st37 = Student(
        name="Kira Lane",
        preferred_learning_style="Read/Write",
        preferred_language="Spanish",
        budget=410.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="kira.lane@example.com"
    )
    db.session.add(st37)
    db.session.commit()
    students[37] = st37
    ss37 = [
        StudentSubject(student_id=st37.student_id, subject_id=subjects["Calculus 2"].subject_id),
        StudentSubject(student_id=st37.student_id, subject_id=subjects["Programming"].subject_id)
    ]
    db.session.add_all(ss37)
    db.session.commit()
    sas37 = [
        StudentAvailableSlot(student_id=st37.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st37.student_id, available_date=dt.datetime(2025, 4, 22),
                            start_time=dt.time(9, 35, 0), end_time=dt.time(10, 35, 0)),
        StudentAvailableSlot(student_id=st37.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(11, 10, 0), end_time=dt.time(12, 10, 0))
    ]
    db.session.add_all(sas37)
    db.session.commit()
    slp37 = StudentLearningPath(student_id=st37.student_id, learning_item="Calculus 1", step_order=1)
    db.session.add(slp37)
    db.session.commit()

    # Student 38
    st38 = Student(
        name="Liam Fox",
        preferred_learning_style="Auditory",
        preferred_language="French",
        budget=535.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="liam.fox@example.com"
    )
    db.session.add(st38)
    db.session.commit()
    students[38] = st38
    ss38 = [
        StudentSubject(student_id=st38.student_id, subject_id=subjects["Machine Learning"].subject_id),
        StudentSubject(student_id=st38.student_id, subject_id=subjects["Data Structures"].subject_id)
    ]
    db.session.add_all(ss38)
    db.session.commit()
    sas38 = [
        StudentAvailableSlot(student_id=st38.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st38.student_id, available_date=dt.datetime(2025, 4, 23),
                            start_time=dt.time(14, 20, 0), end_time=dt.time(15, 20, 0)),
        StudentAvailableSlot(student_id=st38.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(10, 5, 0), end_time=dt.time(11, 5, 0))
    ]
    db.session.add_all(sas38)
    db.session.commit()
    slp38 = StudentLearningPath(student_id=st38.student_id, learning_item="Data Structures", step_order=1)
    db.session.add(slp38)
    db.session.commit()

    # Student 39
    st39 = Student(
        name="Mia Summers",
        preferred_learning_style="Visual",
        preferred_language="German",
        budget=440.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="mia.summers@example.com"
    )
    db.session.add(st39)
    db.session.commit()
    students[39] = st39
    ss39 = [
        StudentSubject(student_id=st39.student_id, subject_id=subjects["Algorithms"].subject_id),
        StudentSubject(student_id=st39.student_id, subject_id=subjects["Statistics"].subject_id)
    ]
    db.session.add_all(ss39)
    db.session.commit()
    sas39 = [
        StudentAvailableSlot(student_id=st39.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st39.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(11, 30, 0), end_time=dt.time(12, 30, 0)),
        StudentAvailableSlot(student_id=st39.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(13, 15, 0), end_time=dt.time(14, 15, 0))
    ]
    db.session.add_all(sas39)
    db.session.commit()

    # Student 40
    st40 = Student(
        name="Noah Waters",
        preferred_learning_style="Read/Write",
        preferred_language="Arabic",
        budget=375.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="noah.waters@example.com"
    )
    db.session.add(st40)
    db.session.commit()
    students[40] = st40
    ss40 = [
        StudentSubject(student_id=st40.student_id, subject_id=subjects["Organic Chemistry"].subject_id),
        StudentSubject(student_id=st40.student_id, subject_id=subjects["Calculus 1"].subject_id)
    ]
    db.session.add_all(ss40)
    db.session.commit()
    sas40 = [
        StudentAvailableSlot(student_id=st40.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st40.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(13, 0, 0), end_time=dt.time(14, 0, 0)),
        StudentAvailableSlot(student_id=st40.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(10, 15, 0), end_time=dt.time(11, 15, 0))
    ]
    db.session.add_all(sas40)
    db.session.commit()
    slp40 = StudentLearningPath(student_id=st40.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp40)
    db.session.commit()

    # Student 41
    st41 = Student(
        name="Olivia West",
        preferred_learning_style="Auditory",
        preferred_language="English",
        budget=465.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="olivia.west@example.com"
    )
    db.session.add(st41)
    db.session.commit()
    students[41] = st41
    ss41 = [
        StudentSubject(student_id=st41.student_id, subject_id=subjects["Programming"].subject_id),
        StudentSubject(student_id=st41.student_id, subject_id=subjects["Data Structures"].subject_id)
    ]
    db.session.add_all(ss41)
    db.session.commit()
    sas41 = [
        StudentAvailableSlot(student_id=st41.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st41.student_id, available_date=dt.datetime(2025, 4, 30),
                            start_time=dt.time(10, 5, 0), end_time=dt.time(11, 5, 0)),
        StudentAvailableSlot(student_id=st41.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(11, 45, 0), end_time=dt.time(12, 45, 0))
    ]
    db.session.add_all(sas41)
    db.session.commit()

    # Student 42
    st42 = Student(
        name="Paul Douglas",
        preferred_learning_style="Visual",
        preferred_language="Spanish",
        budget=420.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="paul.douglas@example.com"
    )
    db.session.add(st42)
    db.session.commit()
    students[42] = st42
    ss42 = [
        StudentSubject(student_id=st42.student_id, subject_id=subjects["Physics"].subject_id),
        StudentSubject(student_id=st42.student_id, subject_id=subjects["Machine Learning"].subject_id)
    ]
    db.session.add_all(ss42)
    db.session.commit()
    sas42 = [
        StudentAvailableSlot(student_id=st42.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st42.student_id, available_date=dt.datetime(2025, 4, 22),
                            start_time=dt.time(14, 5, 0), end_time=dt.time(15, 5, 0)),
        StudentAvailableSlot(student_id=st42.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(11, 15, 0), end_time=dt.time(12, 15, 0))
    ]
    db.session.add_all(sas42)
    db.session.commit()
    slp42 = StudentLearningPath(student_id=st42.student_id, learning_item="Calculus", step_order=1)
    db.session.add(slp42)
    db.session.commit()

    # Student 43
    st43 = Student(
        name="Queenie Burns",
        preferred_learning_style="Read/Write",
        preferred_language="French",
        budget=535.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="queenie.burns@example.com"
    )
    db.session.add(st43)
    db.session.commit()
    students[43] = st43
    ss43 = [
        StudentSubject(student_id=st43.student_id, subject_id=subjects["Data Structures"].subject_id),
        StudentSubject(student_id=st43.student_id, subject_id=subjects["Algorithms"].subject_id)
    ]
    db.session.add_all(ss43)
    db.session.commit()
    sas43 = [
        StudentAvailableSlot(student_id=st43.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st43.student_id, available_date=dt.datetime(2025, 4, 23),
                            start_time=dt.time(11, 10, 0), end_time=dt.time(12, 10, 0)),
        StudentAvailableSlot(student_id=st43.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(13, 30, 0), end_time=dt.time(14, 30, 0))
    ]
    db.session.add_all(sas43)
    db.session.commit()

    # Student 44
    st44 = Student(
        name="Rachel Adams",
        preferred_learning_style="Auditory",
        preferred_language="English",
        budget=360.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="rachel.adams@example.com"
    )
    db.session.add(st44)
    db.session.commit()
    students[44] = st44
    ss44 = [
        StudentSubject(student_id=st44.student_id, subject_id=subjects["Organic Chemistry"].subject_id),
        StudentSubject(student_id=st44.student_id, subject_id=subjects["Statistics"].subject_id)
    ]
    db.session.add_all(ss44)
    db.session.commit()
    sas44 = [
        StudentAvailableSlot(student_id=st44.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st44.student_id, available_date=dt.datetime(2025, 4, 24),
                            start_time=dt.time(9, 5, 0), end_time=dt.time(10, 5, 0)),
        StudentAvailableSlot(student_id=st44.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0))
    ]
    db.session.add_all(sas44)
    db.session.commit()
    slp44 = StudentLearningPath(student_id=st44.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp44)
    db.session.commit()

    # Student 45
    st45 = Student(
        name="Steven Clark",
        preferred_learning_style="Read/Write",
        preferred_language="Spanish",
        budget=410.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="steven.clark@example.com"
    )
    db.session.add(st45)
    db.session.commit()
    students[45] = st45
    ss45 = [
        StudentSubject(student_id=st45.student_id, subject_id=subjects["Programming"].subject_id),
        StudentSubject(student_id=st45.student_id, subject_id=subjects["Data Structures"].subject_id)
    ]
    db.session.add_all(ss45)
    db.session.commit()
    sas45 = [
        StudentAvailableSlot(student_id=st45.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st45.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(10, 5, 0), end_time=dt.time(11, 5, 0)),
        StudentAvailableSlot(student_id=st45.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(11, 45, 0), end_time=dt.time(12, 45, 0))
    ]
    db.session.add_all(sas45)
    db.session.commit()

    # Student 46
    st46 = Student(
        name="Tara Lewis",
        preferred_learning_style="Visual",
        preferred_language="French",
        budget=395.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="tara.lewis@example.com"
    )
    db.session.add(st46)
    db.session.commit()
    students[46] = st46
    ss46 = [
        StudentSubject(student_id=st46.student_id, subject_id=subjects["Calculus 2"].subject_id),
        StudentSubject(student_id=st46.student_id, subject_id=subjects["Linear Regression"].subject_id)
    ]
    db.session.add_all(ss46)
    db.session.commit()
    sas46 = [
        StudentAvailableSlot(student_id=st46.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st46.student_id, available_date=dt.datetime(2025, 4, 26),
                            start_time=dt.time(11, 20, 0), end_time=dt.time(12, 20, 0)),
        StudentAvailableSlot(student_id=st46.student_id, available_date=dt.datetime(2025, 4, 28),
                            start_time=dt.time(14, 0, 0), end_time=dt.time(15, 0, 0))
    ]
    db.session.add_all(sas46)
    db.session.commit()
    slp46 = StudentLearningPath(student_id=st46.student_id, learning_item="Calculus 1", step_order=1)
    db.session.add(slp46)
    db.session.commit()

    # Student 47
    st47 = Student(
        name="Uma Patel",
        preferred_learning_style="Auditory",
        preferred_language="German",
        budget=425.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="uma.patel@example.com"
    )
    db.session.add(st47)
    db.session.commit()
    students[47] = st47
    ss47 = [
        StudentSubject(student_id=st47.student_id, subject_id=subjects["Machine Learning"].subject_id),
        StudentSubject(student_id=st47.student_id, subject_id=subjects["Algorithms"].subject_id)
    ]
    db.session.add_all(ss47)
    db.session.commit()
    sas47 = [
        StudentAvailableSlot(student_id=st47.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st47.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(12, 10, 0), end_time=dt.time(13, 10, 0)),
        StudentAvailableSlot(student_id=st47.student_id, available_date=dt.datetime(2025, 4, 29),
                            start_time=dt.time(15, 0, 0), end_time=dt.time(16, 0, 0))
    ]
    db.session.add_all(sas47)
    db.session.commit()
    slp47 = StudentLearningPath(student_id=st47.student_id, learning_item="Data Structures", step_order=1)
    db.session.add(slp47)
    db.session.commit()

    # Student 48
    st48 = Student(
        name="Victor King",
        preferred_learning_style="Read/Write",
        preferred_language="Arabic",
        budget=390.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="victor.king@example.com"
    )
    db.session.add(st48)
    db.session.commit()
    students[48] = st48
    ss48 = [
        StudentSubject(student_id=st48.student_id, subject_id=subjects["Data Structures"].subject_id),
        StudentSubject(student_id=st48.student_id, subject_id=subjects["Programming"].subject_id)
    ]
    db.session.add_all(ss48)
    db.session.commit()
    sas48 = [
        StudentAvailableSlot(student_id=st48.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st48.student_id, available_date=dt.datetime(2025, 4, 28),
                            start_time=dt.time(9, 40, 0), end_time=dt.time(10, 40, 0)),
        StudentAvailableSlot(student_id=st48.student_id, available_date=dt.datetime(2025, 5, 1),
                            start_time=dt.time(11, 0, 0), end_time=dt.time(12, 0, 0))
    ]
    db.session.add_all(sas48)
    db.session.commit()

    # Student 49
    st49 = Student(
        name="Wendy Scott",
        preferred_learning_style="Visual",
        preferred_language="English",
        budget=370.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="wendy.scott@example.com"
    )
    db.session.add(st49)
    db.session.commit()
    students[49] = st49
    ss49 = [
        StudentSubject(student_id=st49.student_id, subject_id=subjects["Physics"].subject_id),
        StudentSubject(student_id=st49.student_id, subject_id=subjects["Organic Chemistry"].subject_id)
    ]
    db.session.add_all(ss49)
    db.session.commit()
    sas49 = [
        StudentAvailableSlot(student_id=st49.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st49.student_id, available_date=dt.datetime(2025, 4, 29),
                            start_time=dt.time(10, 5, 0), end_time=dt.time(11, 5, 0)),
        StudentAvailableSlot(student_id=st49.student_id, available_date=dt.datetime(2025, 5, 1),
                            start_time=dt.time(12, 30, 0), end_time=dt.time(13, 30, 0))
    ]
    db.session.add_all(sas49)
    db.session.commit()
    slp49 = StudentLearningPath(student_id=st49.student_id, learning_item="Basic Chemistry", step_order=1)
    db.session.add(slp49)
    db.session.commit()

    # Student 50
    st50 = Student(
        name="Xavier Young",
        preferred_learning_style="Auditory",
        preferred_language="Spanish",
        budget=405.00,
        password="pbkdf2:sha256:260000$HZuLbem8xVHSdy02$ac76c77729a00cbeefd6460620d611e095523fd81aedce2418332addb6614d78",
        email="xavier.young@example.com"
    )
    db.session.add(st50)
    db.session.commit()
    students[50] = st50
    ss50 = [
        StudentSubject(student_id=st50.student_id, subject_id=subjects["Calculus 1"].subject_id),
        StudentSubject(student_id=st50.student_id, subject_id=subjects["Statistics"].subject_id)
    ]
    db.session.add_all(ss50)
    db.session.commit()
    sas50 = [
        StudentAvailableSlot(student_id=st50.student_id, available_date=dt.datetime(2025, 4, 21),
                            start_time=dt.time(9, 0, 0), end_time=dt.time(10, 0, 0)),
        StudentAvailableSlot(student_id=st50.student_id, available_date=dt.datetime(2025, 4, 25),
                            start_time=dt.time(11, 20, 0), end_time=dt.time(12, 20, 0)),
        StudentAvailableSlot(student_id=st50.student_id, available_date=dt.datetime(2025, 4, 27),
                            start_time=dt.time(13, 10, 0), end_time=dt.time(14, 10, 0))
    ]
    db.session.add_all(sas50)
    db.session.commit()
    slp50 = StudentLearningPath(student_id=st50.student_id, learning_item="Algebra", step_order=1)
    db.session.add(slp50)
    db.session.commit()


    # Session 1
    session1 = Session(
        student_id=1,
        tutor_id=1,
        subject_id=subjects["Calculus 2"].subject_id,
        scheduled_time=dt.datetime(2023, 8, 1, 8, 30, 0),
        session_status="Completed"
    )
    db.session.add(session1)
    db.session.commit()

    feedback1 = SessionFeedback(
        session_id=session1.session_id,
        student_feedback="Very informative session in the past.",
        star_rating=5,
        feedback_sentiment="Positive",
        feedback_issues="",
        improvement_tip="Well done."
    )
    db.session.add(feedback1)
    db.session.commit()

    # Session 2
    session2 = Session(
        student_id=2,
        tutor_id=2,
        subject_id=subjects["Physics"].subject_id,
        scheduled_time=dt.datetime(2023, 8, 1, 9, 45, 0),
        session_status="Completed"
    )
    db.session.add(session2)
    db.session.commit()

    feedback2 = SessionFeedback(
        session_id=session2.session_id,
        student_feedback="Good explanation, a bit rushed.",
        star_rating=4,
        feedback_sentiment="Neutral",
        feedback_issues="",
        improvement_tip="Consider slowing down."
    )
    db.session.add(feedback2)
    db.session.commit()

    # Session 3
    session3 = Session(
        student_id=3,
        tutor_id=3,
        subject_id=subjects["Programming"].subject_id,
        scheduled_time=dt.datetime(2023, 8, 1, 11, 0, 0),
        session_status="Completed"
    )
    db.session.add(session3)
    db.session.commit()

    feedback3 = SessionFeedback(
        session_id=session3.session_id,
        student_feedback="Excellent clarity and depth.",
        star_rating=5,
        feedback_sentiment="Positive",
        feedback_issues="",
        improvement_tip=""
    )
    db.session.add(feedback3)
    db.session.commit()

    # Session 4
    session4 = Session(
        student_id=4,
        tutor_id=4,
        subject_id=subjects["Algorithms"].subject_id,
        scheduled_time=dt.datetime(2023, 8, 1, 12, 15, 0),
        session_status="Completed"
    )
    db.session.add(session4)
    db.session.commit()

    feedback4 = SessionFeedback(
        session_id=session4.session_id,
        student_feedback="Informative session.",
        star_rating=4,
        feedback_sentiment="Positive",
        feedback_issues="",
        improvement_tip=""
    )
    db.session.add(feedback4)
    db.session.commit()

    # Session 5
    session5 = Session(
        student_id=5,
        tutor_id=5,
        subject_id=subjects["Statistics"].subject_id,
        scheduled_time=dt.datetime(2023, 8, 1, 13, 30, 0),
        session_status="Completed"
    )
    db.session.add(session5)
    db.session.commit()

    feedback5 = SessionFeedback(
        session_id=session5.session_id,
        student_feedback="I learned a lot from this session.",
        star_rating=5,
        feedback_sentiment="Positive",
        feedback_issues="",
        improvement_tip=""
    )
    db.session.add(feedback5)
    db.session.commit()

    # Session 6 (Student 5 with Tutor 7 for Organic Chemistry on 2023-09-20)
    session6 = Session(
        student_id=5,
        tutor_id=7,
        subject_id=subjects["Organic Chemistry"].subject_id,
        scheduled_time=dt.datetime(2023, 9, 20, 14, 0, 0),
        session_status="Completed"
    )
    db.session.add(session6)
    db.session.commit()

    feedback6 = SessionFeedback(
        session_id=session6.session_id,
        student_feedback="The session was extremely engaging and clarified many concepts in statistics.",
        star_rating=5,
        feedback_sentiment="Positive",
        feedback_issues="",
        improvement_tip="Keep up the excellent teaching methods!"
    )
    db.session.add(feedback6)
    db.session.commit()

    # Session 7
    session7 = Session(
        student_id=6,
        tutor_id=6,
        subject_id=subjects["Linear Regression"].subject_id,
        scheduled_time=dt.datetime(2023, 8, 1, 14, 45, 0),
        session_status="Completed"
    )
    db.session.add(session7)
    db.session.commit()

    feedback7 = SessionFeedback(
        session_id=session7.session_id,
        student_feedback="Average session, could improve.",
        star_rating=3,
        feedback_sentiment="Neutral",
        feedback_issues="",
        improvement_tip=""
    )
    db.session.add(feedback7)
    db.session.commit()

    # Session 8
    session8 = Session(
        student_id=7,
        tutor_id=7,
        subject_id=subjects["Calculus 2"].subject_id,
        scheduled_time=dt.datetime(2023, 8, 1, 15, 0, 0),
        session_status="Completed"
    )
    db.session.add(session8)
    db.session.commit()

    feedback8 = SessionFeedback(
        session_id=session8.session_id,
        student_feedback="Well explained, very useful.",
        star_rating=5,
        feedback_sentiment="Positive",
        feedback_issues="",
        improvement_tip=""
    )
    db.session.add(feedback8)
    db.session.commit()

    # Session 9
    session9 = Session(
        student_id=8,
        tutor_id=8,
        subject_id=subjects["Machine Learning"].subject_id,
        scheduled_time=dt.datetime(2023, 8, 1, 16, 15, 0),
        session_status="Completed"
    )
    db.session.add(session9)
    db.session.commit()

    feedback9 = SessionFeedback(
        session_id=session9.session_id,
        student_feedback="Interactive and engaging.",
        star_rating=5,
        feedback_sentiment="Positive",
        feedback_issues="",
        improvement_tip=""
    )
    db.session.add(feedback9)
    db.session.commit()

    # Session 10
    session10 = Session(
        student_id=9,
        tutor_id=9,
        subject_id=subjects["Organic Chemistry"].subject_id,
        scheduled_time=dt.datetime(2023, 8, 1, 17, 30, 0),
        session_status="Completed"
    )
    db.session.add(session10)
    db.session.commit()

    feedback10 = SessionFeedback(
        session_id=session10.session_id,
        student_feedback="A bit too fast.",
        star_rating=3,
        feedback_sentiment="Neutral",
        feedback_issues="pace",
        improvement_tip="Slow down next time."
    )
    db.session.add(feedback10)
    db.session.commit()

    # Session 11
    session11 = Session(
        student_id=10,
        tutor_id=10,
        subject_id=subjects["Deep Learning"].subject_id,
        scheduled_time=dt.datetime(2023, 8, 1, 8, 0, 0),
        session_status="Completed"
    )
    db.session.add(session11)
    db.session.commit()

    feedback11 = SessionFeedback(
        session_id=session11.session_id,
        student_feedback="Outstanding session in the past.",
        star_rating=5,
        feedback_sentiment="Positive",
        feedback_issues="",
        improvement_tip=""
    )
    db.session.add(feedback11)
    db.session.commit()

    # ------------------------------------------------------------
    # Group B: Scheduled Sessions (Future Sessions)
    # ------------------------------------------------------------

    # Scheduled Session 12: Student 1, Tutor 1, Calculus 2 at 2025-03-21 09:00:00
    session12 = Session(
        student_id=1,
        tutor_id=1,
        subject_id=subjects["Calculus 2"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 21, 9, 0, 0),
        session_status="Scheduled"
    )
    db.session.add(session12)
    db.session.commit()

    # Session 13: Student 2, Tutor 2, Physics at 2025-03-21 09:00:00
    session13 = Session(
        student_id=2,
        tutor_id=2,
        subject_id=subjects["Physics"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 21, 9, 0, 0),
        session_status="Scheduled"
    )
    db.session.add(session13)
    db.session.commit()

    # Session 14: Student 3, Tutor 3, Programming at 2025-03-21 09:00:00
    session14 = Session(
        student_id=3,
        tutor_id=3,
        subject_id=subjects["Programming"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 21, 9, 0, 0),
        session_status="Scheduled"
    )
    db.session.add(session14)
    db.session.commit()

    # Session 15: Student 4, Tutor 4, Algorithms at 2025-03-21 09:00:00
    session15 = Session(
        student_id=4,
        tutor_id=4,
        subject_id=subjects["Algorithms"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 21, 9, 0, 0),
        session_status="Scheduled"
    )
    db.session.add(session15)
    db.session.commit()

    # Session 16: Student 1, Tutor 1, Algorithms at 2025-03-18 01:40:00
    session16 = Session(
        student_id=1,
        tutor_id=1,
        subject_id=subjects["Algorithms"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 18, 1, 40, 0),
        session_status="Scheduled"
    )
    db.session.add(session16)
    db.session.commit()

    # Session 17: A canceled session for Student 5, Tutor 5, Statistics at 2025-03-21 09:00:00
    session17 = Session(
        student_id=5,
        tutor_id=5,
        subject_id=subjects["Statistics"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 21, 9, 0, 0),
        session_status="Canceled"
    )
    db.session.add(session17)
    db.session.commit()

    # Session 18: Student 5, Tutor 5, Statistics at 2025-03-24 14:00:00
    session18 = Session(
        student_id=5,
        tutor_id=5,
        subject_id=subjects["Statistics"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 24, 14, 0, 0),
        session_status="Scheduled"
    )
    db.session.add(session18)
    db.session.commit()

    # Session 19: Student 6, Tutor 6, Linear Regression at 2025-03-21 09:00:00
    session19 = Session(
        student_id=6,
        tutor_id=6,
        subject_id=subjects["Linear Regression"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 21, 9, 0, 0),
        session_status="Scheduled"
    )
    db.session.add(session19)
    db.session.commit()

    # Session 20: Student 7, Tutor 7, Calculus 2 at 2025-03-21 09:00:00
    session20 = Session(
        student_id=7,
        tutor_id=7,
        subject_id=subjects["Calculus 2"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 21, 9, 0, 0),
        session_status="Scheduled"
    )
    db.session.add(session20)
    db.session.commit()

    # Session 21: Student 8, Tutor 8, Machine Learning at 2025-03-21 09:00:00
    session21 = Session(
        student_id=8,
        tutor_id=8,
        subject_id=subjects["Machine Learning"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 21, 9, 0, 0),
        session_status="Scheduled"
    )
    db.session.add(session21)
    db.session.commit()

    # Session 22: Student 9, Tutor 9, Organic Chemistry at 2025-03-21 09:00:00
    session22 = Session(
        student_id=9,
        tutor_id=9,
        subject_id=subjects["Organic Chemistry"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 21, 9, 0, 0),
        session_status="Scheduled"
    )
    db.session.add(session22)
    db.session.commit()

    # Session 23: Student 10, Tutor 10, Deep Learning at 2025-03-21 09:00:00
    session23 = Session(
        student_id=10,
        tutor_id=10,
        subject_id=subjects["Deep Learning"].subject_id,
        scheduled_time=dt.datetime(2025, 4, 21, 9, 0, 0),
        session_status="Scheduled"
    )
    db.session.add(session23)
    db.session.commit()

    # ------------------------------------------------------------
    # TRIGGERS: Enforce Session Time Consistency and Remove Booked Slot
    # ------------------------------------------------------------

    trigger_before_session_insert = DDL("""
    CREATE TRIGGER before_session_insert
    BEFORE INSERT ON Sessions
    FOR EACH ROW
    BEGIN
        DECLARE tutor_slot_count INT;
        DECLARE student_slot_count INT;
        
        IF DATE(NEW.scheduled_time) >= '2025-03-30' THEN
        SELECT COUNT(*) INTO tutor_slot_count
        FROM TutorAvailableSlots
        WHERE tutor_id = NEW.tutor_id
            AND available_date = DATE(NEW.scheduled_time)
            AND start_time = TIME(NEW.scheduled_time)
            AND end_time = TIME(DATE_ADD(NEW.scheduled_time, INTERVAL 1 HOUR));
        IF tutor_slot_count = 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Tutor not available at the scheduled time';
        END IF;
        
        SELECT COUNT(*) INTO student_slot_count
        FROM StudentAvailableSlots
        WHERE student_id = NEW.student_id
            AND available_date = DATE(NEW.scheduled_time)
            AND start_time = TIME(NEW.scheduled_time)
            AND end_time = TIME(DATE_ADD(NEW.scheduled_time, INTERVAL 1 HOUR));
        IF student_slot_count = 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Student not available at the scheduled time';
        END IF;
        END IF;
    END
    """)
    event.listen(Session.__table__, 'after_create', trigger_before_session_insert)

    trigger_after_session_insert = DDL("""
    CREATE TRIGGER after_session_insert
    AFTER INSERT ON Sessions
    FOR EACH ROW
    BEGIN
        IF DATE(NEW.scheduled_time) >= '2025-03-30' AND NEW.session_status <> 'Canceled' THEN
        DELETE FROM TutorAvailableSlots
        WHERE tutor_id = NEW.tutor_id
            AND available_date = DATE(NEW.scheduled_time)
            AND start_time = TIME(NEW.scheduled_time)
            AND end_time = TIME(DATE_ADD(NEW.scheduled_time, INTERVAL 1 HOUR));
        DELETE FROM StudentAvailableSlots
        WHERE student_id = NEW.student_id
            AND available_date = DATE(NEW.scheduled_time)
            AND start_time = TIME(NEW.scheduled_time)
            AND end_time = TIME(DATE_ADD(NEW.scheduled_time, INTERVAL 1 HOUR));
        END IF;
    END
    """)
    event.listen(Session.__table__, 'after_create', trigger_after_session_insert)
