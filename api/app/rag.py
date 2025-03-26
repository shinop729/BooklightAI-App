"""
RAG (Retrieval-Augmented Generation) モジュール

このモジュールは、ユーザーの質問に対して関連するハイライトを検索し、
それらを使用してOpenAI APIで回答を生成する機能を提供します。
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime

from langchain.vectorstores import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor

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
        """ベクトルストアを初期化する"""
        try:
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
            
            # ハイライトをドキュメントに変換
            documents = []
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
                except Exception as doc_error:
                    # 個別のドキュメント作成エラーをスキップ
                    logger.error(f"ドキュメント作成エラー (ハイライトID: {highlight.id}): {doc_error}")
                    continue
            
            # ドキュメントが存在する場合のみベクトルストアを作成
            if documents:
                try:
                    # ベクトルストアディレクトリの存在確認と作成
                    vector_dir = f"./api/user_data/vector_db/{self.user_id}"
                    import os
                    os.makedirs(vector_dir, exist_ok=True)
                    
                    # ディレクトリの権限を確認
                    if not os.access(vector_dir, os.W_OK):
                        logger.warning(f"ディレクトリ {vector_dir} に書き込み権限がありません")
                        # 権限を設定
                        try:
                            os.chmod(vector_dir, 0o755)
                            logger.info(f"ディレクトリ {vector_dir} の権限を設定しました")
                        except Exception as chmod_error:
                            logger.error(f"ディレクトリ権限設定エラー: {chmod_error}")
                            # 一時ディレクトリを使用
                            import tempfile
                            vector_dir = tempfile.mkdtemp()
                            logger.info(f"一時ディレクトリを使用します: {vector_dir}")
                    
                    # ベクトルストアを作成
                    logger.info(f"ベクトルストアを作成中: {len(documents)}件のドキュメント")
                    
                    # ディレクトリの内容を確認
                    try:
                        dir_contents = os.listdir(vector_dir)
                        logger.info(f"ディレクトリ {vector_dir} の内容: {dir_contents}")
                    except Exception as ls_error:
                        logger.error(f"ディレクトリ内容確認エラー: {ls_error}")
                    
                    self.vector_store = Chroma.from_documents(
                        documents=documents,
                        embedding=self.embeddings,
                        collection_name=f"user_{self.user_id}_highlights",
                        persist_directory=vector_dir
                    )
                    
                    logger.info(f"ユーザーID {self.user_id} のベクトルストアを初期化しました（{len(documents)}件のハイライト）")
                except Exception as vs_error:
                    logger.error(f"Chromaベクトルストア作成エラー: {vs_error}")
                    import traceback
                    logger.error(f"詳細エラー: {traceback.format_exc()}")
                    
                    # Chromaのバージョンを確認
                    try:
                        import chromadb
                        logger.info(f"ChromaDB バージョン: {chromadb.__version__}")
                    except Exception as version_error:
                        logger.error(f"ChromaDBバージョン確認エラー: {version_error}")
                    
                    # エラー時はインメモリベクトルストアを試行
                    try:
                        logger.info("インメモリベクトルストアを試行します")
                        import tempfile
                        with tempfile.TemporaryDirectory() as tmp_dir:
                            self.vector_store = Chroma.from_documents(
                                documents=documents,
                                embedding=self.embeddings,
                                collection_name=f"user_{self.user_id}_highlights_temp",
                                persist_directory=tmp_dir
                            )
                        logger.info(f"一時ディレクトリにベクトルストアを作成しました")
                    except Exception as tmp_error:
                        logger.error(f"一時ベクトルストア作成エラー: {tmp_error}")
                        logger.error(f"詳細エラー: {traceback.format_exc()}")
                        
                        # 最後の手段としてインメモリのみのベクトルストアを試行
                        try:
                            logger.info("インメモリのみのベクトルストアを試行します")
                            from langchain.vectorstores import FAISS
                            
                            # FAISS利用可能かチェック
                            try:
                                import faiss
                                logger.info(f"FAISS利用可能: {faiss.__version__}")
                            except ImportError:
                                logger.warning("FAISSがインストールされていません。インストールを試みます。")
                                import subprocess
                                subprocess.check_call(["pip", "install", "faiss-cpu", "--no-cache-dir"])
                                logger.info("FAISSのインストールが完了しました")
                            
                            self.vector_store = FAISS.from_documents(
                                documents=documents,
                                embedding=self.embeddings
                            )
                            logger.info("FAISSベクトルストアを作成しました")
                        except Exception as faiss_error:
                            logger.error(f"FAISSベクトルストア作成エラー: {faiss_error}")
                            logger.error(f"詳細エラー: {traceback.format_exc()}")
                            self.vector_store = None
            else:
                logger.warning("有効なドキュメントがないため、ベクトルストアを作成しません")
                self.vector_store = None
        
        except Exception as e:
            logger.error(f"ベクトルストアの初期化エラー: {e}")
            import traceback
            logger.error(f"詳細エラー: {traceback.format_exc()}")
            
            # OpenAI APIキーの有効性を確認
            try:
                from openai import OpenAI
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
                search_kwargs={"k": 5}
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
            あなたは書籍のハイライト情報に基づいて質問に答えるアシスタントです。
            以下のハイライト情報を参考にして、ユーザーの質問に答えてください。
            
            ハイライト情報に基づいた回答を心がけ、情報がない場合は正直に「その情報はハイライトにありません」と伝えてください。
            引用元の書籍名、著者名、ページ番号などを回答の中で適切に言及してください。
            
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
            import re
            
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
