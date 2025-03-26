import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from pathlib import Path
from sqlalchemy.orm import Session

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import httpx
from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv

from database.base import get_db
import database.models as models
from app.config import settings

# 環境変数の読み込み
load_dotenv()

# シークレットキー（本番環境では環境変数から取得するべき）
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Google OAuth設定
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# リダイレクトURIの設定（優先順位を明確化）
custom_domain = os.getenv("CUSTOM_DOMAIN")
heroku_app_name = os.getenv("HEROKU_APP_NAME")
explicit_redirect_uri = os.getenv("REDIRECT_URI")

if custom_domain:
    REDIRECT_URI = f"https://{custom_domain}/auth/callback"
    logging.getLogger("booklight-api").info(f"カスタムドメインからリダイレクトURIを設定: {REDIRECT_URI}")
elif explicit_redirect_uri:
    REDIRECT_URI = explicit_redirect_uri
    logging.getLogger("booklight-api").info(f"環境変数からリダイレクトURIを設定: {REDIRECT_URI}")
elif heroku_app_name:
    REDIRECT_URI = f"https://{heroku_app_name}.herokuapp.com/auth/callback"
    logging.getLogger("booklight-api").info(f"Herokuアプリ名からリダイレクトURIを設定: {REDIRECT_URI}")
else:
    REDIRECT_URI = "http://localhost:8000/auth/callback"
    logging.getLogger("booklight-api").info(f"デフォルトのリダイレクトURIを設定: {REDIRECT_URI}")

# リダイレクトURIをログに出力（デバッグ用）
import logging
logging.getLogger("booklight-api").info(f"最終的なリダイレクトURI: {REDIRECT_URI}")

# Google OAuth認証クライアントの設定
oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'redirect_uri': REDIRECT_URI  # 明示的にリダイレクトURIを設定
    }
)

# ユーザーデータディレクトリ（後方互換性のため）
USER_DATA_DIR = Path("user_data")
USER_INFO_FILE = "user_info.json"

# ユーザーモデル
class User(BaseModel):
    id: Optional[int] = None  # id属性を追加
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    google_id: Optional[str] = None
    picture: Optional[str] = None

class UserInDB(User):
    hashed_password: Optional[str] = None

