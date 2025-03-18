# Herokuデプロイ手順

このドキュメントでは、Booklight AIアプリケーションをHerokuにデプロイする手順を説明します。

## 前提条件

- Herokuアカウント
- Heroku CLI
- Git
- PostgreSQLアドオン（Heroku上で使用）

## 1. Herokuアプリケーションの作成

```bash
# Heroku CLIにログイン
heroku login

# アプリケーションを作成
heroku create booklight-ai

# PostgreSQLアドオンを追加
heroku addons:create heroku-postgresql:hobby-dev -a booklight-ai
```

## 2. 環境変数の設定

```bash
# JWT認証用のシークレットキー
heroku config:set JWT_SECRET_KEY="your-secret-key" -a booklight-ai

# Google OAuth認証用の設定
heroku config:set GOOGLE_CLIENT_ID="your-google-client-id" -a booklight-ai
heroku config:set GOOGLE_CLIENT_SECRET="your-google-client-secret" -a booklight-ai
heroku config:set REDIRECT_URI="https://booklight-ai.herokuapp.com/auth/callback" -a booklight-ai

# フロントエンドURL
heroku config:set FRONTEND_URL="https://booklight-ai.herokuapp.com" -a booklight-ai

# デバッグモード（本番環境ではfalse）
heroku config:set DEBUG="false" -a booklight-ai
```

## 3. データベースマイグレーション

```bash
# Alembicマイグレーションの実行
heroku run alembic upgrade head -a booklight-ai

# データ移行スクリプトの実行
heroku run python api/migrate_data.py -a booklight-ai
```

## 4. デプロイ

```bash
# Gitリポジトリの初期化（既に初期化されている場合は不要）
git init
git add .
git commit -m "Initial commit"

# Herokuリモートの追加
heroku git:remote -a booklight-ai

# デプロイ
git push heroku main
```

## 5. アプリケーションの起動

```bash
# アプリケーションを起動
heroku ps:scale web=1 -a booklight-ai

# アプリケーションを開く
heroku open -a booklight-ai
```

## 6. ログの確認

```bash
# ログを表示
heroku logs --tail -a booklight-ai
```

## 7. トラブルシューティング

### データベース接続エラー

データベース接続エラーが発生した場合は、以下のコマンドでデータベースURLを確認してください。

```bash
heroku config:get DATABASE_URL -a booklight-ai
```

### アプリケーションのクラッシュ

アプリケーションがクラッシュした場合は、以下のコマンドでログを確認してください。

```bash
heroku logs --tail -a booklight-ai
```

### デプロイエラー

デプロイエラーが発生した場合は、以下のコマンドでビルドログを確認してください。

```bash
heroku builds:info -a booklight-ai
```

## 8. Chromeエクステンションの設定

Chromeエクステンションのバックグラウンドスクリプト（`chrome-extension/src/background.js`）のAPI URLを本番環境のURLに更新してください。

```javascript
// APIエンドポイント設定
const API_BASE_URL = 'https://booklight-ai.herokuapp.com'; // 本番環境
```

また、マニフェストファイル（`chrome-extension/manifest.json`）のホスト権限も更新してください。

```json
"host_permissions": [
  "https://read.amazon.co.jp/*",
  "https://read.amazon.com/*",
  "https://booklight-ai.herokuapp.com/*",
  "https://accounts.google.com/*",
  "https://oauth2.googleapis.com/*"
]
```

## 9. 定期的なバックアップ

データベースの定期的なバックアップを設定することをお勧めします。

```bash
# バックアップスケジューラーの追加
heroku addons:create pgbackups:auto-month -a booklight-ai

# 手動バックアップの作成
heroku pg:backups:capture -a booklight-ai
```

## 10. スケーリング（必要に応じて）

アプリケーションの負荷が増加した場合は、以下のコマンドでスケーリングを行ってください。

```bash
# Webプロセスのスケーリング
heroku ps:scale web=2 -a booklight-ai

# データベースのアップグレード
heroku addons:upgrade heroku-postgresql:standard-0 -a booklight-ai
