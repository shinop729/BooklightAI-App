/**
 * オンライン状態を監視するカスタムフック
 */
import { useState, useEffect } from 'react';

export const useOnlineStatus = () => {
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
  
  return isOnline;
};

/**
 * オフライン時のリクエストをキューに追加する関数
 */
export const addToSyncQueue = async (request: Request): Promise<boolean> => {
  try {
    const db = await openSyncDB();
    const tx = db.transaction('syncQueue', 'readwrite');
    const store = tx.objectStore('syncQueue');
    
    // リクエストをシリアライズ
    const requestClone = request.clone();
    const body = await requestClone.text();
    
    const item = {
      id: Date.now().toString(),
      url: request.url,
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      body,
      createdAt: Date.now()
    };
    
    // IDBRequest を Promise にラップ
    await new Promise<void>((resolve, reject) => {
      const request = store.add(item);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
    
    // トランザクションの完了を待つ
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    
    // バックグラウンド同期の登録（サポートされている場合）
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
      try {
        const registration = await navigator.serviceWorker.ready;
        // @ts-ignore - SyncManager は TypeScript の型定義に含まれていない場合がある
        await registration.sync.register('sync-highlights');
      } catch (e) {
        console.warn('Background Sync not supported:', e);
      }
    }
    
    return true;
  } catch (e) {
    console.error('同期キューへの追加エラー:', e);
    return false;
  }
};

/**
 * 同期キュー用のIndexedDBを開く関数
 */
export const openSyncDB = async (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('booklight-sync-db', 1);
    
    request.onupgradeneeded = (event) => {
      const db = request.result;
      if (!db.objectStoreNames.contains('syncQueue')) {
        db.createObjectStore('syncQueue', { keyPath: 'id' });
      }
    };
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
};

/**
 * 同期キューからリクエストを取得する関数
 */
export const getSyncQueue = async (): Promise<any[]> => {
  try {
    const db = await openSyncDB();
    const tx = db.transaction('syncQueue', 'readonly');
    const store = tx.objectStore('syncQueue');
    
    // IDBRequest を Promise にラップ
    const items = await new Promise<any[]>((resolve, reject) => {
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    
    // トランザクションの完了を待つ
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    
    return items;
  } catch (e) {
    console.error('同期キューの取得エラー:', e);
    return [];
  }
};

/**
 * 同期キューからリクエストを削除する関数
 */
export const removeSyncQueueItem = async (id: string): Promise<boolean> => {
  try {
    const db = await openSyncDB();
    const tx = db.transaction('syncQueue', 'readwrite');
    const store = tx.objectStore('syncQueue');
    
    // IDBRequest を Promise にラップ
    await new Promise<void>((resolve, reject) => {
      const request = store.delete(id);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
    
    // トランザクションの完了を待つ
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    
    return true;
  } catch (e) {
    console.error('同期キューからの削除エラー:', e);
    return false;
  }
};
