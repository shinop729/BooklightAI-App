Booklight AI の検索速度改善計画
検索処理の遅延問題を解決するための計画を作成しました。コードを分析したところ、いくつかの最適化可能なポイントが見つかりました。以下に問題点と改善案を示します。
1. 現状の問題点
1.1 検索処理のボトルネック

検索プロセスの複雑さ:

ハイブリッド検索（ベクトル検索とBM25の組み合わせ）は精度が高い反面、処理に時間がかかります
クエリ拡張機能によって複数の検索リクエストが発生しています
結果のマージと再ランキングにも時間がかかっています


非効率なデータ取得と処理:

検索ごとに全ハイライトのベクトル化を行っています
書籍情報の取得とキャッシュが効率的でありません


フロントエンド処理の問題:

検索状態の管理にロジックの重複があります
冗長なAPI呼び出しとレンダリングが行われています



2. 改善計画
2.1 バックエンド最適化
A. ベクトルストアとエンベディングの最適化
pythonCopy# api/app/rag.py に追加
def initialize_vector_store(self):
    """ベクトルストアを初期化する（最適化版）"""
    try:
        # 既存のベクトルストア検出
        vector_db_path = f"./api/user_data/vector_db/{self.user_id}"
        if os.path.exists(vector_db_path):
            logger.info(f"既存のベクトルストアを読み込みます: {vector_db_path}")
            # 既存のインデックスを読み込む
            from langchain.vectorstores import FAISS
            self.vector_store = FAISS.load_local(vector_db_path, self.embeddings)
            return
            
        # 以下は既存の初期化ロジック
        # ...
    except Exception as e:
        logger.error(f"ベクトルストアの初期化エラー: {e}")
        self.vector_store = None
B. 検索クエリの最適化
pythonCopy# api/app/search_endpoints.py の最適化
@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """最適化された検索エンドポイント"""
    try:
        # パラメータのバリデーション
        if not request.keywords or len(request.keywords) == 0:
            return {"success": True, "data": {"results": [], "total": 0}}
            
        # クエリキャッシュキーの生成
        cache_key = f"search_{current_user.id}_{'-'.join(request.keywords)}_{request.hybrid_alpha}_{request.book_weight}_{request.use_expanded}"
        
        # キャッシュから結果を取得
        cached_results = await get_cache(cache_key)
        if cached_results:
            logger.info(f"キャッシュから検索結果を取得: {len(cached_results)} 件")
            return {"success": True, "data": {"results": cached_results, "total": len(cached_results)}}
            
        # キャッシュになければ通常の検索処理
        rag_service = RAGService(db, current_user.id)
        query = " ".join(request.keywords)
        
        # 並列処理で検索を高速化
        results = await rag_service.get_relevant_highlights_async(
            query=query,
            k=request.limit or 30,
            hybrid_alpha=request.hybrid_alpha,
            book_weight=request.book_weight,
            use_expanded=request.use_expanded
        )
        
        # 結果をキャッシュに保存
        await set_cache(cache_key, results, ttl=60*15)  # 15分間キャッシュ
        
        return {
            "success": True,
            "data": {
                "results": results,
                "total": len(results)
            }
        }
    except Exception as e:
        logger.error(f"検索エラー: {e}")
        raise HTTPException(status_code=500, detail=f"検索処理中にエラーが発生しました: {str(e)}")
