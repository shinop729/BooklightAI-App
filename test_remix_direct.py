"""
Remix機能を直接テストするスクリプト
"""

import os
import sys
import json
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# データベース接続の設定
from api.database.base import Base
from api.database.models import User, Book, Highlight, Remix, RemixHighlight

# RemixServiceのインポート
from api.app.remix import RemixService

# データベース接続の設定
DATABASE_URL = "sqlite:///api/booklight.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def test_random_theme():
    """ランダムテーマ生成をテスト"""
    db = SessionLocal()
    try:
        # ユーザーIDを取得（最初のユーザーを使用）
        user = db.query(User).first()
        if not user:
            print("ユーザーが見つかりません。テストデータを作成してください。")
            return
        
        print(f"ユーザー: {user.username} (ID: {user.id})")
        
        # RemixServiceのインスタンスを作成
        service = RemixService(db, user.id)
        
        # ランダムテーマを生成
        theme = await service.generate_random_theme()
        print(f"生成されたランダムテーマ: {theme}")
        
        return theme
    finally:
        db.close()

async def test_generate_remix(theme=None):
    """Remix生成をテスト"""
    db = SessionLocal()
    try:
        # ユーザーIDを取得（最初のユーザーを使用）
        user = db.query(User).first()
        if not user:
            print("ユーザーが見つかりません。テストデータを作成してください。")
            return
        
        print(f"ユーザー: {user.username} (ID: {user.id})")
        
        # ハイライト数を確認
        highlight_count = db.query(Highlight).filter(Highlight.user_id == user.id).count()
        print(f"ハイライト数: {highlight_count}")
        
        if highlight_count < 5:
            print("ハイライト数が少なすぎます。少なくとも5つのハイライトが必要です。")
            return
        
        # RemixServiceのインスタンスを作成
        service = RemixService(db, user.id)
        
        # テスト用に少数のハイライトを使用
        print("テスト用に最大20件のハイライトを使用します")
        test_highlights = db.query(Highlight).filter(
            Highlight.user_id == user.id
        ).limit(20).all()
        
        # 少数のハイライトを使用するようにサービスを修正
        service._select_relevant_highlights = lambda theme, max_count: [
            {
                "id": h.id,
                "content": h.content,
                "book_id": h.book_id,
                "book_title": db.query(Book).filter(Book.id == h.book_id).first().title,
                "book_author": db.query(Book).filter(Book.id == h.book_id).first().author
            }
            for h in test_highlights[:10]
        ]
        
        # テーマが指定されていない場合はランダムテーマを使用
        if not theme:
            theme = await service.generate_random_theme()
            print(f"生成されたランダムテーマ: {theme}")
        
        # Remixを生成
        result = await service.generate_remix(theme)
        
        if result["success"]:
            remix_data = result["data"]
            print(f"Remix生成成功: ID={remix_data['id']}")
            print(f"タイトル: {remix_data['title']}")
            print(f"テーマ: {remix_data['theme']}")
            print(f"作成日時: {remix_data['created_at']}")
            print(f"使用ハイライト数: {len(remix_data['highlights'])}")
            print("\n--- Remix内容 ---\n")
            print(remix_data['content'])
            print("\n--- 使用ハイライト ---\n")
            for i, h in enumerate(remix_data['highlights']):
                print(f"{i+1}. 『{h['book_title']}』（{h['book_author']}）: {h['content'][:100]}...")
            
            return remix_data
        else:
            print(f"Remix生成失敗: {result['message']}")
            return None
    finally:
        db.close()

async def test_get_user_remixes():
    """ユーザーのRemix一覧を取得"""
    db = SessionLocal()
    try:
        # ユーザーIDを取得（最初のユーザーを使用）
        user = db.query(User).first()
        if not user:
            print("ユーザーが見つかりません。テストデータを作成してください。")
            return
        
        print(f"ユーザー: {user.username} (ID: {user.id})")
        
        # RemixServiceのインスタンスを作成
        service = RemixService(db, user.id)
        
        # ユーザーのRemix一覧を取得
        remixes = await service.get_user_remixes()
        
        print(f"Remix数: {len(remixes)}")
        for i, remix in enumerate(remixes):
            print(f"{i+1}. ID={remix['id']}, タイトル: {remix['title']}, テーマ: {remix['theme']}")
        
        return remixes
    finally:
        db.close()

async def main():
    """メイン関数"""
    print("=== Remix機能テスト ===\n")
    
    # 1. ランダムテーマ生成テスト
    print("\n--- ランダムテーマ生成テスト ---\n")
    theme = await test_random_theme()
    
    # 2. Remix生成テスト
    print("\n--- Remix生成テスト ---\n")
    remix = await test_generate_remix(theme)
    
    # 3. ユーザーのRemix一覧取得テスト
    print("\n--- ユーザーのRemix一覧取得テスト ---\n")
    remixes = await test_get_user_remixes()

if __name__ == "__main__":
    asyncio.run(main())