# トークンモデル
class TokenData(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None

# パスワードハッシュ化
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# テスト用ユーザーデータ（本番環境ではデータベースから取得）
fake_users_db = {
    "testuser": {
        "username": "testuser",
        "full_name": "Test User",
        "email": "test@example.com",
        "hashed_password": pwd_context.hash("testpassword"),
        "disabled": False,
    }
}

# ユーザーデータの保存と取得（後方互換性のため）
def save_user_to_file(user_data: Dict):
    """ユーザー情報をJSONファイルに保存（後方互換性のため）"""
    user_id = user_data.get("username") or user_data.get("email").split('@')[0]
    user_dir = USER_DATA_DIR / "docs" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    
    user_file = user_dir / USER_INFO_FILE
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return user_id

def get_user_from_file(user_id: str) -> Optional[Dict]:
    """ユーザー情報をJSONファイルから取得（後方互換性のため）"""
    user_file = USER_DATA_DIR / "docs" / user_id / USER_INFO_FILE
    if not user_file.exists():
        return None
    
    with open(user_file, 'r', encoding='utf-8') as f:
        return json.load(f)

# データベースからユーザーを取得または作成
def get_or_create_user_in_db(db: Session, user_data: Dict) -> models.User:
    """ユーザーをデータベースから取得、存在しない場合は作成"""
    logger = logging.getLogger("booklight-api")
    try:
        username = user_data.get("username")
        email = user_data.get("email")
        google_id = user_data.get("google_id")
        
        # ユーザーの検索条件
        db_user = None
        if google_id:
            db_user = db.query(models.User).filter(models.User.google_id == google_id).first()
            if db_user:
                logger.info(f"Google IDでユーザーを検索: {google_id} -> ユーザーID: {db_user.id}")
        elif email:
            db_user = db.query(models.User).filter(models.User.email == email).first()
            if db_user:
                logger.info(f"メールアドレスでユーザーを検索: {email} -> ユーザーID: {db_user.id}")
        elif username:
            db_user = db.query(models.User).filter(models.User.username == username).first()
            if db_user:
                logger.info(f"ユーザー名でユーザーを検索: {username} -> ユーザーID: {db_user.id}")
        else:
            logger.error("ユーザー検索に必要な情報がありません")
            return None
        
        # ユーザーが存在しない場合は作成
        if not db_user:
            logger.info(f"新規ユーザーを作成: {username}")
            db_user = models.User(
                username=username,
                email=email,
                full_name=user_data.get("full_name"),
                picture=user_data.get("picture"),
                google_id=google_id,
                disabled=0 if not user_data.get("disabled") else 1
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            logger.info(f"新規ユーザーを作成しました: {username} -> ユーザーID: {db_user.id}")
        
        # ユーザーデータにIDを追加
        user_data["id"] = db_user.id
        
        return db_user
    except Exception as e:
        logger.error(f"ユーザーの取得/作成中にエラーが発生: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        # エラーを上位に伝播させる
        raise

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str, db_session: Session = None):
    """
    ユーザー情報を取得する関数
    
    Parameters:
    - db: メモリ内ユーザーデータ
    - username: ユーザー名
    - db_session: データベースセッション
    
    Returns:
    - User: ユーザーオブジェクト
    """
    logger = logging.getLogger("booklight-api")
    try:
        # まずメモリ内のユーザーデータを確認
        if username in db:
            user_dict = db[username]
            # id属性がない場合は0をデフォルト値として設定
            if "id" not in user_dict:
                user_dict["id"] = 0
                logger.warning(f"メモリ内ユーザー {username} にID属性がありません。デフォルト値0を設定します。")
            return UserInDB(**user_dict)
        
        # データベースからユーザーデータを取得
        if db_session:
            db_user = db_session.query(models.User).filter(models.User.username == username).first()
            if db_user:
                logger.info(f"データベースからユーザー {username} を取得しました。ID: {db_user.id}")
                return User(
                    id=db_user.id,  # id属性を設定
                    username=db_user.username,
                    email=db_user.email,
                    full_name=db_user.full_name,
                    picture=db_user.picture,
                    google_id=db_user.google_id,
                    disabled=bool(db_user.disabled)
                )
        
        # 後方互換性のため、ファイルからユーザーデータを取得
        user_dict = get_user_from_file(username)
        if user_dict:
            # id属性がない場合は0をデフォルト値として設定
            if "id" not in user_dict:
                user_dict["id"] = 0
                logger.warning(f"ファイルのユーザー {username} にID属性がありません。デフォルト値0を設定します。")
            return UserInDB(**user_dict)
        
        return None
    except Exception as e:
        logger.error(f"ユーザー {username} の取得中にエラーが発生しました: {e}")
        # エラーが発生した場合でも、最低限の情報を持つユーザーオブジェクトを返す
        return User(
            id=0,  # デフォルトID
            username=username,
            email=f"{username}@example.com",  # ダミーメール
            disabled=False
        )

def authenticate_user(username: str, password: str):
    user = get_user(fake_users_db, username)
    if not user:
        return False
    if not user.hashed_password:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    logger = logging.getLogger("booklight-api")
    
    # トークンがない場合
    if token is None:
        return None
    
    # 開発用トークンの場合
    if token == "dev-token-123":
        logger.info("get_current_user: 開発環境用トークンを検出しました。認証をバイパスします。")
        # 開発環境用のダミーユーザーを返す
        return User(
            id=1,
            username="dev_user",
            email="dev@example.com",
            full_name="開発ユーザー",
            disabled=False
        )
        
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # ユーザー情報の取得
    user = get_user(fake_users_db, username, db)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user), request: Request = None):
    """現在のアクティブユーザーを取得"""
    logger = logging.getLogger("booklight-api")
    
    # 開発環境かどうかを確認
    is_development = os.getenv("ENVIRONMENT", "development") != "production"
    debug_mode = os.getenv("DEBUG", "").lower() in ["true", "1", "yes"]
    
    # 環境変数の値をログに出力
    logger.info(f"環境変数DEBUG: {os.getenv('DEBUG', '未設定')}")
    logger.info(f"settings.DEBUG: {settings.DEBUG}")
    logger.info(f"開発環境: {is_development}, デバッグモード: {debug_mode}")
    
    # 開発用トークンの検出
    # 現在のトークンを取得（get_current_userの内部実装に依存）
    current_token = None
    try:
        # FastAPIのリクエストスコープからトークンを取得
        from fastapi.security.utils import get_authorization_scheme_param
        
        # requestパラメータがある場合はヘッダーをチェック
        if request:
            auth_header = request.headers.get("Authorization")
            if auth_header:
                scheme, param = get_authorization_scheme_param(auth_header)
                if scheme.lower() == "bearer":
                    current_token = param
                    logger.info(f"リクエストヘッダーからトークンを取得: {current_token[:10]}...")
    except Exception as e:
        logger.error(f"トークン取得エラー: {e}")
    
    # 開発用トークンの場合は常に認証をバイパス
    if current_token == "dev-token-123":
        logger.info("開発環境用トークンを検出しました。認証をバイパスします。")
        # 開発環境用のダミーユーザーを返す
        return User(
            id=1,
            username="dev_user",
            email="dev@example.com",
            full_name="開発ユーザー",
            disabled=False
        )
    
    # 開発環境では認証なしでもアクセス可能に（トークンがない場合）
    if (is_development or debug_mode or settings.DEBUG) and current_user is None:
        logger.info("開発環境で認証なしアクセス。開発用ユーザーを返します。")
        # 開発環境用のダミーユーザーを返す
        return User(
            id=1,
            username="dev_user",
            email="dev@example.com",
            full_name="開発ユーザー",
            disabled=False
        )
    
    # 本番環境では通常の認証チェック
    if current_user is None:
        logger.error("認証されていないユーザーがAPIにアクセスしようとしました")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if current_user.disabled:
        logger.error(f"無効化されたユーザーがAPIにアクセスしようとしました: {current_user.username}")
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # id属性がない場合のフォールバック
    if not hasattr(current_user, 'id') or current_user.id is None:
        logger.warning(f"ユーザー {current_user.username} にID属性がありません。デフォルト値0を設定します。")
        current_user.id = 0
    
    logger.info(f"アクティブユーザー: {current_user.username} (ID: {current_user.id})")
    return current_user

