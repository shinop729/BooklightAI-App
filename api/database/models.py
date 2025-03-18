from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base
from datetime import datetime

class User(Base):
    """ユーザーモデル"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True)
    disabled = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    highlights = relationship("Highlight", back_populates="user")

class Book(Base):
    """書籍モデル"""
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    author = Column(String, index=True)
    
    highlights = relationship("Highlight", back_populates="book")

class Highlight(Base):
    """ハイライトモデル"""
    __tablename__ = "highlights"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    book_id = Column(Integer, ForeignKey('books.id'), nullable=False)

    user = relationship("User", back_populates="highlights")
    book = relationship("Book", back_populates="highlights")
