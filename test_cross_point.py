#!/usr/bin/env python3
# test_cross_point.py
# Cross Point機能をテストするためのスクリプト

import os
import sys
import json
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# データベースモデルとCross Pointサービスをインポート
from api.database.models import User, Book, Highlight, CrossPoint
from api.app.cross_point import CrossPointService

# api/app/cross_point.py内のimportを修正するためのモンキーパッチ
import sys
import api.database.models
sys.modules['database.models'] = api.database.models

async def test_cross_point():
    print("Cross Point機能テストを開始します...")

    # データベースに接続
    db_path = './booklight.db'
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 開発ユーザーを取得
        dev_user = session.query(User).filter(User.email == 'dev@example.com').first()
        if not dev_user:
            print("開発ユーザーが見つかりません。先に insert_sample_data.py を実行してください。")
            sys.exit(1)
        
        print(f"開発ユーザーを使用します: ID={dev_user.id}")

        # ユーザーの書籍数とハイライト数を確認
        book_count = session.query(Book).filter(Book.user_id == dev_user.id).count()
        highlight_count = session.query(Highlight).filter(Highlight.user_id == dev_user.id).count()
        
        print(f"ユーザーの書籍数: {book_count}")
        print(f"ユーザーのハイライト数: {highlight_count}")
        
        if book_count < 2:
            print("Cross Point機能をテストするには少なくとも2冊の書籍が必要です。")
            sys.exit(1)
        
        # Cross Pointサービスの初期化
        service = CrossPointService(session, dev_user.id)
        
        # 既存のCross Pointを確認
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        existing_cross_point = session.query(CrossPoint).filter(
            CrossPoint.user_id == dev_user.id,
            CrossPoint.created_at.between(today_start, today_end)
        ).first()
        
        if existing_cross_point:
            print(f"既存のCross Pointが見つかりました: ID={existing_cross_point.id}")
            print(f"タイトル: {existing_cross_point.title}")
            print(f"説明: {existing_cross_point.description}")
            
            # ハイライト情報を取得
            highlight1 = session.query(Highlight).filter(
                Highlight.id == existing_cross_point.highlight1_id
            ).first()
            
            highlight2 = session.query(Highlight).filter(
                Highlight.id == existing_cross_point.highlight2_id
            ).first()
            
            # 書籍情報を取得
            book1 = session.query(Book).filter(
                Book.id == highlight1.book_id
            ).first()
            
            book2 = session.query(Book).filter(
                Book.id == highlight2.book_id
            ).first()
            
            print("\n=== ハイライト1 ===")
            print(f"書籍: {book1.title} ({book1.author})")
            print(f"内容: {highlight1.content}")
            
            print("\n=== ハイライト2 ===")
            print(f"書籍: {book2.title} ({book2.author})")
            print(f"内容: {highlight2.content}")
        else:
            print("既存のCross Pointが見つかりませんでした。新しいCross Pointを生成します...")
            
            # Cross Pointの生成
            result = await service.get_daily_cross_point()
            
            if result:
                print("\n=== 生成されたCross Point ===")
                print(f"タイトル: {result['title']}")
                print(f"説明: {result['description']}")
                
                print("\n=== ハイライト1 ===")
                print(f"書籍: {result['highlights'][0]['book_title']} ({result['highlights'][0]['book_author']})")
                print(f"内容: {result['highlights'][0]['content']}")
                
                print("\n=== ハイライト2 ===")
                print(f"書籍: {result['highlights'][1]['book_title']} ({result['highlights'][1]['book_author']})")
                print(f"内容: {result['highlights'][1]['content']}")
            else:
                print("Cross Pointの生成に失敗しました。")
        
        print("\nCross Point機能テストが完了しました。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(test_cross_point())
