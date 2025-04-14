"""
ハイライト関連のAPIエンドポイント

このモジュールは、ハイライト関連のAPIエンドポイントを実装します。
"""

import logging
import random
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.auth import User, get_current_active_user
from database.base import get_db
from pydantic import BaseModel, Field
from datetime import datetime

import database.models as models
from database.session import get_db # get_db をインポート

# ロガーの設定
logger = logging.getLogger("booklight-api")

# --- Pydanticモデル定義 ---
class HighlightCreate(BaseModel):
    content: str
    location: Optional[str] = None

class BookInfo(BaseModel):
    title: str
    author: str
    cover_image_url: Optional[str] = None

class BulkHighlightRequest(BaseModel):
    book_info: BookInfo
    highlights: List[HighlightCreate]

class BulkHighlightResponse(BaseModel):
    success: bool
    message: str
    added_count: int
    book_id: int

# ルーターの作成
router = APIRouter()

@router.get("/api/highlights/random")
async def get_random_highlight(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ランダムなハイライトを取得するエンドポイント"""
    try:
        # ユーザーのハイライト総数を取得
        highlight_count = db.query(models.Highlight).filter(
            models.Highlight.user_id == current_user.id
        ).count()
        
        if highlight_count == 0:
            return {
                "success": False,
                "error": "ハイライトが登録されていません"
            }
        
        # ランダムなオフセットを生成
        random_offset = random.randint(0, highlight_count - 1)
        
        # ランダムなハイライトを取得
        random_highlight = db.query(models.Highlight).filter(
            models.Highlight.user_id == current_user.id
        ).offset(random_offset).limit(1).first()
        
        if not random_highlight:
            return {
                "success": False,
                "error": "ハイライトの取得に失敗しました"
            }
        
        # 書籍情報を取得
        book = db.query(models.Book).filter(
            models.Book.id == random_highlight.book_id
        ).first()
        
        if not book:
            return {
                "success": False,
                "error": "書籍情報の取得に失敗しました"
            }
        
        # レスポンスの整形
        return {
            "success": True,
            "data": {
                "id": random_highlight.id,
                "content": random_highlight.content,
                "title": book.title,
                "author": book.author,
                "bookId": book.id,
                "location": random_highlight.location,
                "createdAt": random_highlight.created_at.isoformat() if random_highlight.created_at else None
            }
        }
    except Exception as e:
        logger.error(f"ランダムハイライト取得エラー: {e}")
        return {
            "success": False,
            "error": "ランダムハイライトの取得中にエラーが発生しました"
        }

@router.post("/api/highlights/bulk", response_model=BulkHighlightResponse, status_code=status.HTTP_201_CREATED)
async def create_bulk_highlights(
    request: BulkHighlightRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Chrome拡張機能からハイライトを一括登録するエンドポイント"""
    logger.info(f"一括ハイライト登録リクエスト受信: User ID={current_user.id}, Book Title='{request.book_info.title}'")
    
    try:
        # 1. 書籍情報の取得または作成
        book = db.query(models.Book).filter(
            models.Book.title == request.book_info.title,
            models.Book.author == request.book_info.author,
            models.Book.user_id == current_user.id  # ユーザーに紐づく書籍を検索
        ).first()

        if not book:
            logger.info(f"書籍が見つからないため新規作成: Title='{request.book_info.title}'")
            book = models.Book(
                title=request.book_info.title,
                author=request.book_info.author,
                cover_image_url=request.book_info.cover_image_url,
                user_id=current_user.id # ユーザーIDを紐付け
            )
            db.add(book)
            db.flush() # book.id を確定させる
        else:
            # 既存書籍のカバー画像を更新（必要であれば）
            if request.book_info.cover_image_url and book.cover_image_url != request.book_info.cover_image_url:
                logger.info(f"書籍カバー画像URLを更新: Book ID={book.id}")
                book.cover_image_url = request.book_info.cover_image_url
                db.add(book) # SQLAlchemyは変更を検知するが、明示的にaddしても良い

        # 2. ハイライトの差分登録
        added_count = 0
        new_highlights = []
        for hl_data in request.highlights:
            # 既存ハイライトの確認 (user_id, book_id, content, location で一意性を判断)
            exists = db.query(models.Highlight).filter(
                models.Highlight.user_id == current_user.id,
                models.Highlight.book_id == book.id,
                models.Highlight.content == hl_data.content,
                models.Highlight.location == hl_data.location
            ).first()

            if not exists:
                new_highlight = models.Highlight(
                    content=hl_data.content,
                    location=hl_data.location,
                    user_id=current_user.id,
                    book_id=book.id,
                    created_at=datetime.utcnow() # 登録日時を設定
                )
                new_highlights.append(new_highlight)
                added_count += 1

        if new_highlights:
            db.add_all(new_highlights)
            logger.info(f"{added_count}件の新規ハイライトを追加: Book ID={book.id}")
        else:
            logger.info(f"新規ハイライトなし: Book ID={book.id}")

        db.commit()
        db.refresh(book) # bookオブジェクトを最新の状態に更新

        return BulkHighlightResponse(
            success=True,
            message=f"{added_count}件のハイライトを追加しました。",
            added_count=added_count,
            book_id=book.id
        )

    except Exception as e:
        db.rollback()
        logger.error(f"一括ハイライト登録エラー: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ハイライトの登録中にエラーが発生しました: {str(e)}"
        )
