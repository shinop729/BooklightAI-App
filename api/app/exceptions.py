import uuid
import logging
import traceback
from fastapi import HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# カスタム例外クラス
class AuthenticationError(Exception):
    """認証関連のエラー"""
    pass

class ConfigurationError(Exception):
    """設定関連のエラー"""
    pass

class DataValidationError(Exception):
    """データ検証エラー"""
    pass

# エラーレスポンスモデル
class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    detail: str = None
    reference_id: str = None
    code: str = None

async def notify_error(error_type: str, message: str, details: str = None):
    """重大なエラーを通知（本番環境用）"""
    from .config import settings
    
    # 本番環境チェック
    if settings.ENVIRONMENT != "production":
        return
    
    # エラー参照ID
    error_id = str(uuid.uuid4())
    
    # 基本的なログ記録
    logger = logging.getLogger("booklight-api")
    logger.critical(f"重大なエラー [{error_id}]: {error_type} - {message}")
    
    # ここに実際の通知ロジックを追加
    # 例: Slack通知、メール送信、エラー追跡システム連携など
    
    return error_id

def create_error_response(
    message: str, 
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, 
    detail: str = None, 
    code: str = "INTERNAL_ERROR"
):
    """エラーレスポンスを生成"""
    from .config import settings
    
    # 本番環境では詳細情報を隠蔽
    if settings.ENVIRONMENT == "production":
        detail = None
    
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            message=message,
            detail=detail,
            reference_id=str(uuid.uuid4()),
            code=code
        ).dict()
    )

def setup_exception_handlers(app):
    """FastAPIアプリケーションに例外ハンドラを追加"""
    
    @app.exception_handler(AuthenticationError)
    async def auth_exception_handler(request: Request, exc: AuthenticationError):
        """認証エラーハンドラー"""
        logger = logging.getLogger("booklight-api")
        logger.warning(f"認証エラー: {str(exc)}")
        
        return create_error_response(
            message="認証に失敗しました。ログイン情報を確認してください。",
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            code="AUTH_ERROR"
        )

    @app.exception_handler(ConfigurationError)
    async def config_exception_handler(request: Request, exc: ConfigurationError):
        """設定エラーハンドラー"""
        logger = logging.getLogger("booklight-api")
        logger.error(f"設定エラー: {str(exc)}")
        logger.error(traceback.format_exc())
        
        # 本番環境では管理者に通知
        error_id = await notify_error("CONFIG_ERROR", str(exc), traceback.format_exc())
        
        return create_error_response(
            message="アプリケーションの設定に問題があります。管理者にお問い合わせください。",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=None,
            code="CONFIG_ERROR"
        )

    @app.exception_handler(DataValidationError)
    async def validation_exception_handler(request: Request, exc: DataValidationError):
        """データ検証エラーハンドラー"""
        logger = logging.getLogger("booklight-api")
        logger.info(f"データ検証エラー: {str(exc)}")
        
        return create_error_response(
            message="入力データが無効です。",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            code="VALIDATION_ERROR"
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """一般的な例外ハンドラー"""
        logger = logging.getLogger("booklight-api")
        logger.error(f"予期しないエラー: {str(exc)}")
        logger.error(traceback.format_exc())
        
        # 重大なエラーかどうかを判断
        is_critical = isinstance(exc, (KeyError, AttributeError, TypeError, IOError))
        
        # 本番環境で重大なエラーの場合は通知
        error_id = None
        from .config import settings
        if is_critical and settings.ENVIRONMENT == "production":
            error_id = await notify_error("CRITICAL_ERROR", str(exc), traceback.format_exc())
        
        return create_error_response(
            message="予期しないエラーが発生しました。後でもう一度お試しください。",
            detail=str(exc) if settings.ENVIRONMENT != "production" else None
        )