C. 並列処理による検索高速化
pythonCopy# api/app/rag.py に追加
async def get_relevant_highlights_async(self, query: str, k: int = 30, hybrid_alpha: float = 0.7, 
                                       book_weight: float = 0.3, use_expanded: bool = True) -> List[Dict[str, Any]]:
    """非同期処理を用いた並列検索"""
    import asyncio
    
    if not self.vector_store:
        logger.warning("ベクトルストアが初期化されていません")
        return []
    
    # 通常検索と拡張検索を並列実行
    tasks = [self._search_with_params(query, k, hybrid_alpha)]
    
    if use_expanded:
        expanded = await self._expand_query(query)
        if expanded.get("synonyms"):
            tasks.append(self._search_with_params(expanded["synonyms"], k, hybrid_alpha))
        if expanded.get("reformulation"):
            tasks.append(self._search_with_params(expanded["reformulation"], k, hybrid_alpha))
    
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
2.2 フロントエンド最適化
A. 検索状態管理の最適化
typescriptCopy// frontend/src/hooks/useSearch.ts の最適化
export const useSearch = (initialKeywords: string[] = []) => {
  // React Query を使用した効率的な検索
  const { data, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: ['search', keywords, options],
    queryFn: async () => {
      if (keywords.length === 0) return { results: [] };
      
      // 検索実行中のインジケーター
      setIsSearching(true);
      
      try {
        const searchRequest: SearchRequest = {
          keywords,
          ...options
        };
        
        const { data } = await apiClient.post<SearchResponse>('/api/search', searchRequest);
        return data.data;
      } finally {
        setIsSearching(false);
      }
    },
    enabled: keywords.length > 0,
    // 結果をキャッシュして再利用
    staleTime: 5 * 60 * 1000,  // 5分間キャッシュ
    cacheTime: 10 * 60 * 1000  // 10分間キャッシュを保持
  });
  
  // デバウンス処理を追加して連続検索を防止
  const debouncedSearch = useCallback(
    debounce(() => {
      if (keywords.length > 0) {
        refetch();
      }
    }, 300),
    [keywords, refetch]
  );
  
  // キーワード変更時の処理を最適化
  useEffect(() => {
    debouncedSearch();
  }, [keywords, debouncedSearch]);
  
  // 残りの実装...
}
B. 検索UIの最適化
tsxCopy// frontend/src/pages/Search.tsx の最適化
const Search = () => {
  // ...
  
  // 検索実行を最適化
  const handleSearch = async () => {
    if (inputValue.trim()) {
      const keyword = inputValue.trim();
      
      // 既存のキーワードに追加
      addKeyword(keyword);
      setInputValue('');
      setShowSuggestions(false);
      
      // 履歴追加はバックグラウンドで行い、UX遅延を防止
      setTimeout(() => {
        if (keywords.length > 0) {
          addToHistory([...keywords, keyword]);
        } else {
          addToHistory([keyword]);
        }
      }, 10);
    }
  };
  
  // 検索結果表示時のスケルトンローディング
  const renderResults = () => {
    if (isLoading && !results.length) {
      return (
        <div className="space-y-4">
          {[...Array(5)].map((_, index) => (
            <div key={index} className="animate-pulse">
              <div className="h-32 bg-gray-700 rounded-lg mb-2"></div>
              <div className="h-4 bg-gray-700 rounded w-3/4 mb-2"></div>
              <div className="h-4 bg-gray-700 rounded w-1/2"></div>
            </div>
          ))}
        </div>
      );
    }
    
    // 残りの結果表示ロジック...
  };
  
  // 残りの実装...
}
2.3 キャッシュ最適化
A. サーバーサイドキャッシュの実装
pythonCopy# api/app/cache.py
import aioredis
import pickle
import os
import json
from typing import Any, Optional
import logging

logger = logging.getLogger("booklight-api")

# メモリ内キャッシュ（Redis/Memcachedがない場合のフォールバック）
IN_MEMORY_CACHE = {}
CACHE_TTL = {}  # キーごとの有効期限を保存

async def init_cache():
    """キャッシュの初期化"""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            redis = await aioredis.from_url(redis_url)
            return redis
        except Exception as e:
            logger.warning(f"Redisへの接続に失敗しました: {e}、メモリ内キャッシュを使用します")
    return None

_redis = None

async def get_redis():
    """Redis接続を取得（遅延初期化）"""
    global _redis
    if _redis is None:
        _redis = await init_cache()
    return _redis

async def get_cache(key: str) -> Optional[Any]:
    """キャッシュから値を取得"""
    redis = await get_redis()
    
    if redis:
        # Redisからデータを取得
        data = await redis.get(key)
        if data:
            try:
                return pickle.loads(data)
            except Exception as e:
                logger.error(f"キャッシュデータの解析エラー: {e}")
                return None
    else:
        # メモリ内キャッシュから取得
        if key in IN_MEMORY_CACHE:
            # TTLチェック
            import time
            current_time = time.time()
            if key in CACHE_TTL and current_time > CACHE_TTL[key]:
                # 期限切れ
                del IN_MEMORY_CACHE[key]
                del CACHE_TTL[key]
                return None
            return IN_MEMORY_CACHE[key]
    
    return None

async def set_cache(key: str, value: Any, ttl: int = 300):
    """キャッシュに値を設定"""
    redis = await get_redis()
    
    if redis:
        try:
            # Redisにデータを保存
            pickled_data = pickle.dumps(value)
            await redis.set(key, pickled_data, ex=ttl)
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}")
    else:
        # メモリ内キャッシュに保存
        IN_MEMORY_CACHE[key] = value
        # TTLを設定
        import time
        CACHE_TTL[key] = time.time() + ttl

