"""
OpenAI APIキーの有効性を確認するテストスクリプト
"""

import os
import sys
import logging
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

try:
    # OpenAIライブラリをインポート
    try:
        from openai import OpenAI
        logger.info("OpenAI APIクライアントライブラリ（新バージョン）を使用します")
        
        # APIクライアントを初期化
        client = OpenAI(api_key=api_key)
        
        # 簡単なAPIリクエストを実行
        logger.info("APIリクエストを送信中...")
        start_time = datetime.now()
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello, are you working?"}]
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"APIリクエスト成功（所要時間: {duration:.2f}秒）")
        logger.info(f"レスポンス: {response.choices[0].message.content}")
        logger.info("APIキーは有効です")
        
    except ImportError:
        # 古いバージョンのOpenAIライブラリを使用
        logger.info("OpenAI APIクライアントライブラリ（旧バージョン）を使用します")
        import openai
        
        # APIキーを設定
        openai.api_key = api_key
        
        # 簡単なAPIリクエストを実行
        logger.info("APIリクエストを送信中...")
        start_time = datetime.now()
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello, are you working?"}]
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"APIリクエスト成功（所要時間: {duration:.2f}秒）")
        logger.info(f"レスポンス: {response['choices'][0]['message']['content']}")
        logger.info("APIキーは有効です")

except Exception as e:
    logger.error(f"APIキーエラー: {e}")
    logger.error("APIキーが無効か、APIリクエストに問題があります")
    sys.exit(1)
