from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, Security, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, APIKeyHeader, HTTPBasic, HTTPBasicCredentials
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import sys
import secrets
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import json
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv # dotenv をインポート

from app.config import settings
from app.exceptions import setup_exception_handlers, AuthenticationError, ConfigurationError
from app.auth import (
    User, authenticate_user, create_access_token, 
    get_current_active_user, authenticate_with_google,
    ACCESS_TOKEN_EXPIRE_MINUTES, oauth, SECRET_KEY, ALGORITHM
)
from app.auth_utils import refresh_access_token
from app.url_utils import determine_frontend_url
from app.monitoring import init_sentry, track_transaction, log_performance_metric
from database.base import get_db
import database.models as models
from database.base import engine, Base

# Sentryの初期化
set_user_context = init_sentry(settings)

# .env ファイルを読み込む
load_dotenv()

# ロギング設定
# settings.LOG_LEVEL ではなく、os.getenv を直接使用
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
# getattrで取得し、無効な場合はINFOにフォールバック
log_level = getattr(logging, log_level_str, logging.INFO)

# basicConfigでルートロガーを設定 (force=True を追加)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()],
    force=True # 設定を強制的に適用
)

# アプリケーションロガーを取得
logger = logging.getLogger("booklight-api")
# ルートロガーの設定が伝播するはずだが、念のためレベルを設定することも可能
# logger.setLevel(log_level)

# 設定されたログレベルとテストメッセージを出力
logger.info(f"ログレベルを '{log_level_str}' (数値: {log_level}) に設定しました。")
logger.debug("これは main.py からの DEBUG レベルのテストメッセージです。") # 設定確認用

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
session_secret = os.getenv("SESSION_SECRET_KEY", os.getenv("JWT_SECRET_KEY", "fallback-secret-key-please-change-in-production"))
app.add_middleware(
    SessionMiddleware, 
    secret_key=session_secret,
    max_age=3600,  # 1時間
    same_site="lax",
    https_only=os.getenv("ENVIRONMENT") == "production"
)

# ベーシック認証の設定
security = HTTPBasic()
USERNAME = os.getenv("BASIC_AUTH_USERNAME", "admin")
PASSWORD = os.getenv("BASIC_AUTH_PASSWORD", "password")

# 認証関数
def verify_basic_auth(credentials: HTTPBasicCredentials = Depends(security)):
    # 開発環境では認証をスキップするオプション
    if os.getenv("ENVIRONMENT") == "development" and os.getenv("SKIP_BASIC_AUTH") == "true":
        return True
        
    correct_username = secrets.compare_digest(credentials.username, USERNAME)
    correct_password = secrets.compare_digest(credentials.password, PASSWORD)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証に失敗しました",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True

# CORS設定の改善
allowed_origins = settings.CORS_ORIGINS

# 開発環境では明示的にポート5173と5174を追加
if os.getenv("ENVIRONMENT", "development") == "development":
    if "http://localhost:5173" not in allowed_origins:
        allowed_origins.append("http://localhost:5173")
    if "http://localhost:5174" not in allowed_origins:
        allowed_origins.append("http://localhost:5174")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Sources"],  # X-Sourcesヘッダーを公開
)

# 認証ミドルウェアの追加
from app.middleware import auth_middleware
app.middleware("http")(auth_middleware)

