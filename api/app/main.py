from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import json
from sqlalchemy.orm import Session

from app.auth import (
    User, authenticate_user, create_access_token, 
    get_current_active_user, authenticate_with_google,
    ACCESS_TOKEN_EXPIRE_MINUTES, oauth
)
from database.base import get_db
import database.models as models
from database.base import engine, Base

# データベーステーブルの作成
Base.metadata.create_all(bind=engine)

# アプリケーションの初期化
app = FastAPI(
    title="Booklight AI API",
    description="Kindle ハイライト管理のためのAPI",
    version="0.1.0"
)

# グローバルなエラーハンドラ
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTPExceptionのハンドラ"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "code": exc.status_code
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """一般的な例外のハンドラ"""
    # エラーをログに記録
    print(f"予期しないエラー: {str(exc)}")
    import traceback
    traceback.print_exc()
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "サーバー内部エラーが発生しました",
            "details": str(exc) if os.getenv("DEBUG") == "true" else None
        }
    )

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限する
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# トークン認証のためのモデル
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    picture: Optional[str] = None

class TokenData(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None

class GoogleToken(BaseModel):
    token: str
    client_id: Optional[str] = None

# データモデル
class Highlight(BaseModel):
    book_title: str
    author: str
    content: str
    location: Optional[str] = None

class HighlightUpload(BaseModel):
    highlights: List[Highlight]

# ユーザーデータディレクトリ
USER_DATA_DIR = Path("user_data/docs")

# ルートパスのハンドラー
@app.get("/")
async def root():
    return {"message": "Booklight AI API へようこそ", "version": "0.1.0", "docs_url": "/docs"}

# ヘルスチェックエンドポイント
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}

# 認証関連のエンドポイント
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": user.username,
        "email": user.email,
        "full_name": user.full_name
    }

# Google OAuth認証関連のエンドポイント
@app.get("/auth/google")
async def login_via_google(request: Request):
    """Google OAuth認証のリダイレクトエンドポイント"""
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """Google OAuth認証のコールバックエンドポイント（DB版）"""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = await oauth.google.parse_id_token(request, token)
        
        # ユーザー情報の整形
        user_data = {
            "username": user_info.get("email").split('@')[0],
            "email": user_info.get("email"),
            "full_name": user_info.get("name"),
            "google_id": user_info.get("sub"),
            "picture": user_info.get("picture"),
            "disabled": False
        }
        
        # データベースにユーザー情報を保存
        db_user = db.query(models.User).filter(models.User.google_id == user_data["google_id"]).first()
        if not db_user:
            db_user = models.User(
                username=user_data["username"],
                email=user_data["email"],
                full_name=user_data["full_name"],
                picture=user_data["picture"],
                google_id=user_data["google_id"],
                disabled=0
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
        
        # JWTトークンの生成
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_data["username"], "email": user_data["email"]},
            expires_delta=access_token_expires
        )
        
        # フロントエンドにリダイレクト（トークンをクエリパラメータとして渡す）
        redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:8505')}?token={access_token}&user={user_data['username']}"
        return RedirectResponse(url=redirect_url)
    
    except Exception as e:
        error_redirect = f"{os.getenv('FRONTEND_URL', 'http://localhost:8505')}?error={str(e)}"
        return RedirectResponse(url=error_redirect)

@app.post("/auth/google/token", response_model=Token)
async def auth_with_google_token(
    token_data: GoogleToken,
    db: Session = Depends(get_db)
):
    """Google IDトークンを検証してユーザー情報を取得（DB版）"""
    try:
        # Googleトークンを検証してユーザー情報を取得
        user_info = await authenticate_with_google(token_data.token, db)
        
        # アクセストークンを生成
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_info["username"], "email": user_info["email"]},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "user_id": user_info["username"],
            "email": user_info["email"],
            "full_name": user_info.get("full_name"),
            "picture": user_info.get("picture")
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )

@app.get("/auth/user")
async def get_user_info(current_user: User = Depends(get_current_active_user)):
    """現在のユーザー情報を取得"""
    return {
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "picture": current_user.picture
    }

# 現在のユーザーを取得する依存関数
async def get_current_user(current_user: User = Depends(get_current_active_user)):
    return current_user.username

