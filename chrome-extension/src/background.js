// APIエンドポイント設定
const API_BASE_URL = 'http://localhost:8000'; // 開発環境
// const API_BASE_URL = 'https://your-production-api.com'; // 本番環境

// 開発モードの設定
const DEV_MODE = true; // 開発中はtrueに設定

// ダミーデータのインポート（開発用）
let dummyData = null;
try {
  // 開発環境でのみ利用可能
  if (typeof importScripts === 'function') {
    importScripts('./dummy-data.js');
    dummyData = {
      simulateApiResponse
    };
  }
} catch (e) {
  console.log('Booklight AI: ダミーデータのインポートに失敗しました（本番環境では正常）', e);
}

// 認証関連の関数
async function authenticateWithGoogle() {
  try {
    if (DEV_MODE) {
      console.log('Booklight AI: 開発モードでダミー認証を使用します');
      const token = {
        access_token: 'dummy_token_' + Date.now(),
        token_type: 'bearer',
        user_id: 'google_user',
        email: 'google_user@example.com',
        full_name: 'Google User',
        status: 'success'
      };
      await chrome.storage.local.set({ 
        'authToken': token.access_token,
        'userId': token.user_id,
        'userEmail': token.email,
        'userName': token.full_name,
        'authTime': Date.now()
      });
      return { success: true, user: token.full_name || token.user_id };
    }
    
    // Google OAuth認証を行う
    // 新しいタブでGoogle認証ページを開く
    const authTabId = await openGoogleAuthTab();
    
    // 認証完了を待機
    return new Promise((resolve) => {
      // メッセージリスナーを設定
      const messageListener = async (message, sender) => {
        if (message.action === 'google_auth_success' && message.token) {
          // Google IDトークンをAPIに送信
          try {
            const response = await fetch(`${API_BASE_URL}/auth/google/token`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json'
              },
              body: JSON.stringify({ token: message.token })
            });
            
            if (!response.ok) {
              throw new Error(`認証エラー: ${response.status}`);
            }
            
            const data = await response.json();
            
            // トークンとユーザー情報を保存
            await chrome.storage.local.set({ 
              'authToken': data.access_token,
              'userId': data.user_id,
              'userEmail': data.email,
              'userName': data.full_name,
              'userPicture': data.picture,
              'authTime': Date.now()
            });
            
            // 認証タブを閉じる
            if (authTabId) {
              chrome.tabs.remove(authTabId);
            }
            
            // リスナーを削除
            chrome.runtime.onMessage.removeListener(messageListener);
            
            resolve({ success: true, user: data.full_name || data.user_id });
          } catch (error) {
            console.error('Booklight AI: トークン検証エラー', error);
            resolve({ success: false, message: `認証エラー: ${error.message}` });
          }
        } else if (message.action === 'google_auth_error') {
          console.error('Booklight AI: Google認証エラー', message.error);
          resolve({ success: false, message: `Google認証エラー: ${message.error}` });
        }
      };
      
      // メッセージリスナーを登録
      chrome.runtime.onMessage.addListener(messageListener);
      
      // タイムアウト処理（2分後）
      setTimeout(() => {
        chrome.runtime.onMessage.removeListener(messageListener);
        if (authTabId) {
          chrome.tabs.remove(authTabId);
        }
        resolve({ success: false, message: '認証がタイムアウトしました' });
      }, 120000);
    });
  } catch (error) {
    console.error('Booklight AI: 認証エラー', error);
    return { success: false, message: `認証エラー: ${error.message}` };
  }
}

// Google認証ページを開く
async function openGoogleAuthTab() {
  try {
    const authUrl = `${API_BASE_URL}/auth/google`;
    const tab = await chrome.tabs.create({ url: authUrl });
    return tab.id;
  } catch (error) {
    console.error('Booklight AI: 認証ページを開けませんでした', error);
    return null;
  }
}

// トークンの有効性を確認
async function validateToken() {
  try {
    const authData = await chrome.storage.local.get(['authToken', 'authTime']);
    
    // トークンがない場合
    if (!authData.authToken) {
      return false;
    }
    
    // トークンの有効期限をチェック（30分）
    const now = Date.now();
    const tokenAge = now - (authData.authTime || 0);
    if (tokenAge > 30 * 60 * 1000) {
      // トークンの有効期限切れ
      return false;
    }
    
    return true;
  } catch (error) {
    console.error('Booklight AI: トークン検証エラー', error);
    return false;
  }
}

