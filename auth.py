import os
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# .envファイルを読み込む（存在する場合）
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()  # Herokuでは環境変数が直接設定されている

# Google OAuth設定
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# リダイレクトURIの設定（Herokuでは環境変数から取得）
REDIRECT_URI = os.getenv("REDIRECT_URI")
if not REDIRECT_URI or 'localhost' in REDIRECT_URI:
    # 環境変数が設定されていない場合はデフォルト値を使用
    # 本番環境では適切に設定する必要がある
    is_heroku = os.getenv("DYNO") is not None  # Herokuで実行されているかどうか
    if is_heroku:
        app_name = os.getenv("HEROKU_APP_NAME", "")
        if app_name:
            # Heroku環境では、Streamlitのルートパスをリダイレクトとして使用
            REDIRECT_URI = f"https://{app_name}.herokuapp.com/"
            print(f"Heroku環境でのリダイレクトURI: {REDIRECT_URI}")
        else:
            # アプリ名が不明な場合はデフォルト値を使用
            REDIRECT_URI = "http://localhost:8501/"
    else:
        REDIRECT_URI = "http://localhost:8501/"
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
    
    if code:
        try:
            # コードをトークンと交換
            credentials = exchange_code_for_token(code)
            
            # ユーザー情報を取得
            user_info = get_user_info(credentials)
            
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
                print(f"認証成功: ユーザーID={user_id}, セッション設定完了")
                print(f"セッション状態: {list(st.session_state.keys())}")
                print(f"ユーザー情報: {user_info.get('name')} ({user_info.get('email')})")
                
                # URLパラメータをクリア
                st.query_params.clear()
                
                return True
        except Exception as e:
            import traceback
            print(f"認証エラー詳細: {str(e)}")
            print(traceback.format_exc())
            st.error(f"認証エラー: {str(e)}")
            st.error(f"詳細エラー: {traceback.format_exc()}")
    
    return False

def logout():
    """ログアウト処理"""
    if "user_info" in st.session_state:
        del st.session_state.user_info
    if "credentials" in st.session_state:
        del st.session_state.credentials
