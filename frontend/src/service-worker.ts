/// <reference lib="webworker" />
/* eslint-disable no-restricted-globals */

import { clientsClaim } from 'workbox-core';
import { ExpirationPlugin } from 'workbox-expiration';
import { precacheAndRoute, createHandlerBoundToURL, PrecacheEntry } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { StaleWhileRevalidate, CacheFirst } from 'workbox-strategies';

declare const self: ServiceWorkerGlobalScope;
declare const process: { env: { PUBLIC_URL: string } };

// Workbox manifestの型定義
declare global {
  interface ServiceWorkerGlobalScope {
    __WB_MANIFEST: (string | PrecacheEntry)[];
  }
}

clientsClaim();

// プリキャッシュの設定
precacheAndRoute(self.__WB_MANIFEST);

// シングルページアプリケーションのナビゲーション
const fileExtensionRegexp = new RegExp('/[^/?]+\\.[^/]+$');
registerRoute(
  ({ request, url }: { request: Request; url: URL }) => {
    if (request.mode !== 'navigate') {
      return false;
    }
    if (url.pathname.startsWith('/_')) {
      return false;
    }
    if (url.pathname.match(fileExtensionRegexp)) {
      return false;
    }
    return true;
  },
  createHandlerBoundToURL(process.env.PUBLIC_URL + '/index.html')
);

// APIリクエストのキャッシュ戦略
registerRoute(
  ({ url }: { url: URL }) => url.origin === self.location.origin && url.pathname.startsWith('/api/v2/'),
  new StaleWhileRevalidate({
    cacheName: 'api-cache',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 50,
        maxAgeSeconds: 60 * 60 * 24, // 1日
      }),
    ],
  })
);

// 画像のキャッシュ戦略
registerRoute(
  ({ request }: { request: Request }) => request.destination === 'image',
  new CacheFirst({
    cacheName: 'images',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 60,
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30日
      }),
    ],
  })
);

// オフラインフォールバックページ
const FALLBACK_HTML = '/offline.html';
self.addEventListener('install', (event) => {
  const files = [FALLBACK_HTML];
  event.waitUntil(
    self.caches.open('offline-fallbacks').then((cache) => cache.addAll(files))
  );
});

// オフラインフォールバックの適用
self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(FALLBACK_HTML) as Promise<Response>;
      })
    );
  }
});

// 同期キューの処理
// @ts-ignore - SyncEvent は TypeScript の型定義に含まれていない場合がある
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-highlights') {
    event.waitUntil(syncHighlights());
  }
});

async function syncHighlights() {
  try {
    const db = await openDB();
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
    
    for (const item of items) {
      try {
        const response = await fetch(item.url, {
          method: item.method,
          headers: item.headers,
          body: item.body,
        });
        
        if (response.ok) {
          // 成功したら同期キューから削除
          const deleteTx = db.transaction('syncQueue', 'readwrite');
          const deleteStore = deleteTx.objectStore('syncQueue');
          
          // IDBRequest を Promise にラップ
          await new Promise<void>((resolve, reject) => {
            const request = deleteStore.delete(item.id);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
          });
          
          // トランザクションの完了を待つ
          await new Promise<void>((resolve, reject) => {
            deleteTx.oncomplete = () => resolve();
            deleteTx.onerror = () => reject(deleteTx.error);
          });
        }
      } catch (e) {
        console.error('同期エラー:', e);
      }
    }
  } catch (e) {
    console.error('同期キュー処理エラー:', e);
  }
}

async function openDB(): Promise<IDBDatabase> {
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
}

// Service Workerのアクティベーション
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
