# Cross Point実装計画書

## 概要

「Cross Point」は、ユーザーがログインするたびに、過去に読んだ異なる書籍から選ばれた2つのハイライトを、意外な視点で関連付けて提示する機能です。特に「離れた内容」のハイライト同士をつなぐことで、ユーザーに「マジックモーメント」を提供することが目的です。

## 目標

- ユーザーの読書体験に新たな価値を付加する
- 思いがけない発見を通じて知的好奇心を刺激する
- 単なるハイライト検索を超えた体験を提供する
- 離れた内容同士の繋がりを見出すことで、新たな視点や洞察を促す

## 全体の実装アーキテクチャ

```
┌─────────────────┐    ┌──────────────────────┐    ┌────────────────────┐
│                 │    │                      │    │                    │
│  フロントエンド  │◄───┤  APIエンドポイント    │◄───┤  コネクション生成   │
│  (React)        │    │  (FastAPI)          │    │  アルゴリズム        │
│                 │    │                      │    │                    │
└─────────────────┘    └──────────────────────┘    └────────────────────┘
                                 │                           │
                                 ▼                           ▼
                        ┌─────────────────┐         ┌─────────────────┐
                        │                 │         │                 │
                        │  データベース    │         │  OpenAI API     │
                        │  (SQLite/Postgres)│        │  (Embeddings/GPT)│
                        │                 │         │                 │
                        └─────────────────┘         └─────────────────┘
```

## 実装ステップ詳細

### 1. データベーススキーマの拡張

#### 新規テーブル設計

```sql
-- Cross Point履歴テーブル
CREATE TABLE cross_point (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    highlight1_id INTEGER NOT NULL,
    highlight2_id INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    liked BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (highlight1_id) REFERENCES highlights(id),
    FOREIGN KEY (highlight2_id) REFERENCES highlights(id)
);

-- ハイライト埋め込みキャッシュテーブル
CREATE TABLE highlight_embeddings (
    highlight_id INTEGER PRIMARY KEY,
    embedding BLOB NOT NULL,  -- バイナリ形式で埋め込みベクトルを保存
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (highlight_id) REFERENCES highlights(id)
);

-- 既に表示した組み合わせを記録するテーブル
CREATE TABLE connection_history (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    highlight1_id INTEGER NOT NULL,
    highlight2_id INTEGER NOT NULL, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (highlight1_id) REFERENCES highlights(id),
    FOREIGN KEY (highlight2_id) REFERENCES highlights(id)
);
```

#### Alembicマイグレーションスクリプト

```python
"""add_daily_connection_tables

Revision ID: xxxxxxxxxxxx
Revises: xxxxxxxxxxxx
Create Date: 2025-03-31 XX:XX:XX.XXXXXX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Cross Point履歴テーブル
    op.create_table(
        'cross_point',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('highlight1_id', sa.Integer(), nullable=False),
        sa.Column('highlight2_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('liked', sa.Boolean(), nullable=True, default=False),
        sa.ForeignKeyConstraint(['highlight1_id'], ['highlights.id'], ),
        sa.ForeignKeyConstraint(['highlight2_id'], ['highlights.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ハイライト埋め込みキャッシュテーブル
    op.create_table(
        'highlight_embeddings',
        sa.Column('highlight_id', sa.Integer(), nullable=False),
        sa.Column('embedding', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['highlight_id'], ['highlights.id'], ),
        sa.PrimaryKeyConstraint('highlight_id')
    )
    
    # 既に表示した組み合わせを記録するテーブル
    op.create_table(
        'connection_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('highlight1_id', sa.Integer(), nullable=False),
        sa.Column('highlight2_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['highlight1_id'], ['highlights.id'], ),
        sa.ForeignKeyConstraint(['highlight2_id'], ['highlights.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('connection_history')
    op.drop_table('highlight_embeddings')
    op.drop_table('cross_point')
```

#### 新規モデル定義

```python
# api/database/models.py に追加

class DailyConnection(Base):
    """Cross Point履歴モデル"""
    __tablename__ = "cross_point"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    highlight1_id = Column(Integer, ForeignKey('highlights.id'), nullable=False)
    highlight2_id = Column(Integer, ForeignKey('highlights.id'), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    liked = Column(Boolean, default=False)
    
    user = relationship("User", backref="cross_point")
    highlight1 = relationship("Highlight", foreign_keys=[highlight1_id])
    highlight2 = relationship("Highlight", foreign_keys=[highlight2_id])

class HighlightEmbedding(Base):
    """ハイライト埋め込みキャッシュモデル"""
    __tablename__ = "highlight_embeddings"

    highlight_id = Column(Integer, ForeignKey('highlights.id'), primary_key=True)
    embedding = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    highlight = relationship("Highlight", backref="embedding_cache")

class ConnectionHistory(Base):
    """コネクション履歴モデル"""
    __tablename__ = "connection_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    highlight1_id = Column(Integer, ForeignKey('highlights.id'), nullable=False)
    highlight2_id = Column(Integer, ForeignKey('highlights.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref="connection_history")
    highlight1 = relationship("Highlight", foreign_keys=[highlight1_id])
    highlight2 = relationship("Highlight", foreign_keys=[highlight2_id])
```

