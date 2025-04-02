import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { TokenRefreshRequest, TokenRefreshResponse, ErrorResponse } from '../types';
import { SearchRequest } from '../types/search';
import { debounce } from '../utils/textUtils';

// クライアントサイドキャッシュの設定
const CACHE_DURATION = 5 * 60 * 1000; // 5分間
const CACHE_PREFIX = 'booklight_cache_';
const SEARCH_CACHE_KEY = `${CACHE_PREFIX}search_`;

// リトライフラグ用の型拡張
interface RequestWithRetry extends InternalAxiosRequestConfig {
  _retry?: boolean;
  _cacheKey?: string;
  _useCache?: boolean;
}

/**
 * キャッシュ管理ユーティリティ
 */
export const cacheUtils = {
  /**
   * キャッシュからデータを取得
   */
  get: <T>(key: string): T | null => {
    try {
      const cachedData = localStorage.getItem(key);
      if (!cachedData) return null;
      
      const { data, expiry } = JSON.parse(cachedData);
      if (expiry < Date.now()) {
        localStorage.removeItem(key);
        return null;
      }
      
      return data as T;
    } catch (error) {
      console.error('キャッシュ取得エラー:', error);
      return null;
    }
  },
  
  /**
   * データをキャッシュに保存
   */
  set: <T>(key: string, data: T, ttl: number = CACHE_DURATION): void => {
    try {
      const cacheData = {
        data,
        expiry: Date.now() + ttl
      };
      localStorage.setItem(key, JSON.stringify(cacheData));
    } catch (error) {
      console.error('キャッシュ保存エラー:', error);
    }
  },
  
  /**
   * キャッシュを削除
   */
  remove: (key: string): void => {
    localStorage.removeItem(key);
  },
  
  /**
   * 特定のプレフィックスを持つすべてのキャッシュを削除
   */
  clearByPrefix: (prefix: string): void => {
    try {
      Object.keys(localStorage).forEach(key => {
        if (key.startsWith(prefix)) {
          localStorage.removeItem(key);
        }
      });
    } catch (error) {
      console.error('キャッシュクリアエラー:', error);
    }
  }
};

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
  withCredentials: true,
  timeout: 30000 // 30秒タイムアウト
});

