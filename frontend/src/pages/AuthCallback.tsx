import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const AuthCallback = () => {
  const [message, setMessage] = useState('認証処理中...');
  const navigate = useNavigate();
  const { refreshToken } = useAuth();

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // URLからトークンを取得
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        const user = urlParams.get('user');
        
        if (!token) {
          setMessage('認証エラー: トークンがありません');
          setTimeout(() => navigate('/login'), 3000);
          return;
        }
        
        // トークンを保存
        localStorage.setItem('token', token);
        setMessage(`認証成功！ようこそ、${user || 'ユーザー'}さん`);
        
        // トークンリフレッシュを実行して認証状態を更新
        await refreshToken();
        
        // 保存されていたリダイレクト先があればそこへ、なければホームページへ
        const redirectPath = localStorage.getItem('redirect_after_login') || '/';
        localStorage.removeItem('redirect_after_login'); // リダイレクト先をクリア
        
        setMessage('リダイレクトします...');
        setTimeout(() => navigate(redirectPath), 1000);
      } catch (error) {
        console.error('認証コールバックエラー:', error);
        setMessage(`認証エラー: ${error instanceof Error ? error.message : '不明なエラー'}`);
        setTimeout(() => navigate('/login'), 3000);
      }
    };
    
    handleCallback();
  }, [navigate, refreshToken]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900">
      <div className="max-w-md w-full bg-gray-800 p-8 rounded-lg shadow-lg">
        <h1 className="text-2xl font-bold text-white mb-4">Booklight AI</h1>
        <div className="animate-pulse">
          <p className="text-gray-300">{message}</p>
        </div>
      </div>
    </div>
  );
};

export default AuthCallback;
