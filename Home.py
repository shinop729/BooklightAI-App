import streamlit as st
import pandas as pd
import os
import urllib.parse
import unicodedata
import re
import random
from langchain.schema import Document
from dotenv import load_dotenv
import openai
import urllib.parse
from pathlib import Path
import auth
from progress_display import display_summary_progress_in_sidebar
import requests

def local_css(file_name):
    """Load and inject a local CSS file into the Streamlit app"""
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# アプリ全体の設定
def setup_app():
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
    st.set_page_config(page_title="Booklight AI", layout="wide")
    
    st.sidebar.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="color: #4A90E2; font-size: 28px;">Booklight AI</h1>
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("📚 あなたの読書をAIが照らす")
    st.sidebar.markdown("---")

import urllib.parse
import unicodedata
import re
import pandas as pd
import random
import os
import openai
from langchain_core.documents import Document

def normalize_japanese_text(text: str) -> str:
    import unicodedata
    import re
    text = unicodedata.normalize('NFKC', text)
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def load_highlights():
    df = pd.read_csv("docs/KindleHighlights.csv")
    docs = []
    for _, row in df.iterrows():
        normalized_highlight = normalize_japanese_text(row["ハイライト内容"])
        doc = Document(
            page_content=normalized_highlight,
            metadata={
                "original_title": row["書籍タイトル"],
                "original_author": row["著者"]
            }
        )
        docs.append(doc)
    return docs

@st.cache_resource
def load_book_info(user_id=None):
    """書籍情報を読み込む（ユーザー固有のデータがあれば使用）"""
    if user_id:
        # ユーザー固有のハイライトファイルのパス
        user_highlights_path = auth.USER_DATA_DIR / "docs" / user_id / "KindleHighlights.csv"
        
        # ユーザー固有のファイルが存在する場合はそれを使用
        if user_highlights_path.exists():
            df = pd.read_csv(user_highlights_path)
        else:
            # 存在しない場合は共通のファイルを使用
            df = pd.read_csv("docs/KindleHighlights.csv")
    else:
        # ログインしていない場合は共通のファイルを使用
        df = pd.read_csv("docs/KindleHighlights.csv")
    
    df = df[df["書籍タイトル"] != ""]
    
    # Group by book title and aggregate highlights
    grouped = df.groupby("書籍タイトル")["ハイライト内容"].agg(lambda x: "\n".join(x)).reset_index()
    
    book_info = {}
    for _, row in grouped.iterrows():
        title = row["書籍タイトル"]
        # Get author for this book (taking the first one if multiple)
        author = df[df["書籍タイトル"] == title]["著者"].iloc[0] if not df[df["書籍タイトル"] == title]["著者"].empty else ""
        
        # Create a dictionary with the required structure for Search.py
        book_info[title] = {
            "title_text": title,
            "normalized_title": normalize_japanese_text(title),
            "normalized_summary": normalize_japanese_text(row["ハイライト内容"]),
            "author": author
        }
    return book_info

def display_quote(content, title, author, index=0):
    """
    Home.py用の引用表示関数 - 書籍タイトルをクリックして詳細ページへ遷移
    """
    # URLエンコードされたタイトル
    encoded_title = urllib.parse.quote(title)
    
    # ハイライト内容を表示
    st.markdown(f"""
    <div style="padding:15px; border-radius:8px; background-color:#2a2a2a; margin-bottom:15px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
        <p style="color:#ffffff; font-size:16px; line-height:1.6; margin-bottom:12px;">{content}</p>
    </div>
    """, unsafe_allow_html=True)
  
    
    # 書籍タイトルをリンクボタンとして表示
    st.link_button(f"📚 {title} / {author}", f"pages/BookDetail.py?title={encoded_title}", use_container_width=True)

def load_user_highlights(user_id):
    """ユーザー固有のハイライトを読み込む"""
    user_highlights_path = auth.USER_DATA_DIR / "docs" / user_id / "KindleHighlights.csv"
    
    # ユーザー固有のハイライトファイルが存在しない場合は共通のファイルを使用
    if not user_highlights_path.exists():
        return load_highlights()
    
    df = pd.read_csv(user_highlights_path)
    docs = []
    for _, row in df.iterrows():
        normalized_highlight = normalize_japanese_text(row["ハイライト内容"])
        doc = Document(
            page_content=normalized_highlight,
            metadata={
                "original_title": row["書籍タイトル"],
                "original_author": row["著者"]
            }
        )
        docs.append(doc)
    return docs

def display_quote_with_button(content, title, author, index=0):
    """
    書籍タイトルをボタンとして表示し、クリックで詳細ページに遷移する関数
    """
    # ハイライト内容を表示
    st.markdown(f"""
    <div style="padding:15px; border-radius:8px; background-color:#2a2a2a; margin-bottom:15px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
        <p style="color:#ffffff; font-size:16px; line-height:1.6; margin-bottom:12px;">{content}</p>
    </div>
    """, unsafe_allow_html=True)
    
  
    
    # 書籍タイトルをボタンとして表示
    if st.button(f"📚 {title} / {author}", key=f"book_button_{index}"):
        st.session_state.selected_book_title = title
        st.switch_page("pages/BookDetail.py")

