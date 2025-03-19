import logging

# ダミーの関数を定義して、実際のSentry統合の代わりに使用
def init_sentry(settings):
    """
    ダミーのSentry初期化関数
    """
    logger = logging.getLogger("booklight-api")
    logger.info("Sentry integration is disabled")
    
    # ダミーのコンテキスト設定関数を返す
    return lambda user_id=None, email=None: None

def log_performance_metric(metric_name, value, tags=None):
    """
    ダミーのパフォーマンスメトリクス記録関数
    """
    logger = logging.getLogger("booklight-api")
    logger.debug(f"Performance metric (disabled): {metric_name}={value}")

def track_transaction(transaction_name):
    """
    ダミーのトランザクショントラッキングデコレータ
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator
