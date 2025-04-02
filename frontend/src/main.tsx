import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom'; // BrowserRouter をインポート
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'; // React Query をインポート
import './index.css';
import App from './App.tsx';
import { AuthProvider } from './context/AuthContext'; // AuthProvider をインポート
import { ThemeProvider } from './context/ThemeContext'; // ThemeProvider をインポート
import { ToastProvider } from './context/ToastContext'; // ToastProvider をインポート
import { CrossPointProvider } from './context/CrossPointContext'; // CrossPointProvider をインポート
import * as serviceWorkerRegistration from './serviceWorkerRegistration';

// React Query クライアントの作成
const queryClient = new QueryClient();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}> {/* QueryClientProvider は残す */}
      {/* <BrowserRouter> を削除 */}
      <AuthProvider> {/* AuthProvider は残す */}
        <ThemeProvider> {/* ThemeProvider は残す */}
          <ToastProvider> {/* ToastProvider は残す */}
            <CrossPointProvider> {/* CrossPointProvider は残す */}
              <App /> {/* App内でRouterが使われる */}
            </CrossPointProvider>
          </ToastProvider>
        </ThemeProvider>
      </AuthProvider>
      {/* </BrowserRouter> を削除 */}
    </QueryClientProvider>
  </StrictMode>,
);

// サービスワーカーを一時的に無効化（無限リロード問題の解決のため）
serviceWorkerRegistration.unregister();
