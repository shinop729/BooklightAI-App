# Booklight AI

Kindleハイライト情報を収集・管理し、AI技術を活用してユーザーの読書体験を向上させるアプリケーション

## プロジェクト構成

このプロジェクトは以下のコンポーネントで構成されています：

- **バックエンド**: FastAPI（Python）
- **フロントエンド**: React + TypeScript（Vite）
- **Chrome拡張機能**: Kindleハイライト収集用

## フロントエンド移行について

このプロジェクトは、元々Streamlitで実装されていたフロントエンドをReact + TypeScriptに移行中です。移行の主な目的は以下の通りです：

- UIの柔軟性と拡張性の向上
- コンポーネントの再利用性の向上
- パフォーマンスの改善
- 保守性の向上

移行計画の詳細は `.clinerules/migration-plan.md` を参照してください。

## 開発環境のセットアップ

### 前提条件

- Python 3.9以上
- Node.js 18以上
- npm 9以上

### バックエンドのセットアップ

```bash
# 仮想環境の作成と有効化
python -m venv rag-env
source rag-env/bin/activate  # Windowsの場合: rag-env\Scripts\activate

# 依存関係のインストール
cd api
pip install -r requirements.txt

# 開発サーバーの起動
uvicorn app.main:app --reload --port 8000
```

### フロントエンドのセットアップ

```bash
# 依存関係のインストール
cd frontend
npm install

# 開発サーバーの起動
npm run dev
```

### 一括起動スクリプト

バックエンドとフロントエンドを同時に起動するには：

```bash
# 実行権限を付与（初回のみ）
chmod +x run_dev.sh

# 起動
./run_dev.sh
```

## 主な機能

- Google OAuth認証
- Kindleハイライトの自動収集（Chrome拡張機能）
- ハイライト検索（ベクトル検索 + BM25）
- AIチャット機能
- 書籍サマリー自動生成
- 書籍一覧表示
- オフラインサポート

## デプロイ

Herokuへのデプロイ手順は `HEROKU_DEPLOYMENT.md` を参照してください。

## トラブルシューティング

アプリケーションが正常に動作しない場合は、`docs/troubleshooting-guide.md` を参照してください。主な問題と対処法が記載されています。

## ライセンス

このプロジェクトは独自のライセンスの下で提供されています。
