import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { TokenRefreshRequest, TokenRefreshResponse, ErrorResponse } from '../types';

// リトライフラグ用の型拡張
interface RequestWithRetry extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

/**
 * APIクライアントの設定
 */
// 環境に応じたベースURLとAPIパスプレフィックスの設定
const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
// Heroku環境では自動的に /api プレフィックスが追加されるため、開発環境でのみ追加
const apiPrefix = baseURL.includes('localhost') ? '/api' : '';

// デバッグ情報の表示
console.log('APIクライアント初期化', {
  baseURL,
  apiPrefix,
  isDev: import.meta.env.DEV
});

const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true
});

// APIリクエスト時にパスにプレフィックスを追加
apiClient.interceptors.request.use(
  (config) => {
    // URLが既に /api で始まっている場合や、絶対URLの場合はプレフィックスを追加しない
    if (!config.url?.startsWith('/api') && !config.url?.startsWith('http')) {
      config.url = `${apiPrefix}${config.url}`;
    }
    
    // リクエスト情報をログに出力
    console.log(`APIリクエスト: ${config.method?.toUpperCase()} ${config.url}`, {
      headers: config.headers,
      data: config.data
    });
    
    return config;
  }
);

/**
 * リクエストインターセプター（認証トークン付与）
 */
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 開発環境かどうかを確認
    const isDevelopment = import.meta.env.DEV;
    
    // 開発環境では常に開発用トークンを使用
    if (isDevelopment) {
      if (config.headers) {
        config.headers.Authorization = `Bearer dev-token-123`;
        console.log('開発環境: 固定トークンをヘッダーに設定しました');
      }
      return config;
    }
    
    // 本番環境では通常のトークン処理
    const token = localStorage.getItem('token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

/**
 * レスポンスインターセプター（トークンリフレッシュ）
 */
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // レスポンス情報をログに出力
    console.log(`APIレスポンス: ${response.status} ${response.statusText}`, {
      data: response.data,
      headers: response.headers
    });
    return response;
  },
  async (error: AxiosError) => {
    // 元のリクエスト情報を取得
    const originalRequest = error.config as RequestWithRetry;
    if (!originalRequest) {
      return Promise.reject(error);
    }
    
    // エラー情報をログに出力
    console.error('APIエラー:', {
      status: error.response?.status,
      statusText: error.response?.statusText,
      url: originalRequest.url,
      method: originalRequest.method
    });
    
    // トークンリフレッシュエンドポイントへのリクエストの場合は再試行しない
    if (originalRequest.url?.includes('/auth/token')) {
      console.log('トークンリフレッシュエンドポイントへのリクエストはリトライしません');
      return Promise.reject(error);
    }
    
    // 認証エラー（401）かつリトライしていない場合
    if (
      error.response && 
      error.response.status === 401 && 
      !originalRequest._retry
    ) {
      originalRequest._retry = true;
      
      try {
        // トークンリフレッシュを試みる
        const token = localStorage.getItem('token');
        if (token) {
          console.log('トークンリフレッシュを試みます');
          const refreshRequest: TokenRefreshRequest = { token };
          const response = await axios.post<TokenRefreshResponse>(
            `${apiClient.defaults.baseURL}${apiPrefix}/auth/token`,
            refreshRequest,
            { headers: { 'Content-Type': 'application/json' } }
          );
          
          // 新しいトークンを保存
          const newToken = response.data.data.access_token;
          localStorage.setItem('token', newToken);
          console.log('トークンリフレッシュ成功、リクエストを再試行します');
          
          // 元のリクエストを再試行
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
          }
          return axios(originalRequest);
        }
      } catch (refreshError) {
        console.error('トークンリフレッシュエラー:', refreshError);
        // リフレッシュに失敗した場合は認証情報をクリア
        localStorage.removeItem('token');
        // ログインページへリダイレクト
        window.location.href = '/login';
      }
    }
    
    // エラーレスポンスの型変換
    if (error.response && error.response.data) {
      const errorData = error.response.data as ErrorResponse;
      console.error('API Error:', errorData.message || error.message);
    }
    
    return Promise.reject(error);
  }
);

// Cross Point関連のAPI
export const getCrossPoint = async () => {
  try {
    const response = await apiClient.get('/cross-point');
    return response.data;
  } catch (error) {
    console.error('Cross Point取得エラー:', error);
    throw error;
  }
};

export const likeCrossPoint = async (crossPointId: number) => {
  try {
    const response = await apiClient.post(`/cross-point/${crossPointId}/like`);
    return response.data;
  } catch (error) {
    console.error('Cross Pointお気に入り登録エラー:', error);
    throw error;
  }
};

export const generateEmbeddings = async () => {
  try {
    const response = await apiClient.post('/cross-point/embeddings/generate');
    return response.data;
  } catch (error) {
    console.error('埋め込みベクトル生成エラー:', error);
    throw error;
  }
};

// Remix関連のAPI
export const getRandomTheme = async () => {
  try {
    const response = await apiClient.get('/remix/random-theme');
    return response.data;
  } catch (error) {
    console.error('ランダムテーマ取得エラー:', error);
    throw error;
  }
};

export const generateRemix = async (highlightCount: number = 5) => {
  try {
    const response = await apiClient.post('/remix', { highlight_count: highlightCount });
    return response.data;
  } catch (error) {
    console.error('Remix生成エラー:', error);
    throw error;
  }
};

export const getRemixById = async (remixId: number) => {
  try {
    const response = await apiClient.get(`/remix/${remixId}`);
    return response.data;
  } catch (error) {
    console.error('Remix取得エラー:', error);
    throw error;
  }
};

export const getUserRemixes = async (page: number = 1, pageSize: number = 10) => {
  try {
    const response = await apiClient.get('/remixes', {
      params: { page, page_size: pageSize }
    });
    return response.data;
  } catch (error) {
    console.error('Remix一覧取得エラー:', error);
    throw error;
  }
};

export default apiClient;
