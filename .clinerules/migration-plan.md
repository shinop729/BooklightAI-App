# Booklight AI フロントエンド移行計画書

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [技術選定の背景](#2-技術選定の背景)
3. [アーキテクチャ設計](#3-アーキテクチャ設計)
4. [移行計画詳細](#4-移行計画詳細)
5. [開発環境構築](#5-開発環境構築)
6. [リスク管理](#6-リスク管理)
7. [品質保証計画](#7-品質保証計画)
8. [タイムライン](#8-タイムライン)
9. [リソース計画](#9-リソース計画)
10. [参考資料](#10-参考資料)

## 1. プロジェクト概要

### 1.1 背景

Booklight AIは、Kindleハイライト情報を収集・管理し、AI技術を活用してユーザーの読書体験を向上させるアプリケーションです。現在はPython（FastAPI + Streamlit）で実装されていますが、UIの柔軟性と拡張性の向上を目的として、フロントエンドをReact + TypeScriptに移行します。

### 1.2 現状の課題

- **UI制約**: Streamlitでは複雑なUIやインタラクションに制限がある
- **コード重複**: 各ページでサイドバーなど共通要素が重複している
- **パフォーマンス**: 状態変更時にページ全体が再読み込みされる
- **保守性**: 機能が増えるにつれて、スケーラビリティの課題が顕在化している

### 1.3 目標

- バックエンド（FastAPI）はPythonのまま維持
- フロントエンドをReact + TypeScriptに移行
- UIの拡張性と保守性の向上
- ユーザー体験の向上（レスポンシブデザイン強化、高速化など）
- 将来的な機能追加を容易にする基盤の構築

## 2. 技術選定の背景

### 2.1 バックエンド技術の維持

**Python (FastAPI)を維持する理由**:

- AI関連ライブラリ（OpenAI、LangChain、Chroma等）との優れた親和性
- データ処理（pandas、scikit-learn等）の強み
- 既に多くの機能が実装済みで移行コストが高い
- チームのPythonスキルセットを最大限に活用

### 2.2 フロントエンド技術選定

**React + TypeScriptを選定した理由**:

| 技術 | 選定理由 |
|-----|---------|
| **React** | - コンポーネントベースのアーキテクチャによる再利用性<br>- 大規模なエコシステムとコミュニティサポート<br>- 仮想DOMによるパフォーマンス最適化<br>- 将来のモバイル対応（React Native）への道筋 |
| **TypeScript** | - 静的型付けによるコード品質と保守性の向上<br>- API連携時の型安全性確保<br>- リファクタリングの安全性<br>- 自動補完などの開発体験の向上 |
| **Vite** | - 高速な開発・ビルド体験<br>- HMR（Hot Module Replacement）でのリアルタイム更新<br>- 最新のESMネイティブツールチェーン |

### 2.3 代替技術の検討

以下の技術も検討しましたが、最終的にReact + TypeScriptを選択しました：

| 代替技術 | 検討結果 |
|---------|---------|
| **Vue.js** | 学習曲線は低いが、TypeScript統合がやや劣る |
| **Svelte** | パフォーマンス面で優れるが、エコシステムがReactほど充実していない |
| **Dash (Plotly)** | Pythonで書けるが、UIの柔軟性が限られる |
| **Streamlit (現状維持)** | 拡張性・パフォーマンスの根本的課題が解決できない |

## 3. アーキテクチャ設計

### 3.1 全体アーキテクチャ

```
+------------------+        +------------------+
|                  |        |                  |
|  React Frontend  |  <-->  |  FastAPI Backend |
|  (TypeScript)    |        |  (Python)        |
|                  |        |                  |
+------------------+        +------------------+
                                     |
                                     v
                            +------------------+
                            |                  |
                            |  Database        |
                            |  (PostgreSQL)    |
                            |                  |
                            +------------------+
```

### 3.2 フロントエンド構造

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

### 3.3 状態管理戦略

複雑さを抑えつつ、効率的な状態管理を実現するために以下を採用します：

- **ローカル状態**: コンポーネント内のReact useState/useReducer
- **グローバル状態**: Zustand（軽量で使いやすいステート管理ライブラリ）
- **サーバー状態**: TanStack Query（旧React Query）でのデータフェッチと管理
- **コンテキスト**: 認証などの横断的な関心事のための React Context

### 3.4 API連携戦略

FastAPIとReactの連携には以下の方針を採用します：

- **Axios**: HTTP通信の基盤として
- **TanStack Query**: データフェッチング、キャッシュ、無効化のため
- **型安全な通信**: APIレスポンスの型定義による型安全性確保
- **認証**: JWT認証（現状のまま）の対応

## 4. 移行計画詳細

### フェーズ1: 基盤構築（2週間）

#### Week 1: プロジェクト初期化と基本設定

- プロジェクト作成（Vite + React + TypeScript）
- ESLint, Prettier設定
- ディレクトリ構造の確立
- 共通コンポーネントの基盤実装
- FastAPIとの通信基盤構築

**コード例（APIクライアント設定）**:
```typescript
// src/api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true
});

// リクエストインターセプター（認証トークン付与）
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// エラーハンドリング
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 認証エラー（401）時の処理
    if (error.response && error.response.status === 401) {
      // 認証情報クリア
      localStorage.removeItem('token');
      // ログインページへリダイレクト
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

#### Week 2: 認証システムと共通コンポーネント実装

- 認証コンテキスト実装
- Google OAuth連携
- レイアウトコンポーネント（ヘッダー、サイドバー、フッター）
- 基本UIコンポーネント（カード、ボタン、フォームなど）

**コード例（認証コンテキスト）**:
```typescript
// src/context/AuthContext.tsx
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import apiClient from '../api/client';

interface User {
  id: string;
  name: string;
  email: string;
  picture?: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 認証状態の確認
    const checkAuth = async () => {
      try {
        const { data } = await apiClient.get('/auth/user');
        setUser(data);
      } catch (error) {
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, []);

  const login = () => {
    // Google認証ページへリダイレクト
    window.location.href = `${apiClient.defaults.baseURL}/auth/google`;
  };

  const logout = async () => {
    try {
      await apiClient.post('/auth/logout');
      setUser(null);
      localStorage.removeItem('token');
    } catch (error) {
      console.error('ログアウトエラー:', error);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
```

### フェーズ2: 主要機能実装（4週間）

#### Week 3-4: ホームページと書籍一覧機能

- ランディングページ実装
- ホームページ（ランダムハイライト表示）
- 書籍一覧ページと書籍カード
- 書籍詳細ページ

**コード例（書籍カードコンポーネント）**:
```tsx
// src/components/feature/BookCard.tsx
import { FC } from 'react';
import { useNavigate } from 'react-router-dom';

interface BookCardProps {
  id: string;
  title: string;
  author: string;
  coverUrl?: string;
  highlightCount: number;
}

export const BookCard: FC<BookCardProps> = ({
  id,
  title,
  author,
  coverUrl,
  highlightCount
}) => {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/books/${id}`);
  };

  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-shadow">
      <div className="aspect-w-2 aspect-h-3 bg-gray-700">
        {coverUrl ? (
          <img
            src={coverUrl}
            alt={`${title}の表紙`}
            className="object-cover w-full h-full"
          />
        ) : (
          <div className="flex items-center justify-center w-full h-full text-gray-400">
            表紙なし
          </div>
        )}
      </div>
      <div className="p-4">
        <h3 className="text-lg font-semibold text-white mb-1 truncate">{title}</h3>
        <p className="text-sm text-gray-400 mb-2">{author}</p>
        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-500">ハイライト {highlightCount}件</span>
          <button
            onClick={handleClick}
            className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
          >
            詳細
          </button>
        </div>
      </div>
    </div>
  );
};
```

#### Week 5-6: 検索機能とチャット機能

- 検索ページ（キーワード入力、タグ管理）
- 検索結果表示
- チャットインターフェース
- メッセージ履歴管理

**コード例（検索フックの実装）**:
```typescript
// src/hooks/useSearch.ts
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';

export interface SearchResult {
  doc: {
    page_content: string;
    metadata: {
      original_title: string;
      original_author: string;
    };
  };
  score: number;
}

export const useSearch = (initialKeywords: string[] = []) => {
  const [keywords, setKeywords] = useState<string[]>(initialKeywords);
  
  // TanStack Query を使用したAPI通信
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['search', keywords],
    queryFn: async () => {
      if (keywords.length === 0) return { results: [] };
      
      const { data } = await apiClient.post('/search', {
        keywords,
        hybrid_alpha: 0.7,
        book_weight: 0.3,
        use_expanded: true
      });
      
      return data;
    },
    // キーワードが空の場合は実行しない
    enabled: keywords.length > 0
  });
  
  const addKeyword = (keyword: string) => {
    if (keyword && !keywords.includes(keyword)) {
      setKeywords([...keywords, keyword]);
    }
  };
  
  const removeKeyword = (keyword: string) => {
    setKeywords(keywords.filter(k => k !== keyword));
  };
  
  const clearKeywords = () => {
    setKeywords([]);
  };
  
  return {
    keywords,
    results: data?.results || [],
    isLoading,
    error,
    addKeyword,
    removeKeyword,
    clearKeywords,
    search: refetch
  };
};
```

### フェーズ3: 補完と最適化（2週間）

#### Week 7: ハイライトアップロード機能とサマリー生成

- ファイルアップロードコンポーネント
- CSVデータのプレビューと編集
- サマリー生成機能のフロントエンド
- 進捗表示とステータス管理

#### Week 8: 最適化、テスト、品質改善

- パフォーマンス最適化
- アクセシビリティ改善
- 単体テスト・統合テスト
- クロスブラウザテスト

### フェーズ4: 移行完了と公開（1週間）

- ビルド設定の最適化
- デプロイパイプラインの構築
- 本番環境への移行
- 最終テストと品質確認

## 5. 開発環境構築

### 5.1 フロントエンド環境

```bash
# プロジェクト作成
npm create vite@latest booklight-frontend -- --template react-ts
cd booklight-frontend

# 必要なパッケージのインストール
npm install react-router-dom axios @tanstack/react-query zustand
npm install -D tailwindcss postcss autoprefixer

# Tailwind CSS設定
npx tailwindcss init -p

# 開発サーバー起動
npm run dev
```

### 5.2 ローカル開発環境設定

`.env.development`ファイルの作成：

```
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your_client_id_here
```

### 5.3 FastAPIバックエンドとの連携

FastAPIのCORS設定を更新してReactデベロップメントサーバーからのリクエストを許可します：

```python
# api/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Viteのデフォルトポート
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5.4 開発サーバー一括起動スクリプト

```bash
#!/bin/bash
# run_dev.sh

# FastAPIバックエンド起動
cd api && uvicorn app.main:app --reload --port 8000 &
API_PID=$!

# Reactフロントエンド起動
cd ../frontend && npm run dev &
FRONTEND_PID=$!

# 終了時の処理
trap "kill $API_PID $FRONTEND_PID; exit" INT TERM
wait
```

## 6. リスク管理

| リスク | 影響度 | 対策 |
|-------|------|------|
| **API連携の不具合** | 高 | - 早期段階でAPIクライアントの実装とテスト<br>- 明確なAPI型定義の作成<br>- モックサーバーの活用 |
| **認証機能の問題** | 高 | - 認証フローを最優先で実装<br>- 複数環境でのテスト<br>- エラーハンドリングの強化 |
| **パフォーマンス低下** | 中 | - コンポーネントの適切な分割<br>- メモ化の活用<br>- パフォーマンスモニタリング |
| **技術的な学習曲線** | 中 | - チーム向けの勉強会開催<br>- ペアプログラミングの実施<br>- 段階的な移行 |
| **既存機能の見落とし** | 中 | - 既存機能の詳細な棚卸し<br>- 機能検証リストの作成<br>- UAT（ユーザー受け入れテスト）の実施 |

## 7. 品質保証計画

### 7.1 テスト戦略

| テストレベル | ツール | 対象 |
|------------|------|------|
| **単体テスト** | Jest, React Testing Library | - コンポーネント<br>- カスタムフック<br>- ユーティリティ関数 |
| **統合テスト** | React Testing Library | - ページ<br>- フォーム送信<br>- API連携 |
| **E2Eテスト** | Cypress | - 重要なユーザーフロー<br>- 認証フロー |
| **視覚回帰テスト** | Storybook, Chromatic | - UIコンポーネント |

### 7.2 コード品質管理

- ESLint（コード品質）
- Prettier（コードフォーマット）
- TypeScript型チェック
- Husky（コミット前のチェック）

### 7.3 アクセシビリティ

- アクセシビリティチェックツール（axe-core）
- WCAG 2.1 AAレベルの遵守
- キーボード操作のサポート

## 8. タイムライン

| フェーズ | 期間 | 主要マイルストーン |
|---------|-----|------------------|
| **フェーズ1: 基盤構築** | 2週間 | - プロジェクト設定完了<br>- 認証システム実装<br>- 基本レイアウト実装 |
| **フェーズ2: 主要機能実装** | 4週間 | - ホームページ完成<br>- 書籍一覧/詳細機能実装<br>- 検索機能実装<br>- チャット機能実装 |
| **フェーズ3: 補完と最適化** | 2週間 | - アップロード機能実装<br>- パフォーマンス最適化<br>- テスト実施<br>- バグ修正 |
| **フェーズ4: 移行完了と公開** | 1週間 | - 本番ビルド作成<br>- デプロイ完了<br>- 最終確認<br>- 本番リリース |

**合計: 9週間（約2ヶ月強）**

## 9. リソース計画

### 9.1 必要な人員

- フロントエンドエンジニア: 2名（TypeScript/React経験者）
- バックエンドエンジニア: 1名（FastAPIの既存システムに詳しい方）
- QAエンジニア: 1名（一部の時間）

### 9.2 開発ツールとインフラ

- ソースコード管理: GitHub
- プロジェクト管理: GitHub Projects / Trello
- CI/CD: GitHub Actions
- デプロイ: Heroku（現状と同じ）
- デザインツール: Figma

### 9.3 想定コスト

| 項目 | 概算コスト |
|-----|----------|
| **人件費** | 2名×2ヶ月 = 4人月 |
| **ツール・インフラ** | GitHub: $0-4/月/ユーザー<br>Heroku: $25-50/月 |
| **外部サービス** | Google OAuth: $0<br>OpenAI API: 既存のまま |

## 10. 参考資料

### 10.1 技術ドキュメント

- [React 公式ドキュメント](https://react.dev/)
- [TypeScript 公式ドキュメント](https://www.typescriptlang.org/docs/)
- [Vite 公式ドキュメント](https://vitejs.dev/guide/)
- [TanStack Query ドキュメント](https://tanstack.com/query/latest/docs/react/overview)
- [Zustand ドキュメント](https://github.com/pmndrs/zustand)

### 10.2 推奨書籍

- "React Design Patterns and Best Practices" - Carlos Santana Roldán
- "Programming TypeScript" - Boris Cherny
- "Testing React Applications" - Jeff Wainwright

### 10.3 サンプルプロジェクトとテンプレート

- [React TypeScript Cheatsheets](https://github.com/typescript-cheatsheets/react)
- [Vite React TS Tailwind Starter](https://github.com/wobsoriano/vite-react-tailwind-starter)

---

この移行計画は、Booklight AIの現状とニーズに基づいて作成されたものです。実際の実装では、プロジェクトの進行に合わせて柔軟に調整していくことをお勧めします。段階的な移行と継続的なフィードバックが、成功への鍵となります。