// APIリクエスト時にパスにプレフィックスを追加
apiClient.interceptors.request.use(
  (config) => {
    // URLが既に /api で始まっている場合や、絶対URLの場合はプレフィックスを追加しない
    if (!config.url?.startsWith('/api') && !config.url?.startsWith('http')) {
      config.url = `${apiPrefix}${config.url}`;
    }
    
    // キャッシュチェック
    const requestConfig = config as RequestWithRetry;
    if (requestConfig._useCache && requestConfig._cacheKey) {
      const cachedData = cacheUtils.get(requestConfig._cacheKey);
      if (cachedData) {
        console.log(`キャッシュヒット: ${requestConfig._cacheKey}`);
        // キャッシュヒットを示すためにキャンセルトークンを使用
        const source = axios.CancelToken.source();
        requestConfig.cancelToken = source.token;
        setTimeout(() => {
          source.cancel(JSON.stringify({ cached: true, data: cachedData }));
        }, 0);
      }
    }
    
    // リクエスト情報をログに出力（開発環境のみ）
    if (import.meta.env.DEV) {
      console.log(`APIリクエスト: ${config.method?.toUpperCase()} ${config.url}`, {
        headers: config.headers,
        data: config.data
      });
    }
    
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
        if (import.meta.env.DEV) {
          console.log('開発環境: 固定トークンをヘッダーに設定しました');
        }
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
 * レスポンスインターセプター（トークンリフレッシュとキャッシュ処理）
 */
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // レスポンス情報をログに出力（開発環境のみ）
    if (import.meta.env.DEV) {
      console.log(`APIレスポンス: ${response.status} ${response.statusText}`, {
        data: response.data,
        headers: response.headers
      });
    }
    
    // キャッシュ保存
    const requestConfig = response.config as RequestWithRetry;
    if (requestConfig._cacheKey && response.status >= 200 && response.status < 300) {
      cacheUtils.set(requestConfig._cacheKey, response.data);
    }
    
    return response;
  },
  async (error: AxiosError) => {
    // 元のリクエスト情報を取得
    const originalRequest = error.config as RequestWithRetry;
    if (!originalRequest) {
      return Promise.reject(error);
    }
    
    // キャッシュからのキャンセルの場合
    if (axios.isCancel(error)) {
      try {
        const cachedData = JSON.parse(error.message);
        if (cachedData && cachedData.cached) {
          return { data: cachedData.data, status: 200, statusText: 'OK', headers: {}, config: originalRequest };
        }
      } catch (e) {
        // キャンセルメッセージのパースに失敗した場合は通常のキャンセルとして扱う
        console.log('リクエストがキャンセルされました');
        return Promise.reject(error);
      }
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

/**
 * 検索関連のAPI
 */
export const searchHighlights = async (request: SearchRequest) => {
  try {
    // キャッシュキーの生成
    const cacheKey = `${SEARCH_CACHE_KEY}${JSON.stringify(request)}`;
    
    // キャッシュキーを設定
    const config = {
      _useCache: true,
      _cacheKey: cacheKey
    };
    
    // 設定をオプションとして渡す（型キャストでTypeScriptエラーを回避）
    const response = await apiClient.post('/search', request, config as any);
    return response.data;
  } catch (error) {
    console.error('検索エラー:', error);
    throw error;
  }
};

/**
 * 検索結果のプリフェッチ
 */
export const prefetchSearchResults = async (request: SearchRequest) => {
  try {
    // キャッシュキーの生成
    const cacheKey = `${SEARCH_CACHE_KEY}${JSON.stringify(request)}`;
    
    // キャッシュをチェック
    const cachedData = cacheUtils.get(cacheKey);
    if (cachedData) {
      console.log('検索結果がキャッシュに存在します:', cacheKey);
      return;
    }
    
    console.log('検索結果をプリフェッチします:', request);
    
    // バックグラウンドで検索を実行
    const response = await apiClient.post('/search', request);
    
    // キャッシュに保存
    cacheUtils.set(cacheKey, response.data);
    
    console.log('検索結果のプリフェッチが完了しました');
  } catch (error) {
    console.error('プリフェッチエラー:', error);
    // プリフェッチのエラーは無視（ユーザー体験に影響しない）
  }
};

/**
 * キャッシュのクリア
 */
export const clearSearchCache = () => {
  cacheUtils.clearByPrefix(SEARCH_CACHE_KEY);
  console.log('検索キャッシュをクリアしました');
};

/**
 * Cross Point関連のAPI
 */
// デバウンス処理を適用したCross Point取得関数
const _getCrossPointOriginal = async () => {
  try {
    const cacheKey = `${CACHE_PREFIX}cross_point`;
    
    // キャッシュをチェック
    try {
      const cachedData = cacheUtils.get(cacheKey);
      if (cachedData) {
        console.log('Cross Pointキャッシュヒット');
        return cachedData;
      }
    } catch (cacheError) {
      console.warn('Cross Pointキャッシュ取得エラー:', cacheError);
      // キャッシュエラーは無視して処理を続行
    }
    
    console.log('Cross Pointをサーバーから取得');
    const response = await apiClient.get('/cross-point');
    
    // レスポンスをキャッシュ（1時間）
    if (response.data.success) {
      try {
        cacheUtils.set(cacheKey, response.data, 60 * 60 * 1000);
        console.log('Cross Pointをキャッシュに保存しました');
      } catch (cacheError) {
        console.warn('Cross Pointキャッシュ保存エラー:', cacheError);
        // キャッシュエラーは無視して処理を続行
      }
    }
    
    return response.data;
  } catch (error) {
    console.error('Cross Point取得エラー:', error);
    // エラーオブジェクトの詳細情報をログに出力
    if (error instanceof Error) {
      console.error('エラー詳細:', {
        name: error.name,
        message: error.message,
        stack: error.stack
      });
    }
    throw error;
  }
};

// 1秒のデバウンス処理を適用（型を保持）
export const getCrossPoint = _getCrossPointOriginal;
// 注意: デバウンス処理は無限ループの問題を解決するために一時的に無効化しています
// 本来は以下のようにデバウンス処理を適用するべきですが、型の問題があるため保留
// export const getCrossPoint = debounce(_getCrossPointOriginal, 1000) as typeof _getCrossPointOriginal;

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
