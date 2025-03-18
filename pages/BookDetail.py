import streamlit as st
import pandas as pd
import requests
import urllib
import unicodedata
import re
import html
from typing import List, Dict, Any
import os
import sys
from pathlib import Path

# 親ディレクトリをパスに追加（Homeモジュールをインポートするため）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auth
from progress_display import display_summary_progress_in_sidebar
from api.database.base import SessionLocal
from api.database.models import User, Book, Highlight
from api.database import access as db_access

# ページ設定
st.set_page_config(
    page_title="書籍詳細 | Booklight AI", 
    page_icon="📖",
    layout="centered",
    initial_sidebar_state="expanded"
)

# CSSのロード関数
def local_css(file_name):
    """Load and inject a local CSS file into the Streamlit app"""
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# CSSのロード
local_css("style.css")

# サイドバー設定
st.sidebar.image("images/booklight_ai_banner.png", use_container_width=True)
st.sidebar.title("Booklight AI")
st.sidebar.markdown("📚 あなたの読書をAIが照らす")
st.sidebar.markdown("---")

# サイドバーにログイン/ログアウトボタンを追加
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

# サイドバーナビゲーション
st.sidebar.markdown("---")
st.sidebar.markdown("### ナビゲーション")
st.sidebar.markdown("[🏠 ホーム](Home.py)")
st.sidebar.markdown("[🔍 検索モード](pages/Search.py)")
st.sidebar.markdown("[💬 チャットモード](pages/Chat.py)")
st.sidebar.markdown("[📚 書籍一覧](pages/BookList.py)")
st.sidebar.markdown("[📤 ハイライトアップロード](pages/Upload.py)")

# サマリ生成の進捗状況をサイドバーに表示
display_summary_progress_in_sidebar()

# 認証フローの処理
auth_success = auth.handle_auth_flow()
if auth_success:
    st.success("ログインに成功しました！")
    st.rerun()  # ページをリロード

# 1) 書籍要約を読み込む (BookSummaries.csv)
@st.cache_data
def load_book_summaries():
    df = pd.read_csv("docs/BookSummaries.csv")
    df["書籍タイトル"].fillna("", inplace=True)
    df["要約"].fillna("", inplace=True)
    df = df[df["書籍タイトル"] != ""]
    
    # タイトル -> 要約 の辞書
    summaries = {}
    for _, row in df.iterrows():
        t = row["書籍タイトル"]
        s = row["要約"]
        summaries[t] = s
    return summaries

# 2) ハイライトを読み込む (KindleHighlights.csv)
@st.cache_data
def load_highlights():
    df = pd.read_csv("docs/KindleHighlights.csv")
    df.fillna("", inplace=True)
    # 必要に応じて正規化などを適用
    highlights = []
    for _, row in df.iterrows():
        title = row["書籍タイトル"]
        author = row["著者"]
        content = row["ハイライト内容"]
        highlights.append({
            "title": title,
            "author": author,
            "content": content
        })
    return highlights

# 3) タイトル文字列の正規化関数 (Home.pyで使っているものと合わせる)
def normalize_japanese_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# 4) スタイルをインラインで定義する関数
def set_styles():
    """ページ全体のスタイルをインラインで設定する"""
    st.markdown("""
    <style>
    /* 全体の背景色など */
    body {
        background-color: #1E1E1E !important;
    }

    .css-18e3th9 {
        background-color: #1E1E1E !important;
    }

    .css-1cpxqw2 .e1fqkh3o3 {
        background-color: #1E1E1E !important;
    }

    /* --- 引用表示カード共通 --- */
    .quote-container {
        position: relative;
        margin: 1.5em 0;
        padding: 1.5em;
        border-radius: 8px;
        background: #2a2a2a;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }

    .quote-mark {
        position: absolute;
        top: -0.8em;
        left: 1em;
        color: #aaa;
        font-size: 2.5em;
    }

    .quote-text {
        margin: 0 0 1em 0;
        font-style: italic;
        color: #eee;
        line-height: 1.6;
    }

    .quote-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .quote-score {
        text-align: left;
        font-size: 0.9em;
        color: #ccc;
    }

    .quote-meta {
        text-align: right;
        font-size: 0.9em;
        color: #ccc;
    }

    /* ハイライト番号の表示 */
    .highlight-number {
        text-align: right;
        font-size: 0.85em;
        color: #888;
        margin-top: 0.5em;
    }
    </style>
    """, unsafe_allow_html=True)

