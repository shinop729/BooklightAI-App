import os
import json
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
    username = user_data.get("username")
    email = user_data.get("email")
    google_id = user_data.get("google_id")
    
    # ユーザーの検索条件
    if google_id:
        db_user = db.query(models.User).filter(models.User.google_id == google_id).first()
    elif email:
        db_user = db.query(models.User).filter(models.User.email == email).first()
    elif username:
        db_user = db.query(models.User).filter(models.User.username == username).first()
    else:
        return None
    
    # ユーザーが存在しない場合は作成
    if not db_user:
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
    
    return db_user

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str, db_session: Session = None):
    # まずメモリ内のユーザーデータを確認
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    
    # データベースからユーザーデータを取得
    if db_session:
        db_user = db_session.query(models.User).filter(models.User.username == username).first()
        if db_user:
            return User(
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
        return UserInDB(**user_dict)
    
    return None

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
    if token is None:
        return None
        
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

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Google OAuth認証用の関数
async def authenticate_with_google(token: str, db: Session = None):
    """Googleトークンを検証してユーザー情報を取得"""
    try:
        # IDトークンの検証
        async with httpx.AsyncClient() as client:
            # Googleのトークン情報エンドポイントにリクエスト
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google token"
                )
            
            token_info = response.json()
            
            # クライアントIDの検証
            if token_info.get("aud") != GOOGLE_CLIENT_ID:
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
                db_user = get_or_create_user_in_db(db, user_info)
            
            # 後方互換性のため、ファイルにも保存
            user_id = save_user_to_file(user_info)
            
            return user_info
    
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Google API"
        )
    except Exception as e:
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