# 特定のパスのみに認証を適用するミドルウェア
@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    # 認証が必要なパスかチェック
    path = request.url.path
    
    # 認証が必要なパスのリスト
    protected_paths = [
        "/.env", 
        "/.env.local", 
        "/.env.dev", 
        "/api/.env",
        # 他の保護したいパスを追加
    ]
    
    # 認証が必要なパスの場合
    if any(path.startswith(p) for p in protected_paths):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content="認証が必要です",
                headers={"WWW-Authenticate": "Basic"},
            )
            
        try:
            # Basic認証ヘッダーの解析
            auth_type, auth_value = auth_header.split(" ", 1)
            if auth_type.lower() != "basic":
                raise ValueError("Basic認証ではありません")
                
            import base64
            decoded = base64.b64decode(auth_value).decode("utf-8")
            username, password = decoded.split(":", 1)
            
            # 認証情報の検証
            correct_username = secrets.compare_digest(username, USERNAME)
            correct_password = secrets.compare_digest(password, PASSWORD)
            
            if not (correct_username and correct_password):
                raise ValueError("認証情報が無効です")
                
        except Exception as e:
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content="認証に失敗しました",
                headers={"WWW-Authenticate": "Basic"},
            )
    
    # 認証が必要ないパスまたは認証成功の場合は次のミドルウェアへ
    return await call_next(request)

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
@track_transaction("google_oauth_redirect")
@app.get("/auth/google")
async def login_via_google(
    request: Request,
    args: Optional[str] = Query(None),
    kwargs: Optional[str] = Query(None)
):
    """Google OAuth認証のリダイレクトエンドポイント"""
    # カスタムドメインが最優先
    custom_domain = os.getenv("CUSTOM_DOMAIN")
    if custom_domain:
        redirect_uri = f"https://{custom_domain}/auth/callback"
        logger.info(f"カスタムドメインからリダイレクトURI設定: {redirect_uri}")
    # 明示的に設定されたリダイレクトURIを次に優先
    elif os.getenv("REDIRECT_URI"):
        redirect_uri = os.getenv("REDIRECT_URI")
        logger.info(f"環境変数からリダイレクトURI設定: {redirect_uri}")
    # Herokuアプリ名がある場合
    elif os.getenv("HEROKU_APP_NAME"):
        app_name = os.getenv("HEROKU_APP_NAME")
        redirect_uri = f"https://{app_name}.herokuapp.com/auth/callback"
        logger.info(f"Herokuアプリ名からリダイレクトURI設定: {redirect_uri}")
    # それ以外の場合はローカル開発用
    else:
        redirect_uri = "http://localhost:8000/auth/callback"
        logger.info(f"デフォルトのリダイレクトURI設定: {redirect_uri}")
    
    # 明示的にセッション状態を設定
    request.session['oauth_state'] = os.urandom(16).hex()
    
    # フロントエンドURLをセッションに保存
    frontend_url = await determine_frontend_url(request)
    request.session['frontend_url'] = frontend_url
    
    logger.info(f"Google認証リダイレクトURI: {redirect_uri}")
    logger.info(f"セッション状態: {request.session.get('oauth_state')}")
    logger.info(f"フロントエンドURL: {frontend_url}")
    # 追加デバッグ情報
    logger.info(f"リクエストベースURL: {request.base_url}")
    logger.info(f"環境変数状態: DYNO={os.getenv('DYNO')}, HEROKU_APP_NAME={os.getenv('HEROKU_APP_NAME')}, CUSTOM_DOMAIN={os.getenv('CUSTOM_DOMAIN')}")
    
    # 明示的にクエリパラメータを追加
    return await oauth.google.authorize_redirect(
        request, 
        redirect_uri=redirect_uri,
        prompt="consent"
    )

