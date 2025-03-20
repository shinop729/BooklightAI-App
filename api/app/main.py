from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, APIKeyHeader
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import sys
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import json
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.exceptions import setup_exception_handlers, AuthenticationError, ConfigurationError
from app.auth import (
    User, authenticate_user, create_access_token, 
    get_current_active_user, authenticate_with_google,
    ACCESS_TOKEN_EXPIRE_MINUTES, oauth
)
from app.url_utils import determine_frontend_url
from app.monitoring import init_sentry, track_transaction, log_performance_metric
from database.base import get_db
import database.models as models
from database.base import engine, Base

# Sentryの初期化
set_user_context = init_sentry(settings)

# ロギング設定
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("booklight-api")

# Heroku環境を検出した場合の追加設定
if os.getenv("DYNO"):
    # 特定のモジュールのログレベルを調整（必要に応じて）
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    
    logger.info(f"Heroku環境で起動しました: {settings.HEROKU_APP_NAME or 'unknown'}")
else:
    logger.info("開発環境で起動しました")

# 環境検出
def is_development_mode():
    """開発モードかどうかを検出"""
    return os.getenv("ENVIRONMENT", "development") != "production"

# デバッグAPIキー認証
DEBUG_API_KEY = os.getenv("DEBUG_API_KEY", "")
api_key_header = APIKeyHeader(name="X-Debug-API-Key", auto_error=False)

async def verify_debug_access(
    api_key: str = Security(api_key_header),
    dev_mode: bool = Depends(is_development_mode)
):
    """デバッグアクセスの検証"""
    # 開発モードでは常に許可
    if dev_mode:
        return True
    
    # 本番環境ではAPIキーが必要
    if not DEBUG_API_KEY:
        logger.warning("本番環境でDEBUG_API_KEYが設定されていないため、デバッグエンドポイントが無効です")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug endpoints are disabled in production"
        )
    
    if api_key != DEBUG_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    return True

# データベーステーブルの作成
Base.metadata.create_all(bind=engine)

# アプリケーションの初期化
app = FastAPI(
    title=settings.APP_NAME,
    description="Kindle ハイライト管理のためのAPI",
    version=settings.VERSION,
    # Heroku環境ではroot_pathを設定
    root_path="/api" if os.getenv("DYNO") else ""
)

# デバッグ情報をログに出力
logger.info(f"FastAPIアプリを初期化: root_path={'/api' if os.getenv('DYNO') else ''}")

# 例外ハンドラの設定
setup_exception_handlers(app)

# セッションミドルウェアの追加
app.add_middleware(SessionMiddleware, secret_key=os.getenv("JWT_SECRET_KEY", "fallback-secret-key"))

