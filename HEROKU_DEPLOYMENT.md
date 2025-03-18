# Herokuデプロイ手順

このドキュメントでは、BooklightAIアプリケーションをHerokuにデプロイする手順を説明します。

## 変更内容

1. **統合スクリプト（`run_combined.py`）の作成**
   - FastAPIとStreamlitを1つのプロセスとして実行するスクリプト
   - FastAPIはバックグラウンドスレッドで実行
   - Streamlitはメインプロセスとして実行

2. **`Procfile`の修正**
   - 統合スクリプトを使用するように変更

3. **`Dockerfile`の修正**
   - 統合スクリプトを使用するように変更

## デプロイ手順

### 1. 変更をコミット

```bash
git add run_combined.py Procfile Dockerfile
git commit -m "Add combined FastAPI and Streamlit runner for Heroku deployment"
```

### 2. Herokuにプッシュ

```bash
git push heroku main
```

### 3. 環境変数の設定

Herokuダッシュボードから、または以下のコマンドを使用して環境変数を設定します：

```bash
# FastAPIが使用するポート
heroku config:set API_PORT=8000

# フロントエンドのURL（Herokuアプリのドメイン）
heroku config:set FRONTEND_URL=https://<your-heroku-app-name>.herokuapp.com
```

### 4. デプロイの確認

```bash
heroku open
```

ブラウザが開き、Streamlitフロントエンドが表示されることを確認します。

## トラブルシューティング

### ログの確認

問題が発生した場合は、Herokuのログを確認します：

```bash
heroku logs --tail
```

### よくある問題

1. **FastAPIが起動しない**
   - `API_PORT`環境変数が正しく設定されているか確認
   - ログでエラーメッセージを確認

2. **Streamlitが起動しない**
   - ログでエラーメッセージを確認
   - 必要なパッケージがすべてインストールされているか確認

3. **認証リダイレクトが機能しない**
   - `FRONTEND_URL`環境変数が正しく設定されているか確認
   - Google OAuth設定が正しいか確認

## 注意事項

- この設定では、FastAPIとStreamlitが同じHerokuアプリ内で実行されます
- FastAPIは`API_PORT`（デフォルト：8000）で実行され、Streamlitは`PORT`（Herokuが自動的に設定）で実行されます
- 内部的には、FastAPIはStreamlitからAPIエンドポイントとして利用可能です
