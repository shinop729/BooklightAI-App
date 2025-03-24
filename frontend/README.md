# Booklight AI フロントエンド

Booklight AIのReact + TypeScriptフロントエンドアプリケーション。

## 概要

このプロジェクトは、Booklight AIのフロントエンドを提供するReactアプリケーションです。Kindleのハイライト情報を収集・管理し、AI技術を活用してユーザーの読書体験を向上させる機能を提供します。

## 技術スタック

- **フレームワーク**: React 19
- **言語**: TypeScript
- **ビルドツール**: Vite
- **スタイリング**: Tailwind CSS
- **状態管理**: Zustand
- **APIクライアント**: Axios
- **データフェッチング**: TanStack Query (React Query)
- **ルーティング**: React Router
- **オフラインサポート**: Service Worker, Workbox

## 機能

- Google OAuth認証
- ハイライト検索
- 書籍一覧表示
- AIチャット機能
- ハイライトアップロード
- オフラインサポート
- PWA対応

## 実装済みページ

- **ホーム (Home.tsx)**: ランダムハイライト表示、最近の書籍
- **検索 (Search.tsx)**: キーワードによるハイライト検索
- **チャット (Chat.tsx)**: AIアシスタントとのチャット
- **書籍一覧 (BookList.tsx)**: 書籍の一覧表示、フィルタリング、ソート
- **書籍詳細 (BookDetail.tsx)**: 書籍情報、ハイライト一覧、サマリー表示
- **アップロード (Upload.tsx)**: CSVファイルのアップロード、サマリー生成

## 開発環境のセットアップ

### 前提条件

- Node.js 18以上
- npm 9以上

### インストール

```bash
# 依存関係のインストール
npm install
```

### 環境変数の設定

`.env.development`ファイルを作成し、以下の変数を設定します：

```
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your_google_client_id
```

### 開発サーバーの起動

```bash
# 開発サーバーの起動
npm run dev
```

または、バックエンドとフロントエンドを同時に起動するには：

```bash
# プロジェクトルートディレクトリで
./run_dev.sh
```

## ビルド

```bash
# 本番用ビルド
npm run build
```

ビルドされたファイルは`dist`ディレクトリに出力されます。

## プロジェクト構造

```
src/
├── api/            # APIクライアント、リクエスト関数
├── assets/         # 画像、フォントなどの静的リソース
├── components/     # 再利用可能なコンポーネント
│   ├── common/     # ボタン、カードなどの基本コンポーネント
│   ├── layout/     # レイアウト関連コンポーネント
│   └── feature/    # 機能別コンポーネント
├── context/        # Reactコンテキスト（認証など）
├── hooks/          # カスタムフック
├── pages/          # ページコンポーネント
├── services/       # 外部サービス連携
├── store/          # 状態管理（Zustand）
├── styles/         # グローバルスタイル
├── types/          # TypeScript型定義
└── utils/          # ユーティリティ関数
```

## 主要コンポーネント

### レイアウト

- **Layout.tsx**: アプリケーション全体のレイアウト
- **Header.tsx**: ヘッダーコンポーネント
- **Sidebar.tsx**: サイドバーナビゲーション

### 共通コンポーネント

- **HighlightCard.tsx**: ハイライト表示用カード
- **BookCard.tsx**: 書籍表示用カード

### カスタムフック

- **useAuth.tsx**: 認証状態管理
- **useBooks.ts**: 書籍データ取得
- **useSearch.ts**: 検索機能
- **useChat.ts**: チャット機能

### 状態管理

- **summaryProgressStore.ts**: サマリー生成進捗状態
- **chatStore.ts**: チャット履歴管理

## バックエンドとの連携

このフロントエンドアプリケーションは、FastAPIで実装されたバックエンドAPIと連携します。バックエンドAPIは以下の機能を提供します：

- ユーザー認証
- ハイライトデータの保存と取得
- AI検索機能
- チャット機能
- 書籍サマリー生成

## デプロイ

### Herokuへのデプロイ

1. Herokuアカウントを作成し、Heroku CLIをインストールします
2. 以下のコマンドを実行します：

```bash
heroku create booklight-frontend
git push heroku main
```

### 環境変数の設定

Herokuダッシュボードで以下の環境変数を設定します：

- `VITE_API_URL`: 本番環境のAPIエンドポイント
- `VITE_GOOGLE_CLIENT_ID`: Google OAuth用のクライアントID

## ライセンス

このプロジェクトは独自のライセンスの下で提供されています。詳細はLICENSEファイルを参照してください。
