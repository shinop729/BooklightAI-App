import streamlit as st
import pandas as pd
import unicodedata
import re
import html
import os
import sys
import openai
import time
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

from langchain.docstore.document import Document
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.prompts import PromptTemplate
from langchain.schema import SystemMessage, HumanMessage, AIMessage

# 親ディレクトリをパスに追加（Homeモジュールをインポートするため）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auth

# Home.pyから共通関数をインポート
from Home import display_quote, load_highlights, normalize_japanese_text, load_user_highlights

# 環境変数のロード
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ページ設定
st.set_page_config(
    page_title="チャットモード | Booklight AI", 
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="expanded"
)

# CSSファイルを読み込む関数
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# チャット用カスタムCSS
def add_chat_css():
    st.markdown("""
    <style>
    /* メッセージ全体のスタイル */
    .chat-message {
        padding: 1rem;
        border-radius: 0.8rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }

    /* ユーザーメッセージ */
    .user-message {
        background-color: #2a75bb;
        border-top-right-radius: 0.2rem;
        align-self: flex-end;
        color: white;
    }

    /* AIメッセージ */
    .ai-message {
        background-color: #383838;
        border-top-left-radius: 0.2rem;
        align-self: flex-start;
    }

    /* メッセージコンテナ */
    .message-container {
        display: flex;
        flex-direction: column;
        max-width: 90%;
    }

    /* メッセージテキスト */
    .message-text {
        color: inherit;
        padding: 0;
        margin: 0;
    }

    /* 引用情報 */
    .source-info {
        margin-top: 0.8rem;
        padding-top: 0.8rem;
        border-top: 1px solid rgba(255, 255, 255, 0.2);
        font-size: 0.85rem;
        color: rgba(255, 255, 255, 0.7);
    }

    /* 引用リスト */
    .sources-list {
        margin-top: 0.5rem;
        padding-left: 1rem;
    }

    /* 入力エリア */
    .input-area {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        padding: 1rem;
        background-color: #1E1E1E;
        border-top: 1px solid #333;
        display: flex;
        gap: 0.5rem;
    }
    
    /* チャットコンテナに下部余白を追加 */
    .chat-container {
        margin-bottom: 5rem;
    }
    
    /* テキストエリアの高さ自動調整 */
    .stTextArea textarea {
        min-height: 100px !important;
    }
    
    /* 引用カードをチャット内に埋め込み */
    .chat-message .quote-container {
        margin: 0.5rem 0;
        background-color: rgba(255, 255, 255, 0.1);
    }
    
    /* チャット内の引用テキスト */
    .chat-message .quote-text {
        color: rgba(255, 255, 255, 0.9);
    }
    </style>
    """, unsafe_allow_html=True)

# 通常のCSSも読み込み
local_css("style.css")
# チャット用のCSSを追加
add_chat_css()

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

# 認証フローの処理
auth_success = auth.handle_auth_flow()
if auth_success:
    st.success("ログインに成功しました！")
    st.rerun()  # ページをリロード

# サイドバーに会話リセットボタンを配置
st.sidebar.markdown("### チャット設定")
if st.sidebar.button("会話をリセット"):
    for key in list(st.session_state.keys()):
        if key.startswith("chat_"):
            del st.session_state[key]
    st.rerun()

