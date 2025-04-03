"""
OpenAI APIの接続状態を詳細に診断するテストスクリプト
"""

import os
import sys
import logging
import time
import socket
import subprocess
import platform
import json
from datetime import datetime

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("openai-api-test")

# .envファイルから環境変数を読み込む
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("環境変数を.envファイルから読み込みました")
except ImportError:
    logger.warning("python-dotenvがインストールされていないため、.envファイルからの読み込みをスキップします")

# OpenAI APIキーを取得
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logger.error("OPENAI_API_KEYが設定されていません")
    sys.exit(1)

logger.info(f"APIキー: {api_key[:5]}...{api_key[-5:]}")

# プロキシ設定の確認
http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
no_proxy = os.getenv("NO_PROXY") or os.getenv("no_proxy")

if http_proxy or https_proxy:
    logger.info(f"HTTP_PROXY: {http_proxy}")
    logger.info(f"HTTPS_PROXY: {https_proxy}")
    logger.info(f"NO_PROXY: {no_proxy}")
else:
    logger.info("プロキシ設定は見つかりませんでした")

# ネットワーク診断
def check_network():
    """ネットワーク接続状態を確認"""
    logger.info("ネットワーク診断を実行中...")
    
    # ホスト名解決
    try:
        openai_ip = socket.gethostbyname("api.openai.com")
        logger.info(f"api.openai.com のIPアドレス: {openai_ip}")
    except socket.gaierror as e:
        logger.error(f"ホスト名解決エラー: {e}")
        return False
    
    # pingテスト
    try:
        param = "-n" if platform.system().lower() == "windows" else "-c"
        command = ["ping", param, "1", "api.openai.com"]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Ping成功: api.openai.com に到達可能")
        else:
            logger.warning(f"Ping失敗: {result.stderr}")
    except Exception as e:
        logger.warning(f"Pingテスト実行エラー: {e}")
    
    return True

# OpenAI APIテスト
def test_openai_api():
    """OpenAI APIの各エンドポイントをテスト"""
    try:
        # OpenAIライブラリをインポート
        from openai import OpenAI
        logger.info("OpenAI APIクライアントライブラリを使用します")
        
        # APIクライアントを初期化（タイムアウト設定を追加）
        client = OpenAI(
            api_key=api_key,
            timeout=30.0  # 30秒のタイムアウト
        )
        
        # 1. チャット完了APIテスト
        logger.info("1. チャット完了APIリクエストを送信中...")
        start_time = time.time()
        
        try:
            chat_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello, are you working?"}],
                max_tokens=20
            )
            
            chat_duration = time.time() - start_time
            logger.info(f"チャット完了API: 成功 ({chat_duration:.2f}秒)")
            logger.info(f"レスポンス: {chat_response.choices[0].message.content}")
            chat_success = True
        except Exception as e:
            logger.error(f"チャット完了APIエラー: {type(e).__name__}: {e}")
            chat_success = False
        
        # 2. 埋め込みAPIテスト
        logger.info("2. 埋め込みAPIリクエストを送信中...")
        start_time = time.time()
        
        try:
            embedding_response = client.embeddings.create(
                model="text-embedding-3-small",
                input="Hello, world!"
            )
            
            embedding_duration = time.time() - start_time
            logger.info(f"埋め込みAPI: 成功 ({embedding_duration:.2f}秒)")
            logger.info(f"埋め込みベクトルの次元数: {len(embedding_response.data[0].embedding)}")
            embedding_success = True
        except Exception as e:
            logger.error(f"埋め込みAPIエラー: {type(e).__name__}: {e}")
            embedding_success = False
        
        # 3. モデル一覧APIテスト
        logger.info("3. モデル一覧APIリクエストを送信中...")
        start_time = time.time()
        
        try:
            models_response = client.models.list()
            
            models_duration = time.time() - start_time
            logger.info(f"モデル一覧API: 成功 ({models_duration:.2f}秒)")
            logger.info(f"利用可能なモデル数: {len(models_response.data)}")
            models_success = True
        except Exception as e:
            logger.error(f"モデル一覧APIエラー: {type(e).__name__}: {e}")
            models_success = False
        
        # 結果のサマリー
        logger.info("\n=== テスト結果サマリー ===")
        logger.info(f"チャット完了API: {'成功' if chat_success else '失敗'}")
        logger.info(f"埋め込みAPI: {'成功' if embedding_success else '失敗'}")
        logger.info(f"モデル一覧API: {'成功' if models_success else '失敗'}")
        
        if chat_success and embedding_success and models_success:
            logger.info("すべてのAPIテストが成功しました")
            return True
        else:
            logger.warning("一部のAPIテストが失敗しました")
            return False
            
    except ImportError as e:
        logger.error(f"OpenAIライブラリのインポートエラー: {e}")
        logger.error("pip install openai を実行してOpenAIライブラリをインストールしてください")
        return False
    except Exception as e:
        logger.error(f"予期しないエラー: {type(e).__name__}: {e}")
        return False

# メイン処理
if __name__ == "__main__":
    logger.info("=== OpenAI API接続診断ツール ===")
    
    # システム情報
    logger.info(f"OS: {platform.system()} {platform.release()}")
    logger.info(f"Python: {platform.python_version()}")
    
    # ネットワーク診断
    network_ok = check_network()
    if not network_ok:
        logger.error("ネットワーク診断に失敗しました。インターネット接続を確認してください。")
        sys.exit(1)
    
    # OpenAI APIテスト
    api_ok = test_openai_api()
    
    if api_ok:
        logger.info("OpenAI APIは正常に動作しています")
        sys.exit(0)
    else:
        logger.error("OpenAI APIテストに失敗しました")
        sys.exit(1)
