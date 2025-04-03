#!/usr/bin/env python
"""
ハイライトの埋め込みベクトルを事前計算するスクリプト

このスクリプトは、ユーザーのハイライトデータを読み込み、
埋め込みベクトルを事前計算してデータベースに保存します。
これにより、検索時のパフォーマンスが向上します。

使用方法:
python -m api.scripts.precompute_embeddings [--user_id USER_ID] [--batch_size BATCH_SIZE]

オプション:
  --user_id USER_ID      特定のユーザーのみ処理する場合のユーザーID
  --batch_size BATCH_SIZE  バッチサイズ（デフォルト: 50）
"""

import os
import sys
import logging
import pickle
import argparse
import asyncio
import time
from typing import List, Optional
from sqlalchemy.orm import Session
from pathlib import Path

# プロジェクトルートを追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.base import SessionLocal
import database.models as models
from app.config import settings

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('precompute_embeddings.log')
    ]
)
logger = logging.getLogger("precompute-embeddings")

async def generate_embedding(text: str):
    """テキストの埋め込みを生成"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"埋め込み生成エラー: {e}")
        return None

async def process_user(user_id: int, batch_size: int = 50):
    """ユーザーのハイライトを処理"""
    db = SessionLocal()
    try:
        # ユーザーのハイライトを取得
        highlights = db.query(models.Highlight).filter(
            models.Highlight.user_id == user_id
        ).all()
        
        logger.info(f"ユーザーID {user_id} のハイライト数: {len(highlights)}")
        
        if not highlights:
            logger.warning(f"ユーザーID {user_id} のハイライトが見つかりません")
            return 0
        
        # 既に埋め込みが生成されているハイライトを除外
        existing_embeddings = db.query(models.HighlightEmbedding.highlight_id).all()
        existing_ids = {e[0] for e in existing_embeddings}
        
        highlights_to_process = [h for h in highlights if h.id not in existing_ids]
        logger.info(f"処理対象のハイライト: {len(highlights_to_process)}/{len(highlights)}件")
        
        if not highlights_to_process:
            logger.info(f"ユーザーID {user_id} の全てのハイライトは既に処理済みです")
            return 0
        
        # バッチ処理
        total_processed = 0
        start_time = time.time()
        
        for i in range(0, len(highlights_to_process), batch_size):
            batch = highlights_to_process[i:i+batch_size]
            logger.info(f"バッチ処理中: {i+1} ~ {i+len(batch)}/{len(highlights_to_process)}件")
            
            batch_start_time = time.time()
            for highlight in batch:
                embedding = await generate_embedding(highlight.content)
                if embedding:
                    # 埋め込みをキャッシュに保存
                    new_cache = models.HighlightEmbedding(
                        highlight_id=highlight.id,
                        embedding=pickle.dumps(embedding)
                    )
                    db.add(new_cache)
                    total_processed += 1
            
            # バッチごとにコミット
            db.commit()
            
            batch_time = time.time() - batch_start_time
            logger.info(f"バッチ完了: {len(batch)}件処理 ({batch_time:.2f}秒, {batch_time/len(batch):.2f}秒/件)")
        
        total_time = time.time() - start_time
        logger.info(f"処理完了: ユーザーID {user_id} の {total_processed}/{len(highlights)}件のハイライトの埋め込みを生成 (合計: {total_time:.2f}秒, 平均: {total_time/total_processed if total_processed else 0:.2f}秒/件)")
        
        return total_processed
    
    except Exception as e:
        logger.error(f"ユーザー処理エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
        db.rollback()
        return 0
    finally:
        db.close()

async def process_all_users(batch_size: int = 50):
    """全ユーザーのハイライトを処理"""
    db = SessionLocal()
    try:
        # 全ユーザーのリストを取得
        users = db.query(models.User).all()
        logger.info(f"ユーザー数: {len(users)}")
        
        total_processed = 0
        
        # 各ユーザーを処理
        for user in users:
            logger.info(f"ユーザー処理開始: {user.username} (ID: {user.id})")
            processed = await process_user(user.id, batch_size)
            total_processed += processed
        
        logger.info(f"全ユーザー処理完了: 合計 {total_processed}件のハイライトの埋め込みを生成")
    
    except Exception as e:
        logger.error(f"処理エラー: {e}")
        import traceback
        logger.error(f"詳細エラー: {traceback.format_exc()}")
    finally:
        db.close()

def parse_args():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(description='ハイライトの埋め込みベクトルを事前計算するスクリプト')
    parser.add_argument('--user_id', type=int, help='特定のユーザーのみ処理する場合のユーザーID')
    parser.add_argument('--batch_size', type=int, default=50, help='バッチサイズ（デフォルト: 50）')
    return parser.parse_args()

async def main():
    """メイン処理"""
    args = parse_args()
    
    logger.info("埋め込みベクトル事前計算処理を開始します")
    
    # OpenAI APIキーの確認
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEYが設定されていません")
        return
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=5
        )
        logger.info(f"OpenAI APIキーは有効です: {response.model}")
    except Exception as e:
        logger.error(f"OpenAI APIキーエラー: {e}")
        return
    
    # 特定のユーザーのみ処理するか、全ユーザーを処理するか
    if args.user_id:
        logger.info(f"ユーザーID {args.user_id} のハイライトを処理します")
        await process_user(args.user_id, args.batch_size)
    else:
        logger.info("全ユーザーのハイライトを処理します")
        await process_all_users(args.batch_size)
    
    logger.info("埋め込みベクトル事前計算処理が完了しました")

if __name__ == "__main__":
    asyncio.run(main())
