"""
Cross Point機能の実装

このモジュールは、ユーザーの異なる書籍から選ばれた2つのハイライトを
意外な視点で関連付け、「マジックモーメント」を提供する機能を実装します。
"""

import os
import random
import logging
import pickle
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, Union

from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import openai

import database.models as models
from app.config import settings

# ロガーの設定
logger = logging.getLogger("booklight-api")

class CrossPointService:
    """Cross Point生成サービス"""
    
    def __init__(self, db: Session, user_id: int):
        """
        CrossPointServiceの初期化
        
        Args:
            db: SQLAlchemyのセッション
            user_id: ユーザーID
        """
        self.db = db
        self.user_id = user_id
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def get_daily_cross_point(self, force_generate: bool = False) -> Optional[Dict[str, Any]]:
        """
        日次のCross Pointを取得する

        Args:
            force_generate: Trueの場合、既存の今日のCross Pointを無視して強制的に再生成する
        
        Returns:
            Cross Pointの情報を含む辞書、または存在しない場合はNone
        """
        logger.debug(f"[CrossPoint] get_daily_cross_point開始: user_id={self.user_id}")
        # 今日の日付
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # force_generateがFalseの場合のみ、既存のCross Pointを確認
        if not force_generate:
            logger.debug(f"[CrossPoint] 既存のCross Pointを確認中: user_id={self.user_id}, date={today}")
            daily_conn = self.db.query(models.CrossPoint).filter(
                models.CrossPoint.user_id == self.user_id,
                models.CrossPoint.created_at.between(today_start, today_end)
            ).first()

            # 既存のCross Pointがあればそれを返す
            if daily_conn:
                logger.info(f"[CrossPoint] 既存のCross Pointが見つかりました（force_generate=False）: user_id={self.user_id}, cross_point_id={daily_conn.id}")
                formatted_response = self._format_cross_point_response(daily_conn)
                if formatted_response is None:
                     logger.error(f"[CrossPoint] 既存Cross Pointのフォーマットに失敗: cross_point_id={daily_conn.id}")
                     # ここでエラーを返すか、Noneを返すか検討。今回はNoneを返す。
                     return None
                return formatted_response
        else:
             logger.info(f"[CrossPoint] 強制生成フラグ(force_generate=True)のため、既存チェックをスキップ: user_id={self.user_id}")

        # 新しいCross Pointを生成
        logger.info(f"[CrossPoint] 新しいCross Pointの生成を開始します: user_id={self.user_id}")
        
        # ハイライト選択（複数の方法を試す）
        logger.debug(f"[CrossPoint] ハイライト選択プロセス開始: user_id={self.user_id}")
        selection_method = "不明"
        # highlights 変数は List[Tuple[Highlight, Highlight]] または List[Highlight] を想定
        highlights: Optional[Union[List[Tuple[models.Highlight, models.Highlight]], List[models.Highlight]]] = None 
        
        # 方法1: セマンティック距離による選択
        logger.debug(f"[CrossPoint] ハイライト選択試行1: セマンティック距離")
        highlights = await self._select_semantic_distant_highlights()
        if highlights:
            selection_method = "セマンティック距離"
            # highlights は List[Tuple[Highlight, Highlight]] のはず
            if isinstance(highlights, list) and len(highlights) > 0 and isinstance(highlights[0], tuple) and len(highlights[0]) == 2:
                 logger.info(f"[CrossPoint] ハイライト選択成功 (セマンティック距離): user_id={self.user_id}, h1={highlights[0][0].id}, h2={highlights[0][1].id}")
            else:
                 logger.warning(f"[CrossPoint] セマンティック距離選択結果の型が不正: type={type(highlights)}")
                 highlights = None # 不正な場合はNoneに戻す
        
        # 方法1で失敗した場合、方法2: トピック多様性による選択
        if not highlights:
            logger.debug(f"[CrossPoint] ハイライト選択試行2: トピック多様性")
            highlights = await self._select_topic_diverse_highlights()
            if highlights: # highlightsがNoneでないことを確認
                selection_method = "トピック多様性"
                logger.info(f"[CrossPoint] ハイライト選択成功 (トピック多様性): user_id={self.user_id}, h1={highlights[0].id}, h2={highlights[1].id}")
        
        # 方法2で失敗した場合、方法3: ジャンル対比による選択
        if not highlights:
            logger.debug(f"[CrossPoint] ハイライト選択試行3: ジャンル対比")
            highlights = await self._select_genre_diverse_highlights()
            if highlights: # highlightsがNoneでないことを確認
                selection_method = "ジャンル対比"
                logger.info(f"[CrossPoint] ハイライト選択成功 (ジャンル対比): user_id={self.user_id}, h1={highlights[0].id}, h2={highlights[1].id}")
        
        # 全て失敗した場合、方法4: ランダム選択
        if not highlights:
            logger.debug(f"[CrossPoint] ハイライト選択試行4: ランダム")
            highlights = self._select_random_highlights()
            if highlights: # highlightsがNoneでないことを確認
                selection_method = "ランダム"
                logger.info(f"[CrossPoint] ハイライト選択成功 (ランダム): user_id={self.user_id}, h1={highlights[0].id}, h2={highlights[1].id}")
        
        # ハイライトが選択できなかった場合
        if not highlights: 
            logger.warning(f"[CrossPoint] 全てのハイライト選択方法で失敗しました: user_id={self.user_id}")
            return None
            
        # ★ 返り値の型が変更されていることに注意 (List[Tuple[Highlight, Highlight]] or List[Highlight])
        # highlights 変数がペアのリストか、単一ペアのリスト(要素2)か判定が必要
        candidate_pairs: List[Tuple[models.Highlight, models.Highlight]] = []
        if selection_method == "セマンティック距離" and isinstance(highlights, list) and len(highlights) > 0 and isinstance(highlights[0], tuple):
             # _select_semantic_distant_highlights からの返り値 (ペアのリスト)
             candidate_pairs = highlights
             logger.info(f"[CrossPoint] セマンティック距離から {len(candidate_pairs)} 個の候補ペアを取得")
        elif isinstance(highlights, list) and len(highlights) == 2 and all(isinstance(h, models.Highlight) for h in highlights):
             # 他のメソッドからの返り値 (単一ペア) - 型チェックを厳密に
             candidate_pairs = [(highlights[0], highlights[1])]
             logger.info(f"[CrossPoint] {selection_method} から 1 個の候補ペアを取得")
        else:
             logger.warning(f"[CrossPoint] 予期しないハイライト選択結果の型: type={type(highlights)}, content={highlights}")
             return None # 候補がない場合は終了

        # 各候補ペアに対してCross Pointテキストを生成
        generated_candidates = []
        logger.info(f"[CrossPoint] {len(candidate_pairs)} 個の候補ペアからCross Pointテキスト生成開始")
        for i, (h1, h2) in enumerate(candidate_pairs):
            logger.debug(f"[CrossPoint] 候補 {i+1}/{len(candidate_pairs)} のテキスト生成中 (h1={h1.id}, h2={h2.id})")
            text_result = await self._generate_cross_point_text(h1, h2)
            if text_result:
                title, description = text_result
                generated_candidates.append({
                    "highlight1": h1,
                    "highlight2": h2,
                    "title": title,
                    "description": description
                })
                logger.debug(f"[CrossPoint] 候補 {i+1} テキスト生成成功: title='{title}'")
            else:
                logger.warning(f"[CrossPoint] 候補 {i+1} テキスト生成失敗 (h1={h1.id}, h2={h2.id})")

        if not generated_candidates:
            logger.error(f"[CrossPoint] 全ての候補ペアでCross Pointテキスト生成に失敗: user_id={self.user_id}")
            return None

        # 最も良い候補を選択 (ここでは説明文の長さで選択)
        logger.info(f"[CrossPoint] {len(generated_candidates)} 個の生成済み候補からベストを選択中...")
        best_candidate = max(generated_candidates, key=lambda c: len(c.get("description", "")))
        logger.info(f"[CrossPoint] ベスト候補を選択: h1={best_candidate['highlight1'].id}, h2={best_candidate['highlight2'].id}, title='{best_candidate['title']}'")

        # ベスト候補をDBに保存
        logger.debug(f"[CrossPoint] ベスト候補のCross PointをDBに保存開始: user_id={self.user_id}")
        # _save_cross_point 関数を呼び出す
        final_result = await self._save_cross_point(
            best_candidate["highlight1"],
            best_candidate["highlight2"],
            best_candidate["title"],
            best_candidate["description"]
        )
            
        logger.debug(f"[CrossPoint] get_daily_cross_point終了: user_id={self.user_id}")
        return final_result
    
    async def _select_semantic_distant_highlights(self) -> Optional[List[Tuple[models.Highlight, models.Highlight]]]: # 返り値の型ヒントを修正
        """
        セマンティック距離によるハイライト選択
        
        異なる書籍から、埋め込みベクトル間のコサイン距離が大きい（意味的に遠い）
        ハイライトのペアを上位N件選択します。
        
        Returns:
            選択されたハイライトペアのリスト(上位N件)、または失敗した場合はNone
        """
        logger.debug(f"[CrossPoint] _select_semantic_distant_highlights開始: user_id={self.user_id}")
        try:
            # ユーザーのハイライトを取得
            logger.debug(f"[CrossPoint] ユーザーの全ハイライトを取得中...")
            highlights = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id
            ).all()
            logger.debug(f"[CrossPoint] ハイライト取得完了: {len(highlights)}件")
            
            if len(highlights) < 10:
                logger.info(f"[CrossPoint] ハイライト数が10件未満のため、セマンティック距離選択をスキップ: user_id={self.user_id}, count={len(highlights)}")
                return None
            
            # ハイライトとその埋め込みを取得
            logger.debug(f"[CrossPoint] ハイライトの埋め込みを取得/生成中...")
            highlight_embeddings = {}
            for highlight in highlights:
                # 埋め込みキャッシュを確認
                embedding_cache = self.db.query(models.HighlightEmbedding).filter(
                    models.HighlightEmbedding.highlight_id == highlight.id
                ).first()
                logger.debug(f"[CrossPoint] ハイライトID {highlight.id} の埋め込みを確認中...")
                if embedding_cache:
                    # キャッシュから埋め込みを取得
                    logger.debug(f"[CrossPoint] ハイライトID {highlight.id} の埋め込みをキャッシュから取得")
                    embedding = pickle.loads(embedding_cache.embedding)
                else:
                    # 新しく埋め込みを生成
                    logger.debug(f"[CrossPoint] ハイライトID {highlight.id} の埋め込みを生成中...")
                    embedding = await self._generate_embedding(highlight.content)
                    if embedding:
                        # 埋め込みをキャッシュに保存
                        logger.debug(f"[CrossPoint] ハイライトID {highlight.id} の埋め込みをキャッシュに保存")
                        new_cache = models.HighlightEmbedding(
                            highlight_id=highlight.id,
                            embedding=pickle.dumps(embedding)
                        )
                        try:
                            self.db.add(new_cache)
                            self.db.commit()
                        except Exception as commit_error:
                            logger.error(f"[CrossPoint] 埋め込みキャッシュ保存エラー: {commit_error}")
                            self.db.rollback()
                            continue # 保存失敗時はスキップ
                    else:
                        logger.warning(f"[CrossPoint] ハイライトID {highlight.id} の埋め込み生成に失敗")
                        continue  # 埋め込み生成に失敗した場合はスキップ
                
                # 書籍IDをキーとしてハイライトをグループ化
                logger.debug(f"[CrossPoint] ハイライトID {highlight.id} を書籍ID {highlight.book_id} でグループ化")
                book_id = highlight.book_id
                if book_id not in highlight_embeddings:
                    highlight_embeddings[book_id] = []
                
                highlight_embeddings[book_id].append((highlight, embedding))
            logger.debug(f"[CrossPoint] 埋め込み取得/生成完了。グループ化された書籍数: {len(highlight_embeddings)}")
            
            # 書籍が2冊未満の場合は中止
            if len(highlight_embeddings) < 2:
                logger.info(f"[CrossPoint] 書籍数が2冊未満のため、セマンティック距離選択をスキップ: user_id={self.user_id}, count={len(highlight_embeddings)}")
                return None
            
            # 異なる書籍からハイライトを1つずつランダムに選択
            logger.debug(f"[CrossPoint] 異なる書籍から2冊を選択中...")
            book_ids = list(highlight_embeddings.keys())
            random.shuffle(book_ids)
            book_id1, book_id2 = book_ids[:2]
            logger.debug(f"[CrossPoint] 選択された書籍ID: {book_id1}, {book_id2}")
            
            # 各書籍から最大10個のハイライトをサンプリング
            logger.debug(f"[CrossPoint] 各書籍から最大10件のハイライトをサンプリング中...")
            highlights1 = highlight_embeddings[book_id1]
            highlights2 = highlight_embeddings[book_id2]
            
            sample_size = 10
            if len(highlights1) > sample_size:
                highlights1 = random.sample(highlights1, sample_size)
            if len(highlights2) > sample_size:
                highlights2 = random.sample(highlights2, sample_size)
            logger.debug(f"[CrossPoint] サンプリング結果: 書籍1={len(highlights1)}件, 書籍2={len(highlights2)}件")

            # 距離が遠い上位Nペアの候補を探す
            NUM_CANDIDATES = 3 # 候補数を定義
            logger.debug(f"[CrossPoint] 距離が遠い上位{NUM_CANDIDATES}ペアのハイライト候補を探索中...")
            candidate_pairs: List[Tuple[float, models.Highlight, models.Highlight]] = [] # (distance, h1, h2) を格納
            num_comparisons = 0

            for h1, e1 in highlights1:
                for h2, e2 in highlights2:
                    num_comparisons += 1
                    distance = self._cosine_distance(e1, e2)
                    
                    # 候補リストに追加・更新
                    if len(candidate_pairs) < NUM_CANDIDATES:
                        candidate_pairs.append((distance, h1, h2))
                        candidate_pairs.sort(key=lambda x: x[0], reverse=True) # 距離で降順ソート
                    elif distance > candidate_pairs[-1][0]: # 現在の最小距離より大きい場合
                        candidate_pairs.pop() # 最小距離のペアを削除
                        candidate_pairs.append((distance, h1, h2))
                        candidate_pairs.sort(key=lambda x: x[0], reverse=True) # 再度ソート

            logger.debug(f"[CrossPoint] 探索完了: 比較回数={num_comparisons}, 候補数={len(candidate_pairs)}")

            if candidate_pairs:
                # 距離情報を除き、ハイライトペアのリストを返す
                top_highlight_pairs = [(h1, h2) for distance, h1, h2 in candidate_pairs]
                # 変数名を修正 (p -> p1, p2)
                log_details = ", ".join([f"(h1={p1.id}, h2={p2.id}, dist={d:.4f})" for d, p1, p2 in candidate_pairs])
                logger.info(f"[CrossPoint] _select_semantic_distant_highlights成功: user_id={self.user_id}, 候補ペア={log_details}")
                # ★注意: 返り値の型が List[Tuple[Highlight, Highlight]] に変わる
                return top_highlight_pairs 
            else:
                logger.warning(f"[CrossPoint] _select_semantic_distant_highlights失敗: 候補ペアが見つかりませんでした, user_id={self.user_id}")
                return None
        # Correct indentation for the except block
        except Exception as e:
            logger.error(f"[CrossPoint] _select_semantic_distant_highlightsエラー: {e}", exc_info=True)
            return None
    
    async def _select_topic_diverse_highlights(self) -> Optional[List[models.Highlight]]:
        """
        トピック多様性によるハイライト選択
        
        異なる書籍から、ランダムにハイライトを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        logger.debug(f"[CrossPoint] _select_topic_diverse_highlights開始: user_id={self.user_id}")
        try:
            # ユーザーのハイライトを取得
            logger.debug(f"[CrossPoint] ユーザーの全ハイライトを取得中...")
            highlights = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id
            ).all()
            logger.debug(f"[CrossPoint] ハイライト取得完了: {len(highlights)}件")
            
            if len(highlights) < 5:
                logger.info(f"[CrossPoint] ハイライト数が5件未満のため、トピック多様性選択をスキップ: user_id={self.user_id}, count={len(highlights)}")
                return None
            
            # 書籍情報の取得
            logger.debug(f"[CrossPoint] ハイライトから書籍情報を取得中...")
            books = {}
            for highlight in highlights:
                if highlight.book_id not in books:
                    book = self.db.query(models.Book).filter(
                        models.Book.id == highlight.book_id
                    ).first()
                    if book:
                        books[highlight.book_id] = book
            logger.debug(f"[CrossPoint] 書籍情報取得完了。ユニーク書籍数: {len(books)}")
            
            # 書籍が2冊未満の場合は中止
            if len(books) < 2:
                logger.info(f"[CrossPoint] 書籍数が2冊未満のため、トピック多様性選択をスキップ: user_id={self.user_id}, count={len(books)}")
                return None
            
            # 書籍からランダムに2冊選択
            logger.debug(f"[CrossPoint] 書籍からランダムに2冊を選択中...")
            book_ids = list(books.keys())
            random.shuffle(book_ids)
            book_id1, book_id2 = book_ids[:2]
            logger.debug(f"[CrossPoint] 選択された書籍ID: {book_id1}, {book_id2}")
            
            # 各書籍からハイライトを1つずつ選択
            logger.debug(f"[CrossPoint] 各書籍からハイライトをランダムに選択中...")
            highlights1 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book_id1
            ).all()
            
            highlights2 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book_id2
            ).all()
            logger.debug(f"[CrossPoint] 書籍1のハイライト数: {len(highlights1)}, 書籍2のハイライト数: {len(highlights2)}")
            
            if not highlights1 or not highlights2:
                logger.warning(f"[CrossPoint] _select_topic_diverse_highlights失敗: 片方または両方の書籍にハイライトがありません, user_id={self.user_id}")
                return None
            
            # ランダムに選択
            highlight1 = random.choice(highlights1)
            highlight2 = random.choice(highlights2)
            logger.debug(f"[CrossPoint] 選択されたハイライトID: h1={highlight1.id}, h2={highlight2.id}")
            
            logger.info(f"[CrossPoint] _select_topic_diverse_highlights成功: user_id={self.user_id}, book1='{books[book_id1].title}', book2='{books[book_id2].title}', h1={highlight1.id}, h2={highlight2.id}")
            return [highlight1, highlight2] # 単一ペアをリストで返す
            
        except Exception as e:
            logger.error(f"[CrossPoint] _select_topic_diverse_highlightsエラー: {e}", exc_info=True)
            return None
    
    async def _select_genre_diverse_highlights(self) -> Optional[List[models.Highlight]]:
        """
        ジャンル対比によるハイライト選択
        
        異なる書籍から、ランダムにハイライトを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        logger.debug(f"[CrossPoint] _select_genre_diverse_highlights開始: user_id={self.user_id}")
        try:
            # ユーザーの書籍を取得
            logger.debug(f"[CrossPoint] ユーザーの書籍リストを取得中...")
            books = self.db.query(models.Book).join(
                models.Highlight,
                models.Book.id == models.Highlight.book_id
            ).filter(
                models.Highlight.user_id == self.user_id
            ).distinct().all()
            logger.debug(f"[CrossPoint] 書籍リスト取得完了: {len(books)}冊")
            
            if len(books) < 2:
                logger.info(f"[CrossPoint] 書籍数が2冊未満のため、ジャンル対比選択をスキップ: user_id={self.user_id}, count={len(books)}")
                return None
            
            # ランダムに2冊選択
            logger.debug(f"[CrossPoint] 書籍からランダムに2冊を選択中...")
            random.shuffle(books)
            book1, book2 = books[:2]
            logger.debug(f"[CrossPoint] 選択された書籍: book1='{book1.title}', book2='{book2.title}'")
            
            # 各書籍からハイライトを1つずつ選択
            logger.debug(f"[CrossPoint] 各書籍からハイライトをランダムに選択中...")
            highlight1 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book1.id
            ).order_by(func.random()).first()
            
            highlight2 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book2.id
            ).order_by(func.random()).first()
            
            if not highlight1 or not highlight2:
                logger.warning(f"[CrossPoint] _select_genre_diverse_highlights失敗: 片方または両方の書籍にハイライトがありません, user_id={self.user_id}")
                return None
            logger.debug(f"[CrossPoint] 選択されたハイライトID: h1={highlight1.id}, h2={highlight2.id}")
            
            logger.info(f"[CrossPoint] _select_genre_diverse_highlights成功: user_id={self.user_id}, book1='{book1.title}', book2='{book2.title}', h1={highlight1.id}, h2={highlight2.id}")
            return [highlight1, highlight2] # 単一ペアをリストで返す
            
        except Exception as e:
            logger.error(f"[CrossPoint] _select_genre_diverse_highlightsエラー: {e}", exc_info=True)
            return None
    
    def _select_random_highlights(self) -> Optional[List[models.Highlight]]:
        """
        ランダムなハイライト選択（フォールバック）
        
        異なる書籍から、ランダムにハイライトを選択します。
        
        Returns:
            選択されたハイライトのリスト、または失敗した場合はNone
        """
        logger.debug(f"[CrossPoint] _select_random_highlights開始: user_id={self.user_id}")
        try:
            # ユーザーの異なる書籍からハイライトを取得
            logger.debug(f"[CrossPoint] ユーザーの書籍リストを取得中...")
            books = self.db.query(models.Book).join(
                models.Highlight,
                models.Book.id == models.Highlight.book_id
            ).filter(
                models.Highlight.user_id == self.user_id
            ).distinct().all()
            logger.debug(f"[CrossPoint] 書籍リスト取得完了: {len(books)}冊")
            
            if len(books) < 2:
                logger.warning(f"[CrossPoint] 書籍数が2冊未満のため、ランダム選択失敗: user_id={self.user_id}, count={len(books)}")
                return None
            
            # ランダムに2冊選択
            logger.debug(f"[CrossPoint] 書籍からランダムに2冊を選択中...")
            random.shuffle(books)
            book1, book2 = books[:2]
            logger.debug(f"[CrossPoint] 選択された書籍: book1='{book1.title}', book2='{book2.title}'")
            
            # 各書籍からハイライトを1つずつ選択
            logger.debug(f"[CrossPoint] 各書籍からハイライトをランダムに選択中...")
            highlight1 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book1.id
            ).order_by(func.random()).first()
            
            highlight2 = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id,
                models.Highlight.book_id == book2.id
            ).order_by(func.random()).first()
            
            if not highlight1 or not highlight2:
                logger.warning(f"[CrossPoint] _select_random_highlights失敗: 片方または両方の書籍にハイライトがありません, user_id={self.user_id}")
                return None
            logger.debug(f"[CrossPoint] 選択されたハイライトID: h1={highlight1.id}, h2={highlight2.id}")
            
            logger.info(f"[CrossPoint] _select_random_highlights成功: user_id={self.user_id}, book1='{book1.title}', book2='{book2.title}', h1={highlight1.id}, h2={highlight2.id}")
            return [highlight1, highlight2] # 単一ペアをリストで返す
            
        except Exception as e:
            logger.error(f"[CrossPoint] _select_random_highlightsエラー: {e}", exc_info=True)
            return None
    
    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        テキストの埋め込みベクトルを生成
        
        Args:
            text: 埋め込みベクトルを生成するテキスト
            
        Returns:
            埋め込みベクトル、または失敗した場合はNone
        """
        logger.debug(f"[CrossPoint] _generate_embedding開始: text='{text[:50]}...'")
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            embedding = response.data[0].embedding
            logger.debug(f"[CrossPoint] _generate_embedding成功: vector_dim={len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"[CrossPoint] _generate_embeddingエラー: {e}", exc_info=True)
            return None
    
    def _cosine_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """
        コサイン距離を計算（1 - コサイン類似度）
        
        Args:
            vec1: 1つ目のベクトル
            vec2: 2つ目のベクトル
            
        Returns:
            コサイン距離（0-2の範囲、0が最も近く、2が最も遠い）
        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 1.0  # 最大距離
            
        similarity = dot_product / (norm1 * norm2)
        # 距離に変換（1 - 類似度）
        return 1.0 - similarity

    async def _generate_cross_point_text(
        self, highlight1: models.Highlight, highlight2: models.Highlight
    ) -> Optional[Tuple[str, str]]:
        """
        与えられたハイライトペアに対して、LLMを使用してCross Pointのタイトルと説明文を生成する
        
        Args:
            highlight1: 1つ目のハイライト
            highlight2: 2つ目のハイライト
            
        Returns:
            (タイトル, 説明文) のタプル、または生成に失敗した場合はNone
        """
        logger.debug(f"[CrossPoint] _generate_cross_point_text開始: h1={highlight1.id}, h2={highlight2.id}")
        # 書籍情報を取得 (エラーチェックは呼び出し元で行う想定)
        book1 = self.db.query(models.Book).filter(models.Book.id == highlight1.book_id).first()
        book2 = self.db.query(models.Book).filter(models.Book.id == highlight2.book_id).first()
        if not book1 or not book2:
             logger.error(f"[CrossPoint] テキスト生成のための書籍情報取得失敗: book1_id={highlight1.book_id}, book2_id={highlight2.book_id}")
             return None

        # Cross Point生成プロンプト (generate_and_saveから流用)
        prompt = f"""
        以下の2つの一見関連性のない本からのハイライトを結びつける、意外で知的好奇心をくすぐる関連性を発見してください。
        
        書籍1「{book1.title}」（{book1.author}）からのハイライト:
        "{highlight1.content}"
        
        書籍2「{book2.title}」（{book2.author}）からのハイライト:
        "{highlight2.content}"
        
        【指示】
        1. 表面的には全く関係なさそうなこの2つのハイライトの間にある、深層的な繋がりや対照的な面白さを見つけてください。
        2. 誰かに「へぇ！そういう見方があるのか！」と思わせるような関連性を探してください。
        3. 哲学的な洞察、共通する原理原則、対極にありながらも補完しあう関係性などに着目すると良いでしょう。
        
        【返答形式】
        タイトル: [関連性を表す20文字程度の魅力的なタイトル]
        
        [100〜150文字で関連性を説明。この部分は「なるほど！」と思わせる驚きと発見を感じる内容にしてください]
        """
        
        try:
            # OpenAI APIで関連性を生成
            logger.info(f"[CrossPoint] OpenAI API呼び出し開始 (テキスト生成): model=gpt-4-turbo, user_id={self.user_id}")
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo", # モデル名は最新に合わせる
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            logger.info(f"[CrossPoint] OpenAI API呼び出し成功 (テキスト生成): user_id={self.user_id}")
            
            connection_text = response.choices[0].message.content
            
            # タイトルと説明文を分離
            lines = connection_text.strip().split("\n")
            title = lines[0].replace("タイトル:", "").strip()
            description = "\n".join(lines[1:]).strip()
            
            logger.debug(f"[CrossPoint] _generate_cross_point_text成功: title='{title}', description='{description[:50]}...'")
            return title, description
            
        except Exception as e:
            logger.error(f"[CrossPoint] _generate_cross_point_textエラー: {e}", exc_info=True)
            return None

    # async def _generate_and_save_cross_point( # 元の関数はコメントアウトまたは削除
    #     self, highlight1: models.Highlight, highlight2: models.Highlight, title: str, description: str
    # ) -> Dict[str, Any]:
    async def _save_cross_point( # 新しい保存用関数
        self, highlight1: models.Highlight, highlight2: models.Highlight, title: str, description: str
    ) -> Optional[Dict[str, Any]]:
        """
        生成されたCross Pointの情報をデータベースに保存する
        
        Args:
            highlight1: 1つ目のハイライト
            highlight2: 2つ目のハイライト
            title: 生成されたタイトル
            description: 生成された説明文
            
        Returns:
            保存されたCross Pointの情報を含む辞書、または失敗した場合はNone
        """
        logger.debug(f"[CrossPoint] _save_cross_point開始 (DB保存): user_id={self.user_id}, h1={highlight1.id}, h2={highlight2.id}")
        
        try:
            # Cross Pointをデータベースに保存
            logger.debug(f"[CrossPoint] Cross Pointをデータベースに保存中...")
            cross_point = models.CrossPoint(
                user_id=self.user_id,
                highlight1_id=highlight1.id,
                highlight2_id=highlight2.id,
                title=title,
                description=description
            )
            self.db.add(cross_point)
            logger.debug(f"[CrossPoint] CrossPointオブジェクトをセッションに追加")
            
            # コネクション履歴に追加
            logger.debug(f"[CrossPoint] ConnectionHistoryをデータベースに保存中...")
            history = models.ConnectionHistory(
                user_id=self.user_id,
                highlight1_id=highlight1.id,
                highlight2_id=highlight2.id
            )
            self.db.add(history)
            logger.debug(f"[CrossPoint] ConnectionHistoryオブジェクトをセッションに追加")
            
            try:
                self.db.commit()
                logger.info(f"[CrossPoint] データベースへのコミット成功")
                self.db.refresh(cross_point)
                logger.debug(f"[CrossPoint] CrossPointオブジェクトをリフレッシュ")
            except Exception as db_error:
                logger.error(f"[CrossPoint] データベースコミットエラー: {db_error}", exc_info=True)
                self.db.rollback()
                return None

            logger.info(f"[CrossPoint] _save_cross_point成功: user_id={self.user_id}, cross_point_id={cross_point.id}, title='{title}'")
            
            formatted_response = self._format_cross_point_response(cross_point)
            if formatted_response is None:
                 logger.error(f"[CrossPoint] 保存後のCross Pointフォーマットに失敗: cross_point_id={cross_point.id}")
                 return None
            return formatted_response
            
        except Exception as e:
            logger.error(f"[CrossPoint] _save_cross_pointエラー: {e}", exc_info=True)
            self.db.rollback() # ロールバックを追加
            return None
    
    def _format_cross_point_response(self, cross_point: models.CrossPoint) -> Optional[Dict[str, Any]]: # 返り値をOptionalに変更
        """
        APIレスポンス用にデータをフォーマット
        
        Args:
            cross_point: フォーマットするCross Point
            
        Returns:
            フォーマットされたレスポンス辞書、または失敗した場合はNone
        """
        logger.debug(f"[CrossPoint] _format_cross_point_response開始: cross_point_id={cross_point.id}")
        try: # フォーマット処理全体をtry...exceptで囲む
            # ハイライト情報を取得
            logger.debug(f"[CrossPoint] ハイライト情報を取得中: h1_id={cross_point.highlight1_id}, h2_id={cross_point.highlight2_id}")
            highlight1 = self.db.query(models.Highlight).filter(
                models.Highlight.id == cross_point.highlight1_id
            ).first()
            
            highlight2 = self.db.query(models.Highlight).filter(
                models.Highlight.id == cross_point.highlight2_id
            ).first()
            
            # ハイライトが見つからない場合のエラーハンドリングを追加
            if not highlight1 or not highlight2:
                logger.error(f"[CrossPoint] フォーマット中にハイライトが見つかりません: h1_id={cross_point.highlight1_id}, h2_id={cross_point.highlight2_id}")
                # 適切なエラー処理 (例: Noneを返す、例外を発生させるなど)
                # ここでは仮にNoneを返す
                return None 
                
            logger.debug(f"[CrossPoint] ハイライト情報取得完了: h1_content='{highlight1.content[:20]}...', h2_content='{highlight2.content[:20]}...'")
            
            # 書籍情報を取得
            logger.debug(f"[CrossPoint] 書籍情報を取得中: book1_id={highlight1.book_id}, book2_id={highlight2.book_id}")
            book1 = self.db.query(models.Book).filter(
                models.Book.id == highlight1.book_id
            ).first()
            
            book2 = self.db.query(models.Book).filter(
                models.Book.id == highlight2.book_id
            ).first()

            # 書籍が見つからない場合のエラーハンドリングを追加
            if not book1 or not book2:
                 logger.error(f"[CrossPoint] フォーマット中に書籍が見つかりません: book1_id={highlight1.book_id}, book2_id={highlight2.book_id}")
                 # 適切なエラー処理
                 return None

            logger.debug(f"[CrossPoint] 書籍情報取得完了: book1_title='{book1.title}', book2_title='{book2.title}'")
            
            response_data = {
                "id": cross_point.id,
                "title": cross_point.title,
                "description": cross_point.description,
                "created_at": cross_point.created_at.isoformat(),
                "liked": cross_point.liked,
                "highlights": [
                    {
                        "id": highlight1.id,
                        "content": highlight1.content,
                        "book_id": highlight1.book_id,
                        "book_title": book1.title,
                        "book_author": book1.author
                    },
                    {
                        "id": highlight2.id,
                        "content": highlight2.content,
                        "book_id": highlight2.book_id,
                        "book_title": book2.title,
                        "book_author": book2.author
                    }
                ]
            }
            logger.debug(f"[CrossPoint] _format_cross_point_response完了: cross_point_id={cross_point.id}")
            return response_data
        except Exception as e: # フォーマット中の予期せぬエラーをキャッチ
            logger.error(f"[CrossPoint] _format_cross_point_responseエラー: {e}", exc_info=True)
            return None

    async def generate_embeddings_for_all_highlights(self) -> Dict[str, Any]:
        """
        ユーザーの全ハイライトの埋め込みベクトルを生成
        
        Returns:
            処理結果の情報を含む辞書
        """
        logger.info(f"[CrossPoint] generate_embeddings_for_all_highlights開始: user_id={self.user_id}")
        try:
            # ユーザーのハイライトを取得
            logger.debug(f"[CrossPoint] ユーザーの全ハイライトを取得中...")
            highlights = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id
            ).all()
            logger.debug(f"[CrossPoint] ハイライト取得完了: {len(highlights)}件")
            
            if not highlights:
                logger.warning(f"[CrossPoint] 埋め込み生成対象のハイライトがありません: user_id={self.user_id}")
                return {
                    "success": False,
                    "message": "ハイライトが見つかりません",
                    "processed": 0,
                    "total": 0
                }
            
            # 既に埋め込みが生成されているハイライトを除外
            logger.debug(f"[CrossPoint] 既存の埋め込みキャッシュを確認中...")
            existing_embeddings = self.db.query(models.HighlightEmbedding.highlight_id).filter(
                models.HighlightEmbedding.highlight_id.in_([h.id for h in highlights])
            ).all()
            existing_ids = {e[0] for e in existing_embeddings}
            logger.debug(f"[CrossPoint] 既存の埋め込み数: {len(existing_ids)}")
            
            highlights_to_process = [h for h in highlights if h.id not in existing_ids]
            logger.info(f"[CrossPoint] 新規に埋め込みを生成するハイライト数: {len(highlights_to_process)}")
            
            if not highlights_to_process:
                logger.info(f"[CrossPoint] 全てのハイライトの埋め込みは既に生成済みです: user_id={self.user_id}")
                return {
                    "success": True,
                    "message": "全てのハイライトの埋め込みは既に生成されています",
                    "processed": 0,
                    "total": len(highlights)
                }
            
            # 埋め込みベクトルを生成
            logger.info(f"[CrossPoint] 埋め込みベクトル生成ループ開始: user_id={self.user_id}, count={len(highlights_to_process)}")
            processed_count = 0
            for i, highlight in enumerate(highlights_to_process):
                logger.debug(f"[CrossPoint] ハイライト {i+1}/{len(highlights_to_process)} (ID: {highlight.id}) の埋め込みを生成中...")
                embedding = await self._generate_embedding(highlight.content)
                if embedding:
                    # 埋め込みをキャッシュに保存
                    logger.debug(f"[CrossPoint] ハイライトID {highlight.id} の埋め込みをキャッシュに保存中...")
                    new_cache = models.HighlightEmbedding(
                        highlight_id=highlight.id,
                        embedding=pickle.dumps(embedding)
                    )
                    try:
                        self.db.add(new_cache)
                        processed_count += 1
                    except Exception as add_error:
                        logger.error(f"[CrossPoint] 埋め込みキャッシュ追加エラー: {add_error}")
                        # エラーが発生しても続行する可能性があるため、ここではロールバックしない
                else:
                    logger.warning(f"[CrossPoint] ハイライトID {highlight.id} の埋め込み生成に失敗")

            logger.info(f"[CrossPoint] 埋め込みベクトル生成ループ完了: user_id={self.user_id}, processed={processed_count}")
            
            try:
                self.db.commit()
                logger.info(f"[CrossPoint] 埋め込みキャッシュのデータベースコミット成功: user_id={self.user_id}, count={processed_count}")
            except Exception as commit_error:
                 logger.error(f"[CrossPoint] 埋め込みキャッシュのデータベースコミットエラー: {commit_error}", exc_info=True)
                 self.db.rollback()
                 # コミット失敗は致命的なのでエラーを返す
                 return {
                    "success": False,
                    "message": f"埋め込みキャッシュの保存中にエラーが発生しました: {str(commit_error)}",
                    "processed": 0, # コミット失敗のため0
                    "total": len(highlights)
                 }

            logger.info(f"[CrossPoint] generate_embeddings_for_all_highlights成功: user_id={self.user_id}")
            return {
                "success": True,
                "message": f"{processed_count}件のハイライトの埋め込みを生成しました",
                "processed": processed_count,
                "total": len(highlights)
            }
            
        except Exception as e:
            logger.error(f"[CrossPoint] generate_embeddings_for_all_highlightsエラー: {e}", exc_info=True)
            self.db.rollback()
            return {
                "success": False,
                "message": f"埋め込みベクトル生成中にエラーが発生しました: {str(e)}",
                "processed": 0,
                "total": 0
            }
