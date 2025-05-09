# Booklight AI テスト計画

このドキュメントでは、Booklight AIアプリケーションのテスト計画を説明します。

## 1. テスト環境

### 開発環境
- ローカル開発環境
  - OS: macOS / Windows / Linux
  - Python 3.12.2
  - Node.js 18+
  - Chrome 最新版

### ステージング環境
- Heroku (hobby-dev)
  - PostgreSQL (hobby-dev)
  - Python 3.12.2

### 本番環境
- Heroku (standard-1x)
  - PostgreSQL (standard-0)
  - Python 3.12.2

## 2. テスト種別

### 2.1 単体テスト

#### APIエンドポイント
- 認証関連エンドポイント
  - `/token` - アクセストークン取得
  - `/auth/google` - Google OAuth認証リダイレクト
  - `/auth/callback` - Google OAuth認証コールバック
  - `/auth/google/token` - Google IDトークン検証
  - `/auth/user` - ユーザー情報取得

- ハイライト管理エンドポイント
  - `/api/highlights` (POST) - ハイライトアップロード
  - `/api/highlights` (GET) - ハイライト取得

#### Chromeエクステンション
- バックグラウンドスクリプト
  - 認証機能
  - ハイライト送信機能
  - オフライン対応

- コンテンツスクリプト
  - ハイライト収集機能
  - DOM監視機能

- ポップアップUI
  - 認証状態表示
  - ハイライト収集ボタン
  - エラー表示

### 2.2 統合テスト

- 認証フロー
  - Google OAuth認証
  - トークン検証
  - セッション管理

- ハイライト管理フロー
  - ハイライト収集 → 送信 → 保存 → 取得

### 2.3 エンドツーエンドテスト

- Chromeエクステンション + APIサーバー
  - 認証からハイライト収集までの一連の流れ
  - エラーケースの処理

## 3. テストケース

### 3.1 認証機能

#### TC-AUTH-001: Google OAuth認証フロー
1. Chromeエクステンションのポップアップを開く
2. 「Googleでログイン」ボタンをクリック
3. Google認証ページが表示されることを確認
4. Googleアカウントでログイン
5. 認証後、エクステンションのポップアップにユーザー情報が表示されることを確認

#### TC-AUTH-002: トークン期限切れ
1. 期限切れのトークンを使用してAPIリクエストを送信
2. 401エラーが返されることを確認
3. エクステンションが再認証を促すことを確認

#### TC-AUTH-003: ログアウト
1. ログイン状態でエクステンションのポップアップを開く
2. 「ログアウト」ボタンをクリック
3. ログイン画面に戻ることを確認
4. ローカルストレージからトークンが削除されていることを確認

### 3.2 ハイライト収集機能

#### TC-HL-001: テストページからのハイライト収集
1. テストページ（`chrome-extension/test-page.html`）を開く
2. エクステンションのポップアップを開く
3. 「ハイライトを収集」ボタンをクリック
4. 成功メッセージが表示されることを確認
5. APIサーバーにハイライトが保存されていることを確認

#### TC-HL-002: Kindle Web Readerからのハイライト収集
1. Kindle Web Readerのハイライトページを開く
2. エクステンションのポップアップを開く
3. 「ハイライトを収集」ボタンをクリック
4. 成功メッセージが表示されることを確認
5. APIサーバーにハイライトが保存されていることを確認

#### TC-HL-003: 重複ハイライトの処理
1. 既に保存済みのハイライトを含むページでハイライト収集を実行
2. 重複を除外して新規ハイライトのみが保存されることを確認
3. 成功メッセージに新規ハイライト数が正しく表示されることを確認

#### TC-HL-004: オフラインモード
1. ネットワーク接続を切断
2. ハイライト収集を実行
3. オフラインモードでハイライトが保存されることを確認
4. ネットワーク接続を復旧
5. 保存されたハイライトがサーバーに同期されることを確認

