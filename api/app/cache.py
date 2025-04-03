"""
キャッシュモジュール

シンプルなインメモリキャッシュを提供します。
"""

import pickle
import time
from typing import Any, Optional, Dict
import logging
import re

logger = logging.getLogger("booklight-api")

# メモリ内キャッシュ
IN_MEMORY_CACHE: Dict[str, Any] = {}
CACHE_TTL: Dict[str, float] = {}  # キーごとの有効期限を保存

async def get_cache(key: str) -> Optional[Any]:
    """
    キャッシュから値を取得
    
    Args:
        key: キャッシュキー
        
    Returns:
        キャッシュされた値、または None（キャッシュミス時）
    """
    # メモリ内キャッシュから取得
    if key in IN_MEMORY_CACHE:
        # TTLチェック
        current_time = time.time()
        if key in CACHE_TTL and current_time > CACHE_TTL[key]:
            # 期限切れ
            logger.debug(f"キャッシュ期限切れ: {key}")
            del IN_MEMORY_CACHE[key]
            del CACHE_TTL[key]
            return None
        
        logger.debug(f"キャッシュヒット: {key}")
        return IN_MEMORY_CACHE[key]
    
    logger.debug(f"キャッシュミス: {key}")
    return None

async def set_cache(key: str, value: Any, ttl: int = 300):
    """
    キャッシュに値を設定
    
    Args:
        key: キャッシュキー
        value: キャッシュする値
        ttl: 有効期限（秒）
    """
    # メモリ内キャッシュに保存
    IN_MEMORY_CACHE[key] = value
    # TTLを設定
    CACHE_TTL[key] = time.time() + ttl
    logger.debug(f"キャッシュ設定: {key} (TTL: {ttl}秒)")

async def invalidate_cache(pattern: str = "*"):
    """
    キャッシュを無効化
    
    Args:
        pattern: 無効化するキーのパターン（ワイルドカード * 使用可）
    """
    global IN_MEMORY_CACHE, CACHE_TTL
    
    if pattern == "*":
        # 全キャッシュクリア
        logger.info("全キャッシュをクリア")
        IN_MEMORY_CACHE = {}
        CACHE_TTL = {}
    else:
        # パターンマッチング
        pattern_regex = re.compile(pattern.replace("*", ".*"))
        deleted_keys = []
        
        for key in list(IN_MEMORY_CACHE.keys()):
            if pattern_regex.match(key):
                del IN_MEMORY_CACHE[key]
                if key in CACHE_TTL:
                    del CACHE_TTL[key]
                deleted_keys.append(key)
        
        logger.info(f"パターン '{pattern}' に一致する {len(deleted_keys)} 件のキャッシュをクリア")

def measure_time(name: str):
    """
    処理時間を測定するデコレータ
    
    Args:
        name: 処理の名前
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            result = await func(*args, **kwargs)
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            logger.info(f"{name} 処理時間: {elapsed_time:.3f}秒")
            
            return result
        return wrapper
    return decorator