# ハイライト管理API
@app.post("/api/highlights")
async def upload_highlights(
    data: HighlightUpload, 
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Chromeエクステンションからのハイライトアップロード（DB保存版）"""
    try:
        # ユーザーIDの取得
        db_user = db.query(models.User).filter(models.User.username == current_user.username).first()
        if not db_user:
            # ユーザーが存在しない場合は作成
            db_user = models.User(
                username=current_user.username,
                email=current_user.email,
                full_name=current_user.full_name,
                picture=current_user.picture,
                google_id=current_user.google_id,
                disabled=0 if not current_user.disabled else 1
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
        
        user_id = db_user.id
        
        # 新しいハイライトを処理
        new_count = 0
        for h in data.highlights:
            # 書籍の取得または新規作成
            book = db.query(models.Book).filter(
                models.Book.title == h.book_title,
                models.Book.author == h.author
            ).first()
            
            if not book:
                book = models.Book(
                    title=h.book_title,
                    author=h.author
                )
                db.add(book)
                db.commit()
                db.refresh(book)
            
            # ハイライトの重複チェック
            existing_highlight = db.query(models.Highlight).filter(
                models.Highlight.user_id == user_id,
                models.Highlight.book_id == book.id,
                models.Highlight.content == h.content
            ).first()
            
            if not existing_highlight:
                # 新規ハイライトの追加
                highlight = models.Highlight(
                    content=h.content,
                    location=h.location,
                    user_id=user_id,
                    book_id=book.id
                )
                db.add(highlight)
                new_count += 1
        
        # 変更をコミット
        db.commit()
        
        # 後方互換性のために、ファイルベースの保存も維持（一時的）
        _save_highlights_to_file(current_user.username, data.highlights)
        
        # 総ハイライト数を取得
        total_highlights = db.query(models.Highlight).filter(
            models.Highlight.user_id == user_id
        ).count()
        
        return {
            "status": "success", 
            "message": f"{new_count} 件のハイライトを追加しました",
            "total_highlights": total_highlights
        }
    
    except Exception as e:
        db.rollback()  # エラー時はロールバック
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ハイライトの保存中にエラーが発生しました: {str(e)}"
        )

def _save_highlights_to_file(username, highlights):
    """CSVとテキストファイルにもハイライトを保存（後方互換性用）"""
    try:
        user_dir = USER_DATA_DIR / username
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # 既存のハイライトがあれば読み込む
        highlights_path = user_dir / "KindleHighlights.csv"
        if highlights_path.exists():
            df_existing = pd.read_csv(highlights_path)
        else:
            df_existing = pd.DataFrame(columns=["書籍タイトル", "著者", "ハイライト内容", "位置"])
        
        # 新しいハイライトをDataFrameに変換
        new_highlights = []
        for h in highlights:
            new_highlights.append({
                "書籍タイトル": h.book_title,
                "著者": h.author,
                "ハイライト内容": h.content,
                "位置": h.location
            })
        
        df_new = pd.DataFrame(new_highlights)
        
        # 重複を除いて結合
        df_combined = pd.concat([df_existing, df_new]).drop_duplicates(
            subset=["書籍タイトル", "著者", "ハイライト内容"]
        ).reset_index(drop=True)
        
        # CSVとして保存
        df_combined.to_csv(highlights_path, index=False)
        
        # テキストファイルとしても保存
        txt_path = user_dir / "KindleHighlights.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            for _, row in df_combined.iterrows():
                f.write(f"{row['書籍タイトル']} ({row['著者']})\n")
                f.write(f"- {row['ハイライト内容']}\n\n")
    except Exception as e:
        print(f"ファイル保存エラー（無視します）: {e}")

# ハイライト取得API
@app.get("/api/highlights")
async def get_highlights(
    book_title: Optional[str] = None, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """ユーザーのハイライトをDBから取得"""
    try:
        # ユーザーIDの取得
        db_user = db.query(models.User).filter(models.User.username == current_user.username).first()
        if not db_user:
            return {"highlights": [], "count": 0}
        
        user_id = db_user.id
        
        # ハイライトのクエリ
        query = db.query(
            models.Highlight.content,
            models.Highlight.location,
            models.Book.title,
            models.Book.author
        ).join(
            models.Book
        ).filter(
            models.Highlight.user_id == user_id
        )
        
        # 特定の書籍のハイライトのみを取得
        if book_title:
            query = query.filter(models.Book.title == book_title)
        
        # クエリ実行
        results = query.all()
        
        # 結果を整形
        highlights = [
            {
                "book_title": result.title,
                "author": result.author,
                "content": result.content,
                "location": result.location
            }
            for result in results
        ]
        
        return {"highlights": highlights, "count": len(highlights)}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ハイライトの取得中にエラーが発生しました: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
