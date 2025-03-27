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

- **AI-Powered Matching System**  
  Connects students with tutors based on subject needs, learning styles, and availability.

- **Live Tutoring Sessions**  
  Real-time video and chat features enable seamless communication and interactive learning experiences.

- **Smart Feedback System**  
  AI analyzes session data to provide constructive feedback to tutors.

- **User Profiles**  
  Students and tutors can list subjects of interest, areas of expertise, availability, and goals.

## Installation

### Prerequisites

- Python 3.7 or later
- pip (Python package installer)

### Steps

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/your-repo-name.git
   cd your-repo-name

2. **Create and Activate a Virtual Environment:**

   ```bash
    python3 -m venv venv
    source venv/bin/activate   # On Windows: venv\Scripts\activate

3. **Install Dependencies:**

   ```bash
    pip install -r requirements.txt

## Usage

### Running the Application:

    python app.py

### Module-specific Scripts:

issue_extraction.py: Extract and analyze issues from text data.

sentiment_analysis.py: Analyze the sentiment of provided text.

rl_training.py: Train models using reinforcement learning techniques.


## Project Structure
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
│
└── .gitignore            
└── README.md          


## Dependencies
The main dependencies for this project include:

Flask – Core web framework.

Flask-APScheduler, Flask-Cors, Flask-SocketIO, Flask-SQLAlchemy – Extensions for scheduling tasks, handling CORS, real-time communications, and database interactions.

mysql-connector-python – MySQL database connectivity.

MarkupSafe, Werkzeug – Utilities for secure templating.

nltk, transformers, numpy – Libraries for natural language processing and numerical computations.

python-dotenv – Environment variable management.

SQLAlchemy – SQL toolkit and ORM.

eventlet – Asynchronous support.

For the complete list, please refer to the requirements.txt file.

## Contributors
Rudra Thavarankattil - 7544984 - AI, Full Stack Developer
Fathima Haris Ahmed - 7743749 - Full Stack Developer
Teng Ian Khoo - 8121667 - Backend Developer
Nathan Gonsalves - 7849187 - Full Stack Developer
Khaled Ali - 7312167 - Security Developer

