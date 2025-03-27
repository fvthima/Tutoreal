# matching_module.py
import numpy as np
from datetime import datetime

def get_tutors_for_subject(subject_name, cursor):
    """
    Retrieve tutors that teach the given subject.
    Returns a list of dictionaries with tutor info and the subject price.
    """
    query = """
    SELECT t.tutor_id, t.name, t.profile_pic_url, t.average_star_rating, ts.price, t.preferred_language, t.teaching_style
    FROM Tutors t
    JOIN TutorSubjects ts ON t.tutor_id = ts.tutor_id
    JOIN Subjects s ON ts.subject_id = s.subject_id
    WHERE s.subject_name = %s;
    """
    cursor.execute(query, (subject_name,))
    tutors = []
    for (tutor_id, name, profile_pic_url, avg_rating, price, language, teaching_style) in cursor.fetchall():
        tutors.append({
            'tutor_id': tutor_id,
            'name': name,
            'profile_pic_url': profile_pic_url if profile_pic_url else '/static/images/default-profile-picture.png',
            'average_star_rating': float(avg_rating),
            'price': float(price),
            'preferred_language': language,
            'teaching_style': teaching_style,
            'hourly_rate': float(price),  # using price as the hourly rate for display
            'review_count': 0,           # default value if no review count is available
            'timings': "N/A"             # default value; update if you have scheduling info
        })
    return tutors


def check_availability(tutor_id, desired_date, cursor):
    """
    Check if the tutor has any available slot on the given date.
    Returns True if available, otherwise False.
    """
    if isinstance(desired_date, str):
        try:
            desired_date = datetime.strptime(desired_date, '%d-%m-%Y').date().strftime('%Y-%m-%d')
        except Exception as e:
            raise ValueError(f"Invalid date format: {desired_date}. Expected DD-MM-YYYY.")
    elif hasattr(desired_date, 'strftime'):
        desired_date = desired_date.strftime('%Y-%m-%d')
    
    query = """
    SELECT COUNT(*) FROM TutorAvailableSlots
    WHERE tutor_id = %s AND available_date = %s;
    """
    cursor.execute(query, (tutor_id, desired_date))
    count = cursor.fetchone()[0]
    return count > 0


def price_factor(tutor_price, student_budget):
    """
    Calculate a price factor (0 to 1) based on the tutor's price versus the student's budget.
    If the student's budget is 0, then if the tutor's price is also 0, return 1 (perfect match);
    otherwise, return 0.
    If the tutor's price is within the budget, return 1.
    Otherwise, reduce the factor proportionally (minimum 0).
    """
    if student_budget == 0:
        return 1.0 if tutor_price == 0 else 0.0

    if tutor_price <= student_budget:
        return 1.0
    else:
        excess = tutor_price - student_budget
        factor = max(0, 1 - (excess / student_budget))
        return factor


def calculate_dynamic_score(tutor, availability, student_budget, student_language, student_learning_style, weights):
    """
    Calculate a dynamic compatibility score using learned weights.
    'weights' is a dictionary with keys: rating_weight, availability_weight, price_weight, language_weight, learning_style_weight.
    The tutor's rating is normalized by dividing by 5.
    """
    rating_norm = tutor['average_star_rating'] / 5.0
    avail_factor = 1.0 if availability else 0.0
    p_factor = price_factor(tutor['price'], student_budget)
    language_factor = 1.0 if tutor['preferred_language'] == student_language else 0.0
    learning_style_factor = 1.0 if tutor['teaching_style'] == student_learning_style else 0.0
    
    score = (weights['rating_weight'] * rating_norm +
             weights['availability_weight'] * avail_factor +
             weights['price_weight'] * p_factor +
             weights['language_weight'] * language_factor +
             weights['learning_style_weight'] * learning_style_factor)
    return score

def get_learning_path(subject_name, cursor):
    """
    Recursively retrieve the prerequisite chain for a given subject.
    Returns a list of subjects from the most basic prerequisite up to the direct prerequisite.
    """
    learning_path = []
    current_subject = subject_name
    while True:
        cursor.execute("SELECT prerequisite_id FROM Subjects WHERE subject_name = %s", (current_subject,))
        row = cursor.fetchone()
        if row and row[0]:
            prerequisite_id = row[0]
            cursor.execute("SELECT subject_name FROM Subjects WHERE subject_id = %s", (prerequisite_id,))
            prereq_row = cursor.fetchone()
            if prereq_row:
                prereq_subject = prereq_row[0]
                learning_path.insert(0, prereq_subject)
                current_subject = prereq_subject
            else:
                break
        else:
            break
    return learning_path

def get_learning_path_with_tutors(subject_name, desired_date, student_budget, student_language, student_learning_style, weights, cursor):
    """
    Retrieve the prerequisite chain for the subject along with tutors available for each prerequisite.
    Returns a list of dictionaries with:
      'course_title': prerequisite subject,
      'tutors': list of available tutors (with their details and dynamic scores).
    """
    base_learning_path = get_learning_path(subject_name, cursor)
    path_with_tutors = []
    for subj in base_learning_path:
        tutors = get_tutors_for_subject(subj, cursor)
        available_tutors = []
        for tutor in tutors:
            if check_availability(tutor['tutor_id'], desired_date, cursor):
                score = calculate_dynamic_score(tutor, True, student_budget, student_language, student_learning_style, weights)
                tutor['score'] = score
                available_tutors.append(tutor)
        path_with_tutors.append({
            'course_title': subj, 
            'tutors': available_tutors
        })
    if not path_with_tutors:
        path_with_tutors.append({'course_title': subject_name, 'tutors': []})
    while len(path_with_tutors) < 3:
        path_with_tutors.append({'course_title': '', 'tutors': []})
    return path_with_tutors

def match_tutor(subject_name, desired_date, student_budget, student_language, student_learning_style, weights, cursor):
    tutors = get_tutors_for_subject(subject_name, cursor)
    if not tutors:
        print("No tutors found teaching the subject:", subject_name)
        return None, []
    scored_tutors = []
    for tutor in tutors:
        available = check_availability(tutor['tutor_id'], desired_date, cursor)
        score = calculate_dynamic_score(tutor, available, student_budget, student_language, student_learning_style, weights)
        tutor['score'] = score
        tutor['available'] = available
        scored_tutors.append(tutor)
    top_tutor = max(scored_tutors, key=lambda x: x['score'])
    learning_path_with_tutors = get_learning_path_with_tutors(subject_name, desired_date, student_budget, student_language, student_learning_style, weights, cursor)
    return top_tutor, learning_path_with_tutors
