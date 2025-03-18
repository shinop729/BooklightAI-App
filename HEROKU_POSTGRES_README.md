# Heroku Postgres設定ガイド

## 注意事項

### セキュリティ
- DATABASE_URLは絶対に公開しないでください
- .envファイルは.gitignoreに追加してください
- 環境変数は必ずHerokuのConfig Varsで管理してください

### パフォーマンス
- hobby-devプランは無料枠で、リソースに制限があります
- 同時接続数や処理能力に制限があるため、本番環境では有料プランへのアップグレードを検討してください

### データ移行
- 初回デプロイ時は`migrate_data.py`スクリプトを実行してください
- 既存のCSVデータは自動的にPostgresデータベースに移行されます

### 接続とマイグレーション
1. データベース接続の確認
```bash
heroku pg:info
```

2. データベースマイグレーションの実行
```bash
heroku run alembic upgrade head
```

3. データ移行スクリプトの実行
```bash
heroku run python api/migrate_data.py
```

### トラブルシューティング
- データベース接続エラー: 
  - Heroku Config VarsのDATABASE_URLを再確認
  - ネットワーク接続を確認
- マイグレーションエラー:
  - Alembicの設定を再確認
  - データベーススキーマの互換性を確認

### 推奨事項
- 定期的なデータバックアップ
- 本番環境では接続プールの設定を最適化
- セキュリティパッチの適用

## 環境変数の設定例
```bash
heroku config:set DATABASE_URL=postgresql://username:password@host:port/database
heroku config:set GOOGLE_CLIENT_ID=your_client_id
heroku config:set GOOGLE_CLIENT_SECRET=your_client_secret
```

## モニタリングとログ
- データベースのパフォーマンス監視
```bash
heroku pg:diagnose
```

- ログの確認
```bash
heroku logs --tail
