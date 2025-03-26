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

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        
        # データベースからユーザー情報を取得
        db_user = db.query(models.User).filter(models.User.username == username).first()
        
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ユーザーが見つかりません"
            )
        
        # レスポンスの作成
        return {
            "access_token": refresh_result["access_token"],
            "token_type": refresh_result["token_type"],
            "expires_in": refresh_result["expires_in"],
            "user_id": username,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "picture": db_user.picture
        }
    
    except HTTPException as e:
        # 既存のHTTPExceptionはそのまま再送
        raise e
    except JWTError as e:
        logger.warning(f"トークンリフレッシュエラー (JWT): {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なトークンです"
        )
    except Exception as e:
        logger.error(f"トークンリフレッシュエラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"トークンリフレッシュエラー: {str(e)}"
        )

# /api プレフィックス付きのトークンリフレッシュエンドポイント
@track_transaction("token_refresh")
@app.post("/api/auth/token")
async def api_token_refresh_endpoint(request: Request, db: Session = Depends(get_db)):
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
        
        # データベースからユーザー情報を取得
        db_user = db.query(models.User).filter(models.User.username == username).first()
        
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ユーザーが見つかりません"
            )
        
        # レスポンスの作成
        return {
            "access_token": refresh_result["access_token"],
            "token_type": refresh_result["token_type"],
            "expires_in": refresh_result["expires_in"],
            "user_id": username,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "picture": db_user.picture
        }
    
    except HTTPException as e:
        # 既存のHTTPExceptionはそのまま再送
        raise e
    except JWTError as e:
        logger.warning(f"トークンリフレッシュエラー (JWT): {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なトークンです"
        )
    except Exception as e:
        logger.error(f"トークンリフレッシュエラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"トークンリフレッシュエラー: {str(e)}"
        )

# 最小限の認証成功ページ（静的ファイルを使用しない）
@app.get("/auth/success-minimal", response_class=HTMLResponse)
async def auth_success_minimal(
    token: str, 
    user: str,
    args: Optional[str] = Query(None),
    kwargs: Optional[str] = Query(None)
):
    """最小限の認証成功ページ（静的ファイルを使用しない）"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>認証成功</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; text-align: center; }}
            h1 {{ color: #2a75bb; }}
            .card {{ background-color: #f5f5f5; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
            .success {{ color: #5cb85c; }}
            button {{ background-color: #5cb85c; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <h1>Booklight AI</h1>
        <div class="card">
            <h2 class="success">認証成功</h2>
            <p>ようこそ、{user}さん！</p>
            <p>このウィンドウは自動的に閉じられます。</p>
            <p>自動的に閉じられない場合は、下のボタンをクリックしてください。</p>
            <button onclick="window.close()">ウィンドウを閉じる</button>
        </div>
        
        <script>
            // 認証情報
            var authToken = "{token}";
            var userName = "{user}";
            
            // Chrome拡張機能にメッセージを送信
            function sendMessageToExtension() {{
                if (window.chrome && chrome.runtime && chrome.runtime.sendMessage) {{
                    chrome.runtime.sendMessage({{
                        action: 'google_auth_success',
                        token: authToken,
                        user: userName
                    }}, function(response) {{
                        console.log('メッセージ送信結果:', response ? '成功' : '失敗');
                    }});
                }} else {{
                    // Chrome拡張機能APIが利用できない場合は、windowオブジェクトに保存
                    window.BOOKLIGHT_AUTH_DATA = {{ 
                        token: authToken, 
                        user: userName 
                    }};
                    console.log('認証データをwindowオブジェクトに保存しました');
                }}
            }}
            
            // 実行
            try {{
                console.log('認証成功ページが読み込まれました');
                sendMessageToExtension();
                
                // 5秒後に自動的にウィンドウを閉じる
                setTimeout(function() {{
                    window.close();
                }}, 5000);
            }} catch (e) {{
                console.error('エラー:', e);
            }}
        </script>
    </body>
    </html>
    """

# 最小限の認証エラーページ（静的ファイルを使用しない）
@app.get("/auth/error-minimal", response_class=HTMLResponse)
async def auth_error_minimal(
    error: str = "不明なエラー",
    args: Optional[str] = Query(None),
    kwargs: Optional[str] = Query(None)
):
    """最小限の認証エラーページ（静的ファイルを使用しない）"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>認証エラー</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; text-align: center; }}
            h1 {{ color: #d9534f; }}
            .card {{ background-color: #f2dede; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
            .error {{ color: #a94442; }}
            button {{ background-color: #5bc0de; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }}
            pre {{ text-align: left; background: #f8f8f8; padding: 10px; border-radius: 4px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>Booklight AI</h1>
        <div class="card">
            <h2 class="error">認証エラー</h2>
            <p>認証処理中にエラーが発生しました。</p>
            <pre>{error}</pre>
            <p>ウィンドウを閉じて、再度お試しください。</p>
            <button onclick="window.close()">ウィンドウを閉じる</button>
        </div>
        
        <script>
            // エラー情報をコンソールに出力
            console.error('認証エラー:', "{error}".replace(/'/g, "\\'"));
            
            // Chrome拡張機能にエラーメッセージを送信
            if (window.chrome && chrome.runtime && chrome.runtime.sendMessage) {{
                chrome.runtime.sendMessage({{
                    action: 'google_auth_error',
                    error: "{error}".replace(/'/g, "\\'")
                }});
            }}
            
            // 10秒後に自動的にウィンドウを閉じる
            setTimeout(function() {{
                window.close();
            }}, 10000);
        </script>
    </body>
    </html>
    """

