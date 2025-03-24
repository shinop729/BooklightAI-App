import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { TokenRefreshRequest, TokenRefreshResponse, ErrorResponse } from '../types';

// リトライフラグ用の型拡張
interface RequestWithRetry extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

/**
 * APIクライアントの設定
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true
});

/**
 * リクエストインターセプター（認証トークン付与）
 */
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
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
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    // 元のリクエスト情報を取得
    const originalRequest = error.config as RequestWithRetry;
    if (!originalRequest) {
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
          const refreshRequest: TokenRefreshRequest = { token };
          const response = await axios.post<TokenRefreshResponse>(
            `${apiClient.defaults.baseURL}/auth/token`,
            refreshRequest,
            { headers: { 'Content-Type': 'application/json' } }
          );
          
          // 新しいトークンを保存
          const newToken = response.data.data.access_token;
          localStorage.setItem('token', newToken);
          
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

export default apiClient;