# 5) 引用UIを実装（タイトルと著者を非表示に）
def display_quote(index, content):
    """
    引用表示UI - タイトルと著者を削除したバージョン
    """
    # HTMLエスケープ
    safe_content = html.escape(content)
    
    # HTMLを構築 - タイトルと著者の部分を削除
    quote_html = f"""
    <div class="quote-container">
        <div class="quote-mark">"</div>
        <p class="quote-text">{safe_content}</p>
        <div class="highlight-number">[{index}]</div>
    </div>
    """
    
    st.markdown(quote_html, unsafe_allow_html=True)

# 6) 書影を取得 (Google Books API等)
@st.cache_data
def fetch_cover_image(title: str, author: str = "") -> str:
    """
    タイトルと著者名を使ってGoogle Books APIを検索し、
    ISBNを取得してから書影画像のURLを返す。
    より正確な書影画像を取得するために、以下の手順で処理する：
    1. タイトルと著者名を使って検索
    2. 検索結果からISBNを取得
    3. ISBNを使って再検索し、書影画像のURLを取得
    """
    if not title.strip():
        return ""
    
    # 1. タイトルと著者名を使って検索
    query_parts = []
    if title:
        query_parts.append(f"intitle:{urllib.parse.quote(title)}")
    if author:
        query_parts.append(f"inauthor:{urllib.parse.quote(author)}")
    
    query = "+".join(query_parts)
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=5"
    
    try:
        resp = requests.get(url)
        if resp.status_code != 200:
            return ""
        
        data = resp.json()
        items = data.get("items", [])
        if not items:
            # 検索結果がない場合は、タイトルのみで検索
            fallback_query = urllib.parse.quote(title)
            fallback_url = f"https://www.googleapis.com/books/v1/volumes?q={fallback_query}&maxResults=1"
            resp = requests.get(fallback_url)
            if resp.status_code != 200:
                return ""
            
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return ""
        
        # 2. 検索結果からISBNを取得
        isbn = None
        for item in items:
            volume_info = item.get("volumeInfo", {})
            industry_identifiers = volume_info.get("industryIdentifiers", [])
            
            # ISBNを探す
            for identifier in industry_identifiers:
                if identifier.get("type") in ["ISBN_13", "ISBN_10"]:
                    isbn = identifier.get("identifier")
                    break
            
            if isbn:
                break
        
        # ISBNが見つかった場合は、ISBNで再検索
        if isbn:
            isbn_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
            isbn_resp = requests.get(isbn_url)
            if isbn_resp.status_code == 200:
                isbn_data = isbn_resp.json()
                isbn_items = isbn_data.get("items", [])
                if isbn_items:
                    volume_info = isbn_items[0].get("volumeInfo", {})
                    image_links = volume_info.get("imageLinks", {})
                    return image_links.get("thumbnail", "")
        
        # ISBNが見つからなかった場合や、ISBNでの再検索に失敗した場合は、
        # 最初の検索結果から書影画像のURLを返す
        volume_info = items[0].get("volumeInfo", {})
        image_links = volume_info.get("imageLinks", {})
        return image_links.get("thumbnail", "")
    
    except Exception as e:
        print(f"Error fetching cover image: {e}")
        return ""

