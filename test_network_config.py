"""
ネットワーク設定診断スクリプト

このスクリプトは、アプリケーションの実行環境でのネットワーク設定を診断します。
"""

import os
import sys
import logging
import socket
import subprocess
import platform
import requests
import json
import time
from urllib.parse import urlparse

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("network-config-test")

def check_environment_variables():
    """環境変数の確認"""
    logger.info("=== 環境変数の確認 ===")
    
    # プロキシ関連の環境変数
    proxy_vars = [
        "HTTP_PROXY", "http_proxy",
        "HTTPS_PROXY", "https_proxy",
        "NO_PROXY", "no_proxy"
    ]
    
    for var in proxy_vars:
        value = os.environ.get(var)
        if value:
            logger.info(f"{var}: {value}")
    
    # OpenAI API関連の環境変数
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        logger.info(f"OPENAI_API_KEY: {api_key[:5]}...{api_key[-5:]}")
    else:
        logger.warning("OPENAI_API_KEY が設定されていません")
    
    # その他の関連環境変数
    other_vars = [
        "OPENAI_API_BASE", "OPENAI_ORGANIZATION",
        "PYTHONPATH", "PATH"
    ]
    
    for var in other_vars:
        value = os.environ.get(var)
        if value:
            logger.info(f"{var}: {value}")

def check_dns_resolution():
    """DNS解決の確認"""
    logger.info("\n=== DNS解決の確認 ===")
    
    domains = [
        "api.openai.com",
        "google.com",
        "github.com"
    ]
    
    for domain in domains:
        try:
            ip_address = socket.gethostbyname(domain)
            logger.info(f"{domain} -> {ip_address}")
        except socket.gaierror as e:
            logger.error(f"{domain} の解決に失敗: {e}")

def check_connectivity():
    """接続性の確認"""
    logger.info("\n=== 接続性の確認 ===")
    
    # pingテスト
    domains = [
        "api.openai.com",
        "google.com",
        "github.com"
    ]
    
    for domain in domains:
        try:
            param = "-n" if platform.system().lower() == "windows" else "-c"
            command = ["ping", param, "1", domain]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Ping成功: {domain}")
            else:
                logger.warning(f"Ping失敗: {domain} - {result.stderr}")
        except Exception as e:
            logger.warning(f"Pingテスト実行エラー ({domain}): {e}")
    
    # HTTPリクエストテスト
    urls = [
        "https://api.openai.com/v1/models",
        "https://www.google.com",
        "https://github.com"
    ]
    
    for url in urls:
        try:
            start_time = time.time()
            response = requests.head(url, timeout=5)
            elapsed = time.time() - start_time
            
            logger.info(f"HTTP接続成功: {url} - ステータスコード: {response.status_code} ({elapsed:.2f}秒)")
        except Exception as e:
            logger.error(f"HTTP接続失敗: {url} - {type(e).__name__}: {e}")

def check_proxy_settings():
    """プロキシ設定の確認"""
    logger.info("\n=== プロキシ設定の確認 ===")
    
    # 環境変数からプロキシ設定を取得
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    
    if http_proxy or https_proxy:
        logger.info(f"HTTP_PROXY: {http_proxy}")
        logger.info(f"HTTPS_PROXY: {https_proxy}")
        
        # プロキシURLの解析
        proxy_url = http_proxy or https_proxy
        try:
            parsed = urlparse(proxy_url)
            proxy_host = parsed.hostname
            proxy_port = parsed.port
            
            logger.info(f"プロキシホスト: {proxy_host}")
            logger.info(f"プロキシポート: {proxy_port}")
            
            # プロキシサーバーへの接続テスト
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((proxy_host, proxy_port))
                if result == 0:
                    logger.info(f"プロキシサーバーに接続可能: {proxy_host}:{proxy_port}")
                else:
                    logger.warning(f"プロキシサーバーに接続できません: {proxy_host}:{proxy_port}")
                sock.close()
            except Exception as e:
                logger.error(f"プロキシ接続テストエラー: {e}")
        except Exception as e:
            logger.error(f"プロキシURL解析エラー: {e}")
    else:
        logger.info("プロキシ設定は見つかりませんでした")

