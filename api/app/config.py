import os
import logging
from dotenv import load_dotenv # dotenvをインポート
from pathlib import Path      # pathlibをインポート
from typing import List, Optional
from pydantic_settings import BaseSettings

logger = logging.getLogger("booklight-api") # ロガー取得を先に移動

# --- .env ファイルの明示的な読み込み処理を追加 ---
# config.py の場所からプロジェクトルートのパスを取得 (api/app/ -> api/ -> project_root/)
env_path = Path(__file__).resolve().parents[2] / '.env'
logger.debug(f"Attempting to load .env file from: {env_path}")
# .env ファイルを明示的に読み込む (存在しなくてもエラーにはしない)
loaded = load_dotenv(dotenv_path=env_path, override=True) # override=True で既存の環境変数を上書き
logger.debug(f".env file loaded: {loaded} (Path exists: {env_path.exists()})") # 読み込めたかどうかのログも追加
# --- 追加ここまで ---

class Settings(BaseSettings):
    APP_NAME: str = "Booklight AI API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ["true", "1", "yes"]
    
    # データベース設定
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./booklight.db")
    
    # 認証設定
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "fallback-secret-key-for-development-only")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    SESSION_SECRET_KEY: str = os.getenv("SESSION_SECRET_KEY", "fallback-session-secret-key-for-development-only")
    DEBUG_API_KEY: str = os.getenv("DEBUG_API_KEY", "")
    
    # Google OAuth設定
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    # リダイレクトURI
    REDIRECT_URI: str = os.getenv("REDIRECT_URI", "")
    
    # フロントエンドURL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "")
    
    # Heroku設定
    HEROKU_APP_NAME: Optional[str] = os.getenv("HEROKU_APP_NAME")
    
    # CORS設定
    CORS_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://localhost:8501",  # Streamlit
        "http://localhost:5173",  # Vite開発サーバー
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8501",
        "http://127.0.0.1:5173",
        "chrome-extension://",    # Chrome拡張機能
    ]
    
    # カスタムドメインがある場合は追加
    if os.getenv("CUSTOM_DOMAIN"):
        CORS_ORIGINS.append(f"https://{os.getenv('CUSTOM_DOMAIN')}")
    
    # Herokuアプリ名がある場合は追加
    if os.getenv("HEROKU_APP_NAME"):
        CORS_ORIGINS.append(f"https://{os.getenv('HEROKU_APP_NAME')}.herokuapp.com")
    
    # ログレベル
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Sentry設定
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    
    # OpenAI API設定
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    class Config:
        # env_file = ".env" # load_dotenv で読み込むのでコメントアウト
        pass

settings = Settings()

# --- デバッグログ追加 ---
if not settings.OPENAI_API_KEY:
    logger.warning("Config: OPENAI_API_KEY is empty or not set.")
else:
    # キーの一部だけをログに出力（セキュリティのため）
    logger.debug(f"Config: OPENAI_API_KEY loaded successfully (starts with: {settings.OPENAI_API_KEY[:5]}...).")
# --- デバッグログ追加ここまで ---