# ランダムハイライト取得エンドポイント
@app.get("/highlights/random")
async def get_random_highlight(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ランダムなハイライトを1件取得するエンドポイント"""
    try:
        # ユーザーのハイライトからランダムに1件取得
        highlight = db.query(models.Highlight).filter(
            models.Highlight.user_id == current_user.id
        ).order_by(func.random()).first()
        
        if not highlight:
            return {"success": True, "data": None}
        
        # 書籍情報も取得
        book = db.query(models.Book).filter(models.Book.id == highlight.book_id).first()
        
        return {
            "success": True,
            "data": {
                "id": highlight.id,
                "content": highlight.content,
                "title": book.title if book else "不明な書籍",
                "author": book.author if book else "不明な著者",
                "bookId": highlight.book_id,
                "location": highlight.location,
                "createdAt": highlight.created_at.isoformat() if highlight.created_at else None
            }
        }
    except Exception as e:
        logger.error(f"ランダムハイライト取得エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ハイライト取得中にエラーが発生しました"
        )

# /api プレフィックス付きのランダムハイライト取得エンドポイント
@app.get("/api/highlights/random")
async def api_get_random_highlight(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ランダムなハイライトを1件取得するエンドポイント"""
    try:
        # デバッグ情報をログに出力
        logger.info(f"ランダムハイライト取得リクエスト: ユーザーID={current_user.id}")
        
        # ユーザーのハイライトからランダムに1件取得
        highlight_query = db.query(models.Highlight).filter(
            models.Highlight.user_id == current_user.id
        )
        
        # クエリの実行前にログ出力
        logger.info(f"ハイライトクエリ: {str(highlight_query)}")
        
        # ハイライト数を確認
        highlight_count = highlight_query.count()
        logger.info(f"ユーザーのハイライト数: {highlight_count}")
        
        if highlight_count == 0:
            logger.info("ハイライトが見つかりませんでした")
            return {"success": True, "data": None}
        
        # ランダムに1件取得
        highlight = highlight_query.order_by(func.random()).first()
        
        if not highlight:
            logger.info("ランダム取得に失敗しました")
            return {"success": True, "data": None}
        
        logger.info(f"ハイライト取得成功: ID={highlight.id}")
        
        # 書籍情報も取得
        book = db.query(models.Book).filter(models.Book.id == highlight.book_id).first()
        
        if not book:
            logger.warning(f"書籍情報が見つかりません: book_id={highlight.book_id}")
        else:
            logger.info(f"書籍情報取得成功: ID={book.id}, タイトル={book.title}")
        
        return {
            "success": True,
            "data": {
                "id": highlight.id,
                "content": highlight.content,
                "title": book.title if book else "不明な書籍",
                "author": book.author if book else "不明な著者",
                "bookId": highlight.book_id,
                "location": highlight.location,
                "createdAt": highlight.created_at.isoformat() if highlight.created_at else None
            }
        }
    except Exception as e:
        import traceback
        logger.error(f"ランダムハイライト取得エラー: {e}")
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        
        # エラーレスポンスをJSONで返す（HTTPExceptionではなく）
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "ハイライト取得中にエラーが発生しました",
                "message": str(e)
            }
        )

# ユーザー統計情報取得エンドポイント
@app.get("/user/stats")
async def get_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ユーザーの統計情報を取得するエンドポイント"""
    try:
        # 書籍数
        book_count = db.query(models.Book).filter(
            models.Book.user_id == current_user.id
        ).count()
        
        # ハイライト数
        highlight_count = db.query(models.Highlight).filter(
            models.Highlight.user_id == current_user.id
        ).count()
        
        # 最近の検索キーワード（最大5件）
        recent_searches = db.query(models.SearchHistory).filter(
            models.SearchHistory.user_id == current_user.id
        ).order_by(models.SearchHistory.created_at.desc()).limit(5).all()
        
        # 最近のチャット（最大3件）
        recent_chats = db.query(models.ChatSession).filter(
            models.ChatSession.user_id == current_user.id
        ).order_by(models.ChatSession.updated_at.desc()).limit(3).all()
        
        return {
            "success": True,
            "data": {
                "bookCount": book_count,
                "highlightCount": highlight_count,
                "recentSearches": [
                    {
                        "id": search.id,
                        "query": search.query,
                        "createdAt": search.created_at.isoformat()
                    } for search in recent_searches
                ],
                "recentChats": [
                    {
                        "id": chat.id,
                        "title": chat.title,
                        "updatedAt": chat.updated_at.isoformat()
                    } for chat in recent_chats
                ]
            }
        }
    except Exception as e:
        logger.error(f"ユーザー統計情報取得エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="統計情報取得中にエラーが発生しました"
        )

# /api プレフィックス付きのユーザー統計情報取得エンドポイント
@app.get("/api/user/stats")
async def api_get_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ユーザーの統計情報を取得するエンドポイント"""
    try:
        # デバッグ情報をログに出力
        logger.info(f"ユーザー統計情報取得リクエスト: ユーザーID={current_user.id}")
        
        # 書籍数
        book_count = db.query(models.Book).filter(
            models.Book.user_id == current_user.id
        ).count()
        logger.info(f"書籍数: {book_count}")
        
        # ハイライト数
        highlight_count = db.query(models.Highlight).filter(
            models.Highlight.user_id == current_user.id
        ).count()
        logger.info(f"ハイライト数: {highlight_count}")
        
        # 最近の検索キーワード（最大5件）
        try:
            recent_searches = db.query(models.SearchHistory).filter(
                models.SearchHistory.user_id == current_user.id
            ).order_by(models.SearchHistory.created_at.desc()).limit(5).all()
            logger.info(f"検索履歴取得成功: {len(recent_searches)}件")
        except Exception as search_error:
            logger.error(f"検索履歴取得エラー: {search_error}")
            recent_searches = []
        
        # 最近のチャット（最大3件）
        try:
            recent_chats = db.query(models.ChatSession).filter(
                models.ChatSession.user_id == current_user.id
            ).order_by(models.ChatSession.updated_at.desc()).limit(3).all()
            logger.info(f"チャット履歴取得成功: {len(recent_chats)}件")
        except Exception as chat_error:
            logger.error(f"チャット履歴取得エラー: {chat_error}")
            recent_chats = []
        
        return {
            "success": True,
            "data": {
                "bookCount": book_count,
                "highlightCount": highlight_count,
                "recentSearches": [
                    {
                        "id": search.id,
                        "query": search.query,
                        "createdAt": search.created_at.isoformat()
                    } for search in recent_searches
                ],
                "recentChats": [
                    {
                        "id": chat.id,
                        "title": chat.title,
                        "updatedAt": chat.updated_at.isoformat()
                    } for chat in recent_chats
                ]
            }
        }
    except Exception as e:
        import traceback
        logger.error(f"ユーザー統計情報取得エラー: {e}")
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        
        # エラーレスポンスをJSONで返す（HTTPExceptionではなく）
        return {
            "success": False,
            "error": "統計情報取得中にエラーが発生しました",
            "message": str(e),
            "data": {
                "bookCount": 0,
                "highlightCount": 0,
                "recentSearches": [],
                "recentChats": []
            }
        }