@track_transaction("google_oauth_callback")
@app.get("/auth/callback")
async def auth_callback(
    request: Request,
    response: Response,
    code: str = None,
    state: str = None,
    error: str = None,
    args: Optional[str] = Query(None),
    kwargs: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Google OAuth認証のコールバックエンドポイント（DB版）"""
    try:
        logger.info(f"OAuth コールバック受信: {request.url}")
        logger.info(f"クエリパラメータ: {request.query_params}")
        logger.info(f"ヘッダー: Host={request.headers.get('host')}, Origin={request.headers.get('origin')}")
        logger.info(f"セッション状態: {request.session.get('oauth_state')}")
        
        # エラーパラメータのチェック
        if error:
            logger.error(f"Google OAuth エラー: {error}")
            error_url = f"/auth/error-minimal?error={error}"
            return RedirectResponse(url=error_url)
        
        # codeパラメータが存在するか確認
        if not code:
            logger.error("認証コードがありません")
            return RedirectResponse(url="/auth/error-minimal?error=認証コードがありません")
        
        # フロントエンドURLを環境変数から直接取得（設定ファイルではなく直接読み込む）
        frontend_url = os.environ.get('FRONTEND_URL')
        logger.info(f"環境変数から直接取得したフロントエンドURL: {frontend_url}")
        
        # 環境変数が設定されていない場合はデフォルト値を使用
        if not frontend_url:
            frontend_url = "http://localhost:5173"  # デフォルト値を明示的に設定
            logger.info(f"デフォルトのフロントエンドURLを使用: {frontend_url}")
        
        # セッションからのURLも記録（デバッグ用）
        session_url = request.session.get('frontend_url')
        logger.info(f"セッションから取得したフロントエンドURL: {session_url}")
        
        # クエリパラメータを直接ログに出力（デバッグ用）
        for key, value in request.query_params.items():
            logger.info(f"クエリパラメータ: {key}={value}")
        
        token = await oauth.google.authorize_access_token(request)
        # トークンの内容をログに出力（デバッグ用）
        logger.info(f"OAuth token: {token}")

        try:
            # トークンオブジェクトにuserinfoフィールドがある場合はそれを使用
            if 'userinfo' in token:
                logger.info("Using userinfo from token")
                user_info = token['userinfo']
            # id_tokenがある場合は通常通り処理
            elif 'id_token' in token:
                logger.info("Using id_token from token")
                # トークンからid_tokenを取得して直接デコード
                id_token = token['id_token']
                # JWTをデコード
                import jwt
                # ヘッダーとペイロード部分のみを取得（署名検証なし）
                parts = id_token.split('.')
                if len(parts) >= 2:
                    # Base64デコード
                    import base64
                    import json
                    # パディングを調整
                    padded = parts[1] + '=' * (4 - len(parts[1]) % 4)
                    # デコード
                    try:
                        payload = json.loads(base64.b64decode(padded).decode('utf-8'))
                        user_info = payload
                        logger.info(f"Decoded JWT payload: {user_info}")
                    except Exception as jwt_error:
                        logger.error(f"JWT decode error: {jwt_error}")
                        # 失敗した場合はuserinfo_endpointを使用
                        resp = await oauth.google.get('userinfo', token=token)
                        user_info = resp.json()
                        logger.info(f"User info from userinfo endpoint (fallback): {user_info}")
                else:
                    # トークン形式が不正な場合
                    logger.error(f"Invalid token format: {id_token}")
                    resp = await oauth.google.get('userinfo', token=token)
                    user_info = resp.json()
                    logger.info(f"User info from userinfo endpoint (fallback): {user_info}")
            # どちらもない場合はuserinfo_endpointを使用
            else:
                logger.info("Using userinfo endpoint")
                # アクセストークンを使用してユーザー情報を取得
                resp = await oauth.google.get('userinfo', token=token)
                user_info = resp.json()
                logger.info(f"User info from userinfo endpoint: {user_info}")
        except Exception as e:
            logger.error(f"User info extraction error: {e}")
            # エラー時はトークンの内容を詳細にログ出力
            logger.error(f"Token details: {token}")
            raise
        
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
        
        # クッキーを設定
        response = Response()
        response.set_cookie(
            key="auth_token",
            value=access_token,
            httponly=True,
            secure=is_secure,
            samesite="lax",  # クロスサイトリクエストを許可するためlaxに設定
            max_age=1800,  # 30分
            path="/"
        )
        
        # フロントエンドのコールバックページにリダイレクト
        # 環境変数から直接フロントエンドURLを取得（最も信頼性が高い）
        frontend_url = os.getenv('FRONTEND_URL')
        if not frontend_url:
            frontend_url = "http://localhost:5173"  # デフォルト値を明示的に設定
        
        callback_url = f"{frontend_url}/auth/callback?token={access_token}&user={user_data['username']}"
        logger.info(f"最終的なコールバックURL: {callback_url}")
        
        # ユーザーコンテキストの設定
        set_user_context(user_id=user_data["username"], email=user_data["email"])
        
        # パフォーマンスメトリクスの記録
        log_performance_metric("auth_success_rate", 1.0)
        
        # リダイレクト
        logger.info(f"認証成功後のリダイレクト先: {callback_url}")
        
        # HTMLレスポンスを返す（JavaScriptでリダイレクト）
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>認証成功 - リダイレクト中</title>
            <meta charset="utf-8">
            <meta http-equiv="refresh" content="0;url={callback_url}">
            <script>
                console.log("認証成功: リダイレクト実行");
                window.location.href = "{callback_url}";
            </script>
        </head>
        <body>
            <p>認証に成功しました。リダイレクトしています...</p>
            <p>自動的にリダイレクトされない場合は、<a href="{callback_url}">こちらをクリック</a>してください。</p>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    
    except Exception as e:
        logger.error(f"認証エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        
        # パフォーマンスメトリクスの記録
        log_performance_metric("auth_success_rate", 0.0)
        
        # エラー時は専用のエラーページにリダイレクト
        error_url = f"/auth/error-minimal?error={str(e)}"
        return RedirectResponse(url=error_url)
# 現在のユーザー情報を取得するエンドポイント
@app.get("/auth/user")
async def get_current_user(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """現在のユーザー情報を返すエンドポイント"""
    try:
        # データベースから最新のユーザー情報を取得
        db_user = db.query(models.User).filter(
            models.User.username == current_user.username
        ).first()
        
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ユーザーが見つかりません"
            )
        
        return {
            "id": db_user.id,
            "name": db_user.full_name,
            "email": db_user.email,
            "picture": db_user.picture
        }
    except Exception as e:
        logger.error(f"ユーザー情報取得エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ユーザー情報の取得中にエラーが発生しました"
        )

# /api プレフィックス付きのユーザー情報取得エンドポイント
@app.get("/api/auth/user")
async def api_get_current_user(
    request: Request,
    current_user: User = Depends(lambda: get_current_active_user(request=request)),
    db: Session = Depends(get_db)
):
    """現在のユーザー情報を返すエンドポイント"""
    try:
        # データベースから最新のユーザー情報を取得
        db_user = db.query(models.User).filter(
            models.User.username == current_user.username
        ).first()
        
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ユーザーが見つかりません"
            )
        
        return {
            "id": db_user.id,
            "name": db_user.full_name,
            "email": db_user.email,
            "picture": db_user.picture
        }
    except Exception as e:
        logger.error(f"ユーザー情報取得エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ユーザー情報の取得中にエラーが発生しました"
        )

# トークンリフレッシュエンドポイント
@track_transaction("token_refresh")
@app.post("/auth/token")
async def token_refresh_endpoint(request: Request, db: Session = Depends(get_db)):
    """
    トークンリフレッシュエンドポイント
    
    既存のトークンを検証し、新しいトークンを発行します。
    """
    try:
        # リクエストからトークンを取得
        data = await request.json()
        token = data.get("token")
        
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="トークンが提供されていません"
            )
        
        # 開発環境用トークンの特別処理
        if token == "dev-token-123":
            logger.info("開発環境用トークンを検出しました。特別な処理を行います。")
            # 開発用ユーザー情報を返す
            return {
                "access_token": "dev-token-123",
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 秒単位
                "user_id": "dev-user",
                "email": "dev@example.com",
                "full_name": "開発ユーザー",
                "picture": None
            }
        
        # 通常のトークンリフレッシュ処理
        refresh_result = refresh_access_token(token)
        
        # ユーザー情報の取得
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        
        # 正常終了時のレスポンス
        return refresh_result
    except Exception as e:
        logger.error(f"トークンリフレッシュエラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="トークンリフレッシュに失敗しました"
        )
# Cross Point関連のエンドポイントをインクルード
from app.cross_point_endpoints import router as cross_point_router
app.include_router(cross_point_router)

# Remix関連のエンドポイントをインクルード
from app.remix_endpoints import router as remix_router
app.include_router(remix_router)

# 書籍関連のエンドポイントをインクルード
from app.book_endpoints import router as book_router
app.include_router(book_router)

# ハイライト関連のエンドポイントをインクルード
from app.highlight_endpoints import router as highlight_router
app.include_router(highlight_router)

# ユーザー関連のエンドポイントをインクルード
from app.user_endpoints import router as user_router
app.include_router(user_router)

# 検索関連のエンドポイントをインクルード
from app.search_endpoints import router as search_router
app.include_router(search_router)

# チャット関連のエンドポイントをインクルード
from app.chat_endpoints import router as chat_router
app.include_router(chat_router)

# パフォーマンスモニタリングエンドポイント
from app.metrics import get_performance_stats, clear_performance_history

@app.get("/api/admin/performance")
async def get_performance_metrics(
    category: Optional[str] = None,
    period: Optional[str] = None,
    authorized: bool = Depends(verify_debug_access)
):
    """
    パフォーマンス統計情報を取得するエンドポイント
    
    Args:
        category: カテゴリ名（'search', 'chat', 'cross_point', 'remix'）
        period: 期間（'hour', 'day', 'week', 'all'）
    """
    stats = get_performance_stats(category, period)
    return {
        "success": True,
        "data": stats
    }

@app.post("/api/admin/performance/clear")
async def clear_performance_data(
    category: Optional[str] = None,
    authorized: bool = Depends(verify_debug_access)
):
    """
    パフォーマンス履歴をクリアするエンドポイント
    
    Args:
        category: クリアするカテゴリ名（指定しない場合は全カテゴリ）
    """
    clear_performance_history(category)
    return {
        "success": True,
        "message": f"パフォーマンス履歴をクリアしました: {category or '全カテゴリ'}"
    }
