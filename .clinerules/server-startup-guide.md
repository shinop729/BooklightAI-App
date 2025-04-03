# BooklightAI 開発サーバー起動ガイド

このガイドでは、BooklightAIアプリケーションのバックエンドとフロントエンドの起動手順を詳細に説明します。また、ポート番号が既に使用されている場合の対処法やトラブルシューティングについても記載しています。

## 目次

1. [環境設定の確認](#環境設定の確認)
2. [起動方法](#起動方法)
   - [一括起動（推奨）](#一括起動推奨)
   - [個別起動](#個別起動)
3. [ポート番号が既に使用されている場合の対処法](#ポート番号が既に使用されている場合の対処法)
   - [使用中のプロセスの確認](#使用中のプロセスの確認)
   - [プロセスの終了](#プロセスの終了)
   - [別のポートでの起動](#別のポートでの起動)
   - [環境変数の更新](#環境変数の更新)
4. [トラブルシューティング](#トラブルシューティング)
   - [よくあるエラーと解決策](#よくあるエラーと解決策)
   - [ログの確認方法](#ログの確認方法)

## 環境設定の確認

開発サーバーを起動する前に、以下の環境設定が正しく行われていることを確認してください。

### 環境変数

`.env`ファイルに以下の環境変数が設定されていることを確認します：

```bash
# 開発環境設定
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# フロントエンド設定
FRONTEND_URL=http://localhost:5173
REDIRECT_URI=http://localhost:8000/auth/callback

# データベース設定
DATABASE_URL=sqlite:///./booklight.db

# OpenAI API設定
OPENAI_API_KEY=your_openai_api_key
```

### フロントエンド環境変数

`frontend/.env.development`ファイルに以下の環境変数が設定されていることを確認します：

```bash
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your_google_client_id
```

### 依存関係の確認

バックエンドとフロントエンドの依存関係がインストールされていることを確認します：

```bash
# バックエンド依存関係のインストール
cd api
pip install -r requirements.txt

# フロントエンド依存関係のインストール
cd frontend
npm install
```

## 起動方法

BooklightAIアプリケーションは、バックエンドとフロントエンドの両方を起動する必要があります。起動方法は以下の2つがあります：

### 一括起動（推奨）

`run_dev.sh`スクリプトを使用すると、バックエンドとフロントエンドを一括で起動できます：

```bash
bash run_dev.sh
```

このスクリプトは以下の処理を行います：
1. 環境変数`FRONTEND_URL`を`http://localhost:5173`に設定
2. FastAPIバックエンドを`api`ディレクトリで起動（ポート8000）
3. Reactフロントエンドを`frontend`ディレクトリで起動（ポート5173）

起動後、以下のURLでアクセスできます：
- バックエンド: http://localhost:8000
- フロントエンド: http://localhost:5173

### 個別起動

バックエンドとフロントエンドを個別に起動することもできます：

#### バックエンドの起動

```bash
cd api
uvicorn app.main:app --reload --port 8000
```

#### フロントエンドの起動

```bash
cd frontend
npm run dev
```

または、`start_frontend.sh`スクリプトを使用することもできます：

```bash
bash start_frontend.sh
```

## ポート番号が既に使用されている場合の対処法

バックエンドまたはフロントエンドの起動時に「Address already in use」エラーが発生した場合、そのポート番号が既に使用されています。以下の手順で対処してください。

### 使用中のプロセスの確認

#### macOSの場合

```bash
# ポート8000を使用しているプロセスを確認
lsof -i :8000

# または
ps aux | grep uvicorn

# ポート5173を使用しているプロセスを確認
lsof -i :5173

# または
ps aux | grep vite
```

#### Linuxの場合

```bash
# ポート8000を使用しているプロセスを確認
sudo netstat -tulpn | grep 8000

# または
ps aux | grep uvicorn

# ポート5173を使用しているプロセスを確認
sudo netstat -tulpn | grep 5173

# または
ps aux | grep vite
```

#### Windowsの場合

```bash
# ポート8000を使用しているプロセスを確認
netstat -ano | findstr :8000

# ポート5173を使用しているプロセスを確認
netstat -ano | findstr :5173
```

### プロセスの終了

プロセスIDを確認したら、そのプロセスを終了します：

#### macOSとLinuxの場合

```bash
# 通常の終了
kill <PID>

# 強制終了（上記で終了しない場合）
kill -9 <PID>
```

#### Windowsの場合

```bash
taskkill /PID <PID> /F
```

### 別のポートでの起動

既存のプロセスを終了できない場合や、別のポートを使用したい場合は、以下のように別のポートで起動できます：

#### バックエンドの別ポートでの起動

```bash
cd api
uvicorn app.main:app --reload --port 8001
```

#### フロントエンドの別ポートでの起動

```bash
cd frontend
npm run dev -- --port 5174
```

### 環境変数の更新

バックエンドのポートを変更した場合は、フロントエンドの環境変数を更新する必要があります：

```bash
# frontend/.env.development ファイルを編集
VITE_API_URL=http://localhost:8001
```

フロントエンドのポートを変更した場合は、バックエンドの環境変数を更新する必要があります：

```bash
# .env ファイルを編集
FRONTEND_URL=http://localhost:5174
```

## トラブルシューティング

### よくあるエラーと解決策

#### 「Address already in use」エラー

```
ERROR: [Errno 48] Address already in use
```

**解決策**：
- [使用中のプロセスの確認](#使用中のプロセスの確認)と[プロセスの終了](#プロセスの終了)の手順に従ってください。
- または、[別のポートでの起動](#別のポートでの起動)の手順に従ってください。

#### APIリクエストエラー

フロントエンドからバックエンドへのAPIリクエストが失敗する場合：

**解決策**：
1. バックエンドが正常に起動しているか確認してください。
2. フロントエンドの環境変数`VITE_API_URL`が正しいバックエンドのURLを指しているか確認してください。
3. ブラウザのコンソールでネットワークエラーを確認してください。
4. CORSエラーが発生している場合は、バックエンドのCORS設定を確認してください。

#### 「Module not found」エラー

```
Error: Cannot find module '...'
```

**解決策**：
1. 依存関係が正しくインストールされているか確認してください。
2. バックエンドの場合は`pip install -r requirements.txt`を実行してください。
3. フロントエンドの場合は`npm install`を実行してください。

#### データベースエラー

```
SQLAlchemyError: ...
```

**解決策**：
1. データベースファイル（`booklight.db`）が存在するか確認してください。
2. データベースのマイグレーションを実行してください：
   ```bash
   cd api
   alembic upgrade head
   ```

### ログの確認方法

#### バックエンドログ

バックエンドのログは、起動時のコンソール出力で確認できます。また、`api/app/logs/`ディレクトリにもログファイルが保存されます。

#### フロントエンドログ

フロントエンドのログは、ブラウザの開発者ツールのコンソールで確認できます。また、起動時のコンソール出力でも確認できます。

## まとめ

このガイドでは、BooklightAIアプリケーションのバックエンドとフロントエンドの起動手順を詳細に説明しました。また、ポート番号が既に使用されている場合の対処法やトラブルシューティングについても記載しています。

問題が解決しない場合は、開発チームに連絡してください。
