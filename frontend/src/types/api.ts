/**
 * API関連の共通型定義
 */

/**
 * APIレスポンスの基本型
 */
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

/**
 * ページネーション情報
 */
export interface PaginationInfo {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
}

/**
 * ページネーション付きレスポンス
 */
export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: PaginationInfo;
}

/**
 * エラーレスポンス
 */
export interface ErrorResponse {
  success: false;
  error: string;
  message: string;
  statusCode: number;
}

/**
 * アップロードレスポンス
 */
export interface UploadResponse {
  success: boolean;
  message: string;
  bookCount: number;
  highlightCount: number;
}
