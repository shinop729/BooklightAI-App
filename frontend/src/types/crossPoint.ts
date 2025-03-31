/**
 * Cross Point関連の型定義
 */

/**
 * Cross Pointのハイライト情報
 */
export interface CrossPointHighlight {
  id: number;
  content: string;
  book_id: number;
  book_title: string;
  book_author: string;
}

/**
 * Cross Point情報
 */
export interface CrossPoint {
  id: number;
  title: string;
  description: string;
  created_at: string;
  liked: boolean;
  highlights: CrossPointHighlight[];
}

/**
 * Cross Point API レスポンス
 */
export interface CrossPointResponse {
  success: boolean;
  message?: string;
  data?: CrossPoint;
}

/**
 * Cross Point お気に入り API レスポンス
 */
export interface CrossPointLikeResponse {
  success: boolean;
  message?: string;
  data?: {
    id: number;
    liked: boolean;
  };
}

/**
 * 埋め込みベクトル生成 API レスポンス
 */
export interface EmbeddingsGenerateResponse {
  success: boolean;
  message?: string;
  data?: {
    processed_count: number;
    total_count: number;
  };
}