# FastAPIへのリクエストをプロキシする関数
def proxy_api_request():
    """
    /api/で始まるリクエストをFastAPIサーバーにプロキシする
    """
    # リクエストパスを取得
    query_params = st.query_params
    request_path = query_params.get("_path", "")
    
    # /api/で始まるリクエストのみ処理
    if request_path.startswith("/api/"):
        try:
            # FastAPIサーバーのURLを構築
            api_path = request_path[4:]  # /api/ を除去
            
            # Heroku環境ではアプリのURLを使用
            is_heroku = os.getenv("DYNO") is not None
            if is_heroku:
                app_name = os.getenv("HEROKU_APP_NAME", "")
                if app_name:
                    # 同じHerokuアプリ内のAPIにリクエスト
                    api_url = f"https://{app_name}.herokuapp.com/api{api_path}"
                else:
                    # アプリ名が不明な場合はAPI_URLを使用
                    api_url = os.getenv("API_URL", "")
                    if api_url:
                        api_url = f"{api_url}/api{api_path}"
                    else:
                        # フォールバックとしてローカルホストを使用
                        api_port = os.environ.get("API_PORT", "8000")
                        api_url = f"http://localhost:{api_port}{api_path}"
                
                print(f"Heroku環境でのAPIリクエスト: {api_url}")
            else:
                # ローカル環境ではlocalhost:8000を使用
                api_url = f"http://localhost:8000{api_path}"
            
            st.write(f"APIリクエスト: {api_url}")
            
            # リクエストをプロキシ
            response = requests.get(api_url, timeout=10)
            
            # レスポンスを返す
            return response.json()
        except Exception as e:
            st.error(f"APIリクエストエラー: {e}")
            print(f"APIリクエスト詳細エラー: {str(e)}")
            return {"error": str(e)}
    
    return None

def main():
    setup_app()
    
    # 認証チェック - 未ログインの場合はエラーメッセージを表示
    if not auth.is_user_authenticated():
        st.warning("このページにアクセスするにはログインが必要です。")
        return
    
    # APIリクエストをプロキシ
    api_response = proxy_api_request()
    if api_response:
        st.json(api_response)
        return
    
    # ユーザーディレクトリの作成
    auth.create_user_directories()
    
    # 認証フローの処理
    auth_success = auth.handle_auth_flow()
    if auth_success:
        st.success("ログインに成功しました！")
        st.rerun()  # ページをリロード
    
    # サイドバーにログイン/ログアウトボタンを追加
    st.sidebar.markdown("---")
    if auth.is_user_authenticated():
        user_info = st.session_state.user_info
        st.sidebar.markdown(f"### ようこそ、{user_info.get('name', 'ユーザー')}さん！")
        st.sidebar.markdown(f"📧 {user_info.get('email', '')}")
        
        if st.sidebar.button("ログアウト"):
            auth.logout()
            st.rerun()  # ページをリロード
    else:
        st.sidebar.markdown("### ログイン")
        auth_url = auth.get_google_auth_url()
        if auth_url:
            st.sidebar.markdown(f"[Googleでログイン]({auth_url})")
        else:
            st.sidebar.error("認証設定が不完全です。.envファイルを確認してください。")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("[🔍 検索モード](pages/Search.py)")
    st.sidebar.markdown("[💬 チャットモード](pages/Chat.py)")
    st.sidebar.markdown("[📚 書籍一覧](pages/BookList.py)")
    st.sidebar.markdown("[📤 ハイライトアップロード](pages/Upload.py)")
    
    # サマリ生成の進捗状況をサイドバーに表示
    display_summary_progress_in_sidebar()
    
    # ハイライトの読み込み（ログイン中はユーザー固有のデータを使用）
    if auth.is_user_authenticated():
        user_id = auth.get_current_user_id()
        highlight_docs = load_user_highlights(user_id)
        st.title(f"{st.session_state.user_info.get('name', 'ユーザー')}さんのBooklight AI")
    else:
        highlight_docs = load_highlights()
        st.title("Booklight AI")
    
    # ログイン状態に応じたメッセージ表示
    if auth.is_user_authenticated():
        st.info("ログイン中です。あなた専用のハイライトデータが表示されます。")
    else:
        st.info("ログインすると、あなた専用のハイライトデータを管理できます。")

    if not highlight_docs:
        st.write("ハイライトがありません。")
    else:
        # セッション状態にランダムなハイライトを保存
        if 'random_highlight_docs' not in st.session_state:
            st.session_state.random_highlight_docs = random.sample(highlight_docs, min(3, len(highlight_docs)))
        
        # セッション状態からハイライトを取得
        for i, doc in enumerate(st.session_state.random_highlight_docs):
            title = doc.metadata.get("original_title", "不明なタイトル")
            author = doc.metadata.get("original_author", "不明な著者")
            content = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
            display_quote_with_button(content, title, author, i)

if __name__ == "__main__":
    main()