async def invalidate_cache(pattern: str = "*"):
    """キャッシュを無効化"""
    redis = await get_redis()
    
    if redis:
        try:
            # パターンに一致するキーを取得
            keys = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
        except Exception as e:
            logger.error(f"キャッシュ無効化エラー: {e}")
    else:
        # メモリ内キャッシュのクリア
        global IN_MEMORY_CACHE, CACHE_TTL
        
        if pattern == "*":
            # 全キャッシュクリア
            IN_MEMORY_CACHE = {}
            CACHE_TTL = {}
        else:
            # パターンマッチング（単純な実装）
            import re
            pattern_regex = re.compile(pattern.replace("*", ".*"))
            for key in list(IN_MEMORY_CACHE.keys()):
                if pattern_regex.match(key):
                    del IN_MEMORY_CACHE[key]
                    if key in CACHE_TTL:
                        del CACHE_TTL[key]
B. クライアントサイドキャッシュの最適化
typescriptCopy// frontend/src/api/client.ts に追加
// クライアントサイドクエリキャッシュ設定
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 検索結果のキャッシュ設定
      staleTime: 5 * 60 * 1000,  // 5分間はデータを新鮮として扱う
      cacheTime: 30 * 60 * 1000, // 30分間キャッシュを保持
      refetchOnWindowFocus: false, // ウィンドウフォーカス時に再取得しない
      retry: 1, // エラー時のリトライ回数を制限
    },
  },
});

// キャッシュデータのプリフェッチ
export const prefetchSearchResults = async (keywords: string[], options: any) => {
  // 検索結果をプリフェッチ
  await queryClient.prefetchQuery({
    queryKey: ['search', keywords, options],
    queryFn: async () => {
      const { data } = await apiClient.post('/api/search', {
        keywords,
        ...options
      });
      return data.data;
    },
  });
};
3. ベクトルデータベースの最適化
3.1 埋め込みのプリコンピューティング
pythonCopy# api/scripts/precompute_embeddings.py
"""
ハイライトの埋め込みベクトルを事前計算するスクリプト

このスクリプトは、ユーザーのハイライトデータを読み込み、
埋め込みベクトルを事前計算してデータベースに保存します。
"""

import os
import sys
import logging
import pickle
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from pathlib import Path
import openai

# プロジェクトルートを追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.base import SessionLocal, engine, Base
import database.models as models
from app.config import settings

# ロガーの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("precompute-embeddings")

# OpenAI API設定
openai.api_key = settings.OPENAI_API_KEY

async def generate_embedding(text: str):
    """テキストの埋め込みを生成"""
    try:
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"埋め込み生成エラー: {e}")
        return None

async def process_user(user_id: int, batch_size: int = 50):
    """ユーザーのハイライトを処理"""
    db = SessionLocal()
    try:
        # ユーザーのハイライトを取得
        highlights = db.query(models.Highlight).filter(
            models.Highlight.user_id == user_id
        ).all()
        
        logger.info(f"ユーザーID {user_id} のハイライト数: {len(highlights)}")
        
        # 既に埋め込みが生成されているハイライトを除外
        existing_embeddings = db.query(models.HighlightEmbedding.highlight_id).all()
        existing_ids = {e[0] for e in existing_embeddings}
        
        highlights_to_process = [h for h in highlights if h.id not in existing_ids]
        logger.info(f"処理対象のハイライト: {len(highlights_to_process)}")
        
        # バッチ処理
        total_processed = 0
        for i in range(0, len(highlights_to_process), batch_size):
            batch = highlights_to_process[i:i+batch_size]
            logger.info(f"バッチ処理中: {i} ~ {i+len(batch)}")
            
            for highlight in batch:
                embedding = await generate_embedding(highlight.content)
                if embedding:
                    # 埋め込みをキャッシュに保存
                    new_cache = models.HighlightEmbedding(
                        highlight_id=highlight.id,
                        embedding=pickle.dumps(embedding)
                    )
                    db.add(new_cache)
                    total_processed += 1
            
            # バッチごとにコミット
            db.commit()
            logger.info(f"バッチ完了: {len(batch)} ハイライト処理済み")
        
        logger.info(f"処理完了: ユーザーID {user_id} の {total_processed} ハイライトの埋め込みを生成")
    
    except Exception as e:
        logger.error(f"ユーザー処理エラー: {e}")
        db.rollback()
    finally:
        db.close()