# 書籍関連エンドポイント
from math import ceil
from sqlalchemy import asc, desc, or_

# 書籍一覧取得エンドポイント
@app.get("/api/books")
async def get_books(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    sort_by: str = Query("title", regex="^(title|author|highlightCount)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """書籍一覧を取得するエンドポイント"""
    try:
        # デバッグ情報をログに出力
        logger.info(f"書籍一覧取得リクエスト: ユーザーID={current_user.id}, page={page}, page_size={page_size}, sort_by={sort_by}, sort_order={sort_order}, search={search}")
        
        # 基本クエリ（ユーザーIDでフィルタリング）
        query = db.query(models.Book).filter(models.Book.user_id == current_user.id)
        
        # 検索条件の適用
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    models.Book.title.ilike(search_term),
                    models.Book.author.ilike(search_term)
                )
            )
        
        # 総数の取得
        total = query.count()
        logger.info(f"検索条件に一致する書籍数: {total}")
        
        # ソート条件の適用
        if sort_by == "title":
            query = query.order_by(asc(models.Book.title) if sort_order == "asc" else desc(models.Book.title))
        elif sort_by == "author":
            query = query.order_by(asc(models.Book.author) if sort_order == "asc" else desc(models.Book.author))
        elif sort_by == "highlightCount":
            # ハイライト数でソートする場合は、別のアプローチを使用
            # まず全ての書籍を取得し、メモリ内でソート
            books_with_counts = []
            for book in query.all():
                highlight_count = db.query(models.Highlight).filter(
                    models.Highlight.book_id == book.id
                ).count()
                books_with_counts.append((book, highlight_count))
            
            # ハイライト数でソート
            books_with_counts.sort(
                key=lambda x: x[1], 
                reverse=(sort_order == "desc")
            )
            
            # ページネーション処理
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_books = [book for book, _ in books_with_counts[start_idx:end_idx]]
            
            # レスポンスの作成
            book_list = []
            for book, count in books_with_counts[start_idx:end_idx]:
                book_list.append({
                    "id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "highlightCount": count,
                    "coverUrl": None,  # 表紙画像URLは別途取得
                    "createdAt": book.created_at.isoformat() if hasattr(book, 'created_at') else None
                })
            
            # 早期リターン
            total_pages = ceil(total / page_size)
            return {
                "success": True,
                "data": {
                    "items": book_list,
                    "total": total,
                    "total_pages": total_pages,
                    "page": page,
                    "page_size": page_size
                }
            }
        
        # ページネーション（highlightCountでのソート以外の場合）
        total_pages = ceil(total / page_size)
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        # 結果の取得
        books = query.all()
        logger.info(f"取得した書籍数: {len(books)}")
        
        # レスポンスの作成
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
                "highlightCount": highlight_count,
                "coverUrl": None,  # 表紙画像URLは別途取得
                "createdAt": book.created_at.isoformat() if hasattr(book, 'created_at') else None
            })
        
        return {
            "success": True,
            "data": {
                "items": book_list,
                "total": total,
                "total_pages": total_pages,
                "page": page,
                "page_size": page_size
            }
        }
    except Exception as e:
        logger.error(f"書籍一覧取得エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        
        # エラーレスポンスをJSONで返す
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "書籍一覧の取得中にエラーが発生しました",
                "message": str(e),
                "data": {
                    "items": [],
                    "total": 0,
                    "total_pages": 0,
                    "page": page,
                    "page_size": page_size
                }
            }
        )

# IDによる書籍取得エンドポイント
@app.get("/api/books/{book_id}")
async def get_book_by_id(
    book_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """IDで書籍を取得するエンドポイント"""
    try:
        # 書籍の取得（ユーザーIDでフィルタリング）
        book = db.query(models.Book).filter(
            models.Book.id == book_id,
            models.Book.user_id == current_user.id
        ).first()
        
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定されたIDの書籍が見つかりません"
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
                "highlightCount": highlight_count,
                "summary": book.summary if hasattr(book, 'summary') else None,
                "coverUrl": None,  # 表紙画像URLは別途取得
                "createdAt": book.created_at.isoformat() if hasattr(book, 'created_at') else None
            }
        }
    except HTTPException as e:
        # HTTPExceptionはそのまま再送
        raise e
    except Exception as e:
        logger.error(f"書籍取得エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="書籍の取得中にエラーが発生しました"
        )

# タイトルによる書籍取得エンドポイント
@app.get("/api/books/title/{title}")
async def get_book_by_title(
    title: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """タイトルで書籍を取得するエンドポイント"""
    try:
        # 書籍の取得（ユーザーIDでフィルタリング）
        book = db.query(models.Book).filter(
            models.Book.title == title,
            models.Book.user_id == current_user.id
        ).first()
        
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定されたタイトルの書籍が見つかりません"
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
                "highlightCount": highlight_count,
                "coverUrl": None,  # 表紙画像URLは別途取得
                "createdAt": book.created_at.isoformat() if hasattr(book, 'created_at') else None
            }
        }
    except HTTPException as e:
        # HTTPExceptionはそのまま再送
        raise e
    except Exception as e:
        logger.error(f"書籍取得エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="書籍の取得中にエラーが発生しました"
        )

# 書籍ハイライト取得エンドポイント
@app.get("/api/books/{book_id}/highlights")
async def get_book_highlights(
    book_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """書籍のハイライト一覧を取得するエンドポイント"""
    try:
        # 書籍の存在確認（ユーザーIDでフィルタリング）
        book = db.query(models.Book).filter(
            models.Book.id == book_id,
            models.Book.user_id == current_user.id
        ).first()
        
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定されたIDの書籍が見つかりません"
            )
        
        # ハイライトの取得
        highlights = db.query(models.Highlight).filter(
            models.Highlight.book_id == book_id,
            models.Highlight.user_id == current_user.id
        ).all()
        
        # レスポンスの作成
        highlight_list = []
        for highlight in highlights:
            highlight_list.append({
                "id": highlight.id,
                "bookId": highlight.book_id,
                "content": highlight.content,
                "location": highlight.location,
                "createdAt": highlight.created_at.isoformat() if highlight.created_at else None
            })
        
        return {
            "success": True,
            "data": highlight_list
        }
    except HTTPException as e:
        # HTTPExceptionはそのまま再送
        raise e
    except Exception as e:
        logger.error(f"ハイライト取得エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ハイライトの取得中にエラーが発生しました"
        )

# 書籍表紙画像取得エンドポイント
@app.get("/api/books/cover")
async def get_book_cover(
    title: str,
    author: str,
    current_user: User = Depends(get_current_active_user)
):
    """書籍の表紙画像URLを取得するエンドポイント"""
    try:
        # 表紙画像URLの生成（実際にはGoogle Books APIなどを使用）
        # ここでは簡易的な実装として、ダミーURLを返す
        cover_url = f"https://via.placeholder.com/128x192.png?text={title}"
        
        return {
            "success": True,
            "data": {
                "coverUrl": cover_url
            }
        }
    except Exception as e:
        logger.error(f"表紙画像取得エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="表紙画像の取得中にエラーが発生しました"
        )

# 検索関連エンドポイント
from typing import List as TypeList

# 検索履歴アイテムモデル
class SearchHistoryItem(BaseModel):
    """検索履歴アイテムモデル"""
    id: str
    keywords: TypeList[str]
    timestamp: datetime
    result_count: int

# 検索履歴レスポンスモデル
class SearchHistoryResponse(BaseModel):
    """検索履歴レスポンスモデル"""
    history: TypeList[SearchHistoryItem]

# 検索サジェストレスポンスモデル
class SearchSuggestResponse(BaseModel):
    """検索サジェストレスポンスモデル"""
    suggestions: TypeList[str]

class SearchRequest(BaseModel):
    """検索リクエストモデル"""
    keywords: TypeList[str]
    hybrid_alpha: float = 0.7  # ベクトル検索の重み（0-1）
    book_weight: float = 0.3  # 書籍情報の重み（0-1）
    use_expanded: bool = True  # 拡張検索の使用
    limit: int = 20  # 結果の最大数

# 検索履歴取得エンドポイント
@app.get("/api/search/history")
async def get_search_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ユーザーの検索履歴を取得するエンドポイント"""
    try:
        # 検索履歴の取得
        history_items = db.query(models.SearchHistory).filter(
            models.SearchHistory.user_id == current_user.id
        ).order_by(models.SearchHistory.created_at.desc()).limit(20).all()
        
        # レスポンスの作成
        history = []
        for item in history_items:
            # キーワードを配列に変換
            keywords = item.query.split() if item.query else []
            
            history.append({
                "id": str(item.id),
                "keywords": keywords,
                "timestamp": item.created_at.isoformat(),
                "result_count": item.result_count or 0
            })
        
        return {
            "success": True,
            "data": {
                "history": history
            }
        }
    except Exception as e:
        logger.error(f"検索履歴取得エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="検索履歴の取得中にエラーが発生しました"
        )

# 検索履歴追加エンドポイント
@app.post("/api/search/history")
async def add_search_history(
    request: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """検索履歴を追加するエンドポイント"""
    try:
        # リクエストからキーワードを取得
        keywords = request.get("keywords", [])
        if not keywords:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="キーワードが指定されていません"
            )
        
        # 検索クエリの作成
        search_query = " ".join(keywords)
        
        # 検索履歴の保存
        search_history = models.SearchHistory(
            query=search_query,
            user_id=current_user.id,
            result_count=0  # 初期値
        )
        db.add(search_history)
        db.commit()
        db.refresh(search_history)
        
        return {
            "success": True,
            "data": {
                "id": str(search_history.id),
                "keywords": keywords,
                "timestamp": search_history.created_at.isoformat(),
                "result_count": 0
            }
        }
    except HTTPException as e:
        # HTTPExceptionはそのまま再送
        raise e
    except Exception as e:
        logger.error(f"検索履歴追加エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="検索履歴の追加中にエラーが発生しました"
        )

# 検索履歴削除エンドポイント
@app.delete("/api/search/history/{history_id}")
async def delete_search_history(
    history_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """特定の検索履歴を削除するエンドポイント"""
    try:
        # 検索履歴の取得
        history_item = db.query(models.SearchHistory).filter(
            models.SearchHistory.id == history_id,
            models.SearchHistory.user_id == current_user.id
        ).first()
        
        if not history_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定された検索履歴が見つかりません"
            )
        
        # 検索履歴の削除
        db.delete(history_item)
        db.commit()
        
        return {
            "success": True,
            "message": "検索履歴を削除しました"
        }
    except HTTPException as e:
        # HTTPExceptionはそのまま再送
        raise e
    except Exception as e:
        logger.error(f"検索履歴削除エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="検索履歴の削除中にエラーが発生しました"
        )

# 全検索履歴削除エンドポイント
@app.delete("/api/search/history")
async def clear_search_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ユーザーの全検索履歴を削除するエンドポイント"""
    try:
        # ユーザーの全検索履歴を削除
        db.query(models.SearchHistory).filter(
            models.SearchHistory.user_id == current_user.id
        ).delete()
        db.commit()
        
        return {
            "success": True,
            "message": "全ての検索履歴を削除しました"
        }
    except Exception as e:
        logger.error(f"全検索履歴削除エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="検索履歴の削除中にエラーが発生しました"
        )

# 検索サジェストエンドポイント
@app.get("/api/search/suggest")
async def get_search_suggestions(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """検索キーワードの候補を取得するエンドポイント"""
    try:
        if not q or len(q) < 2:
            return {
                "success": True,
                "data": {
                    "suggestions": []
                }
            }
        
        # 検索クエリの作成
        search_term = f"%{q}%"
        
        # ハイライトからキーワード候補を抽出
        highlights = db.query(models.Highlight).filter(
            models.Highlight.user_id == current_user.id,
            models.Highlight.content.ilike(search_term)
        ).limit(10).all()
        
        # 書籍からキーワード候補を抽出
        books = db.query(models.Book).filter(
            models.Book.user_id == current_user.id,
            or_(
                models.Book.title.ilike(search_term),
                models.Book.author.ilike(search_term)
            )
        ).limit(5).all()
        
        # 候補の抽出と重複除去
        suggestions = set()
        
        # ハイライトからの候補
        for highlight in highlights:
            # 単語単位で分割して候補を抽出
            words = highlight.content.split()
            for word in words:
                if q.lower() in word.lower() and len(word) >= 3:
                    suggestions.add(word)
        
        # 書籍からの候補
        for book in books:
            if q.lower() in book.title.lower():
                suggestions.add(book.title)
            if q.lower() in book.author.lower():
                suggestions.add(book.author)
        
        # 最大10件に制限
        suggestions_list = list(suggestions)[:10]
        
        return {
            "success": True,
            "data": {
                "suggestions": suggestions_list
            }
        }
    except Exception as e:
        logger.error(f"検索サジェスト取得エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="検索サジェストの取得中にエラーが発生しました"
        )

@app.post("/api/search")
async def search_highlights(
    request: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ハイライトを検索するエンドポイント"""
    try:
        if not request.keywords:
            return {
                "success": True,
                "data": {
                    "results": []
                }
            }
        
        # 検索履歴の保存
        search_query = " ".join(request.keywords)
        search_history = models.SearchHistory(
            query=search_query,
            user_id=current_user.id
        )
        db.add(search_history)
        db.commit()
        
        # 簡易的な検索実装（実際にはベクトル検索などを使用）
        # ここでは単純なキーワードマッチングを行う
        results = []
        for keyword in request.keywords:
            search_term = f"%{keyword}%"
            
            # ハイライトの検索
            highlights = db.query(models.Highlight).join(
                models.Book, models.Highlight.book_id == models.Book.id
            ).filter(
                models.Highlight.user_id == current_user.id,
                models.Highlight.content.ilike(search_term)
            ).limit(request.limit).all()
            
            for highlight in highlights:
                # 書籍情報の取得
                book = db.query(models.Book).filter(
                    models.Book.id == highlight.book_id
                ).first()
                
                if book:
                    # フロントエンドの期待する形式に変換
                    results.append({
                        "doc": {
                            "page_content": highlight.content,
                            "metadata": {
                                "original_title": book.title,
                                "original_author": book.author,
                                "book_id": book.id,
                                "location": highlight.location
                            }
                        },
                        "score": 0.8  # ダミースコア
                    })
        
        # 重複を除去
        unique_results = []
        seen_contents = set()
        for result in results:
            content = result["doc"]["page_content"]
            if content not in seen_contents:
                seen_contents.add(content)
                unique_results.append(result)
        
        # 検索履歴の結果数を更新
        search_history.result_count = len(unique_results)
        db.commit()
        
        return {
            "success": True,
            "data": {
                "results": unique_results
            }
        }
    except Exception as e:
        logger.error(f"検索エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="検索中にエラーが発生しました"
        )

# チャット関連エンドポイント
class ChatMessage(BaseModel):
    """チャットメッセージモデル"""
    role: str  # 'system', 'user', 'assistant'
    content: str

class ChatRequest(BaseModel):
    """チャットリクエストモデル"""
    messages: TypeList[ChatMessage]
    stream: bool = False  # ストリーミングレスポンスを使用するかどうか
    use_sources: bool = True  # ソース情報を使用するかどうか

from fastapi.responses import StreamingResponse
import asyncio
import json

# RAGサービスのインポート
from app.rag import RAGService

@app.post("/api/chat")
async def chat_with_ai(
    request: ChatRequest,
    req: Request,
    current_user: User = Depends(lambda: get_current_active_user(request=req)),
    db: Session = Depends(get_db)
):
    """AIとチャットするエンドポイント（RAG実装）"""
    try:
        # リクエストの検証とログ出力
        logger.info(f"チャットリクエスト受信: ユーザーID={current_user.id}, ストリーミング={request.stream}")
        
        # 詳細なデバッグ情報
        logger.debug(f"リクエスト内容: {request}")
        logger.debug(f"OpenAI APIキー設定状況: {'設定済み' if settings.OPENAI_API_KEY else '未設定'}")
        logger.debug(f"環境: {settings.ENVIRONMENT}")
        
        # ユーザーメッセージの検証
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            logger.warning("ユーザーメッセージが含まれていないリクエスト")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ユーザーメッセージが含まれていません"
            )
        
        last_user_message = user_messages[-1]
        user_query = last_user_message.content
        logger.info(f"ユーザークエリ: {user_query[:50]}...")
        
        # トランザクション開始
        try:
            # チャットセッションの作成または取得
            session = db.query(models.ChatSession).filter(
                models.ChatSession.user_id == current_user.id
            ).order_by(models.ChatSession.updated_at.desc()).first()
            
            if not session:
                logger.info(f"新しいチャットセッションを作成: ユーザーID={current_user.id}")
                # 新しいセッションを作成
                session = models.ChatSession(
                    title="新しい会話",
                    user_id=current_user.id
                )
                db.add(session)
                db.commit()
                db.refresh(session)
            
            # ユーザーメッセージをDBに保存
            db_message = models.ChatMessage(
                content=user_query,
                role="user",
                session_id=session.id
            )
            db.add(db_message)
            db.commit()
            logger.info(f"ユーザーメッセージをDBに保存: セッションID={session.id}")
            
        except Exception as db_error:
            logger.error(f"データベース操作エラー: {db_error}")
            db.rollback()
            import traceback
            logger.error(f"DB詳細エラー: {traceback.format_exc()}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "error": "データベース操作中にエラーが発生しました",
                    "message": str(db_error)
                }
            )
        
        # 特定の書籍に関する質問かどうかを判断
        book_title = None
        for msg in request.messages:
            if msg.role == "system" and "という本について質問" in msg.content:
                # システムメッセージから書籍タイトルを抽出
                import re
                match = re.search(r'「(.+?)」という本について質問', msg.content)
                if match:
                    book_title = match.group(1)
                    logger.info(f"特定の書籍に関する質問: {book_title}")
        
        # RAGサービスの初期化
        try:
            logger.info("RAGサービスを初期化")
            rag_service = RAGService(db, current_user.id)
            
            # ベクトルストアが初期化されているか確認
            if rag_service.vector_store is None:
                logger.warning(f"ユーザーID {current_user.id} のベクトルストアが初期化されていません")
                
                # ユーザーのハイライト数を確認
                highlight_count = db.query(models.Highlight).filter(
                    models.Highlight.user_id == current_user.id
                ).count()
                logger.info(f"ユーザーID {current_user.id} のハイライト数: {highlight_count}")
                
                # エラーメッセージをDBに保存
                error_message = "申し訳ありません。ハイライトデータが見つからないか、ベクトルストアの初期化に失敗しました。ハイライトをアップロードしてから再度お試しください。"
                
                # ハイライトがない場合は具体的なメッセージを表示
                highlight_count = db.query(models.Highlight).filter(
                    models.Highlight.user_id == current_user.id
                ).count()
                
                if highlight_count == 0:
                    error_message = "ハイライトデータが見つかりません。「アップロード」ページからハイライトをアップロードしてください。"
                else:
                    error_message = "ベクトルストアの初期化に失敗しました。システム管理者にお問い合わせください。"
                try:
                    db_message = models.ChatMessage(
                        content=error_message,
                        role="assistant",
                        session_id=session.id
                    )
                    db.add(db_message)
                    db.commit()
                except Exception:
                    db.rollback()
                
                # クライアントにエラーメッセージを返す（HTTPエラーではなく正常なレスポンス）
                return {
                    "success": True,
                    "data": {
                        "message": {
                            "role": "assistant",
                            "content": error_message
                        },
                        "sources": []
                    }
                }
        except Exception as rag_error:
            logger.error(f"RAGサービス初期化エラー: {rag_error}")
            import traceback
            logger.error(f"RAG詳細エラー: {traceback.format_exc()}")
            
            # OpenAI APIキーの有効性を確認
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Test"}],
                    max_tokens=5
                )
                logger.info("OpenAI APIキーは有効です")
            except Exception as api_error:
                logger.error(f"OpenAI APIキーエラー: {api_error}")
                error_message = f"OpenAI APIキーが無効か、APIリクエストに問題があります: {str(api_error)}"
            
            # エラーメッセージをDBに保存
            error_message = f"申し訳ありません。AIサービスの初期化中にエラーが発生しました: {str(rag_error)}"
            try:
                db_message = models.ChatMessage(
                    content=error_message,
                    role="assistant",
                    session_id=session.id
                )
                db.add(db_message)
                db.commit()
            except Exception:
                db.rollback()
            
            # クライアントにエラーメッセージを返す（HTTPエラーではなく正常なレスポンス）
            return {
                "success": True,
                "data": {
                    "message": {
                        "role": "assistant",
                        "content": error_message
                    },
                    "sources": []
                }
            }
        
        # ストリーミングレスポンスの場合
        if request.stream:
            try:
                async def generate_stream():
                    sources = []
                    first_chunk = True
                    full_response = ""
                    
                    try:
                        logger.info(f"ストリーミングモードで回答生成開始: クエリ='{user_query[:50]}...'")
                        # RAGサービスを使用して回答を生成
                        async for chunk, chunk_sources in rag_service.generate_answer(user_query, book_title):
                            # 最初のチャンクでソース情報を取得
                            if first_chunk and chunk_sources:
                                sources = chunk_sources
                                first_chunk = False
                            
                            full_response += chunk
                            yield chunk
                        
                        # AIメッセージをDBに保存
                        try:
                            db_message = models.ChatMessage(
                                content=full_response,
                                role="assistant",
                                session_id=session.id
                            )
                            db.add(db_message)
                            
                            # セッションの更新日時を更新
                            session.updated_at = datetime.utcnow()
                            db.commit()
                            logger.info(f"AIレスポンスをDBに保存: セッションID={session.id}, 長さ={len(full_response)}")
                        except Exception as save_error:
                            logger.error(f"レスポンス保存エラー: {save_error}")
                            db.rollback()
                    
                    except Exception as stream_error:
                        logger.error(f"ストリーミング生成エラー: {stream_error}")
                        import traceback
                        logger.error(f"ストリーミング詳細エラー: {traceback.format_exc()}")
                        error_message = f"回答の生成中にエラーが発生しました: {str(stream_error)}"
                        yield error_message
                        
                        # エラーメッセージをDBに保存
                        try:
                            db_message = models.ChatMessage(
                                content=error_message,
                                role="assistant",
                                session_id=session.id
                            )
                            db.add(db_message)
                            db.commit()
                        except Exception:
                            db.rollback()
                
                # 関連ハイライトを取得（同期的に呼び出し）
                relevant_highlights = []
                try:
                    relevant_highlights = rag_service.get_relevant_highlights(user_query, 5)
                    logger.info(f"関連ハイライト取得成功: {len(relevant_highlights)}件")
                    
                    # ハイライトの詳細をログに出力
                    for i, highlight in enumerate(relevant_highlights):
                        logger.debug(f"ハイライト {i+1}: タイトル='{highlight.get('title', 'なし')}', スコア={highlight.get('score', 0)}")
                except Exception as highlights_error:
                    logger.error(f"関連ハイライト取得エラー: {highlights_error}")
                    import traceback
                    logger.error(f"ハイライト詳細エラー: {traceback.format_exc()}")
                
                # ソース情報をヘッダーに含めてストリーミングレスポンスを返す
                logger.info("ストリーミングレスポンスを開始")
                
                # ソース情報をJSON文字列に変換
                sources_json = json.dumps([
                    {
                        "book_id": source.get("book_id", ""),
                        "title": source.get("title", ""),
                        "author": source.get("author", ""),
                        "content": source.get("content", ""),
                        "location": source.get("location", "")
                    } for source in relevant_highlights
                ])
                
                logger.info(f"ソース情報ヘッダー: {sources_json[:100]}...")
                
                # CORSヘッダーを追加
                headers = {
                    "X-Sources": sources_json,
                    "Access-Control-Expose-Headers": "X-Sources"
                }
                
                return StreamingResponse(
                    generate_stream(),
                    media_type="text/plain",
                    headers=headers
                )
            
            except Exception as stream_setup_error:
                logger.error(f"ストリーミングセットアップエラー: {stream_setup_error}")
                import traceback
                logger.error(f"ストリーミングセットアップ詳細エラー: {traceback.format_exc()}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "success": False,
                        "error": "ストリーミングの設定中にエラーが発生しました",
                        "message": str(stream_setup_error)
                    }
                )
        
        # 非ストリーミングの場合
        else:
            try:
                logger.info("非ストリーミングモードでの回答生成を開始")
                # 関連ハイライトを取得
                relevant_highlights = await rag_service.get_relevant_highlights(user_query, 5)
                
                # 非ストリーミングでの回答生成
                full_response = ""
                async for chunk, _ in rag_service.generate_answer(user_query, book_title):
                    full_response += chunk
                
                # AIメッセージをDBに保存
                db_message = models.ChatMessage(
                    content=full_response,
                    role="assistant",
                    session_id=session.id
                )
                db.add(db_message)
                
                # セッションの更新日時を更新
                session.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"非ストリーミングレスポンスをDBに保存: 長さ={len(full_response)}")
                
                # 通常のレスポンス
                return {
                    "success": True,
                    "data": {
                        "message": {
                            "role": "assistant",
                            "content": full_response
                        },
                        "sources": [
                            {
                                "book_id": source.get("book_id", ""),
                                "title": source.get("title", ""),
                                "author": source.get("author", ""),
                                "content": source.get("content", ""),
                                "location": source.get("location", "")
                            } for source in relevant_highlights
                        ]
                    }
                }
            
            except Exception as non_stream_error:
                logger.error(f"非ストリーミング処理エラー: {non_stream_error}")
                import traceback
                logger.error(f"非ストリーミング詳細エラー: {traceback.format_exc()}")
                
                # エラーメッセージをDBに保存
                error_message = f"回答の生成中にエラーが発生しました: {str(non_stream_error)}"
                try:
                    db_message = models.ChatMessage(
                        content=error_message,
                        role="assistant",
                        session_id=session.id
                    )
                    db.add(db_message)
                    db.commit()
                except Exception:
                    db.rollback()
                
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "success": False,
                        "error": "回答の生成中にエラーが発生しました",
                        "message": str(non_stream_error),
                        "data": {
                            "message": {
                                "role": "assistant",
                                "content": error_message
                            },
                            "sources": []
                        }
                    }
                )
    
    except HTTPException as http_error:
        # HTTPExceptionはそのまま再送
        logger.warning(f"HTTPエラー: {http_error.detail}")
        raise http_error
    
    except Exception as e:
        logger.error(f"チャットエンドポイント全体エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "チャット処理中にエラーが発生しました",
                "message": str(e),
                "data": {
                    "message": {
                        "role": "assistant",
                        "content": f"申し訳ありません。エラーが発生しました: {str(e)}"
                    },
                    "sources": []
                }
            }
        )

