from sqlalchemy.orm import Session
from .models import User, Book, Highlight
from typing import List, Optional, Dict, Any
import pandas as pd

def get_user_by_google_id(db: Session, google_id: str) -> Optional[User]:
    """Google IDからユーザーを取得"""
    return db.query(User).filter(User.google_id == google_id).first()

def get_books_for_user(db: Session, user_id: int) -> List[Book]:
    """ユーザーIDに関連する書籍を取得"""
    return db.query(Book).\
        join(Highlight).\
        filter(Highlight.user_id == user_id).\
        distinct().\
        all()

def get_highlights_for_book(db: Session, user_id: int, book_id: int) -> List[Highlight]:
    """特定のユーザーと書籍に関連するハイライトを取得"""
    return db.query(Highlight).\
        filter(Highlight.user_id == user_id, Highlight.book_id == book_id).\
        all()

def get_all_highlights_for_user(db: Session, user_id: int) -> List[Highlight]:
    """ユーザーの全ハイライトを取得"""
    return db.query(Highlight).filter(Highlight.user_id == user_id).all()

def create_highlight(db: Session, user_id: int, book_id: int, content: str, location: str = None) -> Highlight:
    """新しいハイライトを作成"""
    db_highlight = Highlight(
        content=content,
        location=location,
        user_id=user_id,
        book_id=book_id
    )
    db.add(db_highlight)
    db.commit()
    db.refresh(db_highlight)
    return db_highlight

def get_or_create_book(db: Session, title: str, author: str) -> Book:
    """書籍を取得または作成"""
    db_book = db.query(Book).filter(Book.title == title, Book.author == author).first()
    if not db_book:
        db_book = Book(title=title, author=author)
        db.add(db_book)
        db.commit()
        db.refresh(db_book)
    return db_book

def get_or_create_user(db: Session, google_id: str, username: str, email: str, 
                      full_name: str = None, picture: str = None) -> User:
    """ユーザーを取得または作成"""
    db_user = get_user_by_google_id(db, google_id)
    if not db_user:
        db_user = User(
            google_id=google_id,
            username=username,
            email=email,
            full_name=full_name,
            picture=picture
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    return db_user

def get_book_summaries_for_user(db: Session, user_id: int) -> pd.DataFrame:
    """ユーザーの書籍サマリーをDataFrameとして取得"""
    # ユーザーを取得
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return pd.DataFrame(columns=["書籍タイトル", "著者", "要約", "ハイライト件数"])
    
    # 書籍とハイライトを取得
    books = get_books_for_user(db, user.id)
    
    # DataFrameに変換
    data = []
    for book in books:
        highlights = get_highlights_for_book(db, user.id, book.id)
        if highlights:
            data.append({
                "書籍タイトル": book.title,
                "著者": book.author,
                "要約": "\n\n".join([h.content for h in highlights[:3]]),
                "ハイライト件数": len(highlights)
            })
    
    return pd.DataFrame(data)

def save_highlights_to_db(db: Session, df: pd.DataFrame, user_id: int) -> Dict[str, Any]:
    """DataFrameからハイライトをデータベースに保存"""
    # ユーザーを取得
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"status": "error", "message": "ユーザーが見つかりません"}
    
    # 追加したハイライト数
    added_count = 0
    
    # 各行を処理
    for _, row in df.iterrows():
        # 書籍を取得または作成
        book = get_or_create_book(db, row["書籍タイトル"], row["著者"])
        
        # ハイライトが既に存在するか確認
        existing = db.query(Highlight).filter(
            Highlight.user_id == user.id,
            Highlight.book_id == book.id,
            Highlight.content == row["ハイライト内容"]
        ).first()
        
        # 存在しない場合は追加
        if not existing:
            location = row.get("位置", "")
            create_highlight(db, user.id, book.id, row["ハイライト内容"], location)
            added_count += 1
    
    return {
        "status": "success",
        "message": f"{added_count} 件のハイライトを追加しました",
        "added_count": added_count
    }

def convert_db_to_csv_format(db: Session, user_id: int) -> pd.DataFrame:
    """データベースのハイライトをCSV形式のDataFrameに変換"""
    # ユーザーを取得
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return pd.DataFrame(columns=["書籍タイトル", "著者", "ハイライト内容", "位置"])
    
    # ハイライトを取得
    highlights = get_all_highlights_for_user(db, user.id)
    
    # DataFrameに変換
    data = []
    for h in highlights:
        book = db.query(Book).filter(Book.id == h.book_id).first()
        if book:
            data.append({
                "書籍タイトル": book.title,
                "著者": book.author,
                "ハイライト内容": h.content,
                "位置": h.location or ""
            })
    
    return pd.DataFrame(data)
