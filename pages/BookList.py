import streamlit as st
import pandas as pd
import requests
import urllib
import os
import sys
from pathlib import Path

# 親ディレクトリをパスに追加（Homeモジュールをインポートするため）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auth
from progress_display import display_summary_progress_in_sidebar

# ページ設定
st.set_page_config(
    page_title="書籍一覧 | Booklight AI", 
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="expanded"
)

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

# =============================================================================
# 1. CSVから書籍データを読み込む関数
# =============================================================================
@st.cache_data
def load_book_data():
    """
    書籍データを読み込む（ユーザー固有のデータがあれば使用）
    """
    # ユーザーがログインしている場合は、ユーザー固有のデータを使用
    if auth.is_user_authenticated():
        user_id = auth.get_current_user_id()
        user_summaries_path = auth.USER_DATA_DIR / "docs" / user_id / "BookSummaries.csv"
        
        # ユーザー固有のファイルが存在する場合はそれを使用
        if user_summaries_path.exists():
            df = pd.read_csv(user_summaries_path)
        else:
            # ユーザー固有のハイライトからサマリーを生成
            user_highlights_path = auth.USER_DATA_DIR / "docs" / user_id / "KindleHighlights.csv"
            if user_highlights_path.exists():
                # ハイライトからサマリーを生成
                highlights_df = pd.read_csv(user_highlights_path)
                
                # 書籍ごとにハイライトをグループ化
                grouped = highlights_df.groupby(["書籍タイトル", "著者"]).agg(
                    ハイライト件数=("ハイライト内容", "count"),
                    要約=("ハイライト内容", lambda x: "\n\n".join(x.tolist()[:3]) + "\n\n(※AIによる要約は生成されていません。ハイライトアップロードページでサマリを生成してください。)")
                ).reset_index()
                
                df = grouped
            else:
                # ユーザー固有のデータがない場合は共通のファイルを使用
                df = pd.read_csv("docs/BookSummaries.csv")
    else:
        # ログインしていない場合は共通のファイルを使用
        df = pd.read_csv("docs/BookSummaries.csv")
    
    df.fillna("", inplace=True)
    # 空のタイトル行を除外
    df = df[df["書籍タイトル"] != ""]
    return df

# =============================================================================
# 2. Google Books API から書影URLを取得する関数
# =============================================================================
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
# 3. ページ描画ロジック（トップレベル）
# =============================================================================

# タイトル表示
st.title("書籍一覧ページ")

# CSVの書籍データを読み込み
df = load_book_data()

# デバッグ用: DataFrame表示 (必要なければコメントアウト)
# st.dataframe(df)

# CSV内の各行をループして表示
for index, row in df.iterrows():
    title = row["書籍タイトル"]
    summary = row["要約"]
    
    # 著者名を取得（存在する場合）
    author = row.get("著者", "")
    
    # 書影取得（著者名も渡す）
    cover_url = fetch_cover_image(title, author)
    
    # 横並びに表示
    col1, col2 = st.columns([1, 3])
    with col1:
        if cover_url:
            st.image(cover_url, width=80)
        else:
            st.write("No image")
    
    with col2:
        # タイトルを見出しとして表示
        st.subheader(title)
        
        # 要約が長い場合は100文字に切り詰め (お好みで調整)
        short_summary = summary[:100]
        if len(summary) > 100:
            short_summary += "..."
        
        # 要約を表示
        st.write(short_summary)
        
        # 書籍詳細ページへのリンクを作成
        if st.button(f"詳細を見る", key=f"detail_{index}"):
            # セッション状態に書籍タイトルを保存
            st.session_state.selected_book_title = title
            # BookDetailページにリダイレクト
            st.switch_page("pages/BookDetail.py")
    
    st.write("---")
