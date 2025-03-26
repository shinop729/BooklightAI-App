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
                    # 最初からFAISSベクトルストアを使用する（Chromaの問題を回避）
                    logger.info("FAISSベクトルストアを使用します")
                    from langchain.vectorstores import FAISS
                    
                    # FAISS利用可能かチェック
                    try:
                        import faiss
                        logger.info(f"FAISS利用可能: {faiss.__version__}")
                    except ImportError:
                        logger.warning("FAISSがインストールされていません。インストールを試みます。")
                        import subprocess
                        subprocess.check_call(["pip", "install", "faiss-cpu", "--no-cache-dir"])
                        import faiss
                        logger.info(f"FAISSのインストールが完了しました: {faiss.__version__}")
                    
                    self.vector_store = FAISS.from_documents(
                        documents=documents,
                        embedding=self.embeddings
                    )
                    logger.info(f"FAISSベクトルストアを作成しました（{len(documents)}件のハイライト）")
                    
                    # ベクトルストアの保存（オプション）
                    try:
                        vector_dir = f"./api/user_data/vector_db/{self.user_id}"
                        import os
                        os.makedirs(vector_dir, exist_ok=True)
                        
                        # 保存パスを作成
                        save_path = os.path.join(vector_dir, "faiss_index")
                        self.vector_store.save_local(save_path)
                        logger.info(f"FAISSベクトルストアを保存しました: {save_path}")
                    except Exception as save_error:
                        logger.warning(f"FAISSベクトルストアの保存に失敗しました: {save_error}")
                        # 保存に失敗してもインメモリのベクトルストアは使用可能なので続行
                
                except Exception as vs_error:
                    logger.error(f"FAISSベクトルストア作成エラー: {vs_error}")
                    import traceback
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
                                    import random
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
