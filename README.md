# Booklight AI - 書籍ハイライト管理アプリ

Booklight AIは、Kindleなどの電子書籍からエクスポートしたハイライト情報を管理し、AIを活用して書籍ごとのサマリを生成するアプリケーションです。

## 主な機能

- Kindleハイライトのアップロードと管理
- 書籍ごとのAIによるサマリ生成
- 書籍一覧表示
- 書籍詳細表示（ハイライト一覧）
- ハイライト検索
- AIチャット（ハイライト情報を活用）

## 新機能: AIによる書籍サマリ生成

アップロードされた書籍のハイライト情報をもとに、AIが書籍ごとのサマリデータを生成し、参照先のサマリファイルとして保存します。

### 使い方

1. ハイライトアップロードページでKindleハイライトをアップロード
2. 「ハイライトを保存」ボタンをクリック
3. AIが自動的に書籍ごとのサマリを生成
4. 生成されたサマリは書籍一覧ページと書籍詳細ページで閲覧可能

### 技術的な詳細

- OpenAI APIを使用してサマリを生成
- 書籍ごとのハイライトを集約し、GPT-4モデルを使用して包括的なサマリを作成
- 生成されたサマリはユーザーごとに`BookSummaries.csv`ファイルに保存

## 必要な環境変数

アプリケーションを実行するには、以下の環境変数が必要です：

```
OPENAI_API_KEY=your_openai_api_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
REDIRECT_URI=http://localhost:8505/
```

## インストールと実行

1. リポジトリをクローン
2. 必要なパッケージをインストール: `pip install -r requirements.txt`
3. `.env`ファイルに必要な環境変数を設定
4. アプリケーションを実行: `streamlit run Home.py`

## ファイル構成

- `Home.py`: メインページ
- `auth.py`: 認証関連の処理
- `book_summary_generator.py`: AIによる書籍サマリ生成機能
- `pages/`: 各ページのスクリプト
  - `Upload.py`: ハイライトアップロードページ
  - `BookList.py`: 書籍一覧ページ
  - `BookDetail.py`: 書籍詳細ページ
  - `Search.py`: 検索ページ
  - `Chat.py`: チャットページ

## テスト

- `test_openai_api.py`: OpenAI APIの接続テスト
- `test_book_summary_generator.py`: 書籍サマリ生成機能のテスト
