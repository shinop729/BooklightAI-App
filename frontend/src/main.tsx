import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import * as serviceWorkerRegistration from './serviceWorkerRegistration'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// サービスワーカーを一時的に無効化（無限リロード問題の解決のため）
serviceWorkerRegistration.unregister();
