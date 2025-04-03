"""
クエリ拡張機能のテストスクリプト

このスクリプトは、BooklightAIアプリケーションのクエリ拡張機能と同じパラメータでOpenAI APIをテストします。
"""

import os
import sys
import logging
import time
import json
import re
import asyncio
from datetime import datetime

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("query-expansion-test")

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

# テスト用のクエリ
TEST_QUERIES = [
    "贈与について教えてください",
    "教育と好奇心の関係は",
    "戦略とは何か",
    "経済成長の要因",
    "哲学的思考の重要性"
]

# 基本的な同義語辞書（フォールバック用）
BASIC_SYNONYMS = {
    "贈与": "贈与 プレゼント ギフト 寄付 施し",
    "教育": "教育 学習 勉強 指導 教授",
    "戦略": "戦略 戦術 計画 方針 アプローチ",
    "経済": "経済 財政 金融 市場 ビジネス",
    "哲学": "哲学 思想 理念 概念 原理",
    "心理": "心理 精神 心 感情 意識"
}

async def expand_query(query: str, timeout: int = 10, retries: int = 3):
    """
    クエリを拡張する（rag.pyの_expand_queryメソッドと同様）
    
    Args:
        query: 検索クエリ
        timeout: タイムアウト秒数
        retries: リトライ回数
    
    Returns:
        拡張されたクエリ情報
    """
    # リトライ設定
    retry_count = 0
    retry_delay = 1  # 秒
    
    # クエリから主要キーワードを抽出（最長の単語を使用）
    main_keyword = max(query.split(), key=len) if query.split() else ""
    logger.info(f"主要キーワード: '{main_keyword}'")
    
    while retry_count < retries:
        try:
            # リクエスト開始時間を記録
            start_time = time.time()
            request_id = f"req_{int(start_time * 1000)}"
            
            logger.info(f"クエリ拡張開始 [ID:{request_id}]: '{query}' (試行: {retry_count+1}/{retries})")
            
            # OpenAIクライアントを初期化
            from openai import OpenAI
            client = OpenAI(api_key=api_key)

            # クエリ拡張プロンプト
            prompt = f"""
            元のクエリ: {query}

            このクエリに関連する以下の情報を提供してください:
            1. 類義語や関連キーワード（スペース区切り）
            2. クエリの言い換え（1つの文として）

            以下の形式で回答してください:
            {{
                "synonyms": "類義語1 類義語2 関連キーワード1 関連キーワード2",
                "reformulation": "クエリの言い換え"
            }}
            """

            # APIリクエスト
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150,
                timeout=timeout  # タイムアウト設定
            )

            # 処理時間を計算
            elapsed_time = time.time() - start_time
            logger.info(f"クエリ拡張成功 [ID:{request_id}]: 処理時間={elapsed_time:.2f}秒")

            result_text = response.choices[0].message.content
            logger.info(f"生のレスポンス: {result_text}")

            # JSON形式の抽出
            # JSON部分を抽出
            json_match = re.search(r'({.*})', result_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                    logger.info(f"パース結果: {result}")
                    return result
                except json.JSONDecodeError as e:
                    logger.warning(f"JSONデコードエラー [ID:{request_id}]: {e}")
                    pass

            # 正規表現でキーと値を抽出
            synonyms_match = re.search(r'"synonyms":\s*"([^"]*)"', result_text)
            reformulation_match = re.search(r'"reformulation":\s*"([^"]*)"', result_text)

            result = {}
            if synonyms_match:
                result["synonyms"] = synonyms_match.group(1)
            if reformulation_match:
                result["reformulation"] = reformulation_match.group(1)

            logger.info(f"正規表現抽出結果: {result}")
            return result

        except Exception as e:
            retry_count += 1
            error_type = type(e).__name__
            error_detail = str(e)
            
            logger.warning(f"クエリ拡張エラー [試行:{retry_count}/{retries}]: {error_type} - {error_detail}")
            
            if retry_count < retries:
                logger.info(f"クエリ拡張リトライ: {retry_delay}秒後に再試行します")
                await asyncio.sleep(retry_delay)
                # 次回のリトライで待機時間を増やす（指数バックオフ）
                retry_delay *= 2
            else:
                logger.error(f"クエリ拡張失敗: 最大リトライ回数に達しました - {error_type}: {error_detail}")
    
    # リトライ失敗時のフォールバック処理
    logger.warning(f"クエリ拡張フォールバック: 基本的な同義語辞書を使用します")
    
    # 基本的な同義語辞書からフォールバック値を取得
    result = {}
    
    # 主要キーワードが辞書にあればその同義語を使用
    for key in BASIC_SYNONYMS:
        if key in query:
            result["synonyms"] = BASIC_SYNONYMS[key]
            result["reformulation"] = f"{query}について詳しく教えてください"
            logger.info(f"フォールバック同義語を適用: '{key}' → '{result['synonyms']}'")
            return result
    
    # 辞書に一致するものがなければ空の結果を返す
    return {}

async def test_all_queries():
    """すべてのテストクエリを実行"""
    logger.info("=== クエリ拡張テスト開始 ===")
    
    results = []
    
    # 異なるタイムアウト設定でテスト
    timeouts = [10, 30, 60]
    
    for timeout in timeouts:
        logger.info(f"\n=== タイムアウト設定: {timeout}秒 ===")
        
        for query in TEST_QUERIES:
            logger.info(f"\nクエリ: '{query}'")
            
            start_time = time.time()
            try:
                result = await expand_query(query, timeout=timeout)
                success = bool(result)
                elapsed = time.time() - start_time
                
                results.append({
                    "query": query,
                    "timeout": timeout,
                    "success": success,
                    "elapsed": elapsed,
                    "result": result
                })
                
                logger.info(f"結果: {'成功' if success else '失敗'} ({elapsed:.2f}秒)")
                if success:
                    logger.info(f"類義語: {result.get('synonyms', '')}")
                    logger.info(f"言い換え: {result.get('reformulation', '')}")
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"テストエラー: {type(e).__name__}: {e} ({elapsed:.2f}秒)")
                results.append({
                    "query": query,
                    "timeout": timeout,
                    "success": False,
                    "elapsed": elapsed,
                    "error": str(e)
                })
            
            # 連続リクエストの間隔を空ける
            await asyncio.sleep(1)
    
    # 結果のサマリー
    logger.info("\n=== テスト結果サマリー ===")
    
    for timeout in timeouts:
        timeout_results = [r for r in results if r["timeout"] == timeout]
        success_count = sum(1 for r in timeout_results if r["success"])
        avg_time = sum(r["elapsed"] for r in timeout_results) / len(timeout_results) if timeout_results else 0
        
        logger.info(f"タイムアウト {timeout}秒: {success_count}/{len(timeout_results)} 成功 (平均 {avg_time:.2f}秒)")
    
    return results

# メイン処理
if __name__ == "__main__":
    asyncio.run(test_all_queries())
