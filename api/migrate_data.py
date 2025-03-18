"""CSVファイルからデータベースへのデータ移行スクリプト"""
import os
import pandas as pd
import sys
from pathlib import Path
from sqlalchemy.orm import Session
from database.base import SessionLocal, engine
from database.models import User, Book, Highlight
from datetime import datetime
import json

def migrate_user_highlights():
    """ユーザーのハイライトデータをCSVからデータベースに移行"""
    # データベースセッションの作成
    db = SessionLocal()
    
    # ユーザーデータディレクトリ
    user_data_dir = Path("user_data/docs")
    
    # 処理されたユーザー数
    processed_users = 0
    processed_highlights = 0
    
    print("データベース移行を開始します...")
    
    for user_dir in user_data_dir.iterdir():
        if user_dir.is_dir():
            user_id = user_dir.name
            print(f"ユーザー {user_id} の処理中...")
            
            # ユーザー情報JSONの確認
            user_info_path = user_dir / "user_info.json"
            if not user_info_path.exists():
                print(f"  ユーザー情報ファイルがありません: {user_info_path}")
                continue
            
            try:
                with open(user_info_path, "r", encoding="utf-8") as f:
                    user_info = json.load(f)
            except json.JSONDecodeError:
                print(f"  ユーザー情報ファイルの解析に失敗しました: {user_info_path}")
                continue
            
            # ユーザーが既にデータベースに存在するか確認
            db_user = db.query(User).filter(
                User.username == user_id
            ).first()
            
            if not db_user:
                # ユーザーの作成
                db_user = User(
                    username=user_id,
                    email=user_info.get("email", f"{user_id}@example.com"),
                    full_name=user_info.get("full_name", ""),
                    picture=user_info.get("picture", ""),
                    google_id=user_info.get("google_id", ""),
                    disabled=0,
                    created_at=datetime.utcnow()
                )
                db.add(db_user)
                db.commit()
                db.refresh(db_user)
                print(f"  新規ユーザーをデータベースに作成しました: {user_id}")
            
            # ハイライトCSVの確認
            highlights_path = user_dir / "KindleHighlights.csv"
            if not highlights_path.exists():
                print(f"  ハイライトCSVがありません: {highlights_path}")
                continue
            
            # CSVファイルを読み込む
            try:
                df = pd.read_csv(highlights_path)
                print(f"  {len(df)}件のハイライトを読み込みました")
                
                # 書籍とハイライトを追加
                for _, row in df.iterrows():
                    # 書籍の追加または取得
                    book_title = row.get('書籍タイトル', '')
                    book_author = row.get('著者', '')
                    
                    if not book_title:
                        continue
                    
                    db_book = db.query(Book).filter_by(
                        title=book_title, 
                        author=book_author
                    ).first()
                    
                    if not db_book:
                        db_book = Book(
                            title=book_title, 
                            author=book_author
                        )
                        db.add(db_book)
                        db.commit()
                        db.refresh(db_book)
                    
                    # ハイライトが既に存在するか確認
                    highlight_content = row.get('ハイライト内容', '')
                    if not highlight_content:
                        continue
                    
                    existing_highlight = db.query(Highlight).filter(
                        Highlight.user_id == db_user.id,
                        Highlight.book_id == db_book.id,
                        Highlight.content == highlight_content
                    ).first()
                    
                    if not existing_highlight:
                        # ハイライトの追加
                        db_highlight = Highlight(
                            content=highlight_content,
                            location=row.get('位置', ''),
                            user_id=db_user.id,
                            book_id=db_book.id,
                            created_at=datetime.utcnow()
                        )
                        db.add(db_highlight)
                        processed_highlights += 1
                
                db.commit()
                processed_users += 1
                print(f"  ユーザー {user_id} のデータベース移行が完了しました")
            
            except Exception as e:
                db.rollback()
                print(f"  エラーが発生しました: {e}")
    
    db.close()
    print(f"移行完了: {processed_users}人のユーザー、{processed_highlights}件のハイライトを処理しました")

if __name__ == "__main__":
    migrate_user_highlights()
