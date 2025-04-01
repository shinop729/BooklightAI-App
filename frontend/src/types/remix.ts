/**
 * Remix関連の型定義
 */

/**
 * Remixのハイライト情報
 */
export interface RemixHighlight {
  id: number;
  content: string;
  book_id: number;
  book_title: string;
  book_author: string;
}

/**
 * Remix情報
 */
export interface Remix {
  id: number;
  title: string;
  theme: string;
  content: string;
  created_at: string;
  highlights: RemixHighlight[];
}

/**
 * Remix API レスポンス
 */
export interface RemixResponse {
  success: boolean;
  message?: string;
  data?: Remix;
}

/**
 * Remix一覧 API レスポンス
 */
export interface RemixListResponse {
  success: boolean;
  message?: string;
  data?: {
    items: Remix[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  };
}

/**
 * ランダムテーマ API レスポンス
 */
export interface RandomThemeResponse {
  success: boolean;
  message?: string;
  data?: {
    theme: string;
  };
}