### 3.3 エラーハンドリング

#### TC-ERR-001: APIサーバー接続エラー
1. APIサーバーを停止
2. ハイライト収集を実行
3. 適切なエラーメッセージが表示されることを確認
4. エラー詳細が表示されることを確認

#### TC-ERR-002: 認証エラー
1. 無効なトークンを設定
2. ハイライト収集を実行
3. 認証エラーメッセージが表示されることを確認
4. 再ログインを促すメッセージが表示されることを確認

#### TC-ERR-003: ハイライト収集エラー
1. ハイライトが存在しないページでハイライト収集を実行
2. 適切なエラーメッセージが表示されることを確認

### 3.4 パフォーマンステスト

#### TC-PERF-001: 大量ハイライト処理
1. 1000件以上のハイライトを含むテストページを用意
2. ハイライト収集を実行
3. 処理時間を計測
4. メモリ使用量を計測
5. すべてのハイライトが正しく保存されることを確認

#### TC-PERF-002: 同時リクエスト処理
1. 複数のクライアントから同時にAPIリクエストを送信
2. サーバーの応答時間を計測
3. すべてのリクエストが正しく処理されることを確認

## 4. テスト実行手順

### 4.1 開発環境でのテスト

```bash
# APIサーバーの起動
cd api
uvicorn app.main:app --reload

# テストの実行
pytest tests/
```

### 4.2 Chromeエクステンションのテスト

1. Chromeを開き、`chrome://extensions/` にアクセス
2. 「デベロッパーモード」を有効化
3. 「パッケージ化されていない拡張機能を読み込む」をクリック
4. `chrome-extension` ディレクトリを選択
5. テストページ（`chrome-extension/test-page.html`）を開く
6. 各テストケースを手動で実行

### 4.3 エンドツーエンドテスト

```bash
# APIサーバーの起動
cd api
uvicorn app.main:app

# Puppeteerを使用したE2Eテスト
cd tests/e2e
npm test
```

## 5. テスト結果の記録

テスト結果は以下の形式で記録します：

```
テストID: TC-XXX-YYY
実行日時: YYYY-MM-DD HH:MM
実行者: 名前
環境: 開発/ステージング/本番
結果: 成功/失敗
詳細: 
- 期待される結果: ...
- 実際の結果: ...
- スクリーンショット: [リンク]
```

## 6. バグ追跡

発見されたバグは以下の形式で記録します：

```
バグID: BUG-XXX
報告日時: YYYY-MM-DD HH:MM
報告者: 名前
環境: 開発/ステージング/本番
重要度: 低/中/高/致命的
再現手順:
1. ...
2. ...
3. ...
期待される動作: ...
実際の動作: ...
スクリーンショット: [リンク]
```

## 7. テスト自動化

### 7.1 単体テスト自動化

```python
# api/tests/test_auth.py
def test_token_endpoint():
    # テストコード

# api/tests/test_highlights.py
def test_upload_highlights():
    # テストコード
```

### 7.2 E2Eテスト自動化

```javascript
// tests/e2e/test_extension.js
describe('Chrome Extension', () => {
  it('should collect highlights from test page', async () => {
    // テストコード
  });
});
```

## 8. テスト環境の準備

### 8.1 開発環境

```bash
# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt

# データベースの準備
cd api
alembic upgrade head
```

### 8.2 テストデータの準備

```bash
# テストデータの生成
python api/tests/generate_test_data.py
```

## 9. テスト実施スケジュール

1. 単体テスト: 各機能実装後
2. 統合テスト: 週1回
3. エンドツーエンドテスト: リリース前
4. パフォーマンステスト: 月1回

## 10. テスト担当者

- API単体テスト: バックエンド開発者
- Chromeエクステンション単体テスト: フロントエンド開発者
- 統合テスト: QAエンジニア
- エンドツーエンドテスト: QAエンジニア
- パフォーマンステスト: インフラエンジニア
