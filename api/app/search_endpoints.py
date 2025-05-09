from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
import json
from datetime import datetime

from database.base import get_db
import database.models as models
from app.rag import RAGService
from app.auth import get_current_active_user, User
from app.cache import get_cache, set_cache, invalidate_cache
from app.metrics import measure_time
import logging

# ロギング設定
logger = logging.getLogger("booklight-api")

# ルーター設定
router = APIRouter(prefix="/api")

# リクエスト/レスポンスモデル
class SearchHistoryAddRequest(BaseModel):
    keywords: List[str]

class SearchRequest(BaseModel):
    keywords: List[str]
    hybrid_alpha: Optional[float] = 0.7
    book_weight: Optional[float] = 0.3
    use_expanded: Optional[bool] = True
    limit: Optional[int] = 30

class SearchResult(BaseModel):
    highlight_id: int
    content: str
    book_id: int
    book_title: str
    book_author: str
    score: float

class SearchResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

class SearchSuggestResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

# 検索エンドポイント
@router.post("/search", response_model=SearchResponse)
@measure_time("search")
async def search(
    request: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ハイブリッド検索エンドポイント（キーワード + FTS）
    
    キーワードに基づいてハイライトを検索します
    直接キーワードマッチングとFTS検索を組み合わせて高速化
    キャッシュ機能を追加
    """
    try:
        # パラメータのバリデーション
        if not request.keywords or len(request.keywords) == 0:
            return {"success": True, "data": {"results": [], "total": 0}}
        
        logger.info(f"検索リクエスト: {request.keywords}")
        
        # クエリキャッシュキーの生成
        cache_key = f"search_{current_user.id}_{'-'.join(request.keywords)}_{request.limit}"
        
        # キャッシュから結果を取得
        cached_results = await get_cache(cache_key)
        if cached_results:
            logger.info(f"キャッシュから検索結果を取得: {len(cached_results)} 件")
            return {
                "success": True,
                "data": {
                    "results": cached_results,
                    "total": len(cached_results)
                }
            }
        
        logger.info("キャッシュミス、検索を実行します")
        
        # 検索結果を格納するリスト
        results = []
        seen_highlight_ids = set()
        
        # 1. キーワード検索（LIKE演算子を使用）
        for keyword in request.keywords:
            keyword_results = db.query(models.Highlight).filter(
                models.Highlight.user_id == current_user.id,
                models.Highlight.content.ilike(f"%{keyword}%")
            ).limit(50).all()
            
            for highlight in keyword_results:
                if highlight.id in seen_highlight_ids:
                    continue
                
                # 書籍情報の取得
                book = db.query(models.Book).filter(
                    models.Book.id == highlight.book_id
                ).first()
                
                if book:
                    results.append({
                        "highlight_id": highlight.id,
                        "content": highlight.content,
                        "book_id": highlight.book_id,
                        "book_title": book.title,
                        "book_author": book.author,
                        "score": 1.0  # 直接マッチは高いスコア
                    })
                    seen_highlight_ids.add(highlight.id)
        
        # 2. FTS検索（十分な結果がない場合）
        if len(results) < 20:
            try:
                # PostgreSQLの全文検索用のクエリを構築
                tsquery_parts = []
                for kw in request.keywords:
                    # 特殊文字をエスケープ
                    kw = kw.replace("'", "''")
                    tsquery_parts.append(f"to_tsquery('english', '{kw}:*')")
                
                tsquery = " || ".join(tsquery_parts)
                
                # PostgreSQLの全文検索を使用
                query = """
                SELECT h.id, h.content, h.book_id, b.title, b.author, 
                       ts_rank(h.search_vector, query) as rank
                FROM highlights h
                JOIN books b ON h.book_id = b.id,
                     to_tsquery('english', :query) as query
                WHERE h.user_id = :user_id
                AND h.search_vector @@ query
                ORDER BY rank DESC
                LIMIT 30
                """
                
                # キーワードをPostgreSQLのtsquery形式に変換
                tsquery_str = " | ".join([f"{kw}:*" for kw in request.keywords])
                
                fts_results = db.execute(
                    query, 
                    {"user_id": current_user.id, "query": tsquery_str}
                ).fetchall()
                
                # 結果の追加（重複を除外）
                for row in fts_results:
                    highlight_id = row[0]
                    if highlight_id in seen_highlight_ids:
                        continue
                    
                    results.append({
                        "highlight_id": highlight_id,
                        "content": row[1],
                        "book_id": row[2],
                        "book_title": row[3],
                        "book_author": row[4],
                        "score": 0.8  # FTS検索は中程度のスコア
                    })
                    seen_highlight_ids.add(highlight_id)
            except Exception as fts_error:
                # FTS検索に失敗した場合はログに記録して続行
                logger.error(f"FTS検索エラー: {fts_error}")
                logger.error(f"FTSテーブルが存在しない可能性があります。マイグレーションを実行してください。")
        
        # 結果をスコアでソート
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # 結果数を制限
        limit = request.limit or 30
        results = results[:limit]
        
        # 結果をキャッシュに保存（15分間）
        await set_cache(cache_key, results, ttl=60*15)
        
        return {
            "success": True,
            "data": {
                "results": results,
                "total": len(results)
            }
        }
    
    except Exception as e:
        logger.error(f"検索エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"検索処理中にエラーが発生しました: {str(e)}")

# 検索履歴エンドポイント
@router.get("/search/history", response_model=SearchResponse)
async def get_search_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ユーザーの検索履歴を取得する
    """
    try:
        # ユーザーの検索履歴を取得
        history_items = db.query(models.SearchHistory).filter(
            models.SearchHistory.user_id == current_user.id
        ).order_by(models.SearchHistory.created_at.desc()).limit(50).all()
        
        # レスポンス形式に変換
        history = []
        for item in history_items:
            # queryフィールドをキーワード配列に変換
            keywords = item.query.split()
            
            history.append({
                "id": str(item.id),
                "keywords": keywords,
                "timestamp": item.created_at.isoformat(),
                "result_count": item.result_count
            })
        
        return {
            "success": True,
            "data": {
                "history": history
            }
        }
    
    except Exception as e:
        logger.error(f"検索履歴取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"検索履歴の取得中にエラーが発生しました: {str(e)}")

@router.post("/search/history", status_code=201)
async def add_search_history(
    request: SearchHistoryAddRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    検索履歴に新しいアイテムを追加する
    """
    try:
        # キーワードを文字列に変換
        query = " ".join(request.keywords)
        
        # 検索履歴を作成
        history_item = models.SearchHistory(
            user_id=current_user.id,
            query=query,
            result_count=0  # 初期値
        )
        
        db.add(history_item)
        db.commit()
        db.refresh(history_item)
        
        return {
            "success": True,
            "data": {
                "id": history_item.id
            }
        }
    
    except Exception as e:
        logger.error(f"検索履歴追加エラー: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"検索履歴の追加中にエラーが発生しました: {str(e)}")

@router.delete("/search/history/{history_id}")
async def delete_search_history_item(
    history_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    特定の検索履歴アイテムを削除する
    """
    try:
        # 検索履歴アイテムを取得
        history_item = db.query(models.SearchHistory).filter(
            models.SearchHistory.id == history_id,
            models.SearchHistory.user_id == current_user.id
        ).first()
        
        if not history_item:
            raise HTTPException(status_code=404, detail="指定された検索履歴が見つかりません")
        
        # 検索履歴を削除
        db.delete(history_item)
        db.commit()
        
        return {
            "success": True,
            "data": {
                "message": "検索履歴を削除しました"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"検索履歴削除エラー: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"検索履歴の削除中にエラーが発生しました: {str(e)}")

@router.delete("/search/history")
async def clear_search_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ユーザーの全検索履歴を削除する
    """
    try:
        # ユーザーの全検索履歴を削除
        db.query(models.SearchHistory).filter(
            models.SearchHistory.user_id == current_user.id
        ).delete()
        
        db.commit()
        
        return {
            "success": True,
            "data": {
                "message": "全ての検索履歴を削除しました"
            }
        }
    
    except Exception as e:
        logger.error(f"検索履歴全削除エラー: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"検索履歴の全削除中にエラーが発生しました: {str(e)}")

# 検索サジェストエンドポイント
@router.get("/search/suggest", response_model=SearchSuggestResponse)
async def search_suggest(
    q: str = Query(..., description="検索クエリ"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    検索サジェストエンドポイント
    
    入力中のクエリに基づいて検索候補を提案します
    """
    try:
        logger.info(f"検索サジェストリクエスト: q={q}")
        
        # 最低文字数チェック
        if len(q) < 2:
            return {
                "success": True,
                "data": {
                    "suggestions": []
                }
            }
        
        # ハイライトからキーワード候補を抽出
        highlights = db.query(models.Highlight).filter(
            models.Highlight.user_id == current_user.id,
            models.Highlight.content.ilike(f"%{q}%")
        ).limit(20).all()
        
        # 書籍タイトルからキーワード候補を抽出
        books = db.query(models.Book).join(
            models.Highlight,
            models.Book.id == models.Highlight.book_id
        ).filter(
            models.Highlight.user_id == current_user.id,
            models.Book.title.ilike(f"%{q}%")
        ).distinct().limit(10).all()
        
        # キーワード候補の抽出
        import re
        from collections import Counter
        
        # 単語の抽出（日本語と英語の両方に対応）
        words = []
        for highlight in highlights:
            # 日本語の場合は文字単位、英語の場合は単語単位で分割
            content = highlight.content
            # 英数字の単語を抽出
            eng_words = re.findall(r'\b[a-zA-Z0-9]{3,}\b', content)
            words.extend([w.lower() for w in eng_words if q.lower() in w.lower()])
            
            # 日本語の場合は部分一致で抽出
            if any('\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff' for c in content):
                for i in range(len(content) - len(q) + 1):
                    if q in content[i:i+len(q)]:
                        # 前後の文字を含めて候補とする
                        start = max(0, i - 2)
                        end = min(len(content), i + len(q) + 2)
                        candidate = content[start:end]
                        if 2 <= len(candidate) <= 10:  # 適切な長さの候補のみ
                            words.append(candidate)
        
        # 書籍タイトルからも候補を追加
        for book in books:
            title_parts = book.title.split()
            for part in title_parts:
                if q.lower() in part.lower() and 2 <= len(part) <= 15:
                    words.append(part)
        
        # 頻度カウントと重複除去
        counter = Counter(words)
        suggestions = [word for word, count in counter.most_common(10)]
        
        # 入力クエリ自体も候補に含める
        if q not in suggestions and len(q) >= 2:
            suggestions.append(q)
        
        return {
            "success": True,
            "data": {
                "suggestions": suggestions
            }
        }
    
    except Exception as e:
        logger.error(f"検索サジェストエラー: {e}")
        raise HTTPException(status_code=500, detail=f"検索サジェスト処理中にエラーが発生しました: {str(e)}")
