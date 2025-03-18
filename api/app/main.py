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

from app.auth import (
    User, authenticate_user, create_access_token, 
    get_current_active_user, authenticate_with_google,
    ACCESS_TOKEN_EXPIRE_MINUTES, oauth
)
from database.base import engine, Base

# データベーステーブルの作成
Base.metadata.create_all(bind=engine)

# アプリケーションの初期化
app = FastAPI(
    title="Booklight AI API",
    description="Kindle ハイライト管理のためのAPI",
    version="0.1.0"
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
    return {"access_token": access_token, "token_type": "bearer"}

# Google OAuth認証関連のエンドポイント
@app.get("/auth/google")
async def login_via_google(request: Request):
    """Google OAuth認証のリダイレクトエンドポイント"""
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Google OAuth認証のコールバックエンドポイント"""
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
async def auth_with_google_token(token_data: GoogleToken):
    """Google IDトークンを検証してユーザー情報を取得"""
    try:
        # Googleトークンを検証してユーザー情報を取得
        user_info = await authenticate_with_google(token_data.token)
        
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
async def upload_highlights(data: HighlightUpload, user_id: str = Depends(get_current_user)):
    """Chromeエクステンションからのハイライトアップロード"""
    try:
        # ユーザーディレクトリの確認
        user_dir = USER_DATA_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # 既存のハイライトがあれば読み込む
        highlights_path = user_dir / "KindleHighlights.csv"
        if highlights_path.exists():
            df_existing = pd.read_csv(highlights_path)
        else:
            df_existing = pd.DataFrame(columns=["書籍タイトル", "著者", "ハイライト内容", "位置"])
        
        # 新しいハイライトをDataFrameに変換
        new_highlights = []
        for h in data.highlights:
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
        
        # テキストファイルとしても保存（既存の形式を維持）
        txt_path = user_dir / "KindleHighlights.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            for _, row in df_combined.iterrows():
                f.write(f"{row['書籍タイトル']} ({row['著者']})\n")
                f.write(f"- {row['ハイライト内容']}\n\n")
        
        return {
            "status": "success", 
            "message": f"{len(df_new)} 件のハイライトを追加しました",
            "total_highlights": len(df_combined)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ハイライトの保存中にエラーが発生しました: {str(e)}"
        )

# ハイライト取得API
@app.get("/api/highlights")
async def get_highlights(book_title: Optional[str] = None, user_id: str = Depends(get_current_user)):
    """ユーザーのハイライトを取得"""
    try:
        # ユーザーディレクトリの確認
        user_dir = USER_DATA_DIR / user_id
        highlights_path = user_dir / "KindleHighlights.csv"
        
        if not highlights_path.exists():
            return {"highlights": [], "count": 0}
        
        # ハイライトを読み込む
        df = pd.read_csv(highlights_path)
        
        # 特定の書籍のハイライトのみを取得
        if book_title:
            df = df[df["書籍タイトル"] == book_title]
        
        # 結果を整形
        highlights = []
        for _, row in df.iterrows():
            highlights.append({
                "book_title": row["書籍タイトル"],
                "author": row["著者"],
                "content": row["ハイライト内容"],
                "location": row.get("位置", "")
            })
        
        return {"highlights": highlights, "count": len(highlights)}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ハイライトの取得中にエラーが発生しました: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
