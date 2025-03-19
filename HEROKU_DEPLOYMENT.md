# Herokuデプロイメント手順

## 前提条件
- Herokuアカウントの作成
- Heroku CLIのインストール
- Gitのインストール

## デプロイ手順

1. Herokuアプリの作成
```bash
heroku create booklight-ai-api
```

2. ビルドパックの設定
```bash
heroku buildpacks:set heroku/python
```

3. 環境変数の設定
```bash
# Google OAuth設定
heroku config:set GOOGLE_CLIENT_ID=your_google_client_id
heroku config:set GOOGLE_CLIENT_SECRET=your_google_client_secret

# JWT設定
heroku config:set JWT_SECRET_KEY=$(openssl rand -hex 32)
heroku config:set JWT_ALGORITHM=HS256
heroku config:set ACCESS_TOKEN_EXPIRE_MINUTES=30

# フロントエンド設定
heroku config:set FRONTEND_URL=https://booklight-ai-app.herokuapp.com
heroku config:set REDIRECT_URI=https://booklight-ai-api.herokuapp.com/auth/callback

# デバッグ設定
heroku config:set ENVIRONMENT=production
heroku config:set DEBUG=false
heroku config:set LOG_LEVEL=WARNING
heroku config:set DEBUG_API_KEY=$(openssl rand -hex 16)

# データベース設定
heroku addons:create heroku-postgresql:hobby-basic
```

4. Herokuにデプロイ
```bash
# プロジェクトをGitリポジトリに追加（まだ行っていない場合）
git init
git add .
git commit -m "Initial Heroku deployment setup"

# Herokuリモートを追加
heroku git:remote -a booklight-ai-api

# デプロイ
git push heroku main
```

5. データベースマイグレーション
```bash
heroku run -a booklight-ai-api cd api && alembic upgrade head
```

6. アプリの起動確認
```bash
heroku open -a booklight-ai-api
heroku logs --tail -a booklight-ai-api
```

## トラブルシューティング

- デプロイ失敗時のログ確認
```bash
heroku logs --tail
```

- 環境変数の確認
```bash
heroku config -a booklight-ai-api
```

## 注意点
- Google Cloud ConsoleでOAuth認証情報を更新
- 承認済みリダイレクトURIに以下を追加:
  `https://booklight-ai-api.herokuapp.com/auth/callback`
