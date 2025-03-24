# BooklightAI API実装計画書

## 1. 現状分析

### 1.1 問題の概要

現在、BooklightAIアプリケーションではAPIエラーが発生しており、ユーザーごとに正しく情報が表示されていません。調査の結果、以下の主要な問題が特定されました：

1. フロントエンドが期待するAPIエンドポイントがバックエンドに実装されていない
2. データベースモデルの定義が不完全である
3. APIパスの不一致（開発環境での`/api`プレフィックス）
4. ユーザーデータの分離が不十分

### 1.2 フロントエンドの期待するエンドポイント

フロントエンドコードを分析した結果、以下のエンドポイントが期待されていることが判明しました：

#### 書籍関連
- `/books` - 書籍一覧の取得
- `/books/${title}` - 特定の書籍の取得
- `/books/${bookId}/highlights` - 書籍のハイライト取得
- `/books/cover` - 書籍の表紙画像取得

#### 機能関連
- `/search` - 検索機能
- `/chat` - チャット機能
- `/upload` - ファイルアップロード

### 1.3 現状のデータベースモデル

現在のデータベースモデル（`api/database/models.py`）には以下のモデルが定義されています：

- `User` - ユーザー情報
- `Book` - 書籍情報
- `Highlight` - ハイライト情報

しかし、バックエンドコード（`main.py`）では以下のモデルも参照されていますが、定義されていません：

- `SearchHistory` - 検索履歴
- `ChatSession` - チャットセッション

### 1.4 APIパスの不一致

フロントエンドのAPIクライアント（`frontend/src/api/client.ts`）では、開発環境（`localhost`を含むURL）で全てのAPIリクエストに`/api`プレフィックスが追加されます：

```typescript
const apiPrefix = baseURL.includes('localhost') ? '/api' : '';
```

しかし、バックエンドには`/api`プレフィックス付きのエンドポイントが実装されていません。

## 2. 実装計画

### 2.1 データベースモデルの完成

まず、不足しているデータベースモデルを`api/database/models.py`に追加します：

1. `SearchHistory` - 検索履歴モデル
   - ユーザーID、検索クエリ、タイムスタンプなどのフィールド

2. `ChatSession` - チャットセッションモデル
   - ユーザーID、セッションタイトル、作成日時、更新日時などのフィールド

3. `ChatMessage` - チャットメッセージモデル
   - セッションID、メッセージ内容、ロール（ユーザー/AI）、タイムスタンプなどのフィールド

### 2.2 APIエンドポイントの実装

次に、必要なAPIエンドポイントを`api/app/main.py`に実装します：

#### 書籍関連エンドポイント

1. **書籍一覧取得**
   - `GET /api/books`
   - クエリパラメータ：ページ、ページサイズ、ソートフィールド、ソート順序、検索語句
   - レスポンス：書籍リスト、総数、ページ数など

2. **特定書籍取得**
   - `GET /api/books/{title}`
   - パスパラメータ：書籍タイトル（URLエンコード済み）
   - レスポンス：書籍詳細情報

3. **書籍ハイライト取得**
   - `GET /api/books/{book_id}/highlights`
   - パスパラメータ：書籍ID
   - レスポンス：ハイライトリスト

4. **書籍表紙画像取得**
   - `GET /api/books/cover`
   - クエリパラメータ：タイトル、著者
   - レスポンス：表紙画像URL

#### 機能関連エンドポイント

5. **検索機能**
   - `POST /api/search`
   - リクエストボディ：キーワード配列、検索オプション
   - レスポンス：検索結果リスト

6. **チャット機能**
   - `POST /api/chat`
   - リクエストボディ：メッセージ配列、ストリーミングフラグ、ソース使用フラグ
   - レスポンス：AIの応答（ストリーミング対応）

7. **ファイルアップロード**
   - `POST /api/upload`
   - リクエストボディ：CSVファイル（multipart/form-data）
   - レスポンス：アップロード結果（書籍数、ハイライト数）

### 2.3 ユーザーデータ分離の徹底

全てのエンドポイントで、以下の点を徹底します：

1. 認証済みユーザーのみアクセス可能（`Depends(get_current_active_user)`を使用）
2. データベースクエリに常にユーザーIDフィルターを適用
3. レスポンスには他のユーザーのデータを含めない

### 2.4 エラーハンドリングの強化

