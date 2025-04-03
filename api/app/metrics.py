"""
パフォーマンスモニタリングモジュール

このモジュールは、APIエンドポイントのパフォーマンスを測定し、
統計情報を収集するための機能を提供します。
"""

import time
import logging
import statistics
import functools
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime, timedelta

# ロギング設定
logger = logging.getLogger("booklight-api")

# パフォーマンス履歴
PERFORMANCE_HISTORY = {
    "search": {
        "times": [],  # 処理時間のリスト
        "query_lengths": [],  # クエリ長のリスト
        "result_counts": [],  # 結果数のリスト
        "timestamps": []  # タイムスタンプのリスト
    },
    "chat": {
        "times": [],
        "query_lengths": [],
        "result_lengths": [],
        "timestamps": []
    },
    "cross_point": {
        "times": [],
        "timestamps": []
    },
    "remix": {
        "times": [],
        "timestamps": []
    }
}

# 最大履歴サイズ
MAX_HISTORY_SIZE = 1000

def measure_time(category: str):
    """
    処理時間を測定するデコレータ
    
    Args:
        category: カテゴリ名（'search', 'chat', 'cross_point', 'remix'）
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 開始時間を記録
            start_time = time.time()
            
            # 元の関数を実行
            result = await func(*args, **kwargs)
            
            # 終了時間を記録
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            # カテゴリごとの追加情報を取得
            additional_info = {}
            
            if category == "search":
                # 検索クエリの長さを取得
                query = None
                for arg in args:
                    if isinstance(arg, dict) and "keywords" in arg:
                        query = " ".join(arg["keywords"])
                        break
                
                if not query and kwargs.get("request"):
                    request = kwargs.get("request")
                    if hasattr(request, "keywords"):
                        query = " ".join(request.keywords)
                
                query_length = len(query) if query else 0
                additional_info["query_length"] = query_length
                
                # 結果数を取得
                result_count = 0
                if result and isinstance(result, dict):
                    if "data" in result and isinstance(result["data"], dict):
                        data = result["data"]
                        if "results" in data and isinstance(data["results"], list):
                            result_count = len(data["results"])
                
                additional_info["result_count"] = result_count
            
            elif category == "chat":
                # チャットクエリの長さを取得
                query = None
                for arg in args:
                    if isinstance(arg, dict) and "query" in arg:
                        query = arg["query"]
                        break
                
                if not query and kwargs.get("query"):
                    query = kwargs.get("query")
                
                query_length = len(query) if query else 0
                additional_info["query_length"] = query_length
                
                # 結果の長さを取得（ストリーミングの場合は推定）
                result_length = 0
                if result and isinstance(result, str):
                    result_length = len(result)
                
                additional_info["result_length"] = result_length
            
            # パフォーマンス情報を記録
            record_performance(category, elapsed_time, additional_info)
            
            # パフォーマンスログ
            log_message = f"{category}処理時間: {elapsed_time:.3f}秒"
            if "query_length" in additional_info:
                log_message += f" (クエリ長: {additional_info['query_length']})"
            if "result_count" in additional_info:
                log_message += f" (結果数: {additional_info['result_count']})"
            if "result_length" in additional_info:
                log_message += f" (結果長: {additional_info['result_length']})"
            
            logger.info(log_message)
            
            return result
        
        return wrapper
    
    return decorator

def record_performance(category: str, elapsed_time: float, additional_info: Dict[str, Any] = None):
    """
    パフォーマンス情報を記録
    
    Args:
        category: カテゴリ名
        elapsed_time: 処理時間（秒）
        additional_info: 追加情報
    """
    if category not in PERFORMANCE_HISTORY:
        PERFORMANCE_HISTORY[category] = {
            "times": [],
            "timestamps": []
        }
    
    # 処理時間を記録
    PERFORMANCE_HISTORY[category]["times"].append(elapsed_time)
    PERFORMANCE_HISTORY[category]["timestamps"].append(datetime.now())
    
    # 追加情報を記録
    if additional_info:
        for key, value in additional_info.items():
            if key not in PERFORMANCE_HISTORY[category]:
                PERFORMANCE_HISTORY[category][key + "s"] = []
            
            PERFORMANCE_HISTORY[category][key + "s"].append(value)
    
    # 履歴サイズを制限
    for key in PERFORMANCE_HISTORY[category]:
        if len(PERFORMANCE_HISTORY[category][key]) > MAX_HISTORY_SIZE:
            PERFORMANCE_HISTORY[category][key] = PERFORMANCE_HISTORY[category][key][-MAX_HISTORY_SIZE:]

def get_performance_stats(category: Optional[str] = None, period: Optional[str] = None) -> Dict[str, Any]:
    """
    パフォーマンス統計を取得
    
    Args:
        category: カテゴリ名（指定しない場合は全カテゴリ）
        period: 期間（'hour', 'day', 'week', 'all'）
        
    Returns:
        パフォーマンス統計
    """
    stats = {}
    
    # 期間によるフィルタリング
    now = datetime.now()
    filter_time = None
    
    if period == "hour":
        filter_time = now - timedelta(hours=1)
    elif period == "day":
        filter_time = now - timedelta(days=1)
    elif period == "week":
        filter_time = now - timedelta(weeks=1)
    
    # カテゴリごとの統計を計算
    categories = [category] if category else PERFORMANCE_HISTORY.keys()
    
    for cat in categories:
        if cat not in PERFORMANCE_HISTORY or not PERFORMANCE_HISTORY[cat]["times"]:
            stats[cat] = {
                "count": 0,
                "avg_time": 0,
                "min_time": 0,
                "max_time": 0,
                "p95_time": 0,
                "p99_time": 0
            }
            continue
        
        # 期間でフィルタリング
        filtered_indices = range(len(PERFORMANCE_HISTORY[cat]["times"]))
        if filter_time:
            filtered_indices = [
                i for i, ts in enumerate(PERFORMANCE_HISTORY[cat]["timestamps"])
                if ts >= filter_time
            ]
        
        if not filtered_indices:
            stats[cat] = {
                "count": 0,
                "avg_time": 0,
                "min_time": 0,
                "max_time": 0,
                "p95_time": 0,
                "p99_time": 0
            }
            continue
        
        # 処理時間の統計を計算
        times = [PERFORMANCE_HISTORY[cat]["times"][i] for i in filtered_indices]
        
        sorted_times = sorted(times)
        p95_idx = int(len(sorted_times) * 0.95)
        p99_idx = int(len(sorted_times) * 0.99)
        
        cat_stats = {
            "count": len(times),
            "avg_time": statistics.mean(times) if times else 0,
            "min_time": min(times) if times else 0,
            "max_time": max(times) if times else 0,
            "p95_time": sorted_times[p95_idx] if p95_idx < len(sorted_times) else (sorted_times[-1] if sorted_times else 0),
            "p99_time": sorted_times[p99_idx] if p99_idx < len(sorted_times) else (sorted_times[-1] if sorted_times else 0)
        }
        
        # 追加情報の統計を計算
        for key in PERFORMANCE_HISTORY[cat]:
            if key not in ["times", "timestamps"] and PERFORMANCE_HISTORY[cat][key]:
                values = [PERFORMANCE_HISTORY[cat][key][i] for i in filtered_indices if i < len(PERFORMANCE_HISTORY[cat][key])]
                if values:
                    cat_stats[f"avg_{key[:-1]}"] = statistics.mean(values)
                    cat_stats[f"max_{key[:-1]}"] = max(values)
        
        stats[cat] = cat_stats
    
    return stats

def clear_performance_history(category: Optional[str] = None):
    """
    パフォーマンス履歴をクリア
    
    Args:
        category: カテゴリ名（指定しない場合は全カテゴリ）
    """
    if category:
        if category in PERFORMANCE_HISTORY:
            for key in PERFORMANCE_HISTORY[category]:
                PERFORMANCE_HISTORY[category][key] = []
    else:
        for cat in PERFORMANCE_HISTORY:
            for key in PERFORMANCE_HISTORY[cat]:
                PERFORMANCE_HISTORY[cat][key] = []
