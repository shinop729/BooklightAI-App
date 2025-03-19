from fastapi import Request
from urllib.parse import urlparse, urljoin
import os
import logging
import socket

logger = logging.getLogger("booklight-api")

def sanitize_url(url: str) -> str:
    """
    URLを標準化し、安全性を確保する
    
    Args:
        url (str): 入力URL
    
    Returns:
        str: サニタイズされたURL
    """
    if not url:
        return ""
    
    # URLの先頭にスキーマがない場合は追加
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    # 末尾のスラッシュを削除
    url = url.rstrip('/')
    
    return url

def validate_url(url: str) -> bool:
    """
    URLの妥当性を検証する
    
    Args:
        url (str): 検証するURL
    
    Returns:
        bool: URLが有効な場合True、そうでない場合False
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

async def determine_frontend_url(request: Request) -> str:
    """
    複数の戦略を用いてフロントエンドURLを決定する
    
    Args:
        request (Request): FastAPIのリクエストオブジェクト
    
    Returns:
        str: 検出されたフロントエンドURL
    """
    # 戦略1: 環境変数からの設定値
    frontend_url = os.getenv('FRONTEND_URL')
    if frontend_url and validate_url(frontend_url):
        logger.info(f"フロントエンドURL（環境変数から）: {frontend_url}")
        return sanitize_url(frontend_url)
    
    # 戦略2: リクエストのオリジンヘッダー
    origin = request.headers.get("origin")
    if origin and validate_url(origin):
        logger.info(f"フロントエンドURL（オリジンヘッダーから）: {origin}")
        return sanitize_url(origin)
    
    # 戦略3: リクエストのリファラー
    referer = request.headers.get("referer")
    if referer and validate_url(referer):
        parsed_url = urlparse(referer)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        logger.info(f"フロントエンドURL（リファラーから）: {base_url}")
        return sanitize_url(base_url)
    
    # 戦略4: リクエストのベースURL
    try:
        host = str(request.base_url)
        
        # APIパスがある場合は削除
        for path in ['/auth/callback', '/auth/', '/api/']:
            if path in host:
                host = host.split(path)[0]
                break
        
        # ポート番号の調整
        parsed_url = urlparse(host)
        if parsed_url.port == 8000:
            if parsed_url.netloc.startswith('localhost:') or parsed_url.netloc.startswith('127.0.0.1:'):
                host = f"{parsed_url.scheme}://localhost:8501"
        
        if validate_url(host):
            logger.info(f"フロントエンドURL（リクエストから）: {host}")
            return sanitize_url(host)
    except Exception as e:
        logger.warning(f"リクエストからのURL検出に失敗: {e}")
    
    # 戦略5: Herokuアプリ名からの構築
    app_name = os.getenv("HEROKU_APP_NAME")
    if app_name:
        heroku_url = f"https://{app_name}.herokuapp.com"
        logger.info(f"フロントエンドURL（Herokuアプリ名から）: {heroku_url}")
        return sanitize_url(heroku_url)
    
    # 戦略6: ホスト名の自動検出
    try:
        hostname = socket.gethostname()
        # Herokuダイノの場合
        if hostname.startswith("dyno.") and os.getenv("DYNO"):
            dyno_id = os.getenv("DYNO")
            heroku_url = f"https://{dyno_id.split('.')[0]}.herokuapp.com"
            logger.info(f"フロントエンドURL（ダイノIDから）: {heroku_url}")
            return sanitize_url(heroku_url)
    except Exception as e:
        logger.warning(f"ホスト名からのURL検出に失敗: {e}")
    
    # フォールバック
    default_url = "http://localhost:8501"
    logger.warning(f"フロントエンドURLの検出に失敗。デフォルトを使用: {default_url}")
    return sanitize_url(default_url)
