import streamlit as st
import pandas as pd
import requests
import urllib

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

# サイドバーナビゲーション
st.sidebar.markdown("### ナビゲーション")
pages = {
    "🏠 ホーム": "Home.py",
    "🔍 検索モード": "pages/Search.py",
    "💬 チャットモード": "pages/Chat.py",
    "📚 書籍一覧": "pages/BookList.py"
}

for page_name, page_url in pages.items():
    st.sidebar.page_link(page_url, label=page_name)

# =============================================================================
# 1. CSVから書籍データを読み込む関数
# =============================================================================
@st.cache_data
def load_book_data():
    """
    docs/BookSummaries.csv を読み込み、「書籍タイトル」「要約」列を保持した DataFrame を返す。
    """
    df = pd.read_csv("docs/BookSummaries.csv")
    df.fillna("", inplace=True)
    # 空のタイトル行を除外
    df = df[df["書籍タイトル"] != ""]
    return df

# =============================================================================
# 2. Google Books API から書影URLを取得する関数
# =============================================================================
@st.cache_data
def fetch_cover_image(title: str) -> str:
    """
    タイトル文字列をGoogle Books APIで検索し、最初にヒットした書影URLを返す。
    """
    if not title.strip():
        return ""
    query = urllib.parse.quote(title)
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=1"
    
    resp = requests.get(url)
    if resp.status_code != 200:
        return ""
    
    data = resp.json()
    items = data.get("items", [])
    if not items:
        return ""
    
    volume_info = items[0].get("volumeInfo", {})
    image_links = volume_info.get("imageLinks", {})
    return image_links.get("thumbnail", "")

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
    
    # 書影取得
    cover_url = fetch_cover_image(title)
    
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
        # ※ ここで "<...>" で囲むと、カッコやスペースが含まれても途切れにくい
        encoded_title = urllib.parse.quote(title)
        link_url = f"pages/BookDetail.py?title={encoded_title}"
        
        # Markdown記法で山カッコ付きリンク
        st.markdown(f"[詳細を見る](<{link_url}>)")
    
    st.write("---")