# =============================================================================
# 7) ユーザー固有のハイライトを読み込む関数
# =============================================================================
@st.cache_data
def load_user_highlights(user_id):
    """ユーザー固有のハイライトを読み込む（データベースから取得、フォールバックとしてCSVを使用）"""
    try:
        # データベースからデータを取得
        db = SessionLocal()
        try:
            # Google IDからユーザーを検索
            db_user = db_access.get_user_by_google_id(db, user_id)
            
            if db_user:
                # データベースからユーザーのハイライトを取得
                highlights = []
                
                # ユーザーの全ハイライトを取得
                db_highlights = db_access.get_all_highlights_for_user(db, db_user.id)
                
                for h in db_highlights:
                    # 書籍情報を取得
                    book = db.query(Book).filter(Book.id == h.book_id).first()
                    if book:
                        highlights.append({
                            "title": book.title,
                            "author": book.author,
                            "content": h.content
                        })
                
                # データが取得できた場合はそれを返す
                if highlights:
                    return highlights
        finally:
            db.close()
        
        # データベースにデータがない場合はCSVファイルを確認
        user_highlights_path = auth.USER_DATA_DIR / "docs" / user_id / "KindleHighlights.csv"
        
        # ユーザー固有のハイライトファイルが存在しない場合は共通のファイルを使用
        if not user_highlights_path.exists():
            return load_highlights()
        
        df = pd.read_csv(user_highlights_path)
        df.fillna("", inplace=True)
        
        highlights = []
        for _, row in df.iterrows():
            title = row["書籍タイトル"]
            author = row["著者"]
            content = row["ハイライト内容"]
            highlights.append({
                "title": title,
                "author": author,
                "content": content
            })
        return highlights
    except Exception as e:
        st.error(f"ハイライト読み込み中にエラーが発生しました: {str(e)}")
        # エラーが発生した場合は共通のファイルを使用
        return load_highlights()

# =============================================================================
# 8) ユーザー固有の書籍要約を読み込む関数
# =============================================================================
@st.cache_data
def load_user_book_summaries(user_id):
    """ユーザー固有の書籍要約を読み込む（データベースから取得、フォールバックとしてCSVを使用）"""
    try:
        # データベースからデータを取得
        db = SessionLocal()
        try:
            # Google IDからユーザーを検索
            db_user = db_access.get_user_by_google_id(db, user_id)
            
            if db_user:
                # データベースからユーザーの書籍とハイライトを取得
                books = db_access.get_books_for_user(db, db_user.id)
                
                # 辞書形式で返す
                result = {}
                for book in books:
                    # 書籍に関連するハイライトを取得
                    highlights = db_access.get_highlights_for_book(db, db_user.id, book.id)
                    
                    if highlights:
                        # 最初の5つのハイライトを要約として使用
                        highlight_texts = [h.content for h in highlights[:5]]
                        result[book.title] = "\n\n".join(highlight_texts) + "\n\n(※AIによる要約は生成されていません。ハイライトアップロードページでサマリを生成してください。)"
                
                # データが取得できた場合はそれを返す
                if result:
                    return result
        finally:
            db.close()
        
        # データベースにデータがない場合はCSVファイルを確認
        user_summaries_path = auth.USER_DATA_DIR / "docs" / user_id / "BookSummaries.csv"
        
        # ユーザー固有のサマリーファイルが存在する場合はそれを使用
        if user_summaries_path.exists():
            df = pd.read_csv(user_summaries_path)
        else:
            # ユーザー固有のハイライトからサマリーを生成
            user_highlights_path = auth.USER_DATA_DIR / "docs" / user_id / "KindleHighlights.csv"
            if user_highlights_path.exists():
                # ハイライトからサマリーを生成
                df = pd.read_csv(user_highlights_path)
                
                # 書籍ごとにハイライトをグループ化
                grouped = df.groupby(["書籍タイトル", "著者"])
                
                # 辞書形式で返す
                result = {}
                for (title, _), group in grouped:
                    # 最初の5つのハイライトを要約として使用
                    highlights = group["ハイライト内容"].tolist()[:5]
                    result[title] = "\n\n".join(highlights) + "\n\n(※AIによる要約は生成されていません。ハイライトアップロードページでサマリを生成してください。)"
                
                return result
            else:
                # ユーザー固有のデータがない場合は共通のファイルを使用
                return load_book_summaries()
        
        # DataFrameから辞書に変換
        df["書籍タイトル"].fillna("", inplace=True)
        df["要約"].fillna("", inplace=True)
        df = df[df["書籍タイトル"] != ""]
        
        # タイトル -> 要約 の辞書
        summaries = {}
        for _, row in df.iterrows():
            t = row["書籍タイトル"]
            s = row["要約"]
            summaries[t] = s
        
        return summaries
    except Exception as e:
        st.error(f"書籍要約読み込み中にエラーが発生しました: {str(e)}")
        # エラーが発生した場合は共通のファイルを使用
        return load_book_summaries()