def check_openai_api_rate_limits():
    """OpenAI APIのレート制限確認"""
    logger.info("\n=== OpenAI APIレート制限の確認 ===")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEYが設定されていないため、レート制限を確認できません")
        return
    
    try:
        # OpenAIのモデル一覧APIを呼び出し、レスポンスヘッダーを確認
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            # レート制限関連のヘッダーを確認
            rate_limit_headers = {
                "x-ratelimit-limit-requests": "リクエスト数の制限",
                "x-ratelimit-remaining-requests": "残りのリクエスト数",
                "x-ratelimit-limit-tokens": "トークン数の制限",
                "x-ratelimit-remaining-tokens": "残りのトークン数",
                "x-ratelimit-reset-requests": "リクエスト制限のリセット時間",
                "x-ratelimit-reset-tokens": "トークン制限のリセット時間"
            }
            
            logger.info("レート制限ヘッダー:")
            for header, description in rate_limit_headers.items():
                value = response.headers.get(header)
                if value:
                    logger.info(f"  {header}: {value} ({description})")
                else:
                    logger.info(f"  {header}: 情報なし ({description})")
        else:
            logger.warning(f"APIリクエスト失敗: ステータスコード {response.status_code}")
            logger.warning(f"レスポンス: {response.text}")
    
    except Exception as e:
        logger.error(f"レート制限確認エラー: {type(e).__name__}: {e}")

def check_network_interfaces():
    """ネットワークインターフェースの確認"""
    logger.info("\n=== ネットワークインターフェースの確認 ===")
    
    try:
        # ネットワークインターフェース情報の取得
        if platform.system() == "Windows":
            command = ["ipconfig"]
        else:
            command = ["ifconfig"]
        
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            # 出力が長すぎる場合は省略
            output = result.stdout
            if len(output) > 1000:
                output = output[:1000] + "... (省略)"
            logger.info(f"ネットワークインターフェース情報:\n{output}")
        else:
            logger.warning(f"ネットワークインターフェース情報の取得に失敗: {result.stderr}")
    except Exception as e:
        logger.error(f"ネットワークインターフェース確認エラー: {e}")

def check_parallel_requests():
    """並列リクエストのテスト"""
    logger.info("\n=== 並列リクエストのテスト ===")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEYが設定されていないため、並列リクエストテストを実行できません")
        return
    
    import concurrent.futures
    
    def make_request():
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5
            }
            
            start_time = time.time()
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=10
            )
            elapsed = time.time() - start_time
            
            return {
                "status_code": response.status_code,
                "elapsed": elapsed,
                "success": response.status_code == 200
            }
        except Exception as e:
            return {
                "error": str(e),
                "type": type(e).__name__,
                "success": False
            }
    
    # 5つの並列リクエストを実行
    num_requests = 5
    logger.info(f"{num_requests}個の並列リクエストを実行中...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(make_request) for _ in range(num_requests)]
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            results.append(result)
            if result.get("success"):
                logger.info(f"リクエスト {i+1}: 成功 (ステータスコード: {result.get('status_code')}, 時間: {result.get('elapsed'):.2f}秒)")
            else:
                logger.warning(f"リクエスト {i+1}: 失敗 (エラー: {result.get('error')})")
    
    # 結果のサマリー
    success_count = sum(1 for r in results if r.get("success"))
    logger.info(f"並列リクエスト結果: {success_count}/{num_requests} 成功")

# メイン処理
if __name__ == "__main__":
    logger.info("=== ネットワーク設定診断ツール ===")
    logger.info(f"OS: {platform.system()} {platform.release()}")
    logger.info(f"Python: {platform.python_version()}")
    
    check_environment_variables()
    check_dns_resolution()
    check_connectivity()
    check_proxy_settings()
    check_openai_api_rate_limits()
    check_network_interfaces()
    check_parallel_requests()
