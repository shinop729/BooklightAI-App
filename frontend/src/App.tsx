import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ThemeProvider } from './context/ThemeContext';
import { CrossPointProvider } from './context/CrossPointContext';
import Layout from './components/layout/Layout';

// ページコンポーネント
import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import Home from './pages/Home';
import Search from './pages/Search';
import Chat from './pages/Chat';
import CrossPoint from './pages/CrossPoint';
import Remix from './pages/Remix';
import RemixDetail from './pages/RemixDetail';
import BookList from './pages/BookList';
import BookDetail from './pages/BookDetail';
import Upload from './pages/Upload';

// 認証が必要なルートのラッパー
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, loading, isAuthenticated } = useAuth();
  
  if (loading) {
    return <div className="flex justify-center items-center h-screen">読み込み中...</div>;
  }
  
  if (!isAuthenticated || !user) {
    console.log('認証されていないため、ログインページにリダイレクト');
    // 現在のURLをローカルストレージに保存
    localStorage.setItem('redirect_after_login', window.location.pathname);
    return <Navigate to="/login" replace />;
  }
  
  console.log('認証済み、保護されたルートにアクセス許可');
  return <>{children}</>;
};

// QueryClientの作成
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5分
    },
  },
});

function AppRoutes() {
  const { user, isAuthenticated } = useAuth();
  
  console.log('AppRoutes レンダリング - 認証状態:', isAuthenticated ? '認証済み' : '未認証');
  
  return (
    <Routes>
      <Route path="/login" element={
        isAuthenticated ? 
          <Navigate to="/" replace /> : 
          <Login />
      } />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/auth/success-minimal" element={<AuthCallback />} />
      
      <Route path="/" element={
        <ProtectedRoute>
          <Layout>
            <Home />
          </Layout>
        </ProtectedRoute>
      } />
      
      <Route path="/search" element={
        <ProtectedRoute>
          <Layout>
            <Search />
          </Layout>
        </ProtectedRoute>
      } />
      
      <Route path="/chat" element={
        <ProtectedRoute>
          <Layout>
            <Chat />
          </Layout>
        </ProtectedRoute>
      } />
      
      <Route path="/cross-point" element={
        <ProtectedRoute>
          <Layout>
            <CrossPoint />
          </Layout>
        </ProtectedRoute>
      } />
      
      <Route path="/remix" element={
        <ProtectedRoute>
          <Layout>
            <Remix />
          </Layout>
        </ProtectedRoute>
      } />
      
      <Route path="/remix/:id" element={
        <ProtectedRoute>
          <Layout>
            <RemixDetail />
          </Layout>
        </ProtectedRoute>
      } />
      
      <Route path="/books" element={
        <ProtectedRoute>
          <Layout>
            <BookList />
          </Layout>
        </ProtectedRoute>
      } />
      
      <Route path="/books/:id" element={
        <ProtectedRoute>
          <Layout>
            <BookDetail />
          </Layout>
        </ProtectedRoute>
      } />
      
      <Route path="/upload" element={
        <ProtectedRoute>
          <Layout>
            <Upload />
          </Layout>
        </ProtectedRoute>
      } />
      
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  // オフライン状態の検出
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
  
  // オフライン通知
  const OfflineNotification = () => (
    <div className={`fixed bottom-0 left-0 right-0 bg-yellow-800 text-white p-2 text-center transition-transform duration-300 ${isOnline ? 'translate-y-full' : 'translate-y-0'}`}>
      現在オフラインモードです。一部の機能が制限されています。
    </div>
  );
  
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <CrossPointProvider>
              <Router>
                <AppRoutes />
                <OfflineNotification />
              </Router>
            </CrossPointProvider>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