1. 一貫したエラーレスポンス形式の定義
2. 詳細なログ記録
3. クライアントに適切なエラーメッセージを返す

## 3. 実装順序

1. データベースモデルの追加と既存モデルの修正
2. マイグレーションスクリプトの作成と実行
3. 書籍関連エンドポイントの実装
4. 検索機能の実装
5. チャット機能の実装
6. ファイルアップロード機能の実装
7. テストの作成と実行
8. ドキュメントの更新

## 4. 技術的詳細

### 4.1 データベースモデル定義

```python
# SearchHistory モデル
class SearchHistory(Base):
    """検索履歴モデル"""
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship("User", backref="search_history")

# ChatSession モデル
class ChatSession(Base):
    """チャットセッションモデル"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship("User", backref="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

# ChatMessage モデル
class ChatMessage(Base):
    """チャットメッセージモデル"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    role = Column(String, nullable=False)  # 'user' または 'assistant'
    created_at = Column(DateTime, default=datetime.utcnow)

    session_id = Column(Integer, ForeignKey('chat_sessions.id'), nullable=False)
    session = relationship("ChatSession", back_populates="messages")
```

### 4.2 APIエンドポイント実装例

#### 書籍一覧取得エンドポイント

```python
@app.get("/api/books")
async def get_books(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    sort_by: str = Query("title", regex="^(title|author|highlightCount)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """書籍一覧を取得するエンドポイント"""
    try:
        # 基本クエリ（ユーザーIDでフィルタリング）
        query = db.query(models.Book).filter(models.Book.user_id == current_user.id)
        
        # 検索条件の適用
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    models.Book.title.ilike(search_term),
                    models.Book.author.ilike(search_term)
                )
            )
        
        # 総数の取得
        total = query.count()
        
        # ソート条件の適用
        if sort_by == "title":
            query = query.order_by(asc(models.Book.title) if sort_order == "asc" else desc(models.Book.title))
        elif sort_by == "author":
            query = query.order_by(asc(models.Book.author) if sort_order == "asc" else desc(models.Book.author))
        elif sort_by == "highlightCount":
            # ハイライト数でソート（サブクエリを使用）
            highlight_count = (
                db.query(func.count(models.Highlight.id))
                .filter(models.Highlight.book_id == models.Book.id)
                .scalar_subquery()
            )
            query = query.order_by(asc(highlight_count) if sort_order == "asc" else desc(highlight_count))
        
        # ページネーション
        total_pages = ceil(total / page_size)
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        # 結果の取得
        books = query.all()
        
        # レスポンスの作成
        book_list = []
        for book in books:
            # ハイライト数を取得
            highlight_count = db.query(models.Highlight).filter(
                models.Highlight.book_id == book.id
            ).count()
            
            book_list.append({
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "highlightCount": highlight_count,
                "coverUrl": None,  # 表紙画像URLは別途取得
                "createdAt": book.created_at.isoformat() if hasattr(book, 'created_at') else None
            })
        
        return {
            "success": True,
            "data": {
                "items": book_list,
                "total": total,
                "total_pages": total_pages,
                "page": page,
                "page_size": page_size
            }
        }
    except Exception as e:
        logger.error(f"書籍一覧取得エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="書籍一覧の取得中にエラーが発生しました"
        )
```

### 4.3 エラーハンドリング

```python
# エラーレスポンスモデル
class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    message: str
    statusCode: int

# エラーハンドラ
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message=exc.detail,
            statusCode=exc.status_code
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"予期しないエラー: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="サーバー内部エラーが発生しました",
            statusCode=status.HTTP_500_INTERNAL_SERVER_ERROR
        ).dict()
    )
```

## 5. 今後の課題

1. パフォーマンス最適化
   - クエリの効率化
   - キャッシュの導入

2. セキュリティ強化
   - 入力バリデーションの徹底
   - レート制限の導入

3. 機能拡張
   - タグ機能の追加
   - 高度な検索オプション
   - ユーザー設定の保存

4. テスト自動化
   - 単体テスト
   - 統合テスト
   - エンドツーエンドテスト

## 6. 参考資料

- [FastAPI公式ドキュメント](https://fastapi.tiangolo.com/)
- [SQLAlchemy公式ドキュメント](https://docs.sqlalchemy.org/)
- [React Query公式ドキュメント](https://tanstack.com/query/latest/docs/react/overview)
