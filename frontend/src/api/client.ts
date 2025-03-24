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
