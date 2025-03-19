import os
import sentry_sdk
import logging
from sentry_sdk import capture_exception, set_tag
from sentry_sdk.integrations.logging import LoggingIntegration

# FastAPIIntegrationが存在しない場合のフォールバック
try:
    from sentry_sdk.integrations.fastapi import FastAPIIntegration
except ImportError:
    FastAPIIntegration = None

# SQLAlchemyIntegrationが存在しない場合のフォールバック
try:
    from sentry_sdk.integrations.sqlalchemy import SqlAlchemyIntegration
except ImportError:
    SqlAlchemyIntegration = None

def init_sentry(settings):
    """
    Sentryを初期化し、エラー追跡を設定する
    
    Args:
        settings: アプリケーション設定オブジェクト
    """
    # Sentryの初期化条件
    if settings.ENVIRONMENT == "production" and os.getenv("SENTRY_DSN"):
        # 利用可能なインテグレーションを追加
        integrations = [
            LoggingIntegration(
                level=logging.INFO,     # 通知レベル
                event_level=logging.ERROR  # エラーレベル
            )
        ]
        
        # 利用可能な場合のみインテグレーションを追加
        if FastAPIIntegration is not None:
            integrations.append(FastAPIIntegration())
            
        if SqlAlchemyIntegration is not None:
            integrations.append(SqlAlchemyIntegration())
        
        sentry_sdk.init(
            dsn=os.getenv("SENTRY_DSN"),
            environment=str(settings.ENVIRONMENT),
            release=settings.VERSION,
            
            # インテグレーションの設定
            integrations=integrations,
            
            # パフォーマンストラッキングの有効化
            traces_sample_rate=0.2,  # 20%のトランザクションをトレース
            
            # エラーサンプリング
            sample_rate=1.0  # 本番環境では全てのエラーをキャプチャ
        )

        # デフォルトタグを設定
        set_tag("app_name", settings.APP_NAME)
        set_tag("environment", str(settings.ENVIRONMENT))
        
        # ユーザーコンテキストの設定関数
        def set_user_context(user_id=None, email=None):
            """
            Sentryにユーザーコンテキストを設定
            
            Args:
                user_id (str, optional): ユーザーID
                email (str, optional): メールアドレス
            """
            sentry_sdk.set_user({
                "id": user_id,
                "email": email
            })
        
        return set_user_context
    
    # 本番環境以外またはSentry DSNがない場合はダミー関数を返す
    return lambda user_id=None, email=None: None

def log_performance_metric(metric_name, value, tags=None):
    """
    パフォーマンスメトリクスをログに記録
    
    Args:
        metric_name (str): メトリクス名
        value (float): メトリクス値
        tags (dict, optional): メトリクスに関連するタグ
    """
    try:
        sentry_sdk.set_measurement(metric_name, value, tags)
    except Exception:
        # Sentryが初期化されていない場合は何もしない
        pass

def track_transaction(transaction_name):
    """
    トランザクショントラッキングのためのデコレータ
    
    Args:
        transaction_name (str): トランザクション名
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                with sentry_sdk.start_transaction(name=transaction_name):
                    return await func(*args, **kwargs)
            except Exception as e:
                # エラーが発生した場合は通常通り処理を続行
                return await func(*args, **kwargs)
        return wrapper
    return decorator
