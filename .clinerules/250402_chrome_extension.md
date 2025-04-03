# Kindle ハイライト抽出エクステンション実装計画

## 概要

Kindle Web リーダーからハイライトデータを抽出するChrome拡張機能を開発します。この拡張機能は、書籍のタイトル、著者名、ハイライト内容を取得し、さらに書籍のカバー画像も抽出します。また、既存のハイライト情報がある場合は、最新のハイライトのみを取得・更新するロジックも実装します。

## 機能要件

1. **基本データの抽出**
   - 書籍タイトル
   - 著者名
   - ハイライト内容（テキスト）
   - ハイライト位置（ページ番号または位置番号）
   - 書籍のカバー画像

2. **差分更新機能**
   - 既存のハイライト情報との比較
   - 最新のハイライトのみを追加・更新

3. **ユーザーインターフェース**
   - データ抽出開始ボタン
   - 抽出状況の表示
   - エクスポート機能（JSON、CSV等）

## 技術的アプローチ

### 1. DOM構造解析

Kindleウェブリーダーページの構造を分析した結果、以下の要素を特定します：

- **タイトル**: `.メモ付きのKINDLE本:` の次のテキスト要素
- **著者**: タイトルの下にある著者情報
- **ハイライト**: `.オレンジ色のハイライト` 要素とその内容
- **位置情報**: 各ハイライトに付随する `位置:` の情報
- **カバー画像**: 左側に表示されている画像要素

### 2. データ抽出プロセス

1. **DOM監視**
   - MutationObserverを使用してページの読み込みを検知
   - ページ内のKindleリーダー要素が完全に読み込まれたことを確認

2. **データ解析**
   ```javascript
   function extractBookData() {
     // タイトル抽出
     const titleElement = document.querySelector('.メモ付きのKINDLE本 + div');
     const title = titleElement ? titleElement.textContent.trim() : null;
     
     // 著者抽出
     const authorElement = document.querySelector('.著者:');
     const author = authorElement ? authorElement.nextElementSibling.textContent.trim() : null;
     
     // カバー画像抽出
     const coverImage = document.querySelector('.book-cover img');
     const coverSrc = coverImage ? coverImage.src : null;
     
     return { title, author, coverSrc };
   }
   
   function extractHighlights() {
     const highlights = [];
     const highlightElements = document.querySelectorAll('.オレンジ色のハイライト');
     
     highlightElements.forEach(element => {
       const text = element.textContent.trim();
       const location = element.closest('.highlight-container').querySelector('.位置').textContent;
       
       highlights.push({
         text,
         location,
         timestamp: new Date().toISOString()
       });
     });
     
     return highlights;
   }
   ```

3. **差分検出ロジック**
   ```javascript
   function findNewHighlights(existingHighlights, currentHighlights) {
     return currentHighlights.filter(current => {
       return !existingHighlights.some(existing => 
         existing.text === current.text && existing.location === current.location
       );
     });
   }
   ```

### 3. データ保存と管理

1. **ストレージ方式**
   - Chrome Storageを使用（`chrome.storage.local`）
   - 書籍ごとに一意のIDを生成し、そのIDでデータを管理

2. **データ構造**
   ```javascript
   const bookData = {
     id: "unique-book-id", // 書籍のタイトルと著者からハッシュを生成
     title: "NEXUS 情報の人類史 上 人間のネットワーク",
     author: "ユヴァル・ノア・ハラリ, 柴田裕之",
     coverSrc: "data:image/jpeg;base64,...", // Base64エンコードされた画像データ
     lastUpdated: "2025-04-02T10:30:00Z",
     highlights: [
       {
         text: "一人ひとりの人間はだいてい自分や世界についての真実を知ることに関心があるのに対して、大規模なネットワークは虚構や空想に頼ってメンバーを束ね、秩序を生み出す。",
         location: "133",
         timestamp: "2025-04-02T10:28:00Z"
       },
       // 他のハイライト
     ]
   };
   ```

## 拡張機能の構成

### 1. マニフェストファイル (manifest.json)

```json
{
  "manifest_version": 3,
  "name": "Kindle Highlight Extractor",
  "version": "1.0",
  "description": "Kindle Web Readerからハイライト情報を抽出",
  "permissions": ["storage", "activeTab", "scripting"],
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "content_scripts": [
    {
      "matches": ["https://read.amazon.co.jp/*"],
      "js": ["content.js"]
    }
  ]
}
```

### 2. コンテンツスクリプト (content.js)

- ページの読み込みを監視
- タイトル、著者、ハイライト、カバー画像を抽出するロジック
- バックグラウンドスクリプトとの通信

### 3. ポップアップUI (popup.html/popup.js)

- 抽出操作の開始ボタン
- 抽出状況の表示
- エクスポートオプション

### 4. バックグラウンドスクリプト (background.js)

- データの保存と管理
- 差分検出と更新ロジック

## 開発ステップ

1. **環境準備**
   - プロジェクトディレクトリ構造の作成
   - マニフェストファイルの設定

2. **DOM解析部分の実装**
   - ページ構造を解析してデータ抽出関数を開発
   - テスト用ページでの動作確認

3. **データ管理ロジックの実装**
   - ストレージへの保存・読み込み機能
   - 差分検出アルゴリズムの実装

4. **ユーザーインターフェース開発**
   - ポップアップUIの設計と実装
   - インタラクション処理の実装

5. **テストとデバッグ**
   - 様々な書籍でのテスト
   - エッジケースの検証（ハイライトがない場合、大量のハイライトがある場合など）

6. **パッケージングとリリース準備**
   - 最終テスト
   - Chrome Web Storeへの提出準備

## 実装上の注意点

1. **ページ構造の変更に対する堅牢性**
   - セレクタだけでなく、テキストコンテンツやパターンマッチングも併用
   - エラー処理を充実させる

2. **パフォーマンス最適化**
   - 大量のハイライトがある場合の処理効率
   - 非同期処理の適切な実装

3. **プライバシーとセキュリティ**
   - ユーザーデータの安全な取り扱い
   - 必要最小限の権限要求

4. **ユーザビリティ**
   - 直感的なUI/UX設計
   - エラー発生時の明確なフィードバック

## タイムライン

1. **企画と要件定義**: 1週間
2. **設計と開発環境構築**: 1週間
3. **コア機能実装**: 2週間
4. **UI実装とテスト**: 1週間
5. **デバッグと改善**: 1週間
6. **最終テストと公開準備**: 1週間

合計: 約7週間

## 将来的な拡張案

1. **複数形式でのエクスポート**
   - Markdown
   - PDF
   - Notion/Evernoteへの直接連携

2. **ハイライト管理機能**
   - タグ付け
   - 検索機能
   - メモの追加

3. **同期機能**
   - クラウドストレージとの連携
   - 複数デバイス間での同期

4. **カスタマイズオプション**
   - UIテーマ
   - エクスポート形式のカスタマイズ