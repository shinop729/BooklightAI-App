from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base
from datetime import datetime

class SearchHistory(Base):
    """検索履歴モデル"""
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, nullable=False)
    result_count = Column(Integer, default=0)  # 検索結果数
    created_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship("User", backref="search_history")

class ChatSession(Base):
    """チャットセッションモデル"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship("User", backref="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    """チャットメッセージモデル"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    role = Column(String, nullable=False)  # 'user' または 'assistant'
    created_at = Column(DateTime, default=datetime.utcnow)

    session_id = Column(Integer, ForeignKey('chat_sessions.id'), nullable=False)
    session = relationship("ChatSession", back_populates="messages")

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
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # user_id属性を追加
    
    user = relationship("User", backref="books")  # ユーザーとの関連を追加
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
