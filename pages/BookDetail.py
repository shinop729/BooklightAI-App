import streamlit as st
import pandas as pd
import requests
import urllib
import unicodedata
import re
import html
from typing import List

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
def fetch_cover_image(title: str) -> str:
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

# -----------------------
# 7) ページを表示
# -----------------------
def main():
    # ページタイトル
    st.title("書籍詳細ページ")
    
    # クエリパラメータからタイトルを取得
    params = st.query_params
    raw_title = params.get("title", "")  # 修正済み: リストではなく単一の値を取得
    
    if not raw_title:
        st.error("書籍タイトルが指定されていません (クエリパラメータなし)。")
        st.markdown("[← 書籍一覧に戻る](pages/BookList.py)")
        st.stop()
    
    # URLデコード
    book_title = urllib.parse.unquote(raw_title)
    
    # CSVから要約を取り出し
    summaries_dict = load_book_summaries()
    book_summary = summaries_dict.get(book_title, "")
    
    # 書影取得
    cover_url = fetch_cover_image(book_title)
    
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
    
    # 全ハイライトをロード
    all_highlights = load_highlights()
    
    # 該当書籍タイトルに一致するハイライトのみフィルタ
    norm_target = normalize_japanese_text(book_title)
    filtered = []
    for hl in all_highlights:
        if normalize_japanese_text(hl["title"]) == norm_target:
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
