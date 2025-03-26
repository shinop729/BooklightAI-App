import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

from fastapi import HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings

# 環境変数から設定を取得
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

logger = logging.getLogger("booklight-api")

class TokenData(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    JWTアクセストークンを生成する
    
    Args:
        data: トークンに含めるデータ
        expires_delta: トークンの有効期限
        
    Returns:
        str: 生成されたJWTトークン
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Dict:
    """
    JWTトークンを検証し、ペイロードを返す
    
    Args:
        token: 検証するJWTトークン
        
    Returns:
        Dict: トークンのペイロード
        
    Raises:
        HTTPException: トークンが無効な場合
    """
    try:
        # 開発環境用トークンバイパス
        if token == "dev-token-123":
            # 常に開発用トークンを許可する
            logger.info("開発環境用トークンを検出しました。認証をバイパスします。")
            return {"sub": "dev-user", "email": "dev@example.com"}
            
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            logger.warning("トークンにユーザー名が含まれていません")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無効なトークンです",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError as e:
        logger.warning(f"トークン検証エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="トークンの有効期限が切れているか、無効です",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"予期しないトークン検証エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"トークン検証中にエラーが発生しました: {str(e)}",
        )

def refresh_access_token(token: str) -> Dict:
    """
    既存のトークンを検証し、新しいトークンを生成する
    
    Args:
        token: リフレッシュするトークン
        
    Returns:
        Dict: 新しいトークン情報
        
    Raises:
        HTTPException: トークンが無効な場合
    """
    try:
        # 開発環境用トークンバイパス
        if token == "dev-token-123":
            # 開発用トークンの場合は検証をスキップして新しいトークンを生成
            logger.info("開発環境用トークンを検出しました。認証をバイパスします。")
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": "dev-user", "email": "dev@example.com"},
                expires_delta=access_token_expires
            )
            
            return {
                "access_token": "dev-token-123",  # 開発環境では同じトークンを返す
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 秒単位
            }
        
        # 通常のトークン検証処理
        payload = verify_token(token)
        
        # 新しいトークンを生成
        username = payload.get("sub")
        email = payload.get("email")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": username, "email": email},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 秒単位
        }
    except JWTError as e:
        logger.warning(f"トークンリフレッシュエラー (JWT): {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="トークンの有効期限が切れているか、無効です",
            headers={"WWW-Authenticate": "Bearer"},
        )