# -----------------------
# 9) ページを表示
# -----------------------
def main():
    # ページタイトル
    st.title("書籍詳細ページ")
    
    # クエリパラメータから書籍タイトルを取得
    query_params = st.query_params
    
    # クエリパラメータから書籍タイトルを取得
    if "title" in query_params:
        book_title = query_params["title"][0]
        # デバッグ情報
        st.write(f"クエリパラメータから取得した書籍タイトル: {book_title}")
    elif "selected_book_title" in st.session_state:
        book_title = st.session_state.selected_book_title
        # デバッグ情報
        st.write(f"セッション状態から取得した書籍タイトル: {book_title}")
        # セッション状態をクリア（次回のために）
        del st.session_state.selected_book_title
    else:
        st.error("書籍タイトルが指定されていません。")
        st.markdown("[← 書籍一覧に戻る](pages/BookList.py)")
        st.stop()
    
    # ユーザー固有のデータを使用するかどうか
    if auth.is_user_authenticated():
        user_id = auth.get_current_user_id()
        summaries_dict = load_user_book_summaries(user_id)
        all_highlights = load_user_highlights(user_id)
        st.info(f"{st.session_state.user_info.get('name', 'ユーザー')}さんのハイライトデータを表示しています。")
    else:
        summaries_dict = load_book_summaries()
        all_highlights = load_highlights()
    
    # 書籍要約を取得
    book_summary = summaries_dict.get(book_title, "")
    
    # 該当書籍タイトルの正規化
    norm_target = normalize_japanese_text(book_title)
    
    # 書影取得（著者名も渡す）
    # 該当書籍の著者名を取得
    author = ""
    for hl in all_highlights:
        if normalize_japanese_text(hl["title"]) == norm_target:
            author = hl["author"]
            break
    
    cover_url = fetch_cover_image(book_title, author)
    
    # 表示レイアウト
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if cover_url:
            st.image(cover_url, width=120)
        else:
            st.markdown("""
            <div style="width:120px; height:180px; background-color:#333; 
                       display:flex; align-items:center; justify-content:center; 
                       border-radius:4px; color:#999; text-align:center;">
                表紙画像<br>なし
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.subheader(book_title)
        if book_summary.strip():
            st.write(book_summary)
        else:
            st.write("要約が登録されていません。")
    
    # 区切り線
    st.write("---")
    
    # ハイライト一覧
    st.write("## ハイライト一覧")
    
    # 該当書籍タイトルに一致するハイライトのみフィルタ
    norm_target = normalize_japanese_text(book_title)
    
    filtered = []
    for hl in all_highlights:
        # 正確に一致するタイトルのハイライトのみを表示
        if hl["title"] == book_title:
            filtered.append(hl)
    
    if not filtered:
        st.info("この書籍のハイライトは見つかりませんでした。")
    else:
        # ハイライト数を表示
        st.write(f"全 {len(filtered)} 件のハイライト")
        
        # ハイライトを表示 - タイトルと著者を削除
        for i, hl in enumerate(filtered, start=1):
            display_quote(i, hl["content"])
    
    # 戻るリンク
    st.markdown("[← 書籍一覧に戻る](pages/BookList.py)")

# エントリーポイント
if __name__ == "__main__":
    main()