// ハイライトをAPIに送信する関数
async function sendHighlightsToAPI(highlights) {
  try {
    console.log('Booklight AI: APIにハイライトを送信します', highlights);
    
    // 開発モードでダミーレスポンスを返す
    if (DEV_MODE && dummyData) {
      console.log('Booklight AI: 開発モードでダミーレスポンスを使用します');
      return dummyData.simulateApiResponse(highlights);
    }
    
    // トークンの有効性を確認
    const isTokenValid = await validateToken();
    if (!isTokenValid) {
      // 再認証
      const authResult = await authenticateWithGoogle();
      if (!authResult.success) {
        return { success: false, message: '認証に失敗しました。再度ログインしてください。' };
      }
    }
    
    // 認証トークンの取得
    const authData = await chrome.storage.local.get(['authToken']);
    if (!authData.authToken) {
      console.error('Booklight AI: 認証トークンがありません');
      return { success: false, message: 'ログインが必要です' };
    }
    
    // APIリクエスト
    const response = await fetch(`${API_BASE_URL}/api/highlights`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authData.authToken}`
      },
      body: JSON.stringify({ highlights: highlights })
    });
    
    // レスポンスの処理
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Booklight AI: APIエラー', response.status, errorText);
      return { 
        success: false, 
        message: `APIエラー: ${response.status} ${response.statusText}` 
      };
    }
    
    const data = await response.json();
    console.log('Booklight AI: API応答', data);
    
    return { 
      success: true, 
      message: data.message || `${highlights.length}件のハイライトを保存しました` 
    };
  } catch (error) {
    console.error('Booklight AI: API通信エラー', error);
    return { 
      success: false, 
      message: `通信エラー: ${error.message}` 
    };
  }
}

// オフラインモード用のキャッシュ
let pendingHighlights = [];

// オフラインモードの確認
function isOffline() {
  return false; // Service Workerではnavigator.onLineが使えないため、常にオンラインと仮定
}

// ハイライトをキャッシュに追加
function cacheHighlights(highlights) {
  pendingHighlights = pendingHighlights.concat(highlights);
  chrome.storage.local.set({ 'pendingHighlights': pendingHighlights });
  console.log('Booklight AI: ハイライトをキャッシュに保存しました', pendingHighlights.length);
}

// キャッシュされたハイライトを送信
async function sendCachedHighlights() {
  if (pendingHighlights.length === 0) {
    return;
  }
  
  console.log('Booklight AI: キャッシュされたハイライトを送信します', pendingHighlights.length);
  
  const result = await sendHighlightsToAPI(pendingHighlights);
  if (result.success) {
    pendingHighlights = [];
    chrome.storage.local.remove('pendingHighlights');
    console.log('Booklight AI: キャッシュされたハイライトの送信に成功しました');
  } else {
    console.error('Booklight AI: キャッシュされたハイライトの送信に失敗しました', result.message);
  }
}

// オンライン状態の変化を監視（Service Worker対応版）
// Service Workerではwindowオブジェクトが存在しないため、代替手段を使用
// 定期的にキャッシュを確認して送信を試みる
setInterval(() => {
  console.log('Booklight AI: キャッシュ確認');
  sendCachedHighlights();
}, 60000); // 1分ごとに確認

// 拡張機能のインストール/更新時の処理
chrome.runtime.onInstalled.addListener(function(details) {
  console.log('Booklight AI: 拡張機能がインストール/更新されました', details.reason);
  
  // キャッシュの復元
  chrome.storage.local.get(['pendingHighlights'], function(data) {
    if (data.pendingHighlights) {
      pendingHighlights = data.pendingHighlights;
      console.log('Booklight AI: キャッシュを復元しました', pendingHighlights.length);
      
      // キャッシュを送信（Service Workerでは常にオンラインと仮定）
      sendCachedHighlights();
    }
  });
});

// メッセージリスナーを設定
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Booklight AI: バックグラウンドスクリプトがメッセージを受信しました', request);
  
  if (request.action === 'sendHighlights') {
    // オフラインの場合はキャッシュに保存
    if (isOffline()) {
      cacheHighlights(request.highlights);
      sendResponse({ 
        success: true, 
        offline: true,
        message: 'オフラインモードでハイライトを保存しました。オンラインになったら自動的に同期されます。' 
      });
      return true;
    }
    
    // オンラインの場合はAPIに送信
    sendHighlightsToAPI(request.highlights)
      .then(result => sendResponse(result))
      .catch(error => {
        console.error('Booklight AI: ハイライト送信中にエラーが発生しました', error);
        sendResponse({ 
          success: false, 
          message: `エラーが発生しました: ${error.message}` 
        });
      });
    
    return true; // 非同期レスポンスのために必要
  }
  
  if (request.action === 'login') {
    // Google認証を実行
    authenticateWithGoogle()
      .then(result => {
        if (result.success) {
          sendResponse({ 
            success: true, 
            userName: result.user
          });
        } else {
          sendResponse({ 
            success: false, 
            message: result.message
          });
        }
      })
      .catch(error => {
        console.error('Booklight AI: ログイン中にエラーが発生しました', error);
        sendResponse({ 
          success: false, 
          message: `エラーが発生しました: ${error.message}` 
        });
      });
    return true;
  }
  
  if (request.action === 'logout') {
    // ログアウト処理
    chrome.storage.local.remove(['authToken', 'userId', 'authTime'], () => {
      sendResponse({ success: true });
    });
    return true;
  }
  
  if (request.action === 'checkAuth') {
    // 認証状態の確認
    validateToken()
      .then(isValid => {
        if (isValid) {
          chrome.storage.local.get(['userId'], (data) => {
            sendResponse({ 
              success: true, 
              isAuthenticated: true,
              userName: data.userId || 'ユーザー'
            });
          });
        } else {
          sendResponse({ 
            success: true, 
            isAuthenticated: false
          });
        }
      })
      .catch(error => {
        console.error('Booklight AI: 認証確認中にエラーが発生しました', error);
        sendResponse({ 
          success: false, 
          isAuthenticated: false,
          message: `エラーが発生しました: ${error.message}` 
        });
      });
    return true;
  }
});

// 初期化メッセージ
console.log('Booklight AI: バックグラウンドスクリプトが読み込まれました');