### 2. ハイライト選択アルゴリズムの実装

#### 実装方針

「遠いコネクション」を見つけるために、以下の方法を実装します：

1. セマンティック距離による選択
2. トピック多様性による選択
3. ジャンル対比による選択
4. 組み合わせ手法による選択

#### 実装コード

```python
# api/app/daily_connection.py

import os
import random
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
import pickle

from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import openai

import database.models as models
from app.config import settings

logger = logging.getLogger("booklight-api")

class DailyConnectionService:
    """Cross Point生成サービス"""
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def get_daily_connection(self) -> Optional[Dict[str, Any]]:
        """Cross Pointを取得する"""
        # 今日の日付
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # 今日既に生成したコネクションがあるか確認
        daily_conn = self.db.query(models.DailyConnection).filter(
            models.DailyConnection.user_id == self.user_id,
            models.DailyConnection.created_at.between(today_start, today_end)
        ).first()
        
        # 既存のコネクションがあればそれを返す
        if daily_conn:
            logger.info(f"既存のCross Pointを返します: ID={daily_conn.id}")
            return self._format_connection_response(daily_conn)
        
        # 新しいコネクションを生成
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
        
        # コネクションを生成して保存
        return await self._generate_and_save_connection(highlights[0], highlights[1])
    
    async def _select_semantic_distant_highlights(self) -> Optional[List[models.Highlight]]:
        """セマンティック距離によるハイライト選択"""
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
        """トピック多様性によるハイライト選択"""
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
        """ジャンル対比によるハイライト選択"""
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
        """ランダムなハイライト選択（フォールバック）"""
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
        """テキストの埋め込みベクトルを生成"""
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
        """コサイン距離を計算（1 - コサイン類似度）"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 1.0  # 最大距離
            
        similarity = dot_product / (norm1 * norm2)
        # 距離に変換（1 - 類似度）
        return 1.0 - similarity
    
    async def _generate_and_save_connection(
        self, highlight1: models.Highlight, highlight2: models.Highlight
    ) -> Dict[str, Any]:
        """コネクションを生成して保存"""
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
        
        # コネクション生成プロンプト
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
            
            # コネクションをDBに保存
            daily_connection = models.DailyConnection(
                user_id=self.user_id,
                highlight1_id=highlight1.id,
                highlight2_id=highlight2.id,
                title=title,
                description=description
            )
            self.db.add(daily_connection)
            
            # コネクション履歴に追加
            history = models.ConnectionHistory(
                user_id=self.user_id,
                highlight1_id=highlight1.id,
                highlight2_id=highlight2.id
            )
            self.db.add(history)
            
            self.db.commit()
            self.db.refresh(daily_connection)
            
            logger.info(f"コネクション生成・保存成功: ID={daily_connection.id}, タイトル={title}")
            
            return self._format_connection_response(daily_connection)
            
        except Exception as e:
            logger.error(f"コネクション生成エラー: {e}")
            self.db.rollback()
            return None
    
    def _format_connection_response(self, daily_conn: models.DailyConnection) -> Dict[str, Any]:
        """APIレスポンス用にデータをフォーマット"""
        # ハイライト情報を取得
        highlight1 = self.db.query(models.Highlight).filter(
            models.Highlight.id == daily_conn.highlight1_id
        ).first()
        
        highlight2 = self.db.query(models.Highlight).filter(
            models.Highlight.id == daily_conn.highlight2_id
        ).first()
        
        # 書籍情報を取得
        book1 = self.db.query(models.Book).filter(
            models.Book.id == highlight1.book_id
        ).first()
        
        book2 = self.db.query(models.Book).filter(
            models.Book.id == highlight2.book_id
        ).first()
        
        return {
            "id": daily_conn.id,
            "title": daily_conn.title,
            "description": daily_conn.description,
            "created_at": daily_conn.created_at.isoformat(),
            "liked": daily_conn.liked,
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
```

### 3. APIエンドポイントの実装

```python
# api/app/main.py に追加

from app.daily_connection import DailyConnectionService

@app.post("/api/daily-connection")
async def get_daily_connection(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cross Pointを取得するエンドポイント"""
    service = DailyConnectionService(db, current_user.id)
    result = await service.get_daily_connection()
    
    if not result:
        logger.warning(f"Cross Pointの生成に失敗: user_id={current_user.id}")
        return {
            "success": False,
            "message": "Cross Pointを生成するには少なくとも2冊の書籍が必要です。"
        }
    
    return {
        "success": True,
        "data": result
    }

@app.post("/api/daily-connection/{connection_id}/like")