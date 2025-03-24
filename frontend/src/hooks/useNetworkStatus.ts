import { useState, useEffect } from 'react';

/**
 * ネットワーク状態を監視するカスタムフック
 * オンライン/オフライン状態の変化を検出し、現在の状態を提供する
 */
export const useNetworkStatus = () => {
  // 初期状態はnavigator.onLineから取得
  const [isOnline, setIsOnline] = useState<boolean>(navigator.onLine);
  
  useEffect(() => {
    // オンラインになった時のハンドラー
    const handleOnline = () => {
      setIsOnline(true);
    };
    
    // オフラインになった時のハンドラー
    const handleOffline = () => {
      setIsOnline(false);
    };
    
    // イベントリスナーの登録
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    // クリーンアップ関数
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
  
  return { isOnline };
};
