import streamlit as st
import pandas as pd
import math
import numpy as np
import unicodedata
import re
import os
import sys
import openai
import html
import urllib
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

from langchain.docstore.document import Document
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.prompts import PromptTemplate
from langchain.retrievers import BM25Retriever
from langchain.schema import SystemMessage, HumanMessage

# タグ入力UIライブラリ
from streamlit_tags import st_tags

# 親ディレクトリをパスに追加（Homeモジュールをインポートするため）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auth
from progress_display import display_summary_progress_in_sidebar

# Home.pyから共通関数をインポート
from Home import display_quote, load_highlights, local_css, normalize_japanese_text, load_book_info, load_user_highlights

# 環境変数のロード
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ページ設定
st.set_page_config(
    page_title="検索モード | Booklight AI", 
    page_icon="🔍",
    layout="centered",
    initial_sidebar_state="expanded"
)

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

# -------------------------------------------
# OpenAI Embeddings
# -------------------------------------------
embeddings_model = OpenAIEmbeddings(
    model="text-embedding-3-small"
)

# ユーザー固有のデータを使用するかどうか
if auth.is_user_authenticated():
    user_id = auth.get_current_user_id()
    # ユーザー固有の書籍情報を読み込み
    book_info = load_book_info(user_id)
    # ユーザー固有のハイライトを読み込み
    highlight_docs = load_user_highlights(user_id)
    st.info(f"{st.session_state.user_info.get('name', 'ユーザー')}さんのハイライトデータを使用して検索します。")
else:
    # 共通の書籍情報とハイライトを読み込み
    book_info = load_book_info()
    highlight_docs = load_highlights()

# BM25（ハイブリッド検索用）
bm25_highlight_retriever = BM25Retriever.from_documents(highlight_docs)

# -------------------------------------------
# ハイライトVectorStore
# -------------------------------------------
@st.cache_resource
def get_highlight_vectorstore(_docs):
    # ユーザー固有のベクトルストアを作成
    if auth.is_user_authenticated():
        user_id = auth.get_current_user_id()
        persist_dir = f"./csv_chroma_db/highlights_user_{user_id}"
    else:
        persist_dir = "./csv_chroma_db/highlights_v2"
    
    return Chroma.from_documents(
        documents=_docs,
        embedding=embeddings_model,
        persist_directory=persist_dir
    )

highlight_vs = get_highlight_vectorstore(highlight_docs)

# -------------------------------------------
# 書籍タイトル＆要約のEmbeddingsを管理
# -------------------------------------------
def cosine_sim(vec1, vec2):
    dot = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return float('nan')
    return dot / (norm1 * norm2)

@st.cache_resource
def embed_book_info(book_info_dict):
    res = {}
    for _, data in book_info_dict.items():
        t_text = data["normalized_title"]
        s_text = data["normalized_summary"]
        original_title = data["title_text"]
        if not t_text.strip() and not s_text.strip():
            continue
        title_emb = embeddings_model.embed_query(t_text)
        if s_text.strip():
            summary_emb = embeddings_model.embed_query(s_text)
        else:
            summary_emb = title_emb
        res[original_title] = (title_emb, summary_emb)
    return res

book_embeddings = embed_book_info(book_info)

