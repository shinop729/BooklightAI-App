"""
RAG (Retrieval-Augmented Generation) モジュール

このモジュールは、ユーザーの質問に対して関連するハイライトを検索し、
それらを使用してOpenAI APIで回答を生成する機能を提供します。
"""
import os
import logging
import time
import pickle
from typing import List, Dict, Any, Optional, Tuple
import json
import re
import asyncio
import traceback
import subprocess
import random
from datetime import datetime

# LangChain components
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None # Define faiss as None if not available

from openai import OpenAI
from langchain.vectorstores import Chroma, FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor

# Database and App specific imports
from sqlalchemy.orm import Session
from sqlalchemy import or_ # or_ をインポート
import database.models as models
from app.config import settings
# Updated import to use the new function name
from app.utils.query_processing import extract_and_expand_keywords

# ロギング設定
logger = logging.getLogger("booklight-api")

class RAGService:
    """
    RAG (Retrieval-Augmented Generation) サービス

    ユーザーの質問に対して関連するハイライトを検索し、
    それらを使用してOpenAI APIで回答を生成するサービスです。
    """

    def __init__(self, db: Session, user_id: int):
        """
        RAGServiceの初期化

        Args:
            db: データベースセッション
            user_id: ユーザーID
        """
        self.db = db
        self.user_id = user_id
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.2,
            streaming=True,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # OpenAIクライアントを初期化（共通で使用）
        # --- デバッグログ追加 ---
        if not settings.OPENAI_API_KEY:
            logger.warning("RAGService Init: OPENAI_API_KEY is empty before client initialization.")
        else:
            logger.debug(f"RAGService Init: Initializing OpenAI client with key starting with: {settings.OPENAI_API_KEY[:5]}...")
        # --- デバッグログ追加ここまで ---
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # ベクトルストアの初期化
        self.vector_store = None
        self.initialize_vector_store()

    def initialize_vector_store(self):
        """ベクトルストアを初期化する（最適化版）"""
        global FAISS_AVAILABLE, faiss # Allow modification of global variable
        try:
            # 既存のベクトルストアを検出して読み込む
            vector_dir = f"./api/user_data/vector_db/{self.user_id}"
            faiss_index_path = os.path.join(vector_dir, "faiss_index")

            if os.path.exists(faiss_index_path):
                try:
                    # 既存のインデックスを読み込む
                    logger.info(f"既存のFAISSベクトルストアを読み込みます: {faiss_index_path}")
                    start_time = time.time()
                    # Added allow_dangerous_deserialization=True
                    self.vector_store = FAISS.load_local(
                        faiss_index_path,
                        self.embeddings,
                        allow_dangerous_deserialization=True
                    )
                    load_time = time.time() - start_time

                    logger.info(f"FAISSベクトルストアの読み込みが完了しました（{load_time:.2f}秒）")
                    return
                except Exception as load_error:
                    logger.warning(f"既存のベクトルストアの読み込みに失敗しました: {load_error}")
                    logger.info("新しいベクトルストアを作成します")

            # 既存のベクトルストアがない場合は新規作成
            # ユーザーのハイライトを取得
            highlights = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id
            ).all()

            # ハイライト数をログに出力
            logger.info(f"ユーザーID {self.user_id} のハイライト数: {len(highlights)}")

            if not highlights:
                logger.warning(f"ユーザーID {self.user_id} のハイライトが見つかりません")
                # ハイライトがない場合は空のベクトルストアを作成
                self.vector_store = None
                return

            # ハイライト数が少ない場合は警告を出力
            if len(highlights) < 5:
                logger.warning(f"ユーザーID {self.user_id} のハイライト数が少なすぎます: {len(highlights)}件")

            # 埋め込みキャッシュの取得
            highlight_embeddings = {}
            cached_highlights = self.db.query(models.HighlightEmbedding).filter(
                models.HighlightEmbedding.highlight_id.in_([h.id for h in highlights])
            ).all()

            for cache in cached_highlights:
                try:
                    highlight_embeddings[cache.highlight_id] = pickle.loads(cache.embedding)
                except Exception as e:
                    logger.warning(f"埋め込みキャッシュの読み込みエラー (ハイライトID: {cache.highlight_id}): {e}")

            logger.info(f"埋め込みキャッシュ: {len(highlight_embeddings)}/{len(highlights)}件")

            # ハイライトをドキュメントに変換
            documents = []
            text_embeddings = []

            for highlight in highlights:
                try:
                    # 書籍情報を取得
                    book = self.db.query(models.Book).filter(
                        models.Book.id == highlight.book_id
                    ).first()

                    if not book:
                        logger.warning(f"書籍ID {highlight.book_id} が見つかりません")
                        continue

                    # ハイライト内容のバリデーション
                    if not highlight.content or len(highlight.content.strip()) == 0:
                        logger.warning(f"ハイライトID {highlight.id} の内容が空です")
                        continue

                    # メタデータを作成
                    metadata = {
                        "book_id": str(book.id),
                        "title": book.title,
                        "author": book.author,
                        "location": highlight.location or "",
                        "highlight_id": str(highlight.id)
                    }

                    # ドキュメントを作成
                    doc = Document(
                        page_content=highlight.content,
                        metadata=metadata
                    )
                    documents.append(doc)

                    # キャッシュされた埋め込みがあれば使用
                    if highlight.id in highlight_embeddings:
                        text_embeddings.append((highlight.content, highlight_embeddings[highlight.id]))

                except Exception as doc_error:
                    # 個別のドキュメント作成エラーをスキップ
                    logger.error(f"ドキュメント作成エラー (ハイライトID: {highlight.id}): {doc_error}")
                    continue

            # ドキュメントが存在する場合のみベクトルストアを作成
            if documents:
                try:
                    # 最初からFAISSベクトルストアを使用する（Chromaの問題を回避）
                    logger.info("FAISSベクトルストアを使用します")

                    # FAISS利用可能かチェック
                    if not FAISS_AVAILABLE:
                         logger.warning("FAISSがインストールされていません。インストールを試みます。")
                         subprocess.check_call(["pip", "install", "faiss-cpu", "--no-cache-dir"])
                         # Attempt to re-import faiss after installation
                         try:
                             import faiss # Re-assign to the global variable
                             FAISS_AVAILABLE = True
                             logger.info(f"FAISSのインストールが完了しました: {faiss.__version__}")
                         except ImportError:
                              logger.error("FAISSのインストール後もインポートできませんでした。")
                              raise RuntimeError("FAISS is required but could not be installed or imported.")
                    else:
                         logger.info(f"FAISS利用可能: {faiss.__version__}")

                    # キャッシュされた埋め込みがあれば使用
                    if text_embeddings:
                        logger.info(f"キャッシュされた埋め込みを使用: {len(text_embeddings)}件")
                        self.vector_store = FAISS.from_embeddings(
                            text_embeddings=text_embeddings,
                            embedding=self.embeddings,
                            metadatas=[doc.metadata for doc in documents[:len(text_embeddings)]]
                        )

                        # キャッシュされていないドキュメントがあれば追加
                        remaining_docs = documents[len(text_embeddings):]
                        if remaining_docs:
                            logger.info(f"残りのドキュメントを追加: {len(remaining_docs)}件")
                            self.vector_store.add_documents(remaining_docs)
                    else:
                        # 全てのドキュメントから新規作成
                        logger.info(f"全てのドキュメントから新規作成: {len(documents)}件")
                        self.vector_store = FAISS.from_documents(
                            documents=documents,
                            embedding=self.embeddings
                        )

                    logger.info(f"FAISSベクトルストアを作成しました（{len(documents)}件のハイライト）")

                    # ベクトルストアの保存
                    try:
                        os.makedirs(vector_dir, exist_ok=True)

                        # 保存パスを作成
                        save_path = os.path.join(vector_dir, "faiss_index")
                        self.vector_store.save_local(save_path)
                        logger.info(f"FAISSベクトルストアを保存しました: {save_path}")

                        # 最適化を実行
                        self.optimize_vector_store()
                    except Exception as save_error:
                        logger.warning(f"FAISSベクトルストアの保存に失敗しました: {save_error}")
                        # 保存に失敗してもインメモリのベクトルストアは使用可能なので続行

                except Exception as vs_error:
                    logger.error(f"FAISSベクトルストア作成エラー: {vs_error}")
                    logger.error(f"詳細エラー: {traceback.format_exc()}")

                    # 最後の手段として簡易的なインメモリベクトルストアを作成
                    try:
                        logger.info("簡易的なインメモリベクトルストアを作成します")

                        # 簡易的なベクトルストアクラスを定義
                        class SimpleVectorStore:
                            def __init__(self, documents):
                                self.documents = documents

                            def similarity_search_with_score(self, query, k=30):
                                # 単純なキーワードマッチング
                                results = []
                                for doc in self.documents:
                                    if any(keyword.lower() in doc.page_content.lower() for keyword in query.split()):
                                        results.append((doc, 0.5))  # ダミースコア

                                # 結果がない場合はランダムに選択
                                if not results and self.documents:
                                    sample_size = min(k, len(self.documents))
                                    results = [(doc, 0.1) for doc in random.sample(self.documents, sample_size)]

                                return results[:k]

                            def as_retriever(self, search_type=None, search_kwargs=None):
                                return SimpleRetriever(self)

                        class SimpleRetriever:
                            def __init__(self, vector_store):
                                self.vector_store = vector_store

                            def get_relevant_documents(self, query):
                                results = self.vector_store.similarity_search_with_score(query, k=30)
                                return [doc for doc, _ in results]

                            def _get_relevant_documents(self, query):
                                return self.get_relevant_documents(query)

                        self.vector_store = SimpleVectorStore(documents)
                        logger.info("簡易的なインメモリベクトルストアを作成しました")

                    except Exception as simple_error:
                        logger.error(f"簡易的なベクトルストア作成エラー: {simple_error}")
                        logger.error(f"詳細エラー: {traceback.format_exc()}")
                        self.vector_store = None
            else:
                logger.warning("有効なドキュメントがないため、ベクトルストアを作成しません")
                self.vector_store = None

        except Exception as e:
            logger.error(f"ベクトルストアの初期化エラー: {e}")
            logger.error(f"詳細エラー: {traceback.format_exc()}")

            # OpenAI APIキーの有効性を確認
            try:
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Test"}],
                    max_tokens=5
                )
                logger.info(f"OpenAI APIキーは有効です: {response.model}")
            except Exception as api_error:
                logger.error(f"OpenAI APIキーエラー: {api_error}")
                logger.error(f"詳細エラー: {traceback.format_exc()}")

            # 初期化エラー時はNoneを設定
            self.vector_store = None

    def get_relevant_highlights(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        クエリに関連するハイライトを取得する

        Args:
            query: 検索クエリ
            k: 取得するハイライトの数

        Returns:
            関連するハイライトのリスト
        """
        if not self.vector_store:
            logger.warning("ベクトルストアが初期化されていません")
            return []

        try:
            # 類似度検索を実行
            docs_with_scores = self.vector_store.similarity_search_with_score(query, k=k)

            # 結果を整形
            results = []
            for doc, score in docs_with_scores:
                result = {
                    "content": doc.page_content,
                    "book_id": doc.metadata.get("book_id", ""),
                    "title": doc.metadata.get("title", ""),
                    "author": doc.metadata.get("author", ""),
                    "location": doc.metadata.get("location", ""),
                    "score": float(score)
                }
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"ハイライト検索エラー: {e}")
            return []

    def optimize_vector_store(self):
        """ベクトルストアの最適化を実行"""
        if not self.vector_store:
            logger.warning("ベクトルストアが初期化されていないため最適化できません")
            return False

        try:
            # ベクトルストアの種類を確認
            if hasattr(self.vector_store, 'optimize'):
                # FAISSなどの最適化可能なベクトルストア
                self.vector_store.optimize()
                logger.info("ベクトルストアの最適化が完了しました")
                return True
            else:
                # 最適化メソッドがない場合はインデックスの再構築
                # 例: FAISS用の再構築処理
                if hasattr(self.vector_store, 'index') and hasattr(self.vector_store, 'docstore'):
                    try: # tryブロックを開始
                        # インデックスとドキュメントストアを再構築

                        # 既存のドキュメントとベクトルを取得
                        docs = list(self.vector_store.docstore.values())
                        vectors = [self.vector_store.index.reconstruct(i) for i in range(len(docs))]

                        # 新しいインデックスを作成
                        new_vs = FAISS.from_embeddings(
                            text_embeddings=list(zip([doc.page_content for doc in docs], vectors)),
                            embedding=self.embeddings,
                            metadatas=[doc.metadata for doc in docs]
                        )

                        # 新しいベクトルストアを使用
                        self.vector_store = new_vs

                        # 保存
                        vector_dir = f"./api/user_data/vector_db/{self.user_id}"
                        os.makedirs(vector_dir, exist_ok=True)
                        new_vs.save_local(os.path.join(vector_dir, "faiss_index"))

                        logger.info("ベクトルストアを再構築しました")
                        return True
                    except Exception as reindex_error: # exceptブロックをtryに対応させる
                        logger.error(f"FAISS再構築中のエラー: {reindex_error}")
                        # logger.error(f"詳細: {traceback.format_exc()}") # 詳細ログはデバッグ時に有効化
                        return False # Indicate optimization failed
                # if hasattr の終わり

            logger.info("ベクトルストアは最適化/再構築の対象外です。")
            return False # Return False if no optimization was performed
        except Exception as e: # optimize_vector_store 全体の except
            logger.error(f"ベクトルストア最適化エラー: {e}")
            # logger.error(f"詳細: {traceback.format_exc()}") # 詳細ログはデバッグ時に有効化
            return False

    async def get_relevant_highlights_async(self, query: str, k: int = 30, hybrid_alpha: float = 0.5,
                                           book_weight: float = 0.2, use_expanded: bool = False) -> List[Dict[str, Any]]:
        """
        キーワード検索優先アプローチを用いた非同期検索

        1. 抽出されたキーワードでDBを直接検索
        2. 不足分をベクトル検索で補完
        """
        search_start_time = time.time()
        search_id = f"search_{int(search_start_time * 1000)}"
        k_total = k # 最終的に取得する総数
        k_keyword_target = 5 # キーワード検索で優先的に確保する数

        logger.info(f"キーワード優先検索開始 [ID:{search_id}]: '{query}' (k_total={k_total}, k_keyword_target={k_keyword_target})")

        # 0. ベクトルストアのチェック
        if not self.vector_store:
            logger.warning(f"[ID:{search_id}] ベクトルストアが初期化されていません")
            # ベクトルストアがない場合でもキーワード検索は試みる
            # return [] # ここで早期リターンしない

        # 1. キーワード抽出と拡張 (新しい関数を使用)
        try:
            # Use the new function to get expanded keywords
            expanded_keywords = await extract_and_expand_keywords(query)
            if not expanded_keywords:
                logger.warning(f"[ID:{search_id}] キーワード抽出・拡張に失敗: '{query}'。元のクエリを分割して使用します。")
                search_keywords = query.split() # Fallback to splitting the original query
            else:
                search_keywords = expanded_keywords # Use the expanded list
                logger.info(f"[ID:{search_id}] 抽出・拡張されたキーワード: {search_keywords}")
        except Exception as e:
            logger.error(f"[ID:{search_id}] キーワード抽出・拡張中にエラー: {e}")
            search_keywords = query.split() # Fallback on error

        # 2. キーワード検索の実行 (DB直接検索 - 拡張されたキーワードを使用)
        keyword_matches_highlights = []
        keyword_match_ids = set()
        if search_keywords:
            try:
                # 各キーワードでilike検索を実行し、結果を結合
                keyword_query_filters = [
                    models.Highlight.content.ilike(f"%{kw}%") for kw in search_keywords
                ]
                # ユーザーIDでのフィルタリングも追加
                keyword_matches_highlights = self.db.query(models.Highlight).filter(
                    models.Highlight.user_id == self.user_id,
                    or_(*keyword_query_filters) # いずれかのキーワードに一致
                ).limit(k_total).all() # 多めに取得しておく

                keyword_match_ids = {h.id for h in keyword_matches_highlights}
                logger.info(f"[ID:{search_id}] キーワード検索結果: {len(keyword_matches_highlights)}件 (キーワード: {search_keywords})")

            except Exception as db_error:
                logger.error(f"[ID:{search_id}] キーワードDB検索エラー: {db_error}")
                # DB検索エラーが発生してもベクトル検索は試みる

        # --- キーワード検索結果が十分かチェック ---
        if len(keyword_matches_highlights) >= k_total:
            logger.info(f"[ID:{search_id}] キーワード検索で十分な結果 ({len(keyword_matches_highlights)}件 >= {k_total}件) が得られたため、ベクトル検索をスキップします。")
            # キーワード検索結果のみを整形して返す
            keyword_results_formatted = []
            for highlight in keyword_matches_highlights[:k_total]: # k_total件に制限
                 book = self.db.query(models.Book).filter(models.Book.id == highlight.book_id).first()
                 keyword_results_formatted.append({
                     "content": highlight.content,
                     "book_id": highlight.book_id,
                     "title": book.title if book else "不明",
                     "author": book.author if book else "不明",
                     "location": highlight.location or "",
                     "highlight_id": highlight.id,
                     "score": 1.0 # キーワード一致スコア
                 })
            # ログ出力 (任意)
            logger.info(f"[ID:{search_id}] キーワード検索のみの結果 (上位{len(keyword_results_formatted)}件) を返します。")
            search_time = time.time() - search_start_time
            logger.info(f"[ID:{search_id}] キーワード優先検索完了 (キーワードのみ): {len(keyword_results_formatted)}件 ({search_time:.2f}秒)")
            return keyword_results_formatted # 整形したキーワード検索結果を返す
        else:
            # キーワード検索結果が k_total 未満の場合、従来のロジックを実行
            logger.info(f"[ID:{search_id}] キーワード検索結果が不十分 ({len(keyword_matches_highlights)}件 < {k_total}件) なため、ベクトル検索で補完します。")
            # 3. キーワード検索結果を整形し、優先的に確保
            final_results = []
            keyword_results_formatted = []
            if keyword_matches_highlights:
                # 書籍情報を取得してフォーマット
                for highlight in keyword_matches_highlights:
                     book = self.db.query(models.Book).filter(models.Book.id == highlight.book_id).first()
                     keyword_results_formatted.append({
                         "content": highlight.content,
                         "book_id": highlight.book_id,
                         "title": book.title if book else "不明",
                         "author": book.author if book else "不明",
                         "location": highlight.location or "",
                         "highlight_id": highlight.id,
                          "score": 1.0 # キーワード一致は最高スコアとする (仮)
                      })

                # --- ここにログ出力を追加 ---
                logger.info(f"[ID:{search_id}] キーワード検索でヒットしたハイライト内容 (整形後, 最大{len(keyword_results_formatted)}件):")
                for i, res in enumerate(keyword_results_formatted):
                     # 内容が長い場合があるので、最初の100文字程度を表示
                     content_preview = res.get('content', '')[:100] + ('...' if len(res.get('content', '')) > 100 else '')
                     logger.info(f"  {i+1}. ID: {res.get('highlight_id')}, Score: {res.get('score')}, Content: '{content_preview}'")
                # --- ログ出力追加ここまで ---

                # 確保する数を決定
                num_to_keep = min(len(keyword_results_formatted), k_keyword_target)
                final_results.extend(keyword_results_formatted[:num_to_keep])
                logger.info(f"[ID:{search_id}] キーワード検索から {len(final_results)}件 を優先確保")

            # 4. 不足分の計算
            k_needed = k_total - len(final_results)
            logger.info(f"[ID:{search_id}] ベクトル検索で必要な追加件数: {k_needed}")

            # 5. ベクトル検索の実行 (補完)
            vector_results_formatted = []
            if k_needed > 0 and self.vector_store:
                try:
                    # ベクトル検索を実行 (キーワード検索で見つかったものは除く必要があるため、多めに取得)
                    # k_vector = k_needed + len(keyword_match_ids) # 除外分を見越して多めに取得
                    k_vector = k_total # シンプルにk_total取得して後でフィルタリング
                    logger.info(f"[ID:{search_id}] ベクトル検索実行 (k={k_vector}, query='{query}')") # 元のクエリでベクトル検索

                    # _search_with_params を呼び出してベクトル検索とスコアリングを行う
                    # 注意: _search_with_params はハイブリッドスコアを計算するが、
                    # このアプローチではベクトルスコアのみが必要。一旦そのまま使う。
                    vector_search_results = await self._search_with_params(
                        query=query, # 元のクエリを使用
                        k=k_vector,
                        hybrid_alpha=1.0, # ベクトルスコアのみ考慮
                        book_weight=0.0 # 書籍ボーナスは不要
                    )

                    # キーワード検索で既に追加されたものを除外
                    for res in vector_search_results:
                        if res.get("highlight_id") not in keyword_match_ids:
                            vector_results_formatted.append(res)
                            # 除外したIDを記録しておく（重複追加防止）
                            keyword_match_ids.add(res.get("highlight_id"))
                            if len(vector_results_formatted) >= k_needed:
                                break # 必要な数が集まったら終了

                    logger.info(f"[ID:{search_id}] ベクトル検索結果（フィルタ後）: {len(vector_results_formatted)}件")

                except Exception as vector_error:
                    logger.error(f"[ID:{search_id}] ベクトル検索エラー: {vector_error}")

            # 6. 結果のマージ
            final_results.extend(vector_results_formatted)

            # 7. 最終結果の重複排除（念のため）と件数調整
            final_unique_results = []
            seen_final_ids = set()
            for res in final_results:
                h_id = res.get("highlight_id")
                if h_id not in seen_final_ids:
                    final_unique_results.append(res)
                    seen_final_ids.add(h_id)

            # スコアで最終ソート（キーワード一致を優先したまま、ベクトル結果内での順序を考慮）
            # キーワード一致(score=1.0)が先頭に来るようにソート
            final_unique_results.sort(key=lambda x: x.get("score", 0), reverse=True)

            # 上位k件を取得
            final_output = final_unique_results[:k_total]

            search_time = time.time() - search_start_time
            logger.info(f"[ID:{search_id}] キーワード優先検索完了 (マージ後): {len(final_output)}件 ({search_time:.2f}秒)")

            return final_output

    async def _search_with_params(self, query: str, k: int, hybrid_alpha: float, book_weight: float) -> List[Dict[str, Any]]:
        """パラメータを指定してベクトル検索とスコアリングを実行（内部ヘルパー）"""
        # この関数はベクトル検索とそのスコアリングに特化させる
        if not self.vector_store:
             logger.warning("ベクトルストアが初期化されていないため、_search_with_params は実行できません")
             return []
        try:
            # 類似度検索を実行
            docs_with_scores = self.vector_store.similarity_search_with_score(query, k=k)

            # 結果を整形
            results = []
            for doc, score in docs_with_scores:
                book_id = doc.metadata.get("book_id", "")
                title = doc.metadata.get("title", "")
                author = doc.metadata.get("author", "")

                # スコア計算（キーワード優先アプローチではベクトルスコアを主に使用）
                # hybrid_alpha=1.0, book_weight=0.0 で呼び出される想定
                vector_score = float(score)

                # キーワードマッチングスコア（ここでは計算しない or 重み0）
                keyword_score = 0.0
                if hybrid_alpha < 1.0: # もしハイブリッドが必要な場合
                    query_keywords = query.lower().split()
                    content_lower = doc.page_content.lower()
                    for keyword in query_keywords:
                        if keyword in content_lower:
                            keyword_score = 1.0 # 単純化: 含まれていれば1.0
                            break

                # スコア計算
                calculated_score = hybrid_alpha * vector_score + (1 - hybrid_alpha) * keyword_score

                # 書籍ボーナス（ここでは計算しない or 重み0）
                if book_weight > 0.0 and book_id and title:
                     final_score = (1 - book_weight) * calculated_score + book_weight
                else:
                     final_score = calculated_score


                # --- デバッグログ ---
                logger.debug(
                    f"Vector Scoring: ID={doc.metadata.get('highlight_id', 'N/A')}, "
                    f"Title='{title}', "
                    f"VectorScore={vector_score:.4f}, FinalScore={final_score:.4f}"
                )
                # --- デバッグログここまで ---

                result = {
                    "content": doc.page_content,
                    "book_id": book_id,
                    "title": title,
                    "author": author,
                    "location": doc.metadata.get("location", ""),
                    "highlight_id": doc.metadata.get("highlight_id", ""),
                    "score": final_score # 計算されたスコアを使用
                }
                results.append(result)

            # スコアでソート
            results.sort(key=lambda x: x.get("score", 0), reverse=True)

            return results[:k] # k件に制限して返す

        except Exception as e:
            logger.error(f"_search_with_params エラー: {e}")
            return []

    async def generate_answer(self, query: str, book_title: Optional[str] = None):
        """
        クエリに対する回答を生成する

        Args:
            query: ユーザーの質問
            book_title: 特定の書籍に限定する場合の書籍タイトル

        Returns:
            生成された回答とソース情報
        """
        if not self.vector_store:
            logger.warning("ベクトルストアが初期化されていません")
            yield "申し訳ありませんが、ハイライトデータが見つかりません。ハイライトをアップロードしてから再度お試しください。", []
            return

        try:
            # 検索クエリをログ出力
            logger.info(f"検索クエリ: '{query}'")
            if book_title:
                logger.info(f"指定書籍: '{book_title}'")

            # キーワード抽出と拡張 (新しい関数を使用)
            # Note: get_relevant_highlights_async already performs extraction and expansion.
            # We call it directly with the original query.
            # The keywords used for DB search inside get_relevant_highlights_async
            # will be the expanded ones.
            logger.info(f"関連ハイライト検索開始 (generate_answer内): query='{query}'")
            relevant_docs_data = await self.get_relevant_highlights_async(
                query=query, # Pass the original query here
                k=15, # 抽出件数を15に変更
                hybrid_alpha=0.5, # Keep hybrid approach for ranking
                book_weight=0.2,
                use_expanded=False # This parameter is effectively ignored now
            )
            logger.info(f"関連ハイライト検索完了 (generate_answer内): {len(relevant_docs_data)}件取得")

            # 書籍ごとのハイライト数をログ出力
            book_counts = {}
            for doc in relevant_docs_data:
                title = doc.get("title", "不明")
                if title not in book_counts:
                    book_counts[title] = 0
                book_counts[title] += 1

            logger.info(f"書籍別ハイライト数: {book_counts}")

            # --- コンテキスト並び替えのための準備 ---
            keyword_matched_data = []
            vector_matched_data = []
            for data in relevant_docs_data:
                # スコアが1.0のものをキーワード一致とみなす（現在の実装に基づく）
                if data.get("score") == 1.0:
                    keyword_matched_data.append(data)
                else:
                    vector_matched_data.append(data)

            # キーワード一致を先に、ベクトル一致を後に結合
            # スコアで再度ソート（ベクトル一致内での順序維持のため）
            vector_matched_data.sort(key=lambda x: x.get("score", 0), reverse=True)
            ordered_docs_data = keyword_matched_data + vector_matched_data
            logger.info(f"コンテキスト並び替え: キーワード一致 {len(keyword_matched_data)}件, ベクトル一致 {len(vector_matched_data)}件")
            # --- 並び替えここまで ---


            # Documentオブジェクトに変換し、ソース情報も準備 (並び替えたリストを使用)
            relevant_docs = []
            sources = []
            seen_highlight_ids = set() # 重複排除用
            for data in ordered_docs_data: # 並び替えたリストを使用
                highlight_id = data.get("highlight_id") # highlight_id を取得
                if highlight_id and highlight_id in seen_highlight_ids:
                    continue # 重複はスキップ

                doc = Document(
                    page_content=data.get("content", ""),
                    metadata={
                        "book_id": data.get("book_id", ""),
                        "title": data.get("title", ""),
                        "author": data.get("author", ""),
                        "location": data.get("location", ""),
                        "highlight_id": highlight_id # メタデータに highlight_id を含める
                    }
                )
                relevant_docs.append(doc)
                sources.append(data) # 返却用のソース情報
                if highlight_id:
                    seen_highlight_ids.add(highlight_id)


            # 特定の書籍に限定する場合のフィルタリング
            if book_title:
                relevant_docs = [doc for doc in relevant_docs if doc.metadata.get("title") == book_title]
                sources = [src for src in sources if src.get("title") == book_title]

            # プロンプトテンプレートを作成
            prompt = ChatPromptTemplate.from_template("""
            あなたは、ユーザーの読書体験を深めるための洞察を提供するAIアシスタントです。
            提供された書籍のハイライト情報を分析し、ユーザーの質問に対して、単なる要約や情報の提示を超えた、示唆に富む回答を生成してください。

            【指示】
            1.  **深い理解**: 以下のハイライト情報を注意深く読み込み、それぞれの文脈や意味合いを深く理解してください。
            2.  **関連性の発見**: ハイライト間の隠れた関連性、共通するテーマ、あるいは対照的な視点を見つけ出してください。
            3.  **新たな視点の提供**: ハイライト情報から得られる学びを踏まえつつ、ユーザーがまだ気づいていないであろう新しい視点や解釈、応用可能なアイデアを提示してください。表面的な情報だけでなく、その背後にある原理原則や著者の意図にも言及できるとより良いでしょう。
            4.  **思考の刺激**: 回答の最後に、ユーザーがさらに思考を深められるような、示唆に富んだ問いかけを1つ含めてください。
            5.  **自然な対話**: 回答は、ユーザーに語りかけるような、自然で分かりやすい言葉遣いを心がけてください。専門用語を使いすぎず、具体的な例を交えると理解が深まります。
            6.  **情報の正確性**: 回答は、提供されたハイライト情報に基づいてください。不確かな情報や推測に基づく断定的な記述は避けてください。

            【ハイライト情報】
            {context}

            【ユーザーの質問】
            {input}

            【回答】
            """)

            # ドキュメント結合チェーンを作成
            document_chain = create_stuff_documents_chain(self.llm, prompt)

            # 回答を生成 (取得したドキュメントのリストを直接渡す)
            # context_string = "\n\n---\n\n".join([doc.page_content for doc in relevant_docs]) # この行は不要
            response = await document_chain.ainvoke(
                {"input": query, "context": relevant_docs}, # relevant_docs (Documentのリスト) を渡す
                {"callbacks": []}
            )

            # 回答とソース情報を返す (sources は既に上で取得済み)
            # response の型に応じて answer を抽出
            if isinstance(response, str):
                answer = response
            elif isinstance(response, dict):
                answer = response.get("answer", "") # 辞書の場合は 'answer' キーを取得
            else:
                # 予期しない型の場合の処理
                logger.warning(f"Unexpected response type from document_chain: {type(response)}. Response: {response}")
                answer = str(response) # フォールバックとして文字列化

            # answer が文字列でない場合の最終フォールバック
            if not isinstance(answer, str):
                logger.warning(f"Answer is not a string after processing: {type(answer)}. Value: {answer}")
                answer = str(answer)

            # ストリーミング用に文または段落単位で返す
            # 文または段落で分割
            chunks = re.split(r'([。.!?]\s*)', answer)

            # 分割したチャンクを結合して返す
            current_chunk = ""
            for i in range(0, len(chunks), 2):
                current_chunk += chunks[i]
                if i + 1 < len(chunks):
                    current_chunk += chunks[i + 1]  # 区切り文字を追加

                # 一定の長さになったら返す
                if len(current_chunk) >= 20 or i + 2 >= len(chunks):
                    yield current_chunk, sources
                    current_chunk = ""

            # 残りのチャンクがあれば返す
            if current_chunk:
                yield current_chunk, sources

        except Exception as e:
            logger.error(f"回答生成エラー: {e}")
            error_message = f"回答の生成中にエラーが発生しました: {str(e)}"
            for char in error_message:
                yield char, []
                
    async def debug_keyword_search(self, keyword: str, limit: int = 10):
        """特定キーワードを含むハイライトを直接検索（デバッグ用）"""
        if not self.db:
            return {"error": "データベース接続がありません"}
        
        try:
            # データベースから直接検索
            highlights = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.content.ilike(f"%{keyword}%")
            ).limit(limit).all()
            
            # 結果の整形
            results = []
            for highlight in highlights:
                # 書籍情報を取得
                book = self.db.query(models.Book).filter(
                    models.Book.id == highlight.book_id
                ).first()
                
                results.append({
                    "highlight_id": highlight.id,
                    "content": highlight.content,
                    "book_id": highlight.book_id,
                    "book_title": book.title if book else "不明",
                    "book_author": book.author if book else "不明",
                    "location": highlight.location or ""
                })
            
            return {
                "keyword": keyword,
                "total_found": len(results),
                "results": results
            }
        except Exception as e:
            logger.error(f"キーワード検索エラー: {e}")
            return {"error": str(e)}
