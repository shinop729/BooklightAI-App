#!/usr/bin/env python3
# test_cross_point_direct.py
# Cross Point機能を直接テストするためのスクリプト

import os
import sys
import json
import asyncio
import random
import logging
import pickle
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional

from sqlalchemy import create_engine, func, or_
from sqlalchemy.orm import sessionmaker, Session

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# データベースモデルをインポート
from api.database.models import User, Book, Highlight, CrossPoint, HighlightEmbedding, ConnectionHistory

# OpenAI APIをインポート
import openai
from api.app.config import settings

# ロガーの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-cross-point")

class CrossPointTester:
    """Cross Point機能テスト用クラス"""
    
    def __init__(self, db: Session, user_id: int):
        """
        CrossPointTesterの初期化
        
        Args:
            db: SQLAlchemyのセッション
            user_id: ユーザーID
        """
        self.db = db
        self.user_id = user_id
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def test_cross_point(self):
        """Cross Point機能をテスト"""
        print("Cross Point機能テストを開始します...")
        
        # ユーザーの書籍数とハイライト数を確認
        book_count = self.db.query(Book).filter(Book.user_id == self.user_id).count()
        highlight_count = self.db.query(Highlight).filter(Highlight.user_id == self.user_id).count()
        
        print(f"ユーザーの書籍数: {book_count}")
        print(f"ユーザーのハイライト数: {highlight_count}")
        
        if book_count < 2:
            print("Cross Point機能をテストするには少なくとも2冊の書籍が必要です。")
            return
        
        # Cross Pointテーブルが存在するか確認
        try:
            # 既存のCross Pointを確認
            today = datetime.now().date()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())
            
            existing_cross_point = self.db.query(CrossPoint).filter(
                CrossPoint.user_id == self.user_id,
                CrossPoint.created_at.between(today_start, today_end)
            ).first()
            
            if existing_cross_point:
                print(f"既存のCross Pointが見つかりました: ID={existing_cross_point.id}")
                print(f"タイトル: {existing_cross_point.title}")
                print(f"説明: {existing_cross_point.description}")
                
                # ハイライト情報を取得
                highlight1 = self.db.query(Highlight).filter(
                    Highlight.id == existing_cross_point.highlight1_id
                ).first()
                
                highlight2 = self.db.query(Highlight).filter(
                    Highlight.id == existing_cross_point.highlight2_id
                ).first()
                
                # 書籍情報を取得
                book1 = self.db.query(Book).filter(
                    Book.id == highlight1.book_id
                ).first()
                
                book2 = self.db.query(Book).filter(
                    Book.id == highlight2.book_id
                ).first()
                
                print("\n=== ハイライト1 ===")
                print(f"書籍: {book1.title} ({book1.author})")
                print(f"内容: {highlight1.content}")
                
                print("\n=== ハイライト2 ===")
                print(f"書籍: {book2.title} ({book2.author})")
                print(f"内容: {highlight2.content}")
                return
        except Exception as e:
            print(f"Cross Pointテーブルが存在しないか、アクセスできません: {e}")
            print("新しいCross Pointの生成のみを行います。")
        
            print("既存のCross Pointが見つかりませんでした。新しいCross Pointを生成します...")
            
            # ハイライト選択（複数の方法を試す）
            highlights = None
            
            # 方法1: セマンティック距離による選択
            highlights = await self._select_semantic_distant_highlights()
            
            # 方法1で失敗した場合、方法2: トピック多様性による選択
            if not highlights:
                highlights = await self._select_topic_diverse_highlights()
            
            # 方法2で失敗した場合、方法3: ジャンル対比による選択
            if not highlights:
                highlights = await self._select_genre_diverse_highlights()
            
            # 全て失敗した場合、方法4: ランダム選択
            if not highlights:
                highlights = self._select_random_highlights()
            
            # ハイライトが選択できなかった場合
            if not highlights or len(highlights) < 2:
                print("ハイライトの選択に失敗しました。")
                return
            
            # Cross Pointを生成して保存
            result = await self._generate_and_save_cross_point(highlights[0], highlights[1])
            
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
    
    async def _select_semantic_distant_highlights(self) -> Optional[List[Highlight]]:
        """
        セマンティック距離によるハイライト選択
        
        異なる書籍から、埋め込みベクトル間のコサイン距離が最も大きい（意味的に遠い）
        ハイライトのペアを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        try:
            # ユーザーのハイライトを取得
            highlights = self.db.query(Highlight).filter(
                Highlight.user_id == self.user_id
            ).all()
            
            if len(highlights) < 10:
                print(f"ハイライト数が少ないため、セマンティック距離選択をスキップ: {len(highlights)} < 10")
                return None
            
            # ハイライトとその埋め込みを取得
            highlight_embeddings = {}
            for highlight in highlights:
                # 埋め込みキャッシュを確認
                embedding_cache = self.db.query(HighlightEmbedding).filter(
                    HighlightEmbedding.highlight_id == highlight.id
                ).first()
                
                if embedding_cache:
                    # キャッシュから埋め込みを取得
                    embedding = pickle.loads(embedding_cache.embedding)
                else:
                    # 新しく埋め込みを生成
                    embedding = await self._generate_embedding(highlight.content)
                    if embedding:
                        # 埋め込みをキャッシュに保存
                        new_cache = HighlightEmbedding(
                            highlight_id=highlight.id,
                            embedding=pickle.dumps(embedding)
                        )
                        self.db.add(new_cache)
                        self.db.commit()
                    else:
                        continue  # 埋め込み生成に失敗した場合はスキップ
                
                # 書籍IDをキーとしてハイライトをグループ化
                book_id = highlight.book_id
                if book_id not in highlight_embeddings:
                    highlight_embeddings[book_id] = []
                
                highlight_embeddings[book_id].append((highlight, embedding))
            
            # 書籍が2冊未満の場合は中止
            if len(highlight_embeddings) < 2:
                print(f"書籍数が少ないため、セマンティック距離選択をスキップ: {len(highlight_embeddings)} < 2")
                return None
            
            # 異なる書籍からハイライトを1つずつランダムに選択
            book_ids = list(highlight_embeddings.keys())
            random.shuffle(book_ids)
            book_id1, book_id2 = book_ids[:2]
            
            # 各書籍から最大10個のハイライトをサンプリング
            highlights1 = highlight_embeddings[book_id1]
            highlights2 = highlight_embeddings[book_id2]
            
            if len(highlights1) > 10:
                highlights1 = random.sample(highlights1, 10)
            if len(highlights2) > 10:
                highlights2 = random.sample(highlights2, 10)
            
            # 最も遠い組み合わせを探す
            max_distance = -1
            best_pair = None
            
            for h1, e1 in highlights1:
                for h2, e2 in highlights2:
                    distance = self._cosine_distance(e1, e2)
                    if distance > max_distance:
                        max_distance = distance
                        best_pair = (h1, h2)
            
            if best_pair:
                print(f"セマンティック距離による選択成功: 距離={max_distance:.4f}")
                return list(best_pair)
            else:
                print("セマンティック距離による選択失敗")
                return None
                
        except Exception as e:
            print(f"セマンティック距離選択エラー: {e}")
            return None
    
    async def _select_topic_diverse_highlights(self) -> Optional[List[Highlight]]:
        """
        トピック多様性によるハイライト選択
        
        異なる書籍から、ランダムにハイライトを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        try:
            # ユーザーのハイライトを取得
            highlights = self.db.query(Highlight).filter(
                Highlight.user_id == self.user_id
            ).all()
            
            if len(highlights) < 5:
                print(f"ハイライト数が少ないため、トピック多様性選択をスキップ: {len(highlights)} < 5")
                return None
            
            # 書籍情報の取得
            books = {}
            for highlight in highlights:
                if highlight.book_id not in books:
                    book = self.db.query(Book).filter(
                        Book.id == highlight.book_id
                    ).first()
                    if book:
                        books[highlight.book_id] = book
            
            # 書籍が2冊未満の場合は中止
            if len(books) < 2:
                print(f"書籍数が少ないため、トピック多様性選択をスキップ: {len(books)} < 2")
                return None
            
            # 書籍からランダムに2冊選択
            book_ids = list(books.keys())
            random.shuffle(book_ids)
            book_id1, book_id2 = book_ids[:2]
            
            # 各書籍からハイライトを1つずつ選択
            highlights1 = self.db.query(Highlight).filter(
                Highlight.user_id == self.user_id,
                Highlight.book_id == book_id1
            ).all()
            
            highlights2 = self.db.query(Highlight).filter(
                Highlight.user_id == self.user_id,
                Highlight.book_id == book_id2
            ).all()
            
            if not highlights1 or not highlights2:
                return None
            
            # ランダムに選択
            highlight1 = random.choice(highlights1)
            highlight2 = random.choice(highlights2)
            
            print(f"トピック多様性による選択成功: 書籍1={books[book_id1].title}, 書籍2={books[book_id2].title}")
            return [highlight1, highlight2]
            
        except Exception as e:
            print(f"トピック多様性選択エラー: {e}")
            return None
    
    async def _select_genre_diverse_highlights(self) -> Optional[List[Highlight]]:
        """
        ジャンル対比によるハイライト選択
        
        異なる書籍から、ランダムにハイライトを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        try:
            # ユーザーの書籍を取得
            books = self.db.query(Book).join(
                Highlight,
                Book.id == Highlight.book_id
            ).filter(
                Highlight.user_id == self.user_id
            ).distinct().all()
            
            if len(books) < 2:
                print(f"書籍数が少ないため、ジャンル対比選択をスキップ: {len(books)} < 2")
                return None
            
            # ランダムに2冊選択
            random.shuffle(books)
            book1, book2 = books[:2]
            
            # 各書籍からハイライトを1つずつ選択
            highlight1 = self.db.query(Highlight).filter(
                Highlight.user_id == self.user_id,
                Highlight.book_id == book1.id
            ).order_by(func.random()).first()
            
            highlight2 = self.db.query(Highlight).filter(
                Highlight.user_id == self.user_id,
                Highlight.book_id == book2.id
            ).order_by(func.random()).first()
            
            if not highlight1 or not highlight2:
                return None
            
            print(f"ジャンル対比による選択成功: 書籍1={book1.title}, 書籍2={book2.title}")
            return [highlight1, highlight2]
            
        except Exception as e:
            print(f"ジャンル対比選択エラー: {e}")
            return None
    
    def _select_random_highlights(self) -> Optional[List[Highlight]]:
        """
        ランダムなハイライト選択（フォールバック）
        
        異なる書籍から、ランダムにハイライトを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        try:
            # ユーザーの異なる書籍からハイライトを取得
            books = self.db.query(Book).join(
                Highlight,
                Book.id == Highlight.book_id
            ).filter(
                Highlight.user_id == self.user_id
            ).distinct().all()
            
            if len(books) < 2:
                print(f"書籍数が少ないため、ランダム選択失敗: {len(books)} < 2")
                return None
            
            # ランダムに2冊選択
            random.shuffle(books)
            book1, book2 = books[:2]
            
            # 各書籍からハイライトを1つずつ選択
            highlight1 = self.db.query(Highlight).filter(
                Highlight.user_id == self.user_id,
                Highlight.book_id == book1.id
            ).order_by(func.random()).first()
            
            highlight2 = self.db.query(Highlight).filter(
                Highlight.user_id == self.user_id,
                Highlight.book_id == book2.id
            ).order_by(func.random()).first()
            
            if not highlight1 or not highlight2:
                return None
            
            print(f"ランダム選択成功: 書籍1={book1.title}, 書籍2={book2.title}")
            return [highlight1, highlight2]
            
        except Exception as e:
            print(f"ランダム選択エラー: {e}")
            return None
    
    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        テキストの埋め込みベクトルを生成
        
        Args:
            text: 埋め込みベクトルを生成するテキスト
            
        Returns:
            埋め込みベクトル、または失敗した場合はNone
        """
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"埋め込み生成エラー: {e}")
            return None
    
    def _cosine_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """
        コサイン距離を計算（1 - コサイン類似度）
        
        Args:
            vec1: 1つ目のベクトル
            vec2: 2つ目のベクトル
            
        Returns:
            コサイン距離（0-2の範囲、0が最も近く、2が最も遠い）
        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 1.0  # 最大距離
            
        similarity = dot_product / (norm1 * norm2)
        # 距離に変換（1 - 類似度）
        return 1.0 - similarity
    
    async def _generate_and_save_cross_point(
        self, highlight1: Highlight, highlight2: Highlight
    ) -> Dict[str, Any]:
        """
        Cross Pointを生成して保存
        
        Args:
            highlight1: 1つ目のハイライト
            highlight2: 2つ目のハイライト
            
        Returns:
            生成されたCross Pointの情報を含む辞書
        """
        # 書籍情報を取得
        book1 = self.db.query(Book).filter(
            Book.id == highlight1.book_id
        ).first()
        
        book2 = self.db.query(Book).filter(
            Book.id == highlight2.book_id
        ).first()
        
        if not book1 or not book2:
            print(f"書籍情報の取得に失敗: book1_id={highlight1.book_id}, book2_id={highlight2.book_id}")
            return None
        
        # Cross Point生成プロンプト
        prompt = f"""
        以下の2つの一見関連性のない本からのハイライトを結びつける、意外で知的好奇心をくすぐる関連性を発見してください。
        
        書籍1「{book1.title}」（{book1.author}）からのハイライト:
        "{highlight1.content}"
        
        書籍2「{book2.title}」（{book2.author}）からのハイライト:
        "{highlight2.content}"
        
        【指示】
        1. 表面的には全く関係なさそうなこの2つのハイライトの間にある、深層的な繋がりや対照的な面白さを見つけてください。
        2. 誰かに「へぇ！そういう見方があるのか！」と思わせるような関連性を探してください。
        3. 哲学的な洞察、共通する原理原則、対極にありながらも補完しあう関係性などに着目すると良いでしょう。
        
        【返答形式】
        タイトル: [関連性を表す20文字程度の魅力的なタイトル]
        
        [100〜150文字で関連性を説明。この部分は「なるほど！」と思わせる驚きと発見を感じる内容にしてください]
        """
        
        try:
            # OpenAI APIで関連性を生成
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            connection_text = response.choices[0].message.content
            
            # タイトルと説明文を分離
            lines = connection_text.strip().split("\n")
            title = lines[0].replace("タイトル:", "").strip()
            description = "\n".join(lines[1:]).strip()
            
            print(f"Cross Point生成成功: タイトル={title}")
            
            # テスト環境ではデータベースへの保存をスキップし、生成された内容のみを返す
            return {
                "id": 0,  # ダミーID
                "title": title,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "liked": False,
                "highlights": [
                    {
                        "id": highlight1.id,
                        "content": highlight1.content,
                        "book_id": highlight1.book_id,
                        "book_title": book1.title,
                        "book_author": book1.author
                    },
                    {
                        "id": highlight2.id,
                        "content": highlight2.content,
                        "book_id": highlight2.book_id,
                        "book_title": book2.title,
                        "book_author": book2.author
                    }
                ]
            }
            
        except Exception as e:
            print(f"Cross Point生成エラー: {e}")
            return None
    
    def _format_cross_point_response(self, cross_point: CrossPoint) -> Dict[str, Any]:
        """
        APIレスポンス用にデータをフォーマット
        
        Args:
            cross_point: フォーマットするCross Point
            
        Returns:
            フォーマットされたレスポンス辞書
        """
        # ハイライト情報を取得
        highlight1 = self.db.query(Highlight).filter(
            Highlight.id == cross_point.highlight1_id
        ).first()
        
        highlight2 = self.db.query(Highlight).filter(
            Highlight.id == cross_point.highlight2_id
        ).first()
        
        # 書籍情報を取得
        book1 = self.db.query(Book).filter(
            Book.id == highlight1.book_id
        ).first()
        
        book2 = self.db.query(Book).filter(
            Book.id == highlight2.book_id
        ).first()
        
        return {
            "id": cross_point.id,
            "title": cross_point.title,
            "description": cross_point.description,
            "created_at": cross_point.created_at.isoformat(),
            "liked": cross_point.liked,
            "highlights": [
                {
                    "id": highlight1.id,
                    "content": highlight1.content,
                    "book_id": highlight1.book_id,
                    "book_title": book1.title,
                    "book_author": book1.author
                },
                {
                    "id": highlight2.id,
                    "content": highlight2.content,
                    "book_id": highlight2.book_id,
                    "book_title": book2.title,
                    "book_author": book2.author
                }
            ]
        }

async def main():
    """メイン関数"""
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

        # Cross Pointテスターの初期化
        tester = CrossPointTester(session, dev_user.id)
        
        # Cross Point機能をテスト
        await tester.test_cross_point()

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(main())
