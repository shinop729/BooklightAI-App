#!/usr/bin/env python3
# insert_sample_data.py
# 開発ユーザー用のサンプルハイライトデータを直接データベースに挿入するスクリプト

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# データベースモデルをインポート
from api.database.models import User, Book, Highlight

print("開発ユーザー用サンプルデータ挿入スクリプトを開始します...")

# データベースに接続
db_path = './booklight.db'
engine = create_engine(f'sqlite:///{db_path}')
Session = sessionmaker(bind=engine)
session = Session()

try:
    # 開発ユーザーを作成または取得
    dev_user = session.query(User).filter(User.email == 'dev@example.com').first()
    if not dev_user:
        print("開発ユーザーを作成します...")
        dev_user = User(
            username='dev-user',
            email='dev@example.com',
            full_name='開発ユーザー',
            google_id='dev-google-id',
            disabled=0,
            created_at=datetime.utcnow()
        )
        session.add(dev_user)
        session.commit()
        print(f"開発ユーザーを作成しました: ID={dev_user.id}")
    else:
        print(f"既存の開発ユーザーを使用します: ID={dev_user.id}")

    # サンプル書籍データ
    sample_books = [
        {"title": "人工知能の哲学", "author": "ブライアン・クリスチャン"},
        {"title": "デザイン思考", "author": "ティム・ブラウン"},
        {"title": "ゼロ・トゥ・ワン", "author": "ピーター・ティール"},
        {"title": "サピエンス全史", "author": "ユヴァル・ノア・ハラリ"},
        {"title": "アトミック・ハビット", "author": "ジェームズ・クリアー"}
    ]

    # サンプルハイライトデータ
    sample_highlights = [
        {"book_idx": 0, "content": "AIシステムの設計において最も重要なのは、人間の価値観をどのように組み込むかという点である。", "location": "1234"},
        {"book_idx": 0, "content": "機械学習アルゴリズムは、与えられたデータから学習するため、そのデータに含まれるバイアスも学習してしまう。", "location": "1567"},
        {"book_idx": 0, "content": "AIの倫理的問題は、技術的な問題ではなく、社会的な問題である。", "location": "2345"},
        
        {"book_idx": 1, "content": "イノベーションは技術的な発明だけでなく、人間中心の視点から生まれることが多い。", "location": "890"},
        {"book_idx": 1, "content": "プロトタイピングの目的は完璧な製品を作ることではなく、アイデアを素早く形にして検証することである。", "location": "1023"},
        {"book_idx": 1, "content": "デザイン思考は、分析と直感のバランスを取ることが重要である。", "location": "1456"},
        
        {"book_idx": 2, "content": "競争ではなく独占を目指せ。競争は利益を減らし、独占は利益を生む。", "location": "345"},
        {"book_idx": 2, "content": "成功する企業は、他社が見落としている真実を発見する。", "location": "678"},
        {"book_idx": 2, "content": "未来を予測する最善の方法は、それを創造することだ。", "location": "912"},
        
        {"book_idx": 3, "content": "人類は、共有する虚構を信じることで大規模な協力が可能になった。", "location": "2341"},
        {"book_idx": 3, "content": "農業革命は、人類史上最大の詐欺かもしれない。", "location": "3456"},
        {"book_idx": 3, "content": "人間は常に物語を求める生き物である。", "location": "4567"},
        
        {"book_idx": 4, "content": "習慣の力は、複利のように時間とともに大きくなる。", "location": "789"},
        {"book_idx": 4, "content": "目標ではなくシステムに焦点を当てよ。", "location": "1234"},
        {"book_idx": 4, "content": "小さな習慣の積み重ねが、大きな変化をもたらす。", "location": "2345"}
    ]

    # 書籍データの挿入
    books = []
    new_book_count = 0
    
    for book_data in sample_books:
        # 既存の書籍を確認
        book = session.query(Book).filter(
            Book.title == book_data["title"],
            Book.author == book_data["author"],
            Book.user_id == dev_user.id
        ).first()
        
        if not book:
            book = Book(
                title=book_data["title"],
                author=book_data["author"],
                user_id=dev_user.id
            )
            session.add(book)
            session.commit()
            new_book_count += 1
        
        books.append(book)
    
    print(f"書籍データを挿入しました: {new_book_count}冊の新規書籍（合計{len(books)}冊）")

    # ハイライトデータの挿入
    new_highlight_count = 0
    
    for highlight_data in sample_highlights:
        book = books[highlight_data["book_idx"]]
        
        # 既存のハイライトを確認
        highlight = session.query(Highlight).filter(
            Highlight.content == highlight_data["content"],
            Highlight.book_id == book.id,
            Highlight.user_id == dev_user.id
        ).first()
        
        if not highlight:
            highlight = Highlight(
                content=highlight_data["content"],
                location=highlight_data["location"],
                user_id=dev_user.id,
                book_id=book.id,
                created_at=datetime.utcnow()
            )
            session.add(highlight)
            new_highlight_count += 1

    session.commit()
    print(f"ハイライトデータを挿入しました: {new_highlight_count}件の新規ハイライト（合計{len(sample_highlights)}件）")

    # 確認のためにデータを取得して表示
    total_books = session.query(Book).filter(Book.user_id == dev_user.id).count()
    total_highlights = session.query(Highlight).filter(Highlight.user_id == dev_user.id).count()
    
    print(f"\n開発ユーザー（ID={dev_user.id}）のデータ:")
    print(f"- 書籍数: {total_books}冊")
    print(f"- ハイライト数: {total_highlights}件")
    
    print("\nサンプルデータの挿入が完了しました。")

except Exception as e:
    session.rollback()
    print(f"エラーが発生しました: {e}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