def rank_books_by_title_and_summary(query: str, alpha=0.5, top_k=5):
    normalized_query = normalize_japanese_text(query)
    query_emb = embeddings_model.embed_query(normalized_query)
    scores = []
    for bk_title, (title_emb, summary_emb) in book_embeddings.items():
        t_score = cosine_sim(query_emb, title_emb)
        s_score = cosine_sim(query_emb, summary_emb)
        final_score = alpha * t_score + (1 - alpha) * s_score
        if math.isnan(final_score):
            final_score = float('-inf')
        scores.append((bk_title, final_score, t_score, s_score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]

# -------------------------------------------
# ハイブリッド検索 - ベクトル検索とBM25の組み合わせ
# -------------------------------------------
def hybrid_search(query, top_k=20, alpha=0.7):
    """
    Embedding検索とBM25検索を組み合わせたハイブリッド検索
    alpha: Embedding検索の重み（0～1）
    """
    normalized_query = normalize_japanese_text(query)
    
    # ベクトル検索の実行
    vector_results = highlight_vs.similarity_search_with_score(normalized_query, k=top_k)
    
    # BM25検索の実行
    bm25_results = bm25_highlight_retriever.get_relevant_documents(normalized_query)
    
    # 結果のマージと重み付け
    merged_results = {}
    
    # ベクトル検索結果の処理
    for doc, score in vector_results:
        doc_id = doc.page_content
        merged_results[doc_id] = {
            "doc": doc,
            "vector_score": score,
            "bm25_score": 0.0,
            "final_score": alpha * score
        }
    
    # BM25結果の処理
    for i, doc in enumerate(bm25_results[:top_k]):
        doc_id = doc.page_content
        # BM25のランクをスコアに変換（簡易的）
        bm25_score = 1.0 - (i / len(bm25_results[:top_k])) if bm25_results else 0.0
        
        if doc_id in merged_results:
            # 既存結果に加算
            merged_results[doc_id]["bm25_score"] = bm25_score
            merged_results[doc_id]["final_score"] += (1 - alpha) * bm25_score
        else:
            # 新規追加
            merged_results[doc_id] = {
                "doc": doc,
                "vector_score": 0.0,
                "bm25_score": bm25_score,
                "final_score": (1 - alpha) * bm25_score
            }
    
    # ソートして返却
    return sorted(
        [item for item in merged_results.values()], 
        key=lambda x: x["final_score"], 
        reverse=True
    )[:top_k]

# -------------------------------------------
# クエリ拡張 (LLM を用いた多様なクエリ生成)
# -------------------------------------------
def enhanced_query_expansion(query: str) -> dict:
    """
    シノニム拡張、クエリリフォーミュレーション等の追加
    """
    if not query.strip():
        return {"original": "", "synonyms": "", "reformulation": ""}
        
    system_msg = SystemMessage(content="You are a helpful assistant for search query enhancement in Japanese.")
    
    # 1. シノニム拡張
    synonym_prompt = f"""
以下の検索クエリに関連する類義語または関連用語を5つ、コンマ区切りで生成してください。
表記ゆれや送り仮名違い、カタカナ・漢字の違いも考慮してください。
クエリ: "{query}"

余計な説明は不要で、類義語のみ出力してください。
"""
    
    # 2. クエリリフォーミュレーション
    reformulation_prompt = f"""
以下の検索キーワードを、同じ意味を持つ別の言葉で表現してください。
キーワード: "{query}"

余計な説明は不要で、言い換えた表現のみを出力してください。
"""
    
    synonym_llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.0)
    
    try:
        synonym_result = synonym_llm([system_msg, HumanMessage(content=synonym_prompt)])
        reformulation_result = synonym_llm([system_msg, HumanMessage(content=reformulation_prompt)])
        
        synonyms = [s.strip() for s in synonym_result.content.split(",")]
        reformulation = reformulation_result.content.strip()
        
        return {
            "original": query,
            "synonyms": query + " " + " ".join(synonyms),
            "reformulation": reformulation
        }
    except Exception as e:
        st.error(f"クエリ拡張エラー: {str(e)}")
        return {"original": query, "synonyms": query, "reformulation": query}

# -------------------------------------------
# 複数検索結果のマージ
# -------------------------------------------
def merge_search_results(result_sets, weights=None):
    """
    複数の検索結果をマージし、重み付けしたスコアを算出する
    """
    if weights is None:
        weights = [1.0] * len(result_sets)
    
    if len(result_sets) != len(weights):
        raise ValueError("結果セットと重みの数が一致しません")
    
    merged = {}
    
    for i, results in enumerate(result_sets):
        weight = weights[i]
        for result in results:
            doc = result["doc"]
            doc_id = doc.page_content
            score = result["final_score"] * weight
            
            if doc_id in merged:
                merged[doc_id]["score"] += score
            else:
                merged[doc_id] = {
                    "doc": doc,
                    "score": score,
                    "sources": []
                }
            
            source_info = {
                "type": f"result_set_{i}",
                "score": score
            }
            merged[doc_id]["sources"].append(source_info)
    
    return sorted(merged.values(), key=lambda x: x["score"], reverse=True)

# 検索結果表示用の関数
def display_search_results(results, max_chars=300, show_feedback=True):
    """
    検索結果を表示
    """
    if not results:
        st.warning("関連するハイライトが見つかりませんでした。")
        return
    
    for i, result in enumerate(results, start=1):
        doc = result["doc"]
        score = result.get("score", None)
        
        # オリジナルのメタデータを優先的に使用
        title = doc.metadata.get("original_title", doc.metadata.get("title", "不明"))
        author = doc.metadata.get("original_author", doc.metadata.get("author", ""))
        content = doc.metadata.get("original_content", doc.page_content)
        
        # 長さ制限
        if len(content) > max_chars:
            display_content = content[:max_chars] + "..."
        else:
            display_content = content
        
        # 引用表示関数を使用
        display_quote(display_content, title, author)

