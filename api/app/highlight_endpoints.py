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
import database.models as models

# ロガーの設定
logger = logging.getLogger("booklight-api")

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
