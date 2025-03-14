import streamlit as st
import pandas as pd
import random
import os
import openai
import html
import urllib
from dotenv import load_dotenv

from langchain.docstore.document import Document

# デザイン関連のユーティリティ
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# アプリ全体の設定
def setup_app():
    # 環境変数のロード
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
    # ページ設定
    st.set_page_config(
        page_title="Booklight AI", 
        page_icon="📚", 
        layout="centered",
        initial_sidebar_state="expanded"
    )
    
    # CSSのロード
    local_css("style.css")
    
    # サイドバー設定
    st.sidebar.image("images/booklight_ai_banner.png", use_column_width=True)
    st.sidebar.title("Booklight AI")
    st.sidebar.markdown("📚 あなたの読書をAIが照らす")
    
    # 区切り線
    st.sidebar.markdown("---")

# 引用UIの表示
def display_quote(content, title, author):
    """
    引用カード表示UI - タイトルにリンクを追加し、クリック可能であることをわかりやすく
    """
    # HTMLエスケープ
    safe_content = html.escape(content)
    safe_title = html.escape(title)
    safe_author = html.escape(author)
    
    # URL用にタイトルをエンコード
    encoded_title = urllib.parse.quote(title)
    detail_link = f"BookDetail?title={encoded_title}"
    
    # 引用用のHTMLを生成
    quote_html = f"""
    <div class="random-quote-container">
        <div class="random-quote-mark">"</div>
        <p class="random-quote-text">{safe_content}</p>
        <div class="random-quote-footer">
            <a href="{detail_link}" style="text-decoration: none; color: inherit;">
                {safe_title} / {safe_author}
            </a>
        </div>
    </div>
    """
    
    st.markdown(quote_html, unsafe_allow_html=True)

# 日本語テキスト正規化
def normalize_japanese_text(text: str) -> str:
    """
    日本語テキストの正規化
    - 全角/半角の統一
    - 余分な空白除去
    - 小文字化 など
    """
    if not isinstance(text, str):
        return ""
    
    # 正規化処理（NFKC）
    text = unicodedata.normalize('NFKC', text)
    
    # 小文字化
    text = text.lower()
    
    # 余分な空白を削除
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

# ハイライトデータのロード（他のページからも呼び出せるように公開）
@st.cache_resource
def load_highlights():
    """
    docs/KindleHighlights.csv:
      - 書籍タイトル
      - 著者
      - ハイライト内容
    """
    df = pd.read_csv("docs/KindleHighlights.csv")
    docs = []
    for _, row in df.iterrows():
        # 正規化を適用
        normalized_highlight = normalize_japanese_text(row["ハイライト内容"])
        doc = Document(
            page_content=normalized_highlight,
            metadata={
                "title": normalize_japanese_text(row["書籍タイトル"]),
                "author": normalize_japanese_text(row["著者"]),
                "original_content": row["ハイライト内容"],  # 表示用に元の内容も保持
                "original_title": row["書籍タイトル"],      # 元のタイトルも保持
                "original_author": row["著者"]             # 元の著者名も保持
            }
        )
        docs.append(doc)
    return docs

# 書籍タイトル & 要約データ読み込み
@st.cache_resource
def load_book_info():
    """
    docs/BookSummaries.csv:
      - 書籍タイトル
      - 要約
    """
    df = pd.read_csv("docs/BookSummaries.csv")
    df["書籍タイトル"].fillna("", inplace=True)
    df["要約"].fillna("", inplace=True)
    df = df[df["書籍タイトル"] != ""]
    grouped = df.groupby("書籍タイトル")["要約"].agg(lambda x: "\n".join(x)).reset_index()

    book_info = {}
    for _, row in grouped.iterrows():
        t = row["書籍タイトル"]
        s = row["要約"]
        if not isinstance(s, str):
            s = ""
        # タイトルと要約を正規化
        normalized_title = normalize_japanese_text(t)
        normalized_summary = normalize_japanese_text(s)
        book_info[normalized_title] = {
            "title_text": t,  # 元のタイトルを保持
            "summary_text": s,  # 元の要約を保持
            "normalized_title": normalized_title,
            "normalized_summary": normalized_summary
        }
    return book_info

# メインページの表示
def main():
    # アプリ全体のセットアップ
    setup_app()
    
    # サイドバーナビゲーション
    st.sidebar.markdown("### ナビゲーション")
    pages = {
        "🏠 ホーム": "/",
        "🔍 検索モード": "Search",
        "💬 チャットモード": "Chat",
        "📚 書籍一覧": "BookList"
    }

    for page_name, page_url in pages.items():
        st.sidebar.page_link(page_url, label=page_name)
    
    # メインコンテンツ
    st.image("images/booklight_ai_banner.png", use_container_width=True)
    st.title("Booklight AI へようこそ！")
    st.markdown("""
    Booklight AIはあなたの読書ハイライトを管理し、知識の探索をお手伝いします。
    
    **サイドバーから以下の機能にアクセスできます：**
    - **🔍 検索モード**: ハイライトをキーワードで検索
    - **💬 チャットモード**: ハイライトに基づいた会話
    - **📚 書籍一覧**: 登録済みの書籍を閲覧
    """)
    
    # ランダムハイライト表示
    st.markdown("## 今日のランダムハイライト")
    highlight_docs = load_highlights()
    random_count = min(2, len(highlight_docs))
    if random_count == 0:
        st.write("ハイライトがありません。")
    else:
        random_docs = random.sample(highlight_docs, random_count)
        for doc in random_docs:
            # オリジナルのメタデータを優先的に使用
            title = doc.metadata.get("original_title", doc.metadata.get("title", "不明"))
            author = doc.metadata.get("original_author", doc.metadata.get("author", ""))
            content = doc.metadata.get("original_content", doc.page_content)
            
            # 長さ制限
            if len(content) > 300:
                display_content = content[:300] + "..."
            else:
                display_content = content
            
            # 引用表示関数を使用
            display_quote(display_content, title, author)

if __name__ == "__main__":
    main()