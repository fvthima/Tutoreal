# About Tutoreal

Tutoreal is an AI-powered smart tutoring platform designed to transform the way students learn and tutors teach. Built by a passionate team of students from the University of Wollongong in Dubai, Tutoreal bridges the gap between learners and educators through smart matchmaking, real-time collaboration, and intelligent feedback.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Contributors](#contributors)

## Overview

The **Tutoreal** project is designed to provide a robust solution for text analysis and machine learning tasks. It includes modules for:
- Issue extraction
- Sentiment analysis
- Reinforcement learning training
- Secure password hashing

The project demonstrates best practices in modular programming and code organization, making it ideal for academic evaluation and professional review.

## Features

- **AI-Powered Matching System:**  
   - Uses AI algorithms to match students with tutors based on compatibility scores.
   - Takes into account subject expertise, teaching style, learning preferences, and availability.

- **Real-Time Collaboration:**  
   - Supports live video conferencing, audio-only sessions, chat, whiteboard, and file sharing.
   - Powered by WebRTC and Socket.IO for minimal latency and real-time interaction.

- **AI-Driven Feedback System:**  
   - Uses NLP to analyze session feedback from the student and generate actionable insights.
   - Provides personalized tips for improving the tutors.

- **Scheduling**  
   - Book and manage tutoring sessions with calendar integration.
     
- **Secure Payment System:**
   - Supports secure transactions

## Installation

### Prerequisites

- Python 3.7 or later
- pip (Python package installer)

### Steps

1. **Clone the Repository:**

   ```
   git clone https://github.com/yourusername/your-repo-name.git
   cd your-repo-name

2. **Create and Activate a Virtual Environment:**

   ```
    python3 -m venv venv
    source venv/bin/activate   # On Windows: venv\Scripts\activate

3. **Install Dependencies:**

   ```
    pip install -r requirements.txt

## Usage

### Running the Application:

    python app.py

### Accessing the Platform:

    http://localhost:5001

## Detailed workflow 

### For the tutor case:

   ```

 1. First, the tutor can either log in or sign up. If logging in with an existing account, the tutor enters their email and password, and upon successful authentication, they are directed to the tutor dashboard. If signing up, they provide an email and password and are immediately taken to the profile settings page to input their details.

 2. From the dashboard (or profile settings page in the signup case), the tutor can navigate to the Profile Settings page (accessed via the top right corner). Here, they can update their personal information and add details for any upcoming sessions by clicking on edit and then save.

 3. Both login and signup flows allow the tutor to access the My Sessions tab which can be accessed from the left side of the dashboard. In this section, they can see a list of upcoming sessions (booked by students) and review completed sessions.

 4. After a session ends, the student provides review and feedback. The tutor can then navigate to the Reviews page via the left side navigation on the dashboard. This page not only shows the review details but also features AI-driven sentiment analysis and improvement tips to help the tutor enhance their teaching practices.

This end-to-end workflow ensures that tutors have a streamlined experience from authentication, profile management, and session scheduling to receiving actionable feedback after sessions.
   ```

### For the student case:

 1. ⁠First, the student can either log in or sign up. Both processes work similarly—upon entering their email and password, they are directed to the student profile settings page where they input or update their personal details by clicking on edit and then saving.

 2. From the dashboard, the student navigates to the “Find a Tutor” page ( accessed from the left-side menu). Here, they can enter key criteria such as the subject they need help with, their availability, language preference, and learning style. After entering these details, the student clicks the “Match Me” button.

 3. ⁠The system then processes these inputs through the AI Matching Module and presents a top tutor recommendation based on compatibility.

 4. The student has two options:  – View the tutor’s profile for additional details about qualifications, reviews, and availability.  – Book a session with the recommended tutor. For booking, the student inputs the desired date and time, and then proceeds to the payment stage.

 5. Upon successful payment, the student can navigate to the “My Sessions” tab where all upcoming sessions are listed. At the designated time, the student clicks the “Join” button to enter the session.

 6. After the session concludes, the student is prompted to provide feedback and leave a review. This input not only helps the tutor improve but also refines future matching recommendations for the student.

This workflow ensures a seamless end-to-end experience for students—from account creation and personalized tutor matching to booking, session participation, and post-session review—reflecting the system specifications detailed in our documentation.

## Step‐by‐step testing workflow for the real‑time collaboration feature using an existing tutor and student account:

1.⁠  ⁠Start by opening your browser and logging in as the tutor in one tab. 
 - Log in with the following existing credentials:

         Tutor
         username: sophia.anderson@example.com
         password: password
   
2.⁠  Navigate to the Profile Settings page and input an availability slot that starts in the next 5 minutes.
   
3.⁠  ⁠Open a new browser tab and log in as a student. 

         Student
         username: adam.freeman@example.com
         password: password

4.⁠  From the dashboard, go to the “Find a Tutor” page. Enter the following criteria:
 – Subject: Calculus 2
 – Date: Current date
 – Language: English
 – Learning Style: Visual
Then click the “Match Me” button. (For testing purposes, the system is set up to return the tutor you’re logged in as.)

5.⁠  ⁠Once the matching returns your tutor, book the session for the available time slot you entered earlier in the tutor’s profile.

6.⁠  ⁠After booking, both tutor and student should navigate to the “My Sessions” tab. At the designated time, both parties click “Join” to initiate the real‑time video calling session.

7.⁠  ⁠Once the session concludes, have the student provide feedback and leave a review. The tutor can then log in to view the received feedback.

8.⁠  ⁠For further testing, the student can repeat the booking process multiple times and deliberately leave a few bad reviews for the same tutor. Then, by re‐entering the same search criteria on the “Find a Tutor” page, you can observe that the top match changes, demonstrating that the matching system is learning from past session data.


### Module-Specific Scripts:

 - issue_extraction.py: Extract and analyze issues from text data.

 - sentiment_analysis.py: Analyze the sentiment of provided text.

 - rl_training.py: Train models using reinforcement learning techniques.


## Project Structure
```
Tutoreal/
├── app.py                   
├── config.py   
├── models.py
├── improvement_tips.py      
├── issue_extraction.py    
├── matching_module.py       
├── rl_training.py         
├── sentiment_analysis.py   
├── weights.json         
├── requirements.txt    
│
├── static/             
│   ├── css/                  
│   ├── images/        
│   ├── js/
│   ├── uploads/     
│   ├── webfonts/     
│
├── templates/           
│   ├── landing-page.html  
│   ├── login-page.html    
│   ├── sign-up-page.html   
│   ├── sign-up-student-page.html   
│   ├── dashboard-student.html 
│   ├── dashboard-tutor.html 
│   ├── find-a-tutor.html    
│   ├── match-tutor.html    
│   ├── call_page.html 
│   ├── call-feedback.html 
│   ├── review-feedback.html
│   ├── feedback.html
│   ├── student_session.html
│   ├── tutor_session.html
│   ├── booking-page.html
│   ├── book-confirmation.html
│   ├── student-profile-setting.html
│   ├── tutor-profile-page.html
│   ├── tutor-profile-setting.html
│
├── __pycache__/            
├── .gitignore            
└── README.md  
```

## Dependencies
The main dependencies for this project include:

 - Flask – Core web framework.
 - Flask-APScheduler, Flask-Cors, Flask-SocketIO, Flask-SQLAlchemy – Extensions for scheduling tasks, handling CORS, real-time communications, and database interactions.
 - mysql-connector-python – MySQL database connectivity.
 - MarkupSafe, Werkzeug – Utilities for secure templating.
 - nltk, transformers, numpy – Libraries for natural language processing and numerical computations.
 - python-dotenv – Environment variable management.
 - SQLAlchemy – SQL toolkit and ORM.
 - eventlet – Asynchronous support.

For the complete list, please refer to the requirements.txt file.

## Contributors
 - Rudra Thavarankattil - 7544984 - AI and Backend Developer -GROUP LEADER
 - Fathima Haris Ahmed - 7743749 - Frontend and UI/UX developer
 - Nathan Gonsalves - 7849187 - Backend Developer
 - Teng Ian Khoo - 8121667 - Backend Developer -SCRIBE
 - Khaled Ali - 7312167 - Security Developer