# ファイルアップロード関連エンドポイント
from fastapi import File, UploadFile
import csv
import io

@app.post("/api/upload")
async def upload_highlights(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """ハイライトCSVファイルをアップロードするエンドポイント"""
    try:
        # ファイル形式の検証
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSVファイルのみアップロード可能です"
            )
        
        # ファイルの読み込み
        contents = await file.read()
        
        # CSVの解析
        csv_text = contents.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(csv_text))
        
        # ヘッダー行の取得
        headers = next(csv_reader, None)
        if not headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSVファイルが空です"
            )
        
        # ヘッダーの検証
        required_headers = ['Title', 'Author', 'Highlight']
        if not all(header in headers for header in required_headers):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSVファイルに必要なヘッダーがありません。必要なヘッダー: {', '.join(required_headers)}"
            )
        
        # ヘッダーのインデックスを取得
        title_idx = headers.index('Title')
        author_idx = headers.index('Author')
        highlight_idx = headers.index('Highlight')
        location_idx = headers.index('Location') if 'Location' in headers else None
        
        # データの処理
        book_count = 0
        highlight_count = 0
        books = {}  # 書籍の重複を避けるための辞書
        
        for row in csv_reader:
            # 必須フィールドのインデックスチェック
            max_required_idx = max(title_idx, author_idx, highlight_idx)
            if len(row) <= max_required_idx:
                continue  # 不完全な行はスキップ
            
            title = row[title_idx].strip()
            author = row[author_idx].strip()
            highlight_text = row[highlight_idx].strip()
            # Locationヘッダーが存在する場合のみ値を取得
            location = row[location_idx].strip() if location_idx is not None and location_idx < len(row) else ""
            
            if not title or not author or not highlight_text:
                continue  # 必須フィールドが空の行はスキップ
            
            # 書籍の取得または作成
            book_key = f"{title}|{author}"
            if book_key not in books:
                # データベースで既存の書籍を検索
                book = db.query(models.Book).filter(
                    models.Book.title == title,
                    models.Book.author == author,
                    models.Book.user_id == current_user.id
                ).first()
                
                if not book:
                    # 新しい書籍を作成
                    book = models.Book(
                        title=title,
                        author=author,
                        user_id=current_user.id
                    )
                    db.add(book)
                    db.commit()
                    db.refresh(book)
                    book_count += 1
                
                books[book_key] = book
            
            # 書籍の取得
            book = books[book_key]
            
            # ハイライトの作成
            highlight = models.Highlight(
                content=highlight_text,
                location=location,
                user_id=current_user.id,
                book_id=book.id
            )
            db.add(highlight)
            highlight_count += 1
        
        # 一括コミット
        db.commit()
        
        return {
            "success": True,
            "message": f"{book_count}冊の書籍から{highlight_count}件のハイライトを取り込みました。",
            "bookCount": book_count,
            "highlightCount": highlight_count
        }
    except HTTPException as e:
        # HTTPExceptionはそのまま再送
        raise e
    except Exception as e:
        logger.error(f"アップロードエラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ファイルのアップロード中にエラーが発生しました"
        )