# CORS設定の改善
allowed_origins = settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# デバッグエンドポイント
@app.get("/debug")
async def debug_info(authorized: bool = Depends(verify_debug_access)):
    """
    アプリケーション環境に関するデバッグ情報を返す
    
    本番環境では X-Debug-API-Key ヘッダーが必要です
    """
    # 環境検出
    is_prod = settings.ENVIRONMENT == "production"
    is_heroku = os.getenv("DYNO") is not None
    
    # 基本情報を収集
    info = {
        "environment": {
            "type": str(settings.ENVIRONMENT),
            "is_heroku": is_heroku,
            "port": os.getenv("PORT"),
            "app_name": settings.HEROKU_APP_NAME,
            "dyno": os.getenv("DYNO"),
        },
        "auth_config": {
            "google_client_id_configured": bool(settings.GOOGLE_CLIENT_ID),
            "google_client_secret_configured": bool(settings.GOOGLE_CLIENT_SECRET),
            "redirect_uri": settings.REDIRECT_URI,
            "frontend_url": settings.FRONTEND_URL,
        },
        "database": {
            "url_configured": bool(settings.DATABASE_URL),
            "type": "PostgreSQL" if "postgresql" in settings.DATABASE_URL else "SQLite",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # 本番環境では詳細情報を制限
    if is_prod:
        # 機密情報を削除
        if "auth_config" in info:
            info["auth_config"].pop("redirect_uri", None)
            info["auth_config"].pop("frontend_url", None)
        if "database" in info:
            info["database"].pop("url_configured", None)
    else:
        # 開発環境では詳細情報を追加
        info["python"] = {
            "version": sys.version,
            "path": sys.path,
        }
        info["environment_variables"] = {k: v for k, v in os.environ.items() 
                                        if not any(secret in k.lower() for secret in 
                                                  ["key", "secret", "token", "password", "pwd"])}
    
    return info

# ルートパスをHTMLレスポンスに
@app.get("/", response_class=HTMLResponse)
async def root():
    """ルートパスに基本的なHTMLを返す"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Booklight AI API</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #2a75bb; }
            .card { background-color: #f5f5f5; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
            .endpoints { list-style-type: none; padding: 0; }
            .endpoints li { margin-bottom: 10px; }
            .endpoints a { color: #2a75bb; text-decoration: none; }
            .endpoints a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>Booklight AI API</h1>
        <div class="card">
            <p>Booklight AI APIへようこそ。これはBooklight AIアプリケーションのバックエンドサービスです。</p>
            <p>API詳細については <a href="/docs">/docs</a> をご覧ください。</p>
        </div>
        <h2>利用可能なエンドポイント</h2>
        <ul class="endpoints">
            <li><a href="/docs">/docs</a> - API詳細ドキュメント</li>
            <li><a href="/health">/health</a> - ヘルスチェックエンドポイント</li>
            <li><a href="/debug">/debug</a> - デバッグ情報</li>
        </ul>
    </body>
    </html>
    """

# Google OAuth認証関連のエンドポイント
@app.get("/auth/google")
@track_transaction("google_oauth_redirect")
async def login_via_google(request: Request):
    """Google OAuth認証のリダイレクトエンドポイント"""
    # カスタムドメインを優先的に使用
    custom_domain = os.getenv("CUSTOM_DOMAIN")
    if custom_domain:
        redirect_uri = f"https://{custom_domain}/auth/callback"
        logger.info(f"カスタムドメインからリダイレクトURI設定: {redirect_uri}")
    elif os.getenv("HEROKU_APP_NAME"):
        # Herokuアプリ名がある場合
        app_name = os.getenv("HEROKU_APP_NAME")
        redirect_uri = f"https://{app_name}.herokuapp.com/auth/callback"
        logger.info(f"Herokuアプリ名からリダイレクトURI設定: {redirect_uri}")
    else:
        # 環境変数のREDIRECT_URIを使用
        redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
        logger.info(f"環境変数からリダイレクトURI設定: {redirect_uri}")
    
    logger.info(f"Google認証リダイレクトURI: {redirect_uri}")
    # 追加デバッグ情報
    logger.info(f"リクエストベースURL: {request.base_url}")
    logger.info(f"環境変数状態: DYNO={os.getenv('DYNO')}, HEROKU_APP_NAME={os.getenv('HEROKU_APP_NAME')}, CUSTOM_DOMAIN={os.getenv('CUSTOM_DOMAIN')}")
    
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
@track_transaction("google_oauth_callback")
async def auth_callback(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Google OAuth認証のコールバックエンドポイント（DB版）"""
    try:
        logger.info(f"OAuth コールバック受信: {request.url}")
        logger.info(f"クエリパラメータ: {request.query_params}")
        logger.info(f"ヘッダー: Host={request.headers.get('host')}, Origin={request.headers.get('origin')}")
        
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
        
        # フロントエンドURLの動的検出
        frontend_url = await determine_frontend_url(request)
        logger.info(f"検出されたフロントエンドURL: {frontend_url}")
        
        # セキュアなクッキーにトークンを設定
        # Heroku環境ではHTTPSが強制されるため、secure=Trueを設定
        is_secure = os.getenv("DYNO") is not None  # Heroku環境ではTrue
        
        # リダイレクトURLの構築（トークンはURLパラメータとクッキーの両方に設定）
        # 既存の実装との互換性のために、URLパラメータも残す
        redirect_url = f"{frontend_url}?token={access_token}&user={user_data['username']}"
        logger.info(f"認証後リダイレクト: {redirect_url}")
        
        # ユーザーコンテキストの設定
        set_user_context(user_id=user_data["username"], email=user_data["email"])
        
        # パフォーマンスメトリクスの記録
        log_performance_metric("auth_success_rate", 1.0)
        
        # リダイレクトレスポンスを作成
        redirect_response = RedirectResponse(url=redirect_url)
        
        # クッキーを設定
        redirect_response.set_cookie(
            key="auth_token",
            value=access_token,
            httponly=True,
            secure=is_secure,
            samesite="lax",  # クロスサイトリクエストを許可するためlaxに設定
            max_age=1800,  # 30分
            path="/"
        )
        
        return redirect_response
    
    except Exception as e:
        logger.error(f"認証エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        
        # パフォーマンスメトリクスの記録
        log_performance_metric("auth_success_rate", 0.0)
        
        # エラー時もフロントエンドURLを検出
        frontend_url = await determine_frontend_url(request)
        error_redirect = f"{frontend_url}?error={str(e)}"
        logger.error(f"エラー時リダイレクト: {error_redirect}")
        
        return RedirectResponse(url=error_redirect)

# デバッグ用の認証情報エンドポイント
@app.get("/debug-auth")
async def debug_auth(request: Request):
    """認証デバッグ用エンドポイント"""
    frontend_url = await determine_frontend_url(request)
    
    return {
        "frontend_url": frontend_url,
        "request_host": str(request.base_url),
        "headers": {k: v for k, v in request.headers.items()},
        "app_name": os.getenv("HEROKU_APP_NAME", "未設定"),
        "is_heroku": os.getenv("DYNO") is not None,
        "redirect_uri": os.getenv("REDIRECT_URI", "未設定"),
        "frontend_url_env": os.getenv("FRONTEND_URL", "未設定")
    }

# 認証成功時のフォールバックページ
@app.get("/auth/success", response_class=HTMLResponse)
async def auth_success(token: str = None, user: str = None):
    """認証成功時のフォールバックページ"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Booklight AI - 認証成功</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; text-align: center; }}
            h1 {{ color: #2a75bb; }}
            .card {{ background-color: #f5f5f5; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
            .success {{ color: #5cb85c; }}
            button {{ background-color: #5cb85c; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }}
        </style>
        <script>
            // トークンとユーザー情報をChromeに送信
            function sendAuthInfoToExtension() {{
                const token = "{token}";
                const user = "{user}";
                if (token && user && chrome && chrome.runtime) {{
                    try {{
                        chrome.runtime.sendMessage({{
                            action: 'google_auth_success',
                            token: token,
                            user: user
                        }});
                        console.log('認証情報を拡張機能に送信しました');
                    }} catch (e) {{
                        console.error('拡張機能への送信に失敗しました:', e);
                    }}
                }}
                // 5秒後に自動的にウィンドウを閉じる
                setTimeout(() => {{
                    window.close();
                }}, 5000);
            }}
            
            // ページ読み込み時に実行
            window.onload = function() {{
                try {{
                    sendAuthInfoToExtension();
                }} catch (e) {{
                    console.error('認証処理中にエラーが発生しました:', e);
                }}
            }};
        </script>
    </head>
    <body>
        <h1>Booklight AI</h1>
        <div class="card">
            <h2 class="success">認証成功</h2>
            <p>ようこそ、{user or "ユーザー"}さん！</p>
            <p>このウィンドウは自動的に閉じられます。</p>
            <p>自動的に閉じられない場合は、下のボタンをクリックしてください。</p>
            <button onclick="window.close()">ウィンドウを閉じる</button>
        </div>
    </body>
    </html>
    """

# 残りのコードは以前のmain.pyと同じ
# （以前のコードをそのままコピー）
# ... [previous code continues]

# 最後の行は変更なし
if __name__ == "__main__":
    import uvicorn
