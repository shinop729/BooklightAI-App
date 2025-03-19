import os
from enum import Enum
from functools import lru_cache
from typing import List, Optional
from pydantic import BaseSettings, Field, validator

class EnvironmentType(str, Enum):
    """環境タイプの列挙型"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

def get_environment() -> EnvironmentType:
    """システム環境を検出"""
    env = os.getenv("ENVIRONMENT", "").lower()
    
    if env in ["production", "prod"]:
        return EnvironmentType.PRODUCTION
    elif env in ["staging", "stage"]:
        return EnvironmentType.STAGING
    # Herokuでの自動検出
    elif os.getenv("DYNO") and not env:
        return EnvironmentType.PRODUCTION
    else:
        return EnvironmentType.DEVELOPMENT

class Settings(BaseSettings):
    """アプリケーション設定"""
    # アプリケーション情報
    APP_NAME: str = "Booklight AI"
    ENVIRONMENT: EnvironmentType = Field(default_factory=get_environment)
    VERSION: str = "0.1.0"
    
    # デバッグ設定
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    
    # データベース設定
    DATABASE_URL: str = Field(
        default="sqlite:///./booklight.db",
        description="データベース接続文字列"
    )
    
    # 認証設定
    JWT_SECRET_KEY: str = Field(
        default="",
        description="JWT署名に使用するシークレットキー"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Google OAuth設定
    GOOGLE_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="Google Client ID"
    )
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(
        default=None,
        description="Google Client Secret"
    )
    
    # フロントエンド・リダイレクト設定
    FRONTEND_URL: Optional[str] = Field(
        default=None,
        description="フロントエンドアプリケーションのベースURL"
    )
    REDIRECT_URI: Optional[str] = Field(
        default=None,
        description="OAuth認証リダイレクトURI"
    )
    
    # CORS設定
    CORS_ORIGINS: List[str] = Field(
        default_factory=list,
        description="CORSで許可するオリジン"
    )
    
    # Heroku関連設定
    HEROKU_APP_NAME: Optional[str] = Field(
        default=None,
        description="Herokuアプリケーション名"
    )
    
    # デバッグ用API Key
    DEBUG_API_KEY: Optional[str] = Field(
        default=None,
        description="本番環境でのデバッグエンドポイントアクセス用APIキー"
    )
    
    @validator('CORS_ORIGINS', pre=True)
    def set_cors_origins(cls, v, values):
        """環境に応じたCORSオリジンの設定"""
        if not v:
            # デフォルトのオリジン
            default_origins = [
                "http://localhost:8501",  # Streamlit
                "http://localhost:3000",  # React
            ]
            
            # フロントエンドURLがある場合は追加
            frontend_url = values.get('FRONTEND_URL')
            if frontend_url and frontend_url not in default_origins:
                default_origins.append(frontend_url)
            
            return default_origins
        return v
    
    def get_database_config(self):
        """環境に応じたデータベース設定を返す"""
        if self.ENVIRONMENT == EnvironmentType.PRODUCTION:
            # 本番環境ではPostgreSQLを優先
            return {
                "url": os.getenv("DATABASE_URL", self.DATABASE_URL),
                "pool_size": 10,
                "max_overflow": 20
            }
        return {
            "url": self.DATABASE_URL,
            "pool_size": 5,
            "max_overflow": 10
        }
    
    class Config:
        """Pydanticの設定"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """設定のシングルトンインスタンスを取得"""
    return Settings()

# グローバル設定インスタンス
settings = get_settings()
