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

// レスポンスインターセプター（トークンリフレッシュ）
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // 認証エラー（401）かつリトライしていない場合
    if (error.response && error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        // トークンリフレッシュを試みる
        const token = localStorage.getItem('token');
        if (token) {
          const response = await axios.post(
            `${apiClient.defaults.baseURL}/auth/token`,
            { token },
            { headers: { 'Content-Type': 'application/json' } }
          );
          
          // 新しいトークンを保存
          const newToken = response.data.access_token;
          localStorage.setItem('token', newToken);
          
          // 元のリクエストを再試行
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
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
    
    return Promise.reject(error);
  }
);

export default apiClient;
