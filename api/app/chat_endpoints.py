"""
チャット関連のAPIエンドポイント

このモジュールは、チャット関連のAPIエンドポイントを実装します。
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
import json
import asyncio

from app.auth import User, get_current_active_user
from database.base import get_db
import database.models as models
from app.rag import RAGService
from app.metrics import measure_time

# ロガーの設定
logger = logging.getLogger("booklight-api")

# ルーターの作成
router = APIRouter()

class ChatRequest:
    """チャットリクエストモデル"""
    def __init__(self, messages: List[Dict[str, str]], stream: bool = False, use_sources: bool = True):
        self.messages = messages
        self.stream = stream
        self.use_sources = use_sources

@router.post("/api/chat")
@measure_time("chat")
async def chat(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    チャットエンドポイント
    
    ユーザーの質問に対して回答を生成します。
    """
    try:
        # リクエストボディを取得
        body = await request.json()
        
        # リクエストパラメータを取得
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        use_sources = body.get("use_sources", True)
        
        # 最後のメッセージを取得（ユーザーの質問）
        if not messages:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "メッセージが空です"}
            )
        
        last_message = messages[-1]
        if last_message.get("role") != "user":
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "最後のメッセージがユーザーのものではありません"}
            )
        
        query = last_message.get("content", "")
        if not query:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "質問が空です"}
            )
        
        # 書籍タイトルの取得（オプション）
        book_title = None
        for message in messages:
            if message.get("role") == "system":
                content = message.get("content", "")
                if "「" in content and "」" in content:
                    start = content.find("「") + 1
                    end = content.find("」", start)
                    if start < end:
                        book_title = content[start:end]
        
        # RAGサービスの初期化
        rag_service = RAGService(db, current_user.id)
        
        # チャットセッションの保存
        # 既存のセッションを検索
        session_id = body.get("session_id")
        chat_session = None
        
        if session_id:
            chat_session = db.query(models.ChatSession).filter(
                models.ChatSession.id == session_id,
                models.ChatSession.user_id == current_user.id
            ).first()
        
        # セッションが存在しない場合は新規作成
        if not chat_session:
            title = f"チャット {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
            if book_title:
                title = f"{book_title}について {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
            
            chat_session = models.ChatSession(
                title=title,
                user_id=current_user.id
            )
            db.add(chat_session)
            db.commit()
            db.refresh(chat_session)
        
        # ユーザーメッセージを保存
        user_message = models.ChatMessage(
            content=query,
            role="user",
            session_id=chat_session.id
        )
        db.add(user_message)
        db.commit()
        
        # ストリーミングレスポンスの場合
        if stream:
            return StreamingResponse(
                generate_streaming_response(rag_service, query, book_title, chat_session.id, db, use_sources),
                media_type="text/event-stream"
            )
        
        # 非ストリーミングレスポンスの場合
        # 回答を生成
        answer = ""
        sources = []
        
        async for chunk, chunk_sources in rag_service.generate_answer(query, book_title):
            answer += chunk
            if chunk_sources and not sources:
                sources = chunk_sources
        
        # AIメッセージを保存
        ai_message = models.ChatMessage(
            content=answer,
            role="assistant",
            session_id=chat_session.id
        )
        db.add(ai_message)
        db.commit()
        
        # レスポンスの整形
        if use_sources:
            # ソース情報をヘッダーに含める
            headers = {"X-Sources": json.dumps(sources)}
            return JSONResponse(
                content={"success": True, "data": {"message": {"content": answer}, "sources": sources}},
                headers=headers
            )
        else:
            return JSONResponse(
                content={"success": True, "data": {"message": {"content": answer}, "sources": []}}
            )
    
    except Exception as e:
        logger.error(f"チャットエラー: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": f"エラーが発生しました: {str(e)}"}
        )

async def generate_streaming_response(rag_service, query, book_title, session_id, db, use_sources):
    """ストリーミングレスポンスを生成する"""
    try:
        # 回答を生成
        answer = ""
        sources = []
        
        async for chunk, chunk_sources in rag_service.generate_answer(query, book_title):
            answer += chunk
            if chunk_sources and not sources:
                sources = chunk_sources
            
            # SSE形式でチャンクを送信
            yield f"data: {json.dumps({'content': chunk, 'sources': sources if use_sources else []})}\n\n"
            await asyncio.sleep(0.01)  # 少し待機
        
        # AIメッセージを保存
        ai_message = models.ChatMessage(
            content=answer,
            role="assistant",
            session_id=session_id
        )
        db.add(ai_message)
        db.commit()
        
        # 終了を示すイベント
        yield f"data: [DONE]\n\n"
    
    except Exception as e:
        logger.error(f"ストリーミングレスポンス生成エラー: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: [DONE]\n\n"

@router.get("/api/debug/search/{keyword}")
async def debug_search(
    keyword: str,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """デバッグ用キーワード検索エンドポイント"""
    rag_service = RAGService(db, current_user.id)
    results = await rag_service.debug_keyword_search(keyword, limit)
    return results

@router.get("/api/chat/sessions")
async def get_chat_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    チャットセッション一覧を取得するエンドポイント
    """
    try:
        # ユーザーのチャットセッションを取得
        sessions = db.query(models.ChatSession).filter(
            models.ChatSession.user_id == current_user.id
        ).order_by(models.ChatSession.updated_at.desc()).all()
        
        # レスポンスの整形
        result = []
        for session in sessions:
            # 最新のメッセージを取得
            latest_message = db.query(models.ChatMessage).filter(
                models.ChatMessage.session_id == session.id
            ).order_by(models.ChatMessage.created_at.desc()).first()
            
            result.append({
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "last_message": latest_message.content[:50] + "..." if latest_message else None
            })
        
        return {
            "success": True,
            "data": result
        }
    
    except Exception as e:
        logger.error(f"チャットセッション一覧取得エラー: {e}")
        return {
            "success": False,
            "message": f"エラーが発生しました: {str(e)}"
        }

@router.get("/api/chat/sessions/{session_id}")
async def get_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    チャットセッションの詳細を取得するエンドポイント
    """
    try:
        # チャットセッションを取得
        session = db.query(models.ChatSession).filter(
            models.ChatSession.id == session_id,
            models.ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            return {
                "success": False,
                "message": "チャットセッションが見つかりません"
            }
        
        # セッションのメッセージを取得
        messages = db.query(models.ChatMessage).filter(
            models.ChatMessage.session_id == session_id
        ).order_by(models.ChatMessage.created_at).all()
        
        # レスポンスの整形
        message_list = []
        for message in messages:
            message_list.append({
                "id": message.id,
                "content": message.content,
                "role": message.role,
                "created_at": message.created_at.isoformat()
            })
        
        return {
            "success": True,
            "data": {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "messages": message_list
            }
        }
    
    except Exception as e:
        logger.error(f"チャットセッション詳細取得エラー: {e}")
        return {
            "success": False,
            "message": f"エラーが発生しました: {str(e)}"
        }

@router.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    チャットセッションを削除するエンドポイント
    """
    try:
        # チャットセッションを取得
        session = db.query(models.ChatSession).filter(
            models.ChatSession.id == session_id,
            models.ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            return {
                "success": False,
                "message": "チャットセッションが見つかりません"
            }
        
        # セッションを削除（関連するメッセージも削除される）
        db.delete(session)
        db.commit()
        
        return {
            "success": True,
            "message": "チャットセッションを削除しました"
        }
    
    except Exception as e:
        logger.error(f"チャットセッション削除エラー: {e}")
        db.rollback()
        return {
            "success": False,
            "message": f"エラーが発生しました: {str(e)}"
        }