# 新規会話ボタン
if st.sidebar.button("新規会話を開始"):
    # 現在の会話IDを保存
    if "chat_history" in st.session_state:
        if "saved_chats" not in st.session_state:
            st.session_state.saved_chats = []
        # 会話に名前をつける（最初の質問を使用）
        if st.session_state.chat_history:
            first_question = st.session_state.chat_history[0]["content"]
            chat_name = first_question[:30] + "..." if len(first_question) > 30 else first_question
            st.session_state.saved_chats.append({
                "name": chat_name,
                "history": st.session_state.chat_history,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
    
    # 会話履歴をリセット
    for key in list(st.session_state.keys()):
        if key.startswith("chat_"):
            del st.session_state[key]
    st.rerun()

# 保存された会話一覧（あれば表示）
if "saved_chats" in st.session_state and st.session_state.saved_chats:
    st.sidebar.markdown("### 過去の会話")
    for i, chat in enumerate(st.session_state.saved_chats):
        chat_btn = st.sidebar.button(f"{chat['name']} ({chat['timestamp']})", key=f"saved_chat_{i}")
        if chat_btn:
            st.session_state.chat_history = chat["history"]
            st.rerun()

# -------------------------------------------
# ハイライトVectorStore
# -------------------------------------------
@st.cache_resource
def get_highlight_vectorstore():
    # OpenAI Embeddings
    embeddings_model = OpenAIEmbeddings(
        model="text-embedding-3-small"
    )
    
    # ユーザー固有のデータを使用するかどうか
    if auth.is_user_authenticated():
        user_id = auth.get_current_user_id()
        # ユーザー固有のハイライトを読み込み
        highlight_docs = load_user_highlights(user_id)
        # ユーザー固有のベクトルストアを作成
        persist_dir = f"./csv_chroma_db/highlights_user_{user_id}"
        st.info(f"{st.session_state.user_info.get('name', 'ユーザー')}さんのハイライトデータを使用してチャットします。")
    else:
        # 共通のハイライトを読み込み
        highlight_docs = load_highlights()
        persist_dir = "./csv_chroma_db/highlights_v2"
    
    return Chroma.from_documents(
        documents=highlight_docs,
        embedding=embeddings_model,
        persist_directory=persist_dir
    )

# 注意: この関数は内部でhighlight_docsを生成するため、
# 引数として渡す必要はありません
highlight_vs = get_highlight_vectorstore()

# -------------------------------------------
# チャットの表示
# -------------------------------------------
def display_chat_message(message, is_user=False):
    if is_user:
        st.markdown(f"""
        <div class="chat-message user-message">
            <div class="message-container">
                <p class="message-text">{message}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # AI応答のHTMLエスケープ
        safe_message = html.escape(message["content"])
        
        # 引用表示（もしあれば）
        sources_html = ""
        if "source_documents" in message:
            sources = message["source_documents"]
            if sources:
                sources_html = """<div class="source-info">参照した書籍:</div>
                <div class="sources-list">"""
                
                seen_titles = set()
                for doc in sources[:5]:  # 表示する引用は最大5つまで
                    title = doc.metadata.get("original_title", doc.metadata.get("title", "不明"))
                    # 重複排除
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    sources_html += f"<div>📚 {html.escape(title)}</div>"
                
                sources_html += "</div>"
        
        st.markdown(f"""
        <div class="chat-message ai-message">
            <div class="message-container">
                <p class="message-text">{safe_message}</p>
                {sources_html}
            </div>
        </div>
        """, unsafe_allow_html=True)

# -------------------------------------------
# 議論プロンプトテンプレート (改善版)
# -------------------------------------------
discussion_prompt_template = """
あなたは書籍のハイライト情報を参照できる文学アシスタントです。
ユーザーとの会話を通じて、読書体験や知識の深化をサポートします。

以下の書籍ハイライト情報を参考にして、質問に回答してください。
もしハイライト情報が質問に直接関連していない場合は、あなた自身の知識を活用して回答してください。

会話の履歴:
{chat_history}

書籍ハイライト情報:
{summaries}

【質問】
{question}

回答を作成してください。書籍の引用を使用した場合は、その事実を示してください。
ただし、回答は自然な会話の流れを保ち、学術的すぎる印象を与えないようにしてください。
"""

DISCUSSION_PROMPT = PromptTemplate(
    template=discussion_prompt_template,
    input_variables=["summaries", "question", "chat_history"]
)

# -------------------------------------------
# チャット処理関数
# -------------------------------------------
def process_chat(user_input):
    # チャット履歴の初期化
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # 入力が空なら処理しない
    if not user_input.strip():
        return
    
    # ユーザー入力を履歴に追加
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    
    # チャット履歴をLangChain形式に変換
    langchain_history = ""
    for msg in st.session_state.chat_history[:-1]:  # 最後のユーザー入力を除く
        role_prefix = "ユーザー: " if msg["role"] == "user" else "アシスタント: "
        langchain_history += f"{role_prefix}{msg['content']}\n\n"
    
    # 回答生成のプレースホルダー
    with st.spinner("回答を生成中..."):
        # LLM準備
        llm = ChatOpenAI(model="gpt-4-turbo", temperature=0.2)
        
        # 関連するハイライトを検索
        search_results = highlight_vs.similarity_search(user_input, k=8)
        
        # ハイライト情報をテキストに変換
        highlights_text = ""
        for i, doc in enumerate(search_results, 1):
            title = doc.metadata.get("original_title", "不明な書籍")
            author = doc.metadata.get("original_author", "")
            content = doc.metadata.get("original_content", doc.page_content)
            highlights_text += f"[{i}] 「{content}」（{title}, {author}）\n\n"
        
        # 回答を生成
        messages = [
            SystemMessage(content="あなたは書籍の知識をもとに会話するアシスタントです。"),
            HumanMessage(content=DISCUSSION_PROMPT.format(
                summaries=highlights_text,
                question=user_input,
                chat_history=langchain_history
            ))
        ]
        
        response = llm(messages)
        
        # AI応答を履歴に追加
        ai_response = {
            "role": "assistant", 
            "content": response.content,
            "source_documents": search_results
        }
        st.session_state.chat_history.append(ai_response)
        
        # 引用した特定のハイライトを表示
        if search_results:
            st.session_state.last_citations = search_results

# -------------------------------------------
# メインページのレイアウト
# -------------------------------------------
st.title("💬 チャットモード")
st.write("書籍のハイライトをもとにチャットで会話しましょう。質問や議論したいトピックを入力してください。")

# チャット履歴表示
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

if "chat_history" in st.session_state:
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            display_chat_message(message["content"], is_user=True)
        else:
            display_chat_message(message)

st.markdown('</div>', unsafe_allow_html=True)

# 送信ボタンのコールバック関数
def on_submit():
    if st.session_state.user_input.strip():
        # 入力内容をコピー
        current_input = st.session_state.user_input
        # チャット処理実行
        process_chat(current_input)
        # 入力欄をクリアするフラグを設定
        st.session_state.clear_input = True
        # 画面を更新して結果を表示
        st.rerun()

# 入力フォームの初期化
if "user_input" not in st.session_state:
    st.session_state.user_input = ""

# クリアフラグの初期化
if "clear_input" in st.session_state and st.session_state.clear_input:
    st.session_state.user_input = ""
    st.session_state.clear_input = False

# ユーザー入力フォーム（下部固定）
with st.container():
    st.markdown('<div style="height: 5rem;"></div>', unsafe_allow_html=True)  # スペース確保
    
    # 入力フォーム
    col1, col2 = st.columns([5, 1])
    
    with col1:
        user_input = st.text_area(
            "質問や議論したいトピックを入力",
            height=100,
            key="user_input",
            label_visibility="collapsed",
            placeholder="質問や議論したいトピックを入力..."
        )
    
    with col2:
        st.markdown('<div style="height: 0.5rem;"></div>', unsafe_allow_html=True)  # 位置調整
        submit = st.button("送信", on_click=on_submit, use_container_width=True)
    
    # Enterキーでの送信処理
    if user_input and user_input.endswith("\n"):
        on_submit()

# 引用の詳細表示（折りたたみセクション）
if "last_citations" in st.session_state and st.session_state.last_citations:
    with st.expander("参照した書籍ハイライト", expanded=False):
        st.write("直近の質問に対して参照したハイライト:")
        
        for i, doc in enumerate(st.session_state.last_citations, start=1):
            # オリジナルのメタデータを優先的に使用
            title = doc.metadata.get("original_title", doc.metadata.get("title", "不明"))
            author = doc.metadata.get("original_author", doc.metadata.get("author", ""))
            content = doc.metadata.get("original_content", doc.page_content)
            
        # 引用表示関数を使用 (ユニークなキーを生成)
        display_quote(content, title, author, f"chat_citation_{i}")
