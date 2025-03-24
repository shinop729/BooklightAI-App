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

  // 認証状態の復元
  useEffect(() => {
    const restoreAuth = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          setLoading(false);
          return;
        }

        // トークンの有効性を確認
        const { data } = await apiClient.get('/auth/user');
        setUser(data);
        setIsAuthenticated(true);
      } catch (error) {
        console.error('認証状態の復元エラー:', error);
        // エラー時はトークンをクリア
        localStorage.removeItem('token');
        setUser(null);
        setIsAuthenticated(false);
      } finally {
        setLoading(false);
      }
    };

    restoreAuth();
  }, []);

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
    
    // Google認証ページへリダイレクト（クエリパラメータ付き）
    window.location.href = `${apiClient.defaults.baseURL}/auth/google?args=&kwargs=`;
  };

  const logout = async () => {
    try {
      await apiClient.post('/auth/logout');
      setUser(null);
      setIsAuthenticated(false);
      localStorage.removeItem('token');
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
