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

def local_css(file_name):
    """Load and inject a local CSS file into the Streamlit app"""
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# アプリ全体の設定
def setup_app():
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
    st.set_page_config(page_title="Booklight AI", layout="wide")
    
    # デバッグ情報を表示
    st.write("環境変数のデバッグ情報:")
    st.write(f"GOOGLE_CLIENT_ID: {os.getenv('GOOGLE_CLIENT_ID')}")
    st.write(f"GOOGLE_CLIENT_SECRET: {os.getenv('GOOGLE_CLIENT_SECRET')}")
    st.write(f"REDIRECT_URI: {os.getenv('REDIRECT_URI')}")
    
    st.sidebar.image("images/booklight_ai_banner.png", use_container_width=True)
    st.sidebar.title("Booklight AI")
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
    Home.py用の引用表示関数 - 書籍詳細ページへのリンク付き
    """
    # ホームページ用のスタイル（ダークモード対応）
    quote_html = f"""
    <div style="padding:15px; border-radius:8px; background-color:#2a2a2a; margin-bottom:15px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
        <p style="color:#ffffff; font-size:16px; line-height:1.6; margin-bottom:12px;">{content}</p>
        <div style="text-align:right;">
            <span style="color:#4da6ff; font-weight:500;">{title} / {author}</span>
        </div>
    </div>
    """
    st.markdown(quote_html, unsafe_allow_html=True)
    
    # 詳細ページへのリンクを追加
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button(f"詳細を見る", key=f"home_detail_{index}"):
            # セッション状態に書籍タイトルを保存
            st.session_state.selected_book_title = title
            # BookDetailページにリダイレクト
            st.switch_page("pages/BookDetail.py")

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

def main():
    setup_app()
    
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
        st.sidebar.write("ログインデバッグ情報:")
        auth_url = auth.get_google_auth_url()
        st.sidebar.write(f"auth_url: {auth_url}")
        if auth_url:
            st.sidebar.markdown(f"[Googleでログイン]({auth_url})")
            # 直接リンクも表示
            st.sidebar.write("直接リンク:")
            st.sidebar.write(auth_url)
        else:
            st.sidebar.error("認証設定が不完全です。.envファイルを確認してください。")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("[🔍 検索モード](pages/Search.py)")
    st.sidebar.markdown("[💬 チャットモード](pages/Chat.py)")
    st.sidebar.markdown("[📚 書籍一覧](pages/BookList.py)")
    st.sidebar.markdown("[📤 ハイライトアップロード](pages/Upload.py)")
    
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
        random_docs = random.sample(highlight_docs, min(3, len(highlight_docs)))
        for i, doc in enumerate(random_docs):
            title = doc.metadata.get("original_title", "不明なタイトル")
            author = doc.metadata.get("original_author", "不明な著者")
            content = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
            display_quote(content, title, author, i)

if __name__ == "__main__":
    main()
