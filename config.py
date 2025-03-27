import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD"))
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

SQLALCHEMY_DATABASE_URI = (
    f"mysql+mysqlconnector://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}?charset=utf8"
)

# Create a shared SQLAlchemy instance.
db = SQLAlchemy()

def get_db_connection():
    """Returns a new database connection using SQLAlchemy."""
    engine = create_engine(SQLALCHEMY_DATABASE_URI)
    return engine.connect()
