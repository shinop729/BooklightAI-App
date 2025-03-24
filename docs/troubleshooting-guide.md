# BooklightAI トラブルシューティングガイド

このガイドは、BooklightAIアプリケーションが正常に動作しない場合の対処方法をまとめたものです。

## 目次

1. [基本的な確認事項](#1-基本的な確認事項)
2. [サーバー起動の問題](#2-サーバー起動の問題)
3. [認証関連の問題](#3-認証関連の問題)
4. [API接続エラー](#4-api接続エラー)
5. [データ表示の問題](#5-データ表示の問題)
6. [よくあるエラーメッセージと対処法](#6-よくあるエラーメッセージと対処法)

## 1. 基本的な確認事項

アプリケーションに問題が発生した場合、まず以下の基本的な確認を行ってください：

- 必要な環境変数が設定されているか
- 依存パッケージが正しくインストールされているか
- ポート番号の競合がないか

### 環境変数の確認

```bash
# .envファイルの内容を確認
cat .env

# 必要な環境変数が設定されているか確認
python check_env.py
```

### 依存パッケージの確認

```bash
# バックエンド依存パッケージの確認
cd api
pip install -r requirements.txt

# フロントエンド依存パッケージの確認
cd frontend
npm install
```

## 2. サーバー起動の問題

### バックエンドサーバーが起動しない場合

バックエンドサーバー（FastAPI）が起動しない場合は、以下の手順で確認してください：

1. プロセスの確認

```bash
# uvicornプロセスが実行されているか確認
ps aux | grep uvicorn
```

2. 手動でサーバーを起動

```bash
# apiディレクトリに移動してサーバーを起動
cd api
uvicorn app.main:app --reload --port 8000
```

3. ログの確認

サーバー起動時のログを確認し、エラーメッセージがないか確認してください。

### フロントエンドサーバーが起動しない場合

フロントエンドサーバー（Vite）が起動しない場合は、以下の手順で確認してください：

1. プロセスの確認

```bash
# nodeプロセスが実行されているか確認
ps aux | grep vite
```

2. 既存のプロセスを終了

```bash
# 既存のViteプロセスを終了（PIDは実際のプロセスIDに置き換えてください）
kill -9 <PID>
```

3. 手動でサーバーを起動

```bash
# frontendディレクトリに移動してサーバーを起動
cd frontend
npm run dev
```

## 3. 認証関連の問題

認証に関する問題が発生した場合は、以下の手順で確認してください：

### トークンの有効期限切れ

トークンの有効期限が切れている場合は、再度ログインが必要です：

1. ブラウザでアプリケーションにアクセスし、ログアウト
2. 再度ログイン

### 認証エラーのデバッグ

認証エラーが発生した場合は、以下のコマンドでAPIエンドポイントをテストしてください：

```bash
# 認証なしでAPIにアクセスした場合の応答を確認
curl -v http://localhost:8000/api/search/history
```

レスポンスが `{"detail":"Not authenticated"}` の場合は、認証が必要なエンドポイントに認証なしでアクセスしています。

### Google OAuth設定の確認

Google OAuth認証に問題がある場合は、以下の設定を確認してください：

1. `.env.development`ファイルのクライアントIDが正しいか確認
2. リダイレクトURIが正しく設定されているか確認

## 4. API接続エラー

APIへの接続エラーが発生した場合は、以下の手順で確認してください：

### APIエンドポイントの確認

```bash
# APIエンドポイントが応答するか確認
curl -v http://localhost:8000/api/health
```

### CORS設定の確認

CORS（Cross-Origin Resource Sharing）の設定に問題がある場合は、`api/app/main.py`ファイルのCORS設定を確認してください：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Viteのデフォルトポート
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 5. データ表示の問題

データが正しく表示されない場合は、以下の手順で確認してください：

### APIレスポンスの確認

```bash
# APIレスポンスを確認（認証が必要な場合はトークンを追加）
curl -v -H "Authorization: Bearer <your_token>" http://localhost:8000/api/books
```

### データベース接続の確認

```bash
# データベースファイルが存在するか確認
ls -la api/booklight.db

# SQLiteデータベースの内容を確認
sqlite3 api/booklight.db ".tables"
sqlite3 api/booklight.db "SELECT * FROM users;"
```

## 6. よくあるエラーメッセージと対処法

### 「Not authenticated」エラー

```
{"detail":"Not authenticated"}
```

**対処法**：
- ログインしているか確認
- トークンが有効か確認
- トークンがリクエストヘッダーに正しく含まれているか確認

### 「Navigation timeout」エラー

```
[Error] $Wt: Navigation timeout of 7000 ms exceeded
```

**対処法**：
- バックエンドサーバーが起動しているか確認
- フロントエンドサーバーが起動しているか確認
- ネットワーク接続に問題がないか確認

### 「Cannot read properties of undefined」エラー

```
Uncaught TypeError: Cannot read properties of undefined (reading 'page_content')
```

**対処法**：
- APIレスポンスの形式が期待通りか確認
- データが存在するか確認
- コンポーネントが正しくデータを処理しているか確認

## アプリケーション再起動手順

問題が解決しない場合は、アプリケーション全体を再起動してみてください：

1. 既存のプロセスを終了

```bash
# uvicornプロセスを終了
pkill -f uvicorn

# viteプロセスを終了
pkill -f vite
```

2. アプリケーションを再起動

```bash
# run_dev.shスクリプトを実行（バックエンドとフロントエンドを同時に起動）
./run_dev.sh

# または個別に起動
cd api && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

このガイドが、BooklightAIアプリケーションのトラブルシューティングに役立つことを願っています。問題が解決しない場合は、開発チームにお問い合わせください。
