import os
import pandas as pd
from sqlalchemy.orm import Session
from database.base import SessionLocal, engine
from database.models import User, Book, Highlight
from pathlib import Path

def migrate_user_data():
    """既存のユーザーデータをデータベースに移行"""
    db = SessionLocal()
    
    # ユーザーデータディレクトリ
    user_data_dir = Path("user_data/docs")
    
    for user_dir in user_data_dir.iterdir():
        if user_dir.is_dir():
            user_id = user_dir.name
            highlights_path = user_dir / "KindleHighlights.csv"
            
            if highlights_path.exists():
                # CSVファイルを読み込む
                df = pd.read_csv(highlights_path)
                
                # ユーザーの作成（仮のデータ）
                db_user = User(
                    username=user_id,
                    email=f"{user_id}@example.com",
                    google_id=user_id
                )
                db.add(db_user)
                db.commit()
                
                # 書籍と既存のハイライトを追加
                for _, row in df.iterrows():
                    # 書籍の追加または取得
                    db_book = db.query(Book).filter_by(
                        title=row['書籍タイトル'], 
                        author=row['著者']
                    ).first()
                    
                    if not db_book:
                        db_book = Book(
                            title=row['書籍タイトル'], 
                            author=row['著者']
                        )
                        db.add(db_book)
                        db.commit()
                    
                    # ハイライトの追加
                    db_highlight = Highlight(
                        content=row['ハイライト内容'],
                        location=row.get('位置', ''),
                        user_id=db_user.id,
                        book_id=db_book.id
                    )
                    db.add(db_highlight)
                
                db.commit()
    
    db.close()
    print("データ移行が完了しました。")

if __name__ == "__main__":
    migrate_user_data()