# Google OAuth認証用の関数
async def authenticate_with_google(token: str, db: Session = None):
    """Googleトークンを検証してユーザー情報を取得"""
    logger = logging.getLogger("booklight-api")
    try:
        # IDトークンの検証
        async with httpx.AsyncClient() as client:
            # Googleのトークン情報エンドポイントにリクエスト
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
            )
            
            if response.status_code != 200:
                logger.error(f"Google APIからの応答エラー: {response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google token"
                )
            
            token_info = response.json()
            
            # クライアントIDの検証
            if token_info.get("aud") != GOOGLE_CLIENT_ID:
                logger.error(f"クライアントID不一致: {token_info.get('aud')} != {GOOGLE_CLIENT_ID}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid client ID"
                )
            
            # ユーザー情報の取得
            user_info = {
                "username": token_info.get("email").split('@')[0],
                "email": token_info.get("email"),
                "full_name": token_info.get("name"),
                "google_id": token_info.get("sub"),
                "picture": token_info.get("picture"),
                "disabled": False
            }
            
            # データベースにユーザー情報を保存
            if db:
                try:
                    db_user = get_or_create_user_in_db(db, user_info)
                    # ユーザー情報にIDを追加（get_or_create_user_in_db内でも設定されるが、念のため）
                    user_info["id"] = db_user.id
                    logger.info(f"Google認証成功: ユーザー {user_info['username']} (ID: {db_user.id})")
                except Exception as db_error:
                    # データベースエラーが発生した場合でも処理を続行
                    logger.error(f"データベース操作中にエラーが発生: {db_error}")
                    user_info["id"] = 0  # デフォルトID
            else:
                # データベースセッションがない場合
                logger.warning("データベースセッションがないため、ユーザーIDを設定できません")
                user_info["id"] = 0  # デフォルトID
            
            # 後方互換性のため、ファイルにも保存
            try:
                user_id = save_user_to_file(user_info)
                logger.info(f"ユーザー情報をファイルに保存しました: {user_id}")
            except Exception as file_error:
                logger.error(f"ファイル保存中にエラーが発生: {file_error}")
            
            return user_info
    
    except httpx.RequestError as req_error:
        logger.error(f"Google API接続エラー: {req_error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not connect to Google API: {str(req_error)}"
        )
    except Exception as e:
        logger.error(f"認証エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )

# リダイレクトURIを取得
redirect_uri = os.getenv("REDIRECT_URI", "https://booklight-ai.com/auth/callback")

# Google OAuth認証クライアントの設定
oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'redirect_uri': redirect_uri  # 明示的にリダイレクトURIを設定
    }
)
