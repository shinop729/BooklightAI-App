"""
Remix機能の実装

このモジュールは、ユーザーのハイライトを組み合わせて
新しいテーマに沿った「仮想の本の章」を作成する機能を実装します。
"""

import os
import random
import logging
import pickle
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional, Union

from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import openai

import database.models as models
from app.config import settings

# ロガーの設定
logger = logging.getLogger("booklight-api")

class RemixService:
    """Remix生成サービス"""
    
    def __init__(self, db: Session, user_id: int):
        """
        RemixServiceの初期化
        
        Args:
            db: SQLAlchemyのセッション
            user_id: ユーザーID
        """
        self.db = db
        self.user_id = user_id
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_random_theme(self) -> str:
        """ユーザーのハイライトに基づいてランダムなテーマを生成"""
        try:
            # 方法1: ユーザーのハイライトから頻出キーワードを抽出
            highlights = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id
            ).limit(50).all()
            
            if not highlights or len(highlights) < 5:
                # ハイライトが少ない場合は汎用テーマから選択
                return self._select_from_generic_themes()
            
            # ハイライトの内容を結合
            combined_text = " ".join([h.content for h in highlights])
            
            # OpenAI APIでテーマを生成
            prompt = f"""
            以下のテキストは、ユーザーが様々な書籍からハイライトした文章です。
            このテキストを分析し、ユーザーが興味を持ちそうな「エッセイのテーマ」を1つ提案してください。
            テーマは具体的で、かつ汎用的すぎない、20文字程度の短い表現にしてください。
            
            【ハイライトテキスト】
            {combined_text[:2000]}  # 長すぎる場合は切り詰め
            
            【返答形式】
            テーマ名のみを返してください。説明は不要です。
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=50
            )
            
            theme = response.choices[0].message.content.strip()
            return theme
            
        except Exception as e:
            logger.error(f"ランダムテーマ生成エラー: {e}")
            # エラー時は汎用テーマから選択
            return self._select_from_generic_themes()
    
    def _select_from_generic_themes(self) -> str:
        """汎用的なテーマリストからランダムに選択"""
        generic_themes = [
            "成功の本質とは何か",
            "幸福を追求する意味",
            "人間関係の築き方",
            "自己成長の道筋",
            "創造性を高める方法",
            "リーダーシップの真髄",
            "変化に適応する力",
            "心の平穏を保つ秘訣",
            "時間管理の新しい視点",
            "学び続けることの価値",
            "直感と論理の使い分け",
            "失敗から学ぶ姿勢",
            "本当の豊かさとは",
            "人生の優先順位",
            "未来を見据える視点",
            "感情のコントロール",
            "決断力を高める方法",
            "コミュニケーションの技術",
            "目標設定の重要性",
            "習慣の力を活かす"
        ]
        return random.choice(generic_themes)
    
    def select_random_highlights_for_remix(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Remix用にランダムなハイライトを選択
        
        Args:
            count: 選択するハイライト数（デフォルト5つ）
            
        Returns:
            選択されたハイライトのリスト
        """
        try:
            # 書籍ごとのハイライト数を確認
            book_highlight_counts = {}
            books = self.db.query(models.Book).join(
                models.Highlight,
                models.Book.id == models.Highlight.book_id
            ).filter(
                models.Highlight.user_id == self.user_id
            ).distinct().all()
            
            for book in books:
                count_result = self.db.query(models.Highlight).filter(
                    models.Highlight.user_id == self.user_id,
                    models.Highlight.book_id == book.id
                ).count()
                book_highlight_counts[book.id] = count_result
            
            # 最低2冊の書籍からハイライトを選択（多様性を確保）
            min_books = min(len(book_highlight_counts), 2)
            
            # 書籍の選択（ランダムに選択するが、少なくとも2冊から選ぶ）
            selected_books = random.sample(list(book_highlight_counts.keys()), min_books)
            
            # 残りの書籍からランダムに選択して追加
            remaining_books = [b for b in book_highlight_counts.keys() if b not in selected_books]
            if remaining_books and len(selected_books) < min(5, len(books)):
                additional_books = random.sample(
                    remaining_books, 
                    min(3, len(remaining_books))  # 最大3冊まで追加
                )
                selected_books.extend(additional_books)
            
            # 各書籍から少なくとも1つのハイライトを選択
            selected_highlights = []
            
            # 各書籍からハイライトを選択
            for book_id in selected_books:
                book_highlights = self.db.query(models.Highlight).filter(
                    models.Highlight.user_id == self.user_id,
                    models.Highlight.book_id == book_id
                ).all()
                
                # 1つのハイライトをランダムに選択
                if book_highlights:
                    highlight = random.choice(book_highlights)
                    
                    # 書籍情報を取得
                    book = self.db.query(models.Book).filter(
                        models.Book.id == highlight.book_id
                    ).first()
                    
                    if book:
                        selected_highlights.append({
                            "id": highlight.id,
                            "content": highlight.content,
                            "book_id": highlight.book_id,
                            "book_title": book.title,
                            "book_author": book.author
                        })
            
            # 残りのハイライト数を全書籍からランダムに選択
            remaining_count = count - len(selected_highlights)
            if remaining_count > 0:
                # 既に選択されたハイライトIDのリスト
                selected_ids = [h["id"] for h in selected_highlights]
                
                # 残りのハイライトを取得
                all_highlights = self.db.query(models.Highlight).filter(
                    models.Highlight.user_id == self.user_id,
                    ~models.Highlight.id.in_(selected_ids)
                ).all()
                
                # ランダムに選択（利用可能なハイライト数を超えないように）
                if all_highlights:
                    additional_highlights = random.sample(
                        all_highlights, 
                        min(remaining_count, len(all_highlights))
                    )
                    
                    for highlight in additional_highlights:
                        # 書籍情報を取得
                        book = self.db.query(models.Book).filter(
                            models.Book.id == highlight.book_id
                        ).first()
                        
                        if book:
                            selected_highlights.append({
                                "id": highlight.id,
                                "content": highlight.content,
                                "book_id": highlight.book_id,
                                "book_title": book.title,
                                "book_author": book.author
                            })
            
            return selected_highlights
            
        except Exception as e:
            logger.error(f"Remix用ハイライト選択エラー: {e}")
            return []
    
    async def generate_theme_from_highlights(self, highlights: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        選択されたハイライトからテーマとタイトルを生成
        
        Args:
            highlights: 選択されたハイライトのリスト
            
        Returns:
            テーマとタイトルを含む辞書
        """
        if not highlights:
            return {"theme": "", "title": ""}
        
        # ハイライトテキストを整形
        highlight_texts = []
        for highlight in highlights:
            highlight_text = f"「{highlight['book_title']}」（{highlight['book_author']}）からのハイライト: \"{highlight['content']}\""
            highlight_texts.append(highlight_text)
        
        # ハイライトがない場合
        if not highlight_texts:
            return {"theme": "", "title": ""}
        
        # APIに送信するプロンプト
        prompt = f"""
        以下の複数の書籍からのハイライトを分析し、これらをつなぐテーマとエッセイのタイトルを提案してください。

        ハイライト:
        {"\n\n".join(highlight_texts)}

        これらのハイライトから見出せる共通点や興味深い対比点を考慮して、以下の形式で回答してください：

        theme: [これらのハイライトをつなぐ統一テーマや概念を簡潔に表現]
        title: [そのテーマに基づく魅力的なエッセイタイトル]
        """
        
        try:
            # OpenAI APIでテーマとタイトルを生成
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # テーマとタイトルを抽出
            theme = ""
            title = ""
            
            for line in result_text.split("\n"):
                if line.lower().startswith("theme:"):
                    theme = line.replace("theme:", "", 1).strip()
                elif line.lower().startswith("title:"):
                    title = line.replace("title:", "", 1).strip()
            
            return {"theme": theme, "title": title}
        
        except Exception as e:
            logger.error(f"テーマ生成エラー: {e}")
            return {"theme": "", "title": ""}
    
    async def generate_remix_essay(self, highlights: List[Dict[str, Any]], theme: str, title: str) -> str:
        """
        選択されたハイライトとテーマからエッセイを生成
        
        Args:
            highlights: 選択されたハイライトのリスト
            theme: 生成されたテーマ
            title: 生成されたタイトル
            
        Returns:
            生成されたエッセイ
        """
        if not highlights or not theme or not title:
            return ""
        
        # APIに送信するプロンプト
        prompt = f"""
        あなたは、様々な書籍からのハイライトを元に、創造的で洞察に満ちたエッセイを生成する専門家です。
        以下のハイライトと導き出されたテーマを基に、800～1200字程度のエッセイを作成してください。

        タイトル: {title}
        テーマ: {theme}

        ハイライト:
        {"\n\n".join([f"「{h['book_title']}」（{h['book_author']}）: \"{h['content']}\"" for h in highlights])}

        【エッセイ作成の指針】
        1. 全てのハイライトを何らかの形で取り入れてください
        2. ハイライトの引用元を明示してください
        3. ハイライトを橋渡しするオリジナルの考察を加えてください
        4. 序論、本論、結論の流れを持たせてください
        5. 読者に新たな視点や気づきを与える内容にしてください
        6. 文体は統一感を持たせ、流れるように自然な文章にしてください

        【エッセイ形式】
        タイトル：{title}

        [ここにエッセイ本文を記載]

        （参考文献）
        {", ".join([f"『{h['book_title']}』（{h['book_author']}）" for h in highlights])}
        """
        
        try:
            # OpenAI APIでエッセイを生成
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",  # より高品質なエッセイのためにGPT-4を使用
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            
            essay = response.choices[0].message.content.strip()
            return essay
        
        except Exception as e:
            logger.error(f"エッセイ生成エラー: {e}")
            return ""
    
    async def generate_remix(self, highlight_count: int = 5) -> Dict[str, Any]:
        """
        Remixを生成
        
        Args:
            highlight_count: 使用するハイライト数
            
        Returns:
            生成されたRemixの情報
        """
        try:
            # 1. ランダムなハイライトを選択
            highlights = self.select_random_highlights_for_remix(count=highlight_count)
            
            if not highlights or len(highlights) < 2:
                return {
                    "success": False,
                    "message": "Remixを生成するには、少なくとも2つのハイライトが必要です"
                }
            
            # 2. ハイライトからテーマとタイトルを生成
            theme_result = await self.generate_theme_from_highlights(highlights)
            
            if not theme_result["theme"] or not theme_result["title"]:
                return {
                    "success": False,
                    "message": "テーマとタイトルの生成に失敗しました"
                }
            
            # 3. エッセイを生成
            essay = await self.generate_remix_essay(
                highlights, 
                theme_result["theme"], 
                theme_result["title"]
            )
            
            if not essay:
                return {
                    "success": False,
                    "message": "エッセイの生成に失敗しました"
                }
            
            # 4. Remixをデータベースに保存
            remix = models.Remix(
                user_id=self.user_id,
                title=theme_result["title"],
                theme=theme_result["theme"],
                content=essay
            )
            self.db.add(remix)
            self.db.flush()  # IDを生成するためにflush
            
            # 5. Remixとハイライトの関連付けを保存
            for i, highlight in enumerate(highlights):
                remix_highlight = models.RemixHighlight(
                    remix_id=remix.id,
                    highlight_id=highlight["id"],
                    position=i
                )
                self.db.add(remix_highlight)
            
            self.db.commit()
            self.db.refresh(remix)
            
            return {
                "success": True,
                "data": self._format_remix_response(remix, highlights)
            }
            
        except Exception as e:
            logger.error(f"Remix生成エラー: {e}")
            self.db.rollback()
            return {
                "success": False,
                "message": f"Remix生成中にエラーが発生しました: {str(e)}"
            }
    
    async def _select_relevant_highlights(self, theme: str, max_count: int) -> List[Dict[str, Any]]:
        """テーマに関連するハイライトを選択"""
        try:
            # ユーザーのハイライトを取得
            highlights = self.db.query(models.Highlight).filter(
                models.Highlight.user_id == self.user_id
            ).all()
            
            if not highlights:
                logger.warning(f"ハイライトが見つかりません: ユーザーID={self.user_id}")
                return []
            
            # ハイライト情報を整形
            highlight_data = []
            for h in highlights:
                # 書籍情報を取得
                book = self.db.query(models.Book).filter(
                    models.Book.id == h.book_id
                ).first()
                
                if book:
                    highlight_data.append({
                        "id": h.id,
                        "content": h.content,
                        "book_id": h.book_id,
                        "book_title": book.title,
                        "book_author": book.author
                    })
            
            # ハイライトが少ない場合はすべて使用
            if len(highlight_data) <= max_count:
                return highlight_data
            
            # テーマに関連するハイライトを選択
            # OpenAI APIを使用して関連性を判定
            prompt = f"""
            以下のハイライトリストから、「{theme}」というテーマに最も関連する上位{max_count}件を選んでください。
            各ハイライトには番号が振られています。関連性の高いハイライトの番号を、カンマ区切りのリストで返してください。
            
            【ハイライトリスト】
            {self._format_highlights_for_relevance_prompt(highlight_data)}
            
            【返答形式】
            関連性の高いハイライト番号をカンマ区切りで返してください。例: 1,4,7,10
            説明は不要です。
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100
            )
            
            # レスポンスからハイライト番号を抽出
            result = response.choices[0].message.content.strip()
            try:
                # カンマ区切りの番号をリストに変換
                selected_indices = [int(idx.strip()) - 1 for idx in result.split(',')]
                # インデックスの範囲チェック
                selected_indices = [idx for idx in selected_indices if 0 <= idx < len(highlight_data)]
                # 選択されたハイライトを返す
                return [highlight_data[idx] for idx in selected_indices]
            except Exception as e:
                logger.error(f"ハイライト選択エラー: {e}")
                # エラー時はランダムに選択
                random.shuffle(highlight_data)
                return highlight_data[:max_count]
                
        except Exception as e:
            logger.error(f"関連ハイライト選択エラー: {e}")
            return []
    
    def _format_highlights_for_relevance_prompt(self, highlights: List[Dict[str, Any]]) -> str:
        """関連性判定プロンプト用にハイライトをフォーマット"""
        formatted = []
        for i, h in enumerate(highlights):
            formatted.append(f"{i+1}. 『{h['book_title']}』（{h['book_author']}）: {h['content']}")
        
        return "\n\n".join(formatted)
    
    async def _generate_remix_content(self, theme: str, highlights: List[Dict[str, Any]]) -> Dict[str, str]:
        """Remixコンテンツを生成"""
        # ハイライトの内容を抽出
        highlight_texts = [h["content"] for h in highlights]
        book_titles = [h["book_title"] for h in highlights]
        
        # プロンプトの作成
        prompt = f"""
        以下のハイライトを使用して、「{theme}」というテーマに沿った文章を作成してください。
        
        【ハイライト】
        {self._format_highlights_for_prompt(highlights)}
        
        【指示】
        1. 上記のハイライトを適切に引用しながら、論理的な構造を持つ文章を作成してください。
        2. 直接引用と生成文章のバランスを取り、自然な流れを作ってください。
        3. 章立てを行い、導入、本論、結論という構造にしてください。
        4. タイトルは魅力的で、テーマを反映したものにしてください。
        5. 各引用の出典（書籍名と著者名）を明記してください。
        
        【返答形式】
        タイトル: [魅力的なタイトル]
        
        [章立てされた文章。引用部分は明確に区別し、出典を明記]
        """
        
        # OpenAI APIでコンテンツを生成
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content
        
        # タイトルと本文を分離
        lines = content.strip().split("\n")
        title = lines[0].replace("タイトル:", "").strip()
        body = "\n".join(lines[1:]).strip()
        
        return {
            "title": title,
            "content": body
        }
    
    def _format_highlights_for_prompt(self, highlights: List[Dict[str, Any]]) -> str:
        """プロンプト用にハイライトをフォーマット"""
        formatted = []
        for i, h in enumerate(highlights):
            formatted.append(f"ハイライト{i+1}（『{h['book_title']}』{h['book_author']}）:\n「{h['content']}」")
        
        return "\n\n".join(formatted)
    
    async def _save_remix(self, theme: str, remix_content: Dict[str, str], highlights: List[Dict[str, Any]]) -> models.Remix:
        """Remixをデータベースに保存"""
        # Remixレコードの作成
        remix = models.Remix(
            user_id=self.user_id,
            title=remix_content["title"],
            theme=theme,
            content=remix_content["content"]
        )
        self.db.add(remix)
        self.db.commit()
        self.db.refresh(remix)
        
        # ハイライト関連付けの保存
        for i, highlight in enumerate(highlights):
            remix_highlight = models.RemixHighlight(
                remix_id=remix.id,
                highlight_id=highlight["id"],
                position=i
            )
            self.db.add(remix_highlight)
        
        self.db.commit()
        return remix
    
    def _format_remix_response(self, remix: models.Remix, highlights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """APIレスポンス用にデータをフォーマット"""
        return {
            "id": remix.id,
            "title": remix.title,
            "theme": remix.theme,
            "content": remix.content,
            "created_at": remix.created_at.isoformat(),
            "highlights": highlights
        }
    
    async def get_remix_by_id(self, remix_id: int) -> Optional[Dict[str, Any]]:
        """IDでRemixを取得"""
        # Remixを取得
        remix = self.db.query(models.Remix).filter(
            models.Remix.id == remix_id,
            models.Remix.user_id == self.user_id
        ).first()
        
        if not remix:
            return None
        
        # 関連ハイライトを取得
        remix_highlights = self.db.query(models.RemixHighlight).filter(
            models.RemixHighlight.remix_id == remix.id
        ).order_by(models.RemixHighlight.position).all()
        
        highlights = []
        for rh in remix_highlights:
            highlight = self.db.query(models.Highlight).filter(
                models.Highlight.id == rh.highlight_id
            ).first()
            
            if highlight:
                # 書籍情報を取得
                book = self.db.query(models.Book).filter(
                    models.Book.id == highlight.book_id
                ).first()
                
                if book:
                    highlights.append({
                        "id": highlight.id,
                        "content": highlight.content,
                        "book_id": highlight.book_id,
                        "book_title": book.title,
                        "book_author": book.author
                    })
        
        return self._format_remix_response(remix, highlights)
    
    async def get_user_remixes(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """ユーザーのRemix一覧を取得"""
        # Remixを取得
        remixes = self.db.query(models.Remix).filter(
            models.Remix.user_id == self.user_id
        ).order_by(models.Remix.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for remix in remixes:
            # 関連ハイライトを取得
            remix_highlights = self.db.query(models.RemixHighlight).filter(
                models.RemixHighlight.remix_id == remix.id
            ).order_by(models.RemixHighlight.position).all()
            
            highlights = []
            for rh in remix_highlights:
                highlight = self.db.query(models.Highlight).filter(
                    models.Highlight.id == rh.highlight_id
                ).first()
                
                if highlight:
                    # 書籍情報を取得
                    book = self.db.query(models.Book).filter(
                        models.Book.id == highlight.book_id
                    ).first()
                    
                    if book:
                        highlights.append({
                            "id": highlight.id,
                            "content": highlight.content,
                            "book_id": highlight.book_id,
                            "book_title": book.title,
                            "book_author": book.author
                        })
            
            result.append(self._format_remix_response(remix, highlights))
        
        return result
