#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import logging
from pathlib import Path

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("env_check.log"),
        logging.StreamHandler()
    ]
)

def check_environment():
    """環境変数の設定状況を確認するスクリプト"""
    load_dotenv()
    
    # 必須環境変数
    required_vars = [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "JWT_SECRET_KEY"
    ]
    
    # 認証関連の環境変数
    auth_vars = [
        "REDIRECT_URI",
        "FRONTEND_URL",
        "CUSTOM_DOMAIN",
        "HEROKU_APP_NAME"
    ]
    
    # 必須環境変数のチェック
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        logging.error(f"必須環境変数が設定されていません: {', '.join(missing)}")
    else:
        logging.info("すべての必須環境変数が設定されています")
    
    # 認証関連の環境変数のチェック
    auth_settings = {}
    for var in auth_vars:
        auth_settings[var] = os.getenv(var)
    
    logging.info("認証関連の環境変数設定:")
    for var, value in auth_settings.items():
        status = "設定済み" if value else "未設定"
        logging.info(f"  {var}: {status}")
    
    # リダイレクトURIの決定ロジックをシミュレート
    custom_domain = os.getenv("CUSTOM_DOMAIN")
    heroku_app_name = os.getenv("HEROKU_APP_NAME")
    explicit_redirect_uri = os.getenv("REDIRECT_URI")
    
    if custom_domain:
        redirect_uri = f"https://{custom_domain}/auth/callback"
        source = "カスタムドメイン"
    elif explicit_redirect_uri:
        redirect_uri = explicit_redirect_uri
        source = "環境変数REDIRECT_URI"
    elif heroku_app_name:
        redirect_uri = f"https://{heroku_app_name}.herokuapp.com/auth/callback"
        source = "Herokuアプリ名"
    else:
        redirect_uri = "http://localhost:8000/auth/callback"
        source = "デフォルト値"
    
    logging.info(f"リダイレクトURI決定結果: {redirect_uri} (ソース: {source})")
    
    # Streamlitのリダイレクトも確認
    if custom_domain:
        streamlit_redirect = f"https://{custom_domain}/auth/callback"
        streamlit_source = "カスタムドメイン"
    elif heroku_app_name:
        streamlit_redirect = f"https://{heroku_app_name}.herokuapp.com/auth/callback"
        streamlit_source = "Herokuアプリ名"
    else:
        streamlit_redirect = "http://localhost:8501/"
        streamlit_source = "デフォルト値"
    
    logging.info(f"StreamlitリダイレクトURI決定結果: {streamlit_redirect} (ソース: {streamlit_source})")
    
    # Google Cloud Consoleの設定確認
    logging.info("\nGoogle Cloud Console設定確認:")
    logging.info("以下のリダイレクトURIがGoogle Cloud Consoleの承認済みリダイレクトURIに設定されているか確認してください:")
    logging.info(f"1. {redirect_uri} (FastAPI)")
    logging.info(f"2. {streamlit_redirect} (Streamlit)")
    
    return not bool(missing)

if __name__ == "__main__":
    print("環境変数の設定状況を確認しています...")
    check_environment()
