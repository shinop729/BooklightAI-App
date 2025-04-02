"""
Cross Point機能のAPIエンドポイント

このモジュールは、Cross Point機能のAPIエンドポイントを実装します。
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import User, get_current_active_user
from database.base import get_db
import database.models as models
from app.cross_point import CrossPointService

# ロガーの設定
logger = logging.getLogger("booklight-api")

# ルーターの作成
router = APIRouter()

# Cross Point取得エンドポイント
@router.get("/api/cross-point")
async def get_cross_point(
    force: bool = Query(False, description="Trueの場合、既存の今日のCross Pointを無視して強制的に再生成する"), # forceクエリパラメータを追加
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cross Pointを取得するエンドポイント"""
    service = CrossPointService(db, current_user.id)
    # force パラメータをサービスメソッドに渡す
    result = await service.get_daily_cross_point(force_generate=force)
    
    if not result:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Cross Pointを生成するには少なくとも2冊の書籍が必要です。"
            }
        )
    
    return {
        "success": True,
        "data": result
    }

# Cross Pointお気に入り登録エンドポイント
@router.post("/api/cross-point/{cross_point_id}/like")
async def like_cross_point(
    cross_point_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cross Pointをお気に入り登録するエンドポイント"""
    # Cross Pointを取得
    cross_point = db.query(models.CrossPoint).filter(
        models.CrossPoint.id == cross_point_id,
        models.CrossPoint.user_id == current_user.id
    ).first()
    
    if not cross_point:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "指定されたCross Pointが見つかりません"
            }
        )
    
    # お気に入り状態を切り替え
    cross_point.liked = not cross_point.liked
    db.commit()
    
    return {
        "success": True,
        "data": {
            "id": cross_point.id,
            "liked": cross_point.liked
        }
    }

# 埋め込みベクトル生成エンドポイント
@router.post("/api/cross-point/embeddings/generate")
async def generate_embeddings(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ハイライトの埋め込みベクトルを生成するエンドポイント"""
    service = CrossPointService(db, current_user.id)
    result = await service.generate_embeddings_for_all_highlights()
    
    if not result["success"]:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": result["message"]
            }
        )
    
    return {
        "success": True,
        "data": {
            "processed": result["processed"],
            "total": result["total"],
            "message": result["message"]
        }
    }
