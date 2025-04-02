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
import database.models as models
from app.config import settings

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

            return False
        except Exception as e:
            logger.error(f"ベクトルストア最適化エラー: {e}")
            return False

    async def get_relevant_highlights_async(self, query: str, k: int = 30, hybrid_alpha: float = 0.7,
                                           book_weight: float = 0.3, use_expanded: bool = True) -> List[Dict[str, Any]]:
        """非同期処理を用いた並列検索"""

        if not self.vector_store:
            logger.warning("ベクトルストアが初期化されていません")
            return []

        # 通常検索と拡張検索を並列実行
        tasks = [self._search_with_params(query, k, hybrid_alpha, book_weight)]

        if use_expanded:
            # クエリ拡張
            expanded = await self._expand_query(query)
            if expanded.get("synonyms"):
                tasks.append(self._search_with_params(expanded["synonyms"], k, hybrid_alpha, book_weight))
            if expanded.get("reformulation"):
                tasks.append(self._search_with_params(expanded["reformulation"], k, hybrid_alpha, book_weight))

        # すべての検索を並列実行
        all_results = await asyncio.gather(*tasks)

        # 結果を統合
        merged_results = []
        seen_content = set()

        for results in all_results:
            for result in results:
                content = result.get("content", "")
                if content not in seen_content:
                    seen_content.add(content)
                    merged_results.append(result)

        # スコアでソート
        merged_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return merged_results[:k]

    async def _search_with_params(self, query: str, k: int, hybrid_alpha: float, book_weight: float) -> List[Dict[str, Any]]:
        """パラメータを指定して検索を実行"""
        try:
            # 類似度検索を実行
            docs_with_scores = self.vector_store.similarity_search_with_score(query, k=k)

            # 結果を整形
            results = []
            for doc, score in docs_with_scores:
                # 書籍情報の重みを適用
                book_id = doc.metadata.get("book_id", "")
                title = doc.metadata.get("title", "")
                author = doc.metadata.get("author", "")

                # ハイブリッドスコアの計算
                # hybrid_alpha: ベクトル検索の重み（0-1）
                # book_weight: 書籍情報の重み（0-1）

                # キーワードマッチングスコア（簡易的な実装）
                keyword_score = 0.0
                for keyword in query.split():
                    if keyword.lower() in doc.page_content.lower():
                        keyword_score += 0.2  # キーワードごとにスコアを加算

                # ハイブリッドスコアの計算
                hybrid_score = hybrid_alpha * float(score) + (1 - hybrid_alpha) * keyword_score

                # 書籍情報の重みを適用
                if book_id and title:
                    # 同じ書籍からの結果にボーナス
                    book_bonus = book_weight
                    final_score = (1 - book_weight) * hybrid_score + book_bonus
                else:
                    final_score = hybrid_score

                result = {
                    "content": doc.page_content,
                    "book_id": book_id,
                    "title": title,
                    "author": author,
                    "location": doc.metadata.get("location", ""),
                    "score": final_score
                }
                results.append(result)

            # スコアでソート
            results.sort(key=lambda x: x.get("score", 0), reverse=True)

            return results[:k]

        except Exception as e:
            logger.error(f"検索エラー: {e}")
            return []

    async def _expand_query(self, query: str) -> Dict[str, str]:
        """クエリを拡張する（類義語や言い換え）"""
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            # クエリ拡張プロンプト
            prompt = f"""
            元のクエリ: {query}

            このクエリに関連する以下の情報を提供してください:
            1. 類義語や関連キーワード（スペース区切り）
            2. クエリの言い換え（1つの文として）

            以下の形式で回答してください:
            {{
                "synonyms": "類義語1 類義語2 関連キーワード1 関連キーワード2",
                "reformulation": "クエリの言い換え"
            }}
            """

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150
            )

            result_text = response.choices[0].message.content

            # JSON形式の抽出
            # JSON部分を抽出
            json_match = re.search(r'({.*})', result_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                    return result
                except json.JSONDecodeError:
                    pass

            # 正規表現でキーと値を抽出
            synonyms_match = re.search(r'"synonyms":\s*"([^"]*)"', result_text)
            reformulation_match = re.search(r'"reformulation":\s*"([^"]*)"', result_text)

            result = {}
            if synonyms_match:
                result["synonyms"] = synonyms_match.group(1)
            if reformulation_match:
                result["reformulation"] = reformulation_match.group(1)

            return result

        except Exception as e:
            logger.error(f"クエリ拡張エラー: {e}")
            return {}

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
            # 検索用のリトリーバーを作成
            retriever = self.vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 30}
            )

            # 特定の書籍に限定する場合
            if book_title:
                # フィルター付きリトリーバーを作成
                original_get_relevant_docs = retriever._get_relevant_documents

                def filtered_get_relevant_docs(query):
                    docs = original_get_relevant_docs(query)
                    return [doc for doc in docs if doc.metadata.get("title") == book_title]

                retriever._get_relevant_documents = filtered_get_relevant_docs

            # プロンプトテンプレートを作成
            prompt = ChatPromptTemplate.from_template("""
            ・あなたは書籍のハイライト情報に基づいて質問に答えるアシスタントです。
            ・以下のハイライト情報を参考にして、ユーザーの質問に詳細に答えてください。
            ・このセクションではハイライト情報を参考にしつつ、新たな独自の視点を付け加えてください
            ・ハイライト情報からの学びを元にしつつ、質問者に新たな気づきを与えるような回答を心がけてください
            ・自然な会話になるように意識してください

            ハイライト:
            {context}

            質問: {input}
            """)

            # ドキュメント結合チェーンを作成
            document_chain = create_stuff_documents_chain(self.llm, prompt)

            # 検索チェーンを作成
            retrieval_chain = create_retrieval_chain(retriever, document_chain)

            # 回答を生成（ストリーミング）
            response = await retrieval_chain.ainvoke(
                {"input": query},
                {"callbacks": []}
            )

            # 関連ハイライトを取得
            relevant_docs = retriever.get_relevant_documents(query)
            sources = []

            for doc in relevant_docs:
                source = {
                    "book_id": doc.metadata.get("book_id", ""),
                    "title": doc.metadata.get("title", ""),
                    "author": doc.metadata.get("author", ""),
                    "content": doc.page_content,
                    "location": doc.metadata.get("location", "")
                }
                sources.append(source)

            # 回答とソース情報を返す
            answer = response["answer"]

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
