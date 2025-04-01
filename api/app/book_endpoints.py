"""
書籍関連のAPIエンドポイント

このモジュールは、書籍関連のAPIエンドポイントを実装します。
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.auth import User, get_current_active_user
from database.base import get_db
import database.models as models

# ロガーの設定
logger = logging.getLogger("booklight-api")

# ルーターの作成
router = APIRouter()

@router.get("/api/books")
async def get_books(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    sort_by: str = Query("title"),
    sort_order: str = Query("asc"),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """書籍一覧を取得するエンドポイント"""
    try:
        # ユーザーの書籍を取得するクエリ
        query = db.query(models.Book).filter(
            models.Book.user_id == current_user.id
        )
        
        # 検索条件がある場合
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    models.Book.title.ilike(search_term),
                    models.Book.author.ilike(search_term)
                )
            )
        
        # 総数を取得
        total = query.count()
        
        # ソート
        if sort_by == "title":
            query = query.order_by(
                models.Book.title.asc() if sort_order == "asc" else models.Book.title.desc()
            )
        elif sort_by == "author":
            query = query.order_by(
                models.Book.author.asc() if sort_order == "asc" else models.Book.author.desc()
            )
        elif sort_by == "highlightCount":
            # ハイライト数でのソートは複雑なので、全ての書籍を取得してPythonでソート
            books = query.all()
            book_with_counts = []
            for book in books:
                highlight_count = db.query(models.Highlight).filter(
                    models.Highlight.book_id == book.id
                ).count()
                book_with_counts.append((book, highlight_count))
            
            # ハイライト数でソート
            book_with_counts.sort(
                key=lambda x: x[1],
                reverse=(sort_order == "desc")
            )
            
            # ページネーション
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paged_books = [book for book, _ in book_with_counts[start_idx:end_idx]]
            
            # レスポンスの整形
            book_list = []
            for book in paged_books:
                highlight_count = db.query(models.Highlight).filter(
                    models.Highlight.book_id == book.id
                ).count()
                
                book_list.append({
                    "id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "highlightCount": highlight_count
                })
            
            return {
                "success": True,
                "data": {
                    "items": book_list,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size
                }
            }
        
        # ハイライト数でのソートでない場合は通常のページネーション
        books = query.offset((page - 1) * page_size).limit(page_size).all()
        
        # レスポンスの整形
        book_list = []
        for book in books:
            # ハイライト数を取得
            highlight_count = db.query(models.Highlight).filter(
                models.Highlight.book_id == book.id
            ).count()
            
            book_list.append({
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "highlightCount": highlight_count
            })
        
        return {
            "success": True,
            "data": {
                "items": book_list,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
    except Exception as e:
        logger.error(f"書籍一覧取得エラー: {e}")
        return {
            "success": False,
            "error": "書籍一覧の取得中にエラーが発生しました"
        }

@router.get("/api/books/{book_id}")
async def get_book_by_id(
    book_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """IDで書籍を取得するエンドポイント"""
    try:
        # 書籍を取得
        book = db.query(models.Book).filter(
            models.Book.id == book_id,
            models.Book.user_id == current_user.id
        ).first()
        
        if not book:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "success": False,
                    "error": "指定された書籍が見つかりません"
                }
            )
        
        # ハイライト数を取得
        highlight_count = db.query(models.Highlight).filter(
            models.Highlight.book_id == book.id
        ).count()
        
        return {
            "success": True,
            "data": {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "highlightCount": highlight_count
            }
        }
    except Exception as e:
        logger.error(f"書籍取得エラー: {e}")
        return {
            "success": False,
            "error": "書籍の取得中にエラーが発生しました"
        }

@router.get("/api/books/{book_id}/highlights")
async def get_book_highlights(
    book_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """書籍のハイライト一覧を取得するエンドポイント"""
    try:
        # 書籍の存在確認
        book = db.query(models.Book).filter(
            models.Book.id == book_id,
            models.Book.user_id == current_user.id
        ).first()
        
        if not book:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "success": False,
                    "error": "指定された書籍が見つかりません"
                }
            )
        
        # ハイライトを取得
        query = db.query(models.Highlight).filter(
            models.Highlight.book_id == book_id,
            models.Highlight.user_id == current_user.id
        )
        
        # 総数を取得
        total = query.count()
        
        # ページネーション
        highlights = query.offset((page - 1) * page_size).limit(page_size).all()
        
        # レスポンスの整形
        highlight_list = []
        for highlight in highlights:
            highlight_list.append({
                "id": highlight.id,
                "content": highlight.content,
                "location": highlight.location,
                "created_at": highlight.created_at.isoformat()
            })
        
        return {
            "success": True,
            "data": {
                "items": highlight_list,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "book": {
                    "id": book.id,
                    "title": book.title,
                    "author": book.author
                }
            }
        }
    except Exception as e:
        logger.error(f"ハイライト一覧取得エラー: {e}")
        return {
            "success": False,
            "error": "ハイライト一覧の取得中にエラーが発生しました"
        }
