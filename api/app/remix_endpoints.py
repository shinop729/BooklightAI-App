"""
Remix機能のAPIエンドポイント

このモジュールは、Remix機能のAPIエンドポイントを実装します。
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import User, get_current_active_user
from database.base import get_db
import database.models as models
from app.remix import RemixService

# ロガーの設定
logger = logging.getLogger("booklight-api")

# ルーターの作成
router = APIRouter()

# ランダムテーマ生成エンドポイント
@router.get("/api/remix/random-theme")
async def get_random_theme(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ランダムなテーマを生成するエンドポイント"""
    service = RemixService(db, current_user.id)
    theme = await service.generate_random_theme()
    
    return {
        "success": True,
        "data": {
            "theme": theme
        }
    }

# Remix生成エンドポイント
@router.post("/api/remix")
async def generate_remix(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ランダムに選択されたハイライトからRemixを生成するエンドポイント"""
    highlight_count = request.get("highlight_count", 5)
    
    # ハイライト数の検証
    if not isinstance(highlight_count, int) or highlight_count < 2:
        highlight_count = 5
    
    service = RemixService(db, current_user.id)
    result = await service.generate_remix(highlight_count)
    return result

# IDによるRemix取得エンドポイント
@router.get("/api/remix/{remix_id}")
async def get_remix_by_id(
    remix_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """IDでRemixを取得するエンドポイント"""
    service = RemixService(db, current_user.id)
    result = await service.get_remix_by_id(remix_id)
    
    if not result:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "指定されたRemixが見つかりません"
            }
        )
    
    return {
        "success": True,
        "data": result
    }

# ユーザーのRemix一覧取得エンドポイント
@router.get("/api/remixes")
async def get_user_remixes(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ユーザーのRemix一覧を取得するエンドポイント"""
    offset = (page - 1) * page_size
    
    service = RemixService(db, current_user.id)
    remixes = await service.get_user_remixes(limit=page_size, offset=offset)
    
    # 総数の取得
    total = db.query(models.Remix).filter(
        models.Remix.user_id == current_user.id
    ).count()
    
    return {
        "success": True,
        "data": {
            "items": remixes,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }
