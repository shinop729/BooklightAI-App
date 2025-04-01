"""
ユーザー関連のAPIエンドポイント

このモジュールは、ユーザー関連のAPIエンドポイントを実装します。
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.auth import User, get_current_active_user
from database.base import get_db
import database.models as models

# ロガーの設定
logger = logging.getLogger("booklight-api")

# ルーターの作成
router = APIRouter()

@router.get("/api/user/stats")
async def get_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ユーザーの統計情報を取得するエンドポイント"""
    try:
        # 書籍数を取得
        book_count = db.query(models.Book).filter(
            models.Book.user_id == current_user.id
        ).count()
        
        # ハイライト数を取得
        highlight_count = db.query(models.Highlight).filter(
            models.Highlight.user_id == current_user.id
        ).count()
        
        # 検索回数を取得（検索履歴テーブルがある場合）
        search_count = 0
        try:
            search_count = db.query(models.SearchHistory).filter(
                models.SearchHistory.user_id == current_user.id
            ).count()
        except Exception as e:
            logger.warning(f"検索履歴テーブルの取得に失敗: {e}")
        
        # チャット回数を取得（チャット履歴テーブルがある場合）
        chat_count = 0
        try:
            chat_count = db.query(models.ChatHistory).filter(
                models.ChatHistory.user_id == current_user.id
            ).count()
        except Exception as e:
            logger.warning(f"チャット履歴テーブルの取得に失敗: {e}")
        
        # 最終アクティビティを取得
        # 最新のハイライト、検索、チャットの日時を比較
        last_activity = datetime.utcnow()
        
        # 最新のハイライト
        latest_highlight = db.query(models.Highlight).filter(
            models.Highlight.user_id == current_user.id
        ).order_by(models.Highlight.created_at.desc()).first()
        
        if latest_highlight and latest_highlight.created_at:
            last_activity = latest_highlight.created_at
        
        # 最新の検索（検索履歴テーブルがある場合）
        try:
            latest_search = db.query(models.SearchHistory).filter(
                models.SearchHistory.user_id == current_user.id
            ).order_by(models.SearchHistory.created_at.desc()).first()
            
            if latest_search and latest_search.created_at and latest_search.created_at > last_activity:
                last_activity = latest_search.created_at
        except Exception:
            pass
        
        # 最新のチャット（チャット履歴テーブルがある場合）
        try:
            latest_chat = db.query(models.ChatHistory).filter(
                models.ChatHistory.user_id == current_user.id
            ).order_by(models.ChatHistory.created_at.desc()).first()
            
            if latest_chat and latest_chat.created_at and latest_chat.created_at > last_activity:
                last_activity = latest_chat.created_at
        except Exception:
            pass
        
        # レスポンスの整形
        return {
            "success": True,
            "data": {
                "book_count": book_count,
                "highlight_count": highlight_count,
                "search_count": search_count,
                "chat_count": chat_count,
                "last_activity": last_activity.isoformat()
            }
        }
    except Exception as e:
        logger.error(f"ユーザー統計情報取得エラー: {e}")
        return {
            "success": False,
            "error": "ユーザー統計情報の取得中にエラーが発生しました"
        }
