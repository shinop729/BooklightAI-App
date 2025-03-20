import os
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
import logging
import traceback

# ロガーの設定
logger = logging.getLogger('booklight-auth')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# ファイルベースのロギング設定
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
file_handler = logging.FileHandler(log_dir / "auth.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# .envファイルを読み込む（存在する場合）
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()  # Herokuでは環境変数が直接設定されている

# 環境変数のロギング
logger.debug("=== auth.py の環境変数 ===")
logger.debug(f"DYNO: {os.getenv('DYNO')}")
logger.debug(f"HEROKU_APP_NAME: {os.getenv('HEROKU_APP_NAME')}")
logger.debug(f"CUSTOM_DOMAIN: {os.getenv('CUSTOM_DOMAIN')}")
logger.debug(f"FRONTEND_URL: {os.getenv('FRONTEND_URL')}")
logger.debug(f"REDIRECT_URI: {os.getenv('REDIRECT_URI')}")
logger.debug(f"GOOGLE_CLIENT_ID: {'設定あり' if os.getenv('GOOGLE_CLIENT_ID') else '未設定'}")

# Google OAuth設定
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# リダイレクトURIの設定
REDIRECT_URI = os.getenv("REDIRECT_URI")
if not REDIRECT_URI:
    # カスタムドメインがある場合（優先）
    custom_domain = os.getenv("CUSTOM_DOMAIN")
    if custom_domain:
        REDIRECT_URI = f"https://{custom_domain}/auth/callback"
        logger.info(f"カスタムドメインからリダイレクトURIを設定: {REDIRECT_URI}")
    # Herokuアプリ名がある場合
    elif os.getenv("HEROKU_APP_NAME"):
        app_name = os.getenv("HEROKU_APP_NAME")
        REDIRECT_URI = f"https://{app_name}.herokuapp.com/auth/callback"
        logger.info(f"Herokuアプリ名からリダイレクトURIを設定: {REDIRECT_URI}")
    # それ以外の場合はローカル開発用
    else:
        REDIRECT_URI = "http://localhost:8501/"
        logger.info(f"ローカル開発用リダイレクトURIを設定: {REDIRECT_URI}")

# リダイレクトURIをログに出力
logger.info(f"最終的なリダイレクトURI: {REDIRECT_URI}")

SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

# ユーザーデータ保存ディレクトリ
USER_DATA_DIR = Path("user_data")

def create_user_directories():
    """ユーザーデータ用のディレクトリ構造を作成"""
    # ユーザーデータのルートディレクトリ
    USER_DATA_DIR.mkdir(exist_ok=True)
    
    # ユーザーごとのドキュメントディレクトリ
    (USER_DATA_DIR / "docs").mkdir(exist_ok=True)

def get_google_auth_url():
    """Googleログイン用のURLを生成"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        st.error("Google OAuth認証情報が設定されていません。.envファイルを確認してください。")
        return None
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI]
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    
    return auth_url

def exchange_code_for_token(code):
    """認証コードをトークンと交換"""
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI]
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    return credentials

def get_user_info(credentials):
    """ユーザー情報を取得"""
    userinfo_endpoint = "https://www.googleapis.com/oauth2/v3/userinfo"
    response = requests.get(
        userinfo_endpoint,
        headers={"Authorization": f"Bearer {credentials.token}"}
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"ユーザー情報の取得に失敗しました: {response.text}")
        return None

def create_user_folder(user_id):
    """ユーザー固有のフォルダを作成"""
    user_folder = USER_DATA_DIR / "docs" / user_id
    user_folder.mkdir(exist_ok=True)
    return user_folder

def save_user_data(user_info):
    """ユーザー情報を保存"""
    user_id = user_info.get("sub")  # Google's unique user ID
    if not user_id:
        return None
    
    # ユーザーフォルダを作成
    user_folder = create_user_folder(user_id)
    
    # ユーザー情報をJSONファイルとして保存
    user_data_file = user_folder / "user_info.json"
    with open(user_data_file, "w") as f:
        json.dump(user_info, f)
    
    return user_id

def is_user_authenticated():
    """ユーザーが認証済みかどうかを確認"""
    return "user_info" in st.session_state and st.session_state.user_info is not None

def get_current_user_id():
    """現在のユーザーIDを取得"""
    if is_user_authenticated():
        return st.session_state.user_info.get("sub")
    return None

def get_user_specific_path(relative_path):
    """ユーザー固有のパスを取得"""
    user_id = get_current_user_id()
    if not user_id:
        return None
    
    return USER_DATA_DIR / "docs" / user_id / relative_path

def handle_auth_flow():
    """認証フローを処理"""
    # URLパラメータからcodeを取得
    code = st.query_params.get("code", None)
    state = st.query_params.get("state", None)
    
    # 追加のデバッグログ
    logger.info(f"認証コールバック処理開始: code={bool(code)}, state={bool(state)}")
    logger.debug(f"クエリパラメータ: {dict(st.query_params)}")
    
    # 代替のパラメータ取得方法は削除
    # st.query_paramsのみを使用するように統一
    if not code:
        logger.info("クエリパラメータからcodeが取得できませんでした")
    
    if code:
        try:
            logger.info("認証コードの交換を開始")
            # コードをトークンと交換
            credentials = exchange_code_for_token(code)
            logger.info("トークン取得成功")
            
            # ユーザー情報を取得
            logger.info("ユーザー情報の取得を開始")
            user_info = get_user_info(credentials)
            logger.info(f"ユーザー情報取得結果: {bool(user_info)}")
            
            if user_info:
                # セッションにユーザー情報を保存
                st.session_state.user_info = user_info
                st.session_state.credentials = {
                    "token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                    "token_uri": credentials.token_uri,
                    "client_id": credentials.client_id,
                    "client_secret": credentials.client_secret,
                    "scopes": credentials.scopes
                }
                
                # ユーザーデータを保存
                user_id = save_user_data(user_info)
                
                # セッション処理のログ
                logger.info(f"認証成功: ユーザーID={user_id}, セッション設定完了")
                logger.info(f"セッション状態: {list(st.session_state.keys())}")
                logger.info(f"ユーザー情報: {user_info.get('name')} ({user_info.get('email')})")
                
                # URLパラメータをクリア
                st.query_params.clear()
                
                return True
            else:
                logger.error("ユーザー情報の取得に失敗しました")
                st.error("ユーザー情報の取得に失敗しました。再度ログインしてください。")
        except Exception as e:
            logger.error(f"認証エラー詳細: {str(e)}")
            logger.error(traceback.format_exc())
            st.error(f"認証エラー: {str(e)}")
            st.code(traceback.format_exc(), language="python")
    else:
        logger.warning("認証コードが見つかりません")
        if state:
            logger.info("stateパラメータは存在しますが、codeパラメータがありません")
        else:
            logger.warning("認証パラメータが完全に欠落しています")
    
    return False

def redirect_if_authenticated():
    """ログイン済みの場合はホームページにリダイレクト"""
    if is_user_authenticated():
        st.switch_page("Home.py")

def logout():
    """ログアウト処理"""
    if "user_info" in st.session_state:
        del st.session_state.user_info
    if "credentials" in st.session_state:
        del st.session_state.credentials
