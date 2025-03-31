"""
Cross Point機能の実装

このモジュールは、ユーザーの異なる書籍から選ばれた2つのハイライトを
意外な視点で関連付け、「マジックモーメント」を提供する機能を実装します。
"""

import os
import random
import logging
import pickle
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, Union

from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import openai

import database.models as models
from app.config import settings

# ロガーの設定
logger = logging.getLogger("booklight-api")

class CrossPointService:
    """Cross Point生成サービス"""
    
    def __init__(self, db: Session, user_id: int):
        """
        CrossPointServiceの初期化
        
        Args:
            db: SQLAlchemyのセッション
            user_id: ユーザーID
        """
        self.db = db
        self.user_id = user_id
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def get_daily_cross_point(self) -> Optional[Dict[str, Any]]:
        """
        日次のCross Pointを取得する
        
        Returns:
            Cross Pointの情報を含む辞書、または存在しない場合はNone
        """
        # 今日の日付
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # 今日既に生成したCross Pointがあるか確認
        daily_conn = self.db.query(models.CrossPoint).filter(
            models.CrossPoint.user_id == self.user_id,
            models.CrossPoint.created_at.between(today_start, today_end)
        ).first()
        
        # 既存のCross Pointがあればそれを返す
        if daily_conn:
            logger.info(f"既存のCross Pointを返します: ID={daily_conn.id}")
            return self._format_cross_point_response(daily_conn)
        
        # 新しいCross Pointを生成
        logger.info(f"新しいCross Pointを生成します: ユーザーID={self.user_id}")
        
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
            logger.warning(f"ハイライトの選択に失敗しました: ユーザーID={self.user_id}")
            return None
        
        # Cross Pointを生成して保存
        return await self._generate_and_save_cross_point(highlights[0], highlights[1])
    
    async def _select_semantic_distant_highlights(self) -> Optional[List[models.Highlight]]:
        """
        セマンティック距離によるハイライト選択
        
        異なる書籍から、埋め込みベクトル間のコサイン距離が最も大きい（意味的に遠い）
        ハイライトのペアを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        try:
            # ユーザーのハイライトを取得
            highlights = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id
            ).all()
            
            if len(highlights) < 10:
                logger.info(f"ハイライト数が少ないため、セマンティック距離選択をスキップ: {len(highlights)} < 10")
                return None
            
            # ハイライトとその埋め込みを取得
            highlight_embeddings = {}
            for highlight in highlights:
                # 埋め込みキャッシュを確認
                embedding_cache = self.db.query(models.HighlightEmbedding).filter(
                    models.HighlightEmbedding.highlight_id == highlight.id
                ).first()
                
                if embedding_cache:
                    # キャッシュから埋め込みを取得
                    embedding = pickle.loads(embedding_cache.embedding)
                else:
                    # 新しく埋め込みを生成
                    embedding = await self._generate_embedding(highlight.content)
                    if embedding:
                        # 埋め込みをキャッシュに保存
                        new_cache = models.HighlightEmbedding(
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
                logger.info(f"書籍数が少ないため、セマンティック距離選択をスキップ: {len(highlight_embeddings)} < 2")
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
                logger.info(f"セマンティック距離による選択成功: 距離={max_distance:.4f}")
                return list(best_pair)
            else:
                logger.warning("セマンティック距離による選択失敗")
                return None
                
        except Exception as e:
            logger.error(f"セマンティック距離選択エラー: {e}")
            return None
    
    async def _select_topic_diverse_highlights(self) -> Optional[List[models.Highlight]]:
        """
        トピック多様性によるハイライト選択
        
        異なる書籍から、ランダムにハイライトを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        try:
            # ユーザーのハイライトを取得
            highlights = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id
            ).all()
            
            if len(highlights) < 5:
                logger.info(f"ハイライト数が少ないため、トピック多様性選択をスキップ: {len(highlights)} < 5")
                return None
            
            # 書籍情報の取得
            books = {}
            for highlight in highlights:
                if highlight.book_id not in books:
                    book = self.db.query(models.Book).filter(
                        models.Book.id == highlight.book_id
                    ).first()
                    if book:
                        books[highlight.book_id] = book
            
            # 書籍が2冊未満の場合は中止
            if len(books) < 2:
                logger.info(f"書籍数が少ないため、トピック多様性選択をスキップ: {len(books)} < 2")
                return None
            
            # 書籍からランダムに2冊選択
            book_ids = list(books.keys())
            random.shuffle(book_ids)
            book_id1, book_id2 = book_ids[:2]
            
            # 各書籍からハイライトを1つずつ選択
            highlights1 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book_id1
            ).all()
            
            highlights2 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book_id2
            ).all()
            
            if not highlights1 or not highlights2:
                return None
            
            # ランダムに選択
            highlight1 = random.choice(highlights1)
            highlight2 = random.choice(highlights2)
            
            logger.info(f"トピック多様性による選択成功: 書籍1={books[book_id1].title}, 書籍2={books[book_id2].title}")
            return [highlight1, highlight2]
            
        except Exception as e:
            logger.error(f"トピック多様性選択エラー: {e}")
            return None
    
    async def _select_genre_diverse_highlights(self) -> Optional[List[models.Highlight]]:
        """
        ジャンル対比によるハイライト選択
        
        異なる書籍から、ランダムにハイライトを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        try:
            # ユーザーの書籍を取得
            books = self.db.query(models.Book).join(
                models.Highlight,
                models.Book.id == models.Highlight.book_id
            ).filter(
                models.Highlight.user_id == self.user_id
            ).distinct().all()
            
            if len(books) < 2:
                logger.info(f"書籍数が少ないため、ジャンル対比選択をスキップ: {len(books)} < 2")
                return None
            
            # ランダムに2冊選択
            random.shuffle(books)
            book1, book2 = books[:2]
            
            # 各書籍からハイライトを1つずつ選択
            highlight1 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book1.id
            ).order_by(func.random()).first()
            
            highlight2 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book2.id
            ).order_by(func.random()).first()
            
            if not highlight1 or not highlight2:
                return None
            
            logger.info(f"ジャンル対比による選択成功: 書籍1={book1.title}, 書籍2={book2.title}")
            return [highlight1, highlight2]
            
        except Exception as e:
            logger.error(f"ジャンル対比選択エラー: {e}")
            return None
    
    def _select_random_highlights(self) -> Optional[List[models.Highlight]]:
        """
        ランダムなハイライト選択（フォールバック）
        
        異なる書籍から、ランダムにハイライトを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        try:
            # ユーザーの異なる書籍からハイライトを取得
            books = self.db.query(models.Book).join(
                models.Highlight,
                models.Book.id == models.Highlight.book_id
            ).filter(
                models.Highlight.user_id == self.user_id
            ).distinct().all()
            
            if len(books) < 2:
                logger.warning(f"書籍数が少ないため、ランダム選択失敗: {len(books)} < 2")
                return None
            
            # ランダムに2冊選択
            random.shuffle(books)
            book1, book2 = books[:2]
            
            # 各書籍からハイライトを1つずつ選択
            highlight1 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book1.id
            ).order_by(func.random()).first()
            
            highlight2 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book2.id
            ).order_by(func.random()).first()
            
            if not highlight1 or not highlight2:
                return None
            
            logger.info(f"ランダム選択成功: 書籍1={book1.title}, 書籍2={book2.title}")
            return [highlight1, highlight2]
            
        except Exception as e:
            logger.error(f"ランダム選択エラー: {e}")
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
            logger.error(f"埋め込み生成エラー: {e}")
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
        self, highlight1: models.Highlight, highlight2: models.Highlight
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
        book1 = self.db.query(models.Book).filter(
            models.Book.id == highlight1.book_id
        ).first()
        
        book2 = self.db.query(models.Book).filter(
            models.Book.id == highlight2.book_id
        ).first()
        
        if not book1 or not book2:
            logger.error(f"書籍情報の取得に失敗: book1_id={highlight1.book_id}, book2_id={highlight2.book_id}")
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
            
            # Cross Pointをデータベースに保存
            cross_point = models.CrossPoint(
                user_id=self.user_id,
                highlight1_id=highlight1.id,
                highlight2_id=highlight2.id,
                title=title,
                description=description
            )
            self.db.add(cross_point)
            
            # コネクション履歴に追加
            history = models.ConnectionHistory(
                user_id=self.user_id,
                highlight1_id=highlight1.id,
                highlight2_id=highlight2.id
            )
            self.db.add(history)
            
            self.db.commit()
            self.db.refresh(cross_point)
            
            logger.info(f"Cross Point生成・保存成功: ID={cross_point.id}, タイトル={title}")
            
            return self._format_cross_point_response(cross_point)
            
        except Exception as e:
            logger.error(f"Cross Point生成エラー: {e}")
            self.db.rollback()
            return None
    
    def _format_cross_point_response(self, cross_point: models.CrossPoint) -> Dict[str, Any]:
        """
        APIレスポンス用にデータをフォーマット
        
        Args:
            cross_point: フォーマットするCross Point
            
        Returns:
            フォーマットされたレスポンス辞書
        """
        # ハイライト情報を取得
        highlight1 = self.db.query(models.Highlight).filter(
            models.Highlight.id == cross_point.highlight1_id
        ).first()
        
        highlight2 = self.db.query(models.Highlight).filter(
            models.Highlight.id == cross_point.highlight2_id
        ).first()
        
        # 書籍情報を取得
        book1 = self.db.query(models.Book).filter(
            models.Book.id == highlight1.book_id
        ).first()
        
        book2 = self.db.query(models.Book).filter(
            models.Book.id == highlight2.book_id
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

    async def generate_embeddings_for_all_highlights(self) -> Dict[str, Any]:
        """
        ユーザーの全ハイライトの埋め込みベクトルを生成
        
        Returns:
            処理結果の情報を含む辞書
        """
        try:
            # ユーザーのハイライトを取得
            highlights = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id
            ).all()
            
            if not highlights:
                return {
                    "success": False,
                    "message": "ハイライトが見つかりません",
                    "processed": 0,
                    "total": 0
                }
            
            # 既に埋め込みが生成されているハイライトを除外
            existing_embeddings = self.db.query(models.HighlightEmbedding.highlight_id).all()
            existing_ids = {e[0] for e in existing_embeddings}
            
            highlights_to_process = [h for h in highlights if h.id not in existing_ids]
            
            if not highlights_to_process:
                return {
                    "success": True,
                    "message": "全てのハイライトの埋め込みは既に生成されています",
                    "processed": 0,
                    "total": len(highlights)
                }
            
            # 埋め込みベクトルを生成
            processed_count = 0
            for highlight in highlights_to_process:
                embedding = await self._generate_embedding(highlight.content)
                if embedding:
                    # 埋め込みをキャッシュに保存
                    new_cache = models.HighlightEmbedding(
                        highlight_id=highlight.id,
                        embedding=pickle.dumps(embedding)
                    )
                    self.db.add(new_cache)
                    processed_count += 1
            
            self.db.commit()
            
            return {
                "success": True,
                "message": f"{processed_count}件のハイライトの埋め込みを生成しました",
                "processed": processed_count,
                "total": len(highlights)
            }
            
        except Exception as e:
            logger.error(f"埋め込みベクトル生成エラー: {e}")
            self.db.rollback()
            return {
                "success": False,
                "message": f"埋め込みベクトル生成中にエラーが発生しました: {str(e)}",
                "processed": 0,
                "total": 0
            }
