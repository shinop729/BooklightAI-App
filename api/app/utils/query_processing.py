"""
クエリ処理関連のユーティリティ関数
"""
import logging
import time
import asyncio
import re
from typing import List

from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError
from app.config import settings

logger = logging.getLogger("booklight-api")

# OpenAIクライアントを初期化（モジュールレベルで共有）
# RAGServiceとは別に、キーワード抽出専用のクライアントを持つことも検討可能
# ここではシンプルにRAGServiceと同じキーを使用
# --- デバッグログ追加 ---
if not settings.OPENAI_API_KEY:
    logger.warning("Query Processing Init: OPENAI_API_KEY is empty before client initialization.")
else:
    logger.debug(f"Query Processing Init: Initializing OpenAI client with key starting with: {settings.OPENAI_API_KEY[:5]}...")
# --- デバッグログ追加ここまで ---
try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    logger.error(f"キーワード抽出用OpenAIクライアントの初期化に失敗: {e}")
    openai_client = None

async def extract_and_expand_keywords(query: str, max_keywords_per_concept: int = 3, model: str = "gpt-3.5-turbo") -> List[str]:
    """
    自然言語クエリから主要なキーワードを抽出し、それらの類義語や関連語も合わせて拡張する。

    Args:
        query: ユーザーからの自然言語クエリ
        max_keywords_per_concept: 抽出された主要概念ごとに含める類義語/関連語の最大数（目安）
        model: 使用するOpenAIモデル

    Returns:
        抽出・拡張されたキーワード（類義語含む）のフラットなリスト
    """
    if not openai_client:
        logger.error("OpenAIクライアントが初期化されていません。キーワード抽出・拡張をスキップします。")
        return []

    # リトライ設定
    max_retries = 3
    retry_count = 0
    retry_delay = 1  # 秒

    # プロンプトの定義
    # より多くのキーワードと類義語を抽出するように指示を変更
    prompt = f"""
    以下のユーザーの質問内容を分析し、書籍のハイライト検索に有効と思われる主要なキーワードや概念を特定してください。
    さらに、特定した各キーワードや概念について、その類義語や関連性の高い語句をいくつか挙げてください。
    最終的に、特定したキーワード、概念、およびそれらの類義語・関連語をすべて含んだリストを、カンマ区切りで出力してください。
    リスト全体で最大15個程度の単語・フレーズになるように調整してください。

    質問: {query}

    キーワードと関連語 (カンマ区切り):
    """

    while retry_count < max_retries:
        try:
            start_time = time.time()
            request_id = f"kw_expand_{int(start_time * 1000)}" # IDを変更
            logger.info(f"キーワード抽出・拡張開始 [ID:{request_id}]: '{query}' (試行: {retry_count+1}/{max_retries})")

            response = await asyncio.to_thread(
                openai_client.chat.completions.create,
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, # 少しだけ創造性を許容
                max_tokens=100,  # 類義語も含むためトークン数を増やす
                timeout=20.0,    # タイムアウトも少し延長
                # stop パラメータを削除
            )

            elapsed_time = time.time() - start_time
            logger.info(f"キーワード抽出・拡張成功 [ID:{request_id}]: 処理時間={elapsed_time:.2f}秒")

            raw_response = response.choices[0].message.content.strip()

            # 応答からキーワードリストを抽出 (カンマ区切りを想定)
            # 応答が予期せず複数行になる場合も考慮し、最初の行のみを使うか、全体を処理するか検討
            # ここではシンプルに全体をカンマで分割
            keywords_and_synonyms = [kw.strip() for kw in raw_response.split(',') if kw.strip()]

            # 重複を除去し、元の順序を維持
            unique_keywords = []
            seen = set()
            for kw in keywords_and_synonyms:
                if kw not in seen:
                    unique_keywords.append(kw)
                    seen.add(kw)

            # 必要であればここでさらにフィルタリングや最大数制限をかけることも可能
            # 例: unique_keywords = unique_keywords[:15]

            logger.info(f"抽出・拡張されたキーワード [ID:{request_id}]: {unique_keywords}")
            return unique_keywords

        except (APIConnectionError, RateLimitError, APIStatusError) as e:
            retry_count += 1
            error_type = type(e).__name__
            error_detail = str(e)
            logger.warning(f"キーワード抽出・拡張エラー [試行:{retry_count}/{max_retries}, ID:{request_id}]: {error_type} - {error_detail}")

            if isinstance(e, RateLimitError):
                logger.warning("レート制限エラーのため、リトライ待機時間を延長します。")
                retry_delay = max(retry_delay, 10) # レート制限時は最低10秒待つ

            if retry_count < max_retries:
                logger.info(f"キーワード抽出・拡張リトライ: {retry_delay}秒後に再試行します")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2 # 指数バックオフ
            else:
                logger.error(f"キーワード抽出・拡張失敗: 最大リトライ回数に達しました [ID:{request_id}] - {error_type}: {error_detail}")
                return [] # リトライ失敗時は空リストを返す

        except Exception as e:
            # 予期せぬエラー
            logger.error(f"予期せぬキーワード抽出・拡張エラー [ID:{request_id}]: {type(e).__name__} - {str(e)}")
            logger.error(f"Traceback: {asyncio.traceback.format_exc()}")
            return [] # 予期せぬエラー時も空リスト

    return [] # ループを抜けた場合 (通常は発生しないはず)

# --- 必要に応じて他のクエリ処理関数を追加 ---