# -------------------------------------------
# 検索モード (改善版)
# -------------------------------------------
def improved_search_mode(keywords: list, hybrid_alpha=0.7, book_weight=0.3, use_expanded=True):
    if not keywords:
        st.warning("キーワードが入力されていません。")
        return
    
    raw_query = " ".join(keywords)
    status = st.empty()
    status.info("検索準備中...")
    
    if use_expanded:
        expanded = enhanced_query_expansion(raw_query)
        st.markdown(f"**検索クエリ**: {raw_query}")
        with st.expander("クエリ拡張情報", expanded=False):
            st.markdown(f"**シノニム拡張**: {expanded['synonyms']}")
            st.markdown(f"**言い換えクエリ**: {expanded['reformulation']}")
    else:
        expanded = {"original": raw_query, "synonyms": raw_query, "reformulation": raw_query}
    
    status.info("ハイブリッド検索実行中...")
    results_original = hybrid_search(raw_query, top_k=10, alpha=hybrid_alpha)
    
    if use_expanded:
        results_synonyms = hybrid_search(expanded['synonyms'], top_k=10, alpha=hybrid_alpha)
        results_reformulation = hybrid_search(expanded['reformulation'], top_k=10, alpha=hybrid_alpha)
        
        status.info("検索結果マージ中...")
        merged_results = merge_search_results(
            [results_original, results_synonyms, results_reformulation],
            weights=[1.0, 0.8, 0.9]
        )
    else:
        merged_results = results_original
    
    status.info("書籍情報でリランキング中...")
    book_ranks = rank_books_by_title_and_summary(raw_query, alpha=0.5, top_k=20)
    book_scores = {title: score for title, score, _, _ in book_ranks}
    
    final_results = []
    for result in merged_results:
        doc = result["doc"]
        title = doc.metadata.get("title", "")
        
        # 正規化されたタイトルから元のタイトルを探す（簡易的）
        original_title = ""
        for k, v in book_info.items():
            if normalize_japanese_text(v["title_text"]) == title:
                original_title = v["title_text"]
                break
        
        book_score = book_scores.get(original_title, 0.0)
        final_score = result["score"] + (book_score * book_weight)
        
        final_results.append({
            "doc": doc,
            "score": final_score,
            "original_score": result["score"],
            "book_score": book_score
        })
    
    final_results.sort(key=lambda x: x["score"], reverse=True)
    
    with st.expander("検索詳細情報", expanded=False):
        st.write("#### 書籍スコア (タイトル & 要約)")
        for i, (bk_title, final_s, t_s, s_s) in enumerate(book_ranks[:5], start=1):
            disp_final = f"{final_s:.3f}" if final_s != float('-inf') else "nan"
            disp_t = f"{t_s:.3f}" if not math.isnan(t_s) else "nan"
            disp_s = f"{s_s:.3f}" if not math.isnan(s_s) else "nan"
            st.write(f"**[{i}]** {bk_title} : final={disp_final}, title={disp_t}, summary={disp_s}")
    
    status.empty()
    st.subheader("関連するハイライト一覧")
    
    if not final_results:
        st.warning("検索条件に一致するハイライトが見つかりませんでした。別のキーワードをお試しください。")
        return
    
    display_search_results(final_results[:15], show_feedback=False)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "query": raw_query,
        "expanded_query": expanded['synonyms'],
        "reformulated_query": expanded['reformulation'],
        "results_count": len(final_results)
    }
    with st.expander("検索ログ", expanded=False):
        st.json(log_entry)

# メインページのレイアウト
st.title("🔍 検索モード")
st.write("複数のキーワードを入力して検索できます。")

# デフォルト値を固定
hybrid_alpha = 0.7
book_weight = 0.3
use_expanded = True

# カスタムタグ入力UI
st.write("### 検索キーワード")

if 'search_tags' not in st.session_state:
    st.session_state.search_tags = []

# タグ追加のコールバック関数
def add_tag():
    if st.session_state.new_tag.strip() and st.session_state.new_tag not in st.session_state.search_tags:
        st.session_state.search_tags.append(st.session_state.new_tag)
        # 次回のレンダリング用にクリアフラグを設定
        st.session_state.clear_tag_input = True
        st.rerun()

def remove_tag(tag_to_remove):
    st.session_state.search_tags = [tag for tag in st.session_state.search_tags if tag != tag_to_remove]
    st.rerun()

def clear_all_tags():
    st.session_state.search_tags = []
    st.rerun()

# 入力フォームの初期化
if "new_tag" not in st.session_state:
    st.session_state.new_tag = ""

# クリアフラグの処理
if "clear_tag_input" in st.session_state and st.session_state.clear_tag_input:
    st.session_state.new_tag = ""
    st.session_state.clear_tag_input = False

col1, col2 = st.columns([3, 1])
with col1:
    st.text_input("キーワードを入力してEnterで追加", key="new_tag", on_change=add_tag)


if st.session_state.search_tags:
    st.write("##### 現在の検索キーワード:")
    tag_cols = st.columns(4)
    for i, tag in enumerate(st.session_state.search_tags):
        with tag_cols[i % 4]:
            st.button(f"× {tag}", key=f"del_{tag}", on_click=remove_tag, args=(tag,))
    
    if st.button("すべてクリア", key="clear_all"):
        clear_all_tags()

if st.button("検索する", key="search_button"):
    if st.session_state.search_tags:
        improved_search_mode(
            st.session_state.search_tags,
            hybrid_alpha=hybrid_alpha,
            book_weight=book_weight,
            use_expanded=use_expanded
        )
    else:
        st.warning("キーワードが入力されていません。")