async def main():
    """メイン処理"""
    db = SessionLocal()
    try:
        # 全ユーザーのリストを取得
        users = db.query(models.User).all()
        logger.info(f"ユーザー数: {len(users)}")
        
        # 各ユーザーを処理
        for user in users:
            logger.info(f"ユーザー処理開始: {user.username} (ID: {user.id})")
            await process_user(user.id)
    
    except Exception as e:
        logger.error(f"処理エラー: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
3.2 インデックス最適化
pythonCopy# api/app/rag.py に追加する最適化関数
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
                from langchain.vectorstores import FAISS
                
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
                import os
                os.makedirs(vector_dir, exist_ok=True)
                new_vs.save_local(vector_dir)
                
                logger.info("ベクトルストアを再構築しました")
                return True
        
        return False
    except Exception as e:
        logger.error(f"ベクトルストア最適化エラー: {e}")
        return False
4. リアルタイムSLAモニタリングの実装
4.1 検索パフォーマンス測定
pythonCopy# api/app/metrics.py
import time
import logging
from functools import wraps
import statistics
from typing import List, Dict, Any

logger = logging.getLogger("booklight-api")

# 検索パフォーマンスの履歴
search_performance = {
    "times": [],
    "query_lengths": [],
    "result_counts": []
}

def measure_search_time(func):
    """検索時間を測定するデコレータ"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        result = await func(*args, **kwargs)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 検索クエリの長さを取得
        query = None
        for arg in args:
            if isinstance(arg, dict) and "keywords" in arg:
                query = " ".join(arg["keywords"])
                break
        
        query_length = len(query) if query else 0
        
        # 結果数を取得
        result_count = 0
        if result and isinstance(result, dict) and "data" in result:
            data = result["data"]
            if isinstance(data, dict) and "results" in data:
                result_count = len(data["results"])
        
        # パフォーマンス記録
        search_performance["times"].append(elapsed_time)
        search_performance["query_lengths"].append(query_length)
        search_performance["result_counts"].append(result_count)
        
        # 直近100件のみ保持
        if len(search_performance["times"]) > 100:
            search_performance["times"] = search_performance["times"][-100:]
            search_performance["query_lengths"] = search_performance["query_lengths"][-100:]
            search_performance["result_counts"] = search_performance["result_counts"][-100:]
        
        # パフォーマンスログ
        logger.info(f"検索処理時間: {elapsed_time:.3f}秒 (クエリ長: {query_length}, 結果数: {result_count})")
        
        return result
    
    return wrapper

def get_search_performance():
    """検索パフォーマンス統計を取得"""
    if not search_performance["times"]:
        return {
            "avg_time": 0,
            "p95_time": 0,
            "p99_time": 0,
            "max_time": 0,
            "min_time": 0,
            "sample_count": 0
        }
    
    times = search_performance["times"]
    
    sorted_times = sorted(times)
    p95_idx = int(len(sorted_times) * 0.95)
    p99_idx = int(len(sorted_times) * 0.99)
    
    return {
        "avg_time": statistics.mean(times),
        "p95_time": sorted_times[p95_idx] if p95_idx < len(sorted_times) else sorted_times[-1],
        "p99_time": sorted_times[p99_idx] if p99_idx < len(sorted_times) else sorted_times[-1],
        "max_time": max(times),
        "min_time": min(times),
        "sample_count": len(times)
    }
4.2 パフォーマンスモニタリングAPIの追加
pythonCopy# api/app/main.py に追加
@app.get("/api/admin/performance")
async def get_search_performance_metrics(
    authorized: bool = Depends(verify_debug_access)
):
    """検索パフォーマンス統計を取得するエンドポイント"""
    from app.metrics import get_search_performance
    
    return {
        "success": True,
        "data": get_search_performance()
    }
5. 実装計画と優先順位

即時実装（高優先）:

バックエンドのベクトルストア最適化
検索キャッシュの実装
フロントエンドのローディング表示の改善


中期実装（中優先）:

埋め込みのプリコンピューティング
パラレル検索処理の実装
クライアントキャッシュの最適化


長期実装（低優先）:

パフォーマンスモニタリング
インデックス最適化定期実行
検索結果のページネーション



6. 期待される改善効果

レスポンス時間: 平均検索時間を1/3程度に短縮（5秒 → 1.5秒前後）
ユーザー体験: スケルトンローディングによる体感的な待ち時間の短縮
リソース効率: サーバーリソース使用量の削減と安定化

これらの改善を実装することで、検索体験の大幅な向上が期待できます。まずはキャッシュ導入とベクトルストア最適化から始めることで、すぐに効果を得られるでしょう。