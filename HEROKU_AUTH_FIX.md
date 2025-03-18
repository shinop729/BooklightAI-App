# Heroku認証問題の修正手順

このドキュメントでは、Herokuでホストしているのにローカルサーバーを起動しないと認証が動かない問題の修正手順を説明します。

## 修正内容の概要

1. Chrome拡張機能のAPI URLを本番環境用に変更
2. リダイレクトURLの自動検出機能の追加
3. 環境変数の適切な設定
4. Heroku環境の検出と適応

## 1. Herokuへのデプロイ前の準備

### 1.1 Chrome拡張機能の更新

Chrome拡張機能のバックグラウンドスクリプト（`chrome-extension/src/background.js`）のAPI URLを本番環境のURLに更新します：

```javascript
// APIエンドポイント設定
// const API_BASE_URL = 'http://localhost:8000'; // 開発環境
const API_BASE_URL = 'https://your-booklight-api.herokuapp.com'; // 本番環境
```

※ `your-booklight-api` の部分は実際のHerokuアプリ名に置き換えてください。

### 1.2 Herokuアプリの作成（既存の場合はスキップ）

```bash
# Heroku CLIにログイン
heroku login

# アプリケーションを作成
heroku create your-booklight-api

# PostgreSQLアドオンを追加
heroku addons:create heroku-postgresql:hobby-dev -a your-booklight-api
```

## 2. 環境変数の設定

以下の環境変数をHerokuに設定します：

```bash
# アプリ名の設定（自動URL検出のため）
heroku config:set HEROKU_APP_NAME="your-booklight-api" -a your-booklight-api

# JWT認証用のシークレットキー
heroku config:set JWT_SECRET_KEY="your-secret-key" -a your-booklight-api

# Google OAuth認証用の設定
heroku config:set GOOGLE_CLIENT_ID="your-google-client-id" -a your-booklight-api
heroku config:set GOOGLE_CLIENT_SECRET="your-google-client-secret" -a your-booklight-api

# フロントエンドURL（認証コールバック用）
heroku config:set FRONTEND_URL="https://your-booklight-api.herokuapp.com" -a your-booklight-api

# リダイレクトURI（Google認証用）
heroku config:set REDIRECT_URI="https://your-booklight-api.herokuapp.com/auth/callback" -a your-booklight-api
```

## 3. Google OAuth設定の更新

Google Cloud Consoleで、以下のリダイレクトURIを承認済みリダイレクトURIに追加します：

```
https://your-booklight-api.herokuapp.com/auth/callback
```

## 4. デプロイ

```bash
# Gitリポジトリの初期化（既に初期化されている場合は不要）
git init
git add .
git commit -m "Fix authentication for Heroku deployment"

# Herokuリモートの追加（既に追加されている場合は不要）
heroku git:remote -a your-booklight-api

# デプロイ
git push heroku main
```

## 5. データベースマイグレーション

```bash
# Alembicマイグレーションの実行
heroku run alembic upgrade head -a your-booklight-api
```

## 6. アプリケーションの起動

```bash
# アプリケーションを起動
heroku ps:scale web=1 -a your-booklight-api

# アプリケーションを開く
heroku open -a your-booklight-api
```

## 7. ログの確認

```bash
# ログを表示
heroku logs --tail -a your-booklight-api
```

## 8. トラブルシューティング

### 8.1 認証エラーが発生する場合

1. ログを確認して具体的なエラーメッセージを確認します：
   ```bash
   heroku logs --tail -a your-booklight-api
   ```

2. 環境変数が正しく設定されているか確認します：
   ```bash
   heroku config -a your-booklight-api
   ```

3. Google Cloud Consoleで、リダイレクトURIが正しく設定されているか確認します。

### 8.2 Chrome拡張機能が接続できない場合

1. Chrome拡張機能のバックグラウンドスクリプト（`chrome-extension/src/background.js`）のAPI URLが正しいか確認します。
2. Chrome拡張機能のコンソールログを確認します（拡張機能のデバッグモードを有効にして確認）。

## 9. 修正内容の詳細

### 9.1 Chrome拡張機能のAPI URL変更

`chrome-extension/src/background.js`のAPI URLを本番環境用に変更しました。

### 9.2 リダイレクトURLの自動検出

`api/app/main.py`の`auth_callback`関数を修正して、リクエストのホストからリダイレクトURLを自動的に検出するようにしました。

### 9.3 環境変数の自動検出

`auth.py`と`api/app/auth.py`を修正して、Heroku環境を自動的に検出し、適切なリダイレクトURIを設定するようにしました。

### 9.4 Heroku環境の検出

`run_combined.py`を修正して、Heroku環境を検出し、適切なポート設定を行うようにしました。
