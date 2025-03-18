import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the models
from database.models import Base
from database.base import engine

def create_tables():
    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("Tables created.")

if __name__ == "__main__":
    create_tables()
