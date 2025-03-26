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
  isAuthenticated: boolean;
  login: () => void;
  logout: () => Promise<void>;
  refreshToken: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  // 認証状態の復元
  useEffect(() => {
    const restoreAuth = async () => {
      // 開発環境での自動ログイン機能を一時的に無効化（リダイレクトループ問題の解決のため）
      console.log('認証状態の復元を開始');
      
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          console.log('トークンが見つかりません');
          setLoading(false);
          return;
        }

        // トークンの有効性を確認（一度だけ試行）
        try {
          console.log('トークンの有効性を確認中...');
          const { data } = await apiClient.get('/auth/user');
          console.log('ユーザー情報取得成功:', data);
          setUser(data);
          setIsAuthenticated(true);
        } catch (error) {
          console.error('認証状態の復元エラー:', error);
          
          // トークンが無効な場合は認証情報をクリア
          localStorage.removeItem('token');
          setUser(null);
          setIsAuthenticated(false);
        }
      } finally {
        setLoading(false);
      }
    };

    // ローカルストレージのクリアを削除
    // localStorage.clear();
    // console.log('ローカルストレージをクリアしました');
    
    restoreAuth();
  }, []); // 依存配列を空にして初回のみ実行

  // トークンリフレッシュ
  const refreshToken = async (): Promise<boolean> => {
    try {
      const token = localStorage.getItem('token');
      if (!token) return false;

      const { data } = await apiClient.post('/auth/token', { token });
      
      // 新しいトークンを保存
      localStorage.setItem('token', data.access_token);
      
      // ユーザー情報を更新
      if (data.user_id && data.email && data.full_name) {
        setUser({
          id: data.user_id,
          name: data.full_name,
          email: data.email,
          picture: data.picture
        });
        setIsAuthenticated(true);
      }
      
      return true;
    } catch (error) {
      console.error('トークンリフレッシュエラー:', error);
      localStorage.removeItem('token');
      setUser(null);
      setIsAuthenticated(false);
      return false;
    }
  };

  const login = () => {
    // リダイレクト前にローカルストレージに現在のURLを保存
    localStorage.setItem('redirect_after_login', window.location.pathname);
    
    // デバッグ情報をコンソールに出力
    console.log('ログイン処理開始');
    console.log('APIクライアントのベースURL:', apiClient.defaults.baseURL);
    console.log('リダイレクト後のURL:', window.location.pathname);
    
    // Google認証ページへリダイレクト（クエリパラメータ付き）
    const authUrl = `${apiClient.defaults.baseURL}/auth/google?args=&kwargs=`;
    console.log('認証URL:', authUrl);
    
    window.location.href = authUrl;
  };

  const logout = async () => {
    try {
      await apiClient.post('/auth/logout');
      setUser(null);
      setIsAuthenticated(false);
      localStorage.removeItem('token');
      console.log('ログアウト完了');
    } catch (error) {
      console.error('ログアウトエラー:', error);
    }
  };

  return (
    <AuthContext.Provider value={{ 
      user, 
      loading, 
      isAuthenticated,
      login, 
      logout,
      refreshToken
    }}>
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
