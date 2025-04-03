// APIエンドポイント設定
// const API_BASE_URL = 'http://localhost:8000'; // 開発環境
const API_BASE_URL = 'https://booklight-ai.com'; // 本番環境


// 開発モードの設定
const DEV_MODE = true; // 開発環境ではtrueに設定

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

// 一括取得を開始する関数
async function startCollectingAllBooks(books, callback) {
  if (isCollectingAll) {
    return { success: false, message: '既に一括取得処理が実行中です' };
  }
  
  // 進捗コールバックを設定
  progressCallback = callback;
  
  // 初期化
  isCollectingAll = true;
  bookQueue = [...books];
  allCollectedData = {};
  
  // 現在のタブを取得
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs.length > 0) {
      currentCollectionTabId = tabs[0].id;
      originalTabUrl = tabs[0].url;
      
      // 処理開始
      notifyProgress(0, books.length, '一括取得を開始します...');
      
      // 最初の書籍の処理を開始
      setTimeout(processBookQueue, 500);
      
      return { success: true, message: '一括取得を開始しました' };
    } else {
      return { success: false, message: 'アクティブなタブが見つかりません' };
    }
  } catch (error) {
    console.error('Booklight AI: 一括取得開始エラー', error);
    isCollectingAll = false;
    return { success: false, message: `一括取得開始エラー: ${error.message}` };
  }
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
      self.setTimeout(() => {
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
    console.log('Booklight AI: Google認証ページを開きます', authUrl);

    // 新しいタブで認証ページを開く
    const tab = await chrome.tabs.create({
      url: authUrl,
      active: true // ユーザーに認証ページを表示するために、タブをアクティブにする
    });

    // タブの読み込み完了を待機
    return new Promise((resolve) => {
      const tabLoadListener = (tabId, changeInfo) => {
        if (tabId === tab.id && changeInfo.status === 'complete') {
          console.log('Booklight AI: 認証ページの読み込みが完了しました');
          chrome.tabs.onUpdated.removeListener(tabLoadListener);
          resolve(tab.id);
        }
      };

      chrome.tabs.onUpdated.addListener(tabLoadListener);

      // タイムアウト処理（30秒後）
      setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(tabLoadListener);
        console.log('Booklight AI: 認証ページの読み込みがタイムアウトしました');
        resolve(tab.id); // タイムアウトしても、タブIDは返す
      }, 30000);
    });
  } catch (error) {
    console.error('Booklight AI: 認証ページを開けませんでした', error);
    return null;
  }
}

// トークンリフレッシュ機能
async function refreshToken() {
  try {
    const authData = await chrome.storage.local.get(['authToken']);
    if (!authData.authToken) {
      console.log('Booklight AI: 認証トークンがありません');
      return false;
    }

    // APIを使用してトークンをリフレッシュ
    const response = await fetch(`${API_BASE_URL}/auth/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ token: authData.authToken })
    });

    if (!response.ok) {
      console.log('Booklight AI: トークンリフレッシュに失敗しました', response.status);
      return false;
    }

    const data = await response.json();

    // 新しいトークンを保存
    await chrome.storage.local.set({
      'authToken': data.access_token,
      'authTime': Date.now()
    });

    return true;
  } catch (error) {
    console.error('Booklight AI: トークンリフレッシュエラー', error);
    return false;
  }
}

// トークンの有効性を確認
async function validateToken() {
  try {
    const authData = await chrome.storage.local.get(['authToken', 'authTime']);

    // トークンがない場合
    if (!authData.authToken) {
      console.log('Booklight AI: 認証トークンがありません');
      return false;
    }

    // トークンの有効期限をチェック（25分）
    const now = Date.now();
    const tokenAge = now - (authData.authTime || 0);
    if (tokenAge > 25 * 60 * 1000) {
      console.log('Booklight AI: 認証トークンの有効期限が近いため、リフレッシュを試みます');
      return await refreshToken();
    }

    // APIを使用してトークンの有効性を確認（オプション）
    try {
      const response = await fetch(`${API_BASE_URL}/auth/user`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authData.authToken}`
        }
      });

      if (!response.ok) {
        console.log('Booklight AI: 認証トークンが無効です', response.status);
        // 401エラーの場合はリフレッシュを試みる
        if (response.status === 401) {
          return await refreshToken();
        }
        return false;
      }

      // トークンが有効な場合、有効期限を更新
      await chrome.storage.local.set({ 'authTime': Date.now() });
      return true;
    } catch (error) {
      console.error('Booklight AI: トークン検証中にエラーが発生しました', error);
      // ネットワークエラーの場合は、トークンの有効期限だけで判断
      return tokenAge <= 30 * 60 * 1000;
    }
  } catch (error) {
    console.error('Booklight AI: トークン検証エラー', error);
    return false;
  }
}

// ハイライトをローカルストレージに保存し、APIにも送信する関数
async function processAndStoreHighlights(highlights) {
  try {
    console.log('Booklight AI: ハイライトを処理・保存します', highlights);

    // --- ローカルストレージへの保存処理 ---
    const highlightsByBook = {};
    // 書籍ごとにハイライトをグループ化
    highlights.forEach(h => {
      // book_title が存在しない、または空の場合のフォールバック
      const title = h.book_title || '不明な書籍';
      const author = h.author || '不明な著者';
      const bookKey = `book-${title}-${author}`; // 書籍ごとの一意なキー
      if (!highlightsByBook[bookKey]) {
        highlightsByBook[bookKey] = {
          title: title,
          author: author,
          cover_image_url: h.cover_image_url, // カバー画像URLも保存
          highlights: []
        };
      }
      // ハイライト情報のみを抽出して追加（重複を避けるため、後で差分更新を実装）
      highlightsByBook[bookKey].highlights.push({
          content: h.content,
          location: h.location
      });
    });

    // 各書籍のデータをストレージに保存/更新
    for (const bookKey in highlightsByBook) {
        const bookData = highlightsByBook[bookKey];
        // 現在のストレージからデータを取得 (差分更新のため - Step 6で実装)
        // const existingData = await chrome.storage.local.get(bookKey);
        // const mergedHighlights = mergeHighlights(existingData[bookKey]?.highlights || [], bookData.highlights);

        // 現時点では単純に上書き保存
        const dataToStore = {
            [bookKey]: {
                title: bookData.title,
                author: bookData.author,
                cover_image_url: bookData.cover_image_url,
                highlights: bookData.highlights, // ここは差分更新後のハイライトを入れる (Step 6)
                lastUpdated: new Date().toISOString()
            }
        };
        await chrome.storage.local.set(dataToStore);
        console.log(`Booklight AI: 書籍「${bookData.title}」のハイライトをローカルに保存しました`);
    }
    // --- ローカルストレージへの保存処理ここまで ---

    // --- APIへの送信処理 (既存のロジック) ---
    console.log('Booklight AI: APIにハイライトを送信します', highlights); // 送信するデータは元の形式のまま

    // 開発モードでダミーレスポンスを返す
    if (DEV_MODE && dummyData) {
      console.log('Booklight AI: 開発モードでダミーレスポンスを使用します');
      // ローカル保存成功のメッセージを返すように変更
      const dummyResponse = dummyData.simulateApiResponse(highlights);
      return {
          success: true,
          message: `${highlights.length}件のハイライトをローカルに保存し、API送信をシミュレートしました`,
          total_highlights: dummyResponse.total_highlights // APIからの合計件数はそのまま返す
      };
    }

    // トークンの有効性を確認
    const isTokenValid = await validateToken();
    if (!isTokenValid) {
      console.log('Booklight AI: 認証トークンが無効なため、再認証を行います');
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

      // 認証エラーの場合
      if (response.status === 401) {
        // 認証トークンをクリアして再認証を促す
        await chrome.storage.local.remove(['authToken', 'authTime']);
        return {
          success: false,
          message: '認証の有効期限が切れました。再度ログインしてください。'
        };
      }

      return {
        success: false,
        message: `APIエラー: ${response.status} ${response.statusText}`
      };
    }

    const data = await response.json();
    console.log('Booklight AI: API応答', data);

    return {
      success: true,
      message: data.message || `${highlights.length}件のハイライトを保存しました`,
      total_highlights: data.total_highlights
    };
  } catch (error) {
    console.error('Booklight AI: ハイライト処理・保存・送信中にエラーが発生しました', error);

    // オフライン判定
    if (!navigator.onLine || error.name === 'TypeError') {
      // オフラインモードでキャッシュに保存
      // ローカル保存は試みているはずなので、キャッシュはAPI送信用
      cacheHighlightsForApi(highlights); // API送信用キャッシュ関数に変更
      return {
        success: true, // ローカル保存は成功している可能性がある
        offline: true,
        message: 'オフラインのため、ハイライトをローカルに保存しました。オンライン時にサーバーへ同期します。'
      };
    }

    return {
      success: false,
      message: `通信エラー: ${error.message}`
    };
  }
}

// オフラインモード用のキャッシュ
let pendingApiHighlights = []; // API送信用キャッシュ

// オフラインモードの確認 (Service Workerではnavigator.onLineが使えないため、常にオンラインと仮定するが、念のため残す)
function isOffline() {
  return typeof navigator !== 'undefined' && !navigator.onLine;
}

// API送信用にハイライトをキャッシュに追加
function cacheHighlightsForApi(highlights) {
  pendingApiHighlights = pendingApiHighlights.concat(highlights);
  chrome.storage.local.set({ 'pendingApiHighlights': pendingApiHighlights });
  console.log('Booklight AI: API送信用ハイライトをキャッシュに保存しました', pendingApiHighlights.length);
}

// キャッシュされたAPI送信用ハイライトを送信
async function sendCachedApiHighlights() {
  if (pendingApiHighlights.length === 0 || isOffline()) { // オンライン状態もチェック
    return;
  }

  console.log('Booklight AI: キャッシュされたAPI送信用ハイライトを送信します', pendingApiHighlights.length);

  // API送信のみを行うヘルパー関数 (sendHighlightsToAPIからAPI送信部分を抜き出すか、引数で制御)
  const result = await sendHighlightsToAPIOnly(pendingApiHighlights); // 仮の関数名

  if (result.success) {
    pendingApiHighlights = [];
    chrome.storage.local.remove('pendingApiHighlights');
    console.log('Booklight AI: キャッシュされたハイライトの送信に成功しました');
  } else {
    console.error('Booklight AI: キャッシュされたハイライトの送信に失敗しました', result.message);
  }
}

// API送信のみを行うヘルパー関数 (sendHighlightsToAPIからAPI送信部分を抽出)
async function sendHighlightsToAPIOnly(highlights) {
    try {
        console.log('Booklight AI: APIにハイライトのみ送信します', highlights);
         // トークンの有効性を確認
        const isTokenValid = await validateToken();
        if (!isTokenValid) {
          return { success: false, message: '認証トークンが無効です' };
        }
         // 認証トークンの取得
        const authData = await chrome.storage.local.get(['authToken']);
        if (!authData.authToken) {
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
         if (!response.ok) {
          const errorText = await response.text();
          if (response.status === 401) {
            await chrome.storage.local.remove(['authToken', 'authTime']);
          }
          throw new Error(`APIエラー: ${response.status} ${errorText}`);
        }
         const data = await response.json();
        return { success: true, message: data.message, total_highlights: data.total_highlights };
     } catch (error) {
        console.error('Booklight AI: API送信エラー', error);
        return { success: false, message: `API送信エラー: ${error.message}` };
    }
}


// 定期的にAPI送信用キャッシュを確認して送信を試みる
self.setInterval(() => {
  console.log('Booklight AI: API送信用キャッシュ確認');
  sendCachedApiHighlights();
}, 60000); // 1分ごとに確認

// 拡張機能のインストール/更新時の処理
chrome.runtime.onInstalled.addListener(function(details) {
  console.log('Booklight AI: 拡張機能がインストール/更新されました', details.reason);

  // API送信用キャッシュの復元
  chrome.storage.local.get(['pendingApiHighlights'], function(data) {
    if (data.pendingApiHighlights) {
      pendingApiHighlights = data.pendingApiHighlights;
      console.log('Booklight AI: API送信用キャッシュを復元しました', pendingApiHighlights.length);
      // オンラインなら送信試行
      sendCachedApiHighlights();
    }
  });
});

// --- 一括取得機能 ---
let isCollectingAll = false; // 一括取得中フラグ
let bookQueue = []; // 処理対象の書籍情報 {title, url}
let allCollectedData = {}; // 全書籍の収集結果 { bookTitle: { url, highlights: [...] } }
let currentCollectionTabId = null; // 一括取得に使用するタブID
let progressCallback = null; // 進捗通知用コールバック (popup.jsへ)
let originalTabUrl = null; // 収集開始時のタブURL

// 進捗を通知する関数
function notifyProgress(processed, total, message = '') {
  if (progressCallback) {
    try {
      progressCallback({
        action: 'updateProgress',
        processed: processed,
        total: total,
        message: message
      });
    } catch (e) {
      console.warn("Booklight AI: 進捗通知コールバックの呼び出しに失敗しました", e);
      progressCallback = null; // コールバックが無効になった場合はクリア
    }
  }
  // ポップアップにもメッセージを送信 (ポップアップが開いている場合)
  chrome.runtime.sendMessage({
    action: 'updateProgress',
    processed: processed,
    total: total,
    message: message
  }).catch(e => { /* ポップアップが開いていない場合のエラーは無視 */ });
}

// --- 一括取得処理の最適化 ---

// 進捗とエラーを記録・通知する関数
function logAndNotify(message, processed, total) {
  console.log(`Booklight AI: ${message}`);
  
  // 進捗通知
  notifyProgress(processed, total, message);
  
  // エラーログ（必要に応じて）
  if (message.includes('エラー') || message.includes('失敗')) {
    console.error(`Booklight AI: ${message}`);
  }
}

// 収集完了時の処理
async function finishCollection() {
  console.log('Booklight AI: 一括取得完了');
  isCollectingAll = false;
  
  const totalCollected = Object.keys(allCollectedData).length;
  const totalHighlights = Object.values(allCollectedData)
    .reduce((sum, book) => sum + (book.highlights?.length || 0), 0);
  
  notifyProgress(
    totalCollected, 
    totalCollected, 
    `一括取得完了: ${totalCollected}冊の書籍から${totalHighlights}件のハイライトを取得しました`
  );
  
  // 元のページに戻る
  if (currentCollectionTabId && originalTabUrl) {
    try {
      await chrome.tabs.update(currentCollectionTabId, { url: originalTabUrl });
      console.log('Booklight AI: 元のページに戻りました:', originalTabUrl);
    } catch (error) {
      console.error('Booklight AI: 元のページへの復元に失敗しました', error);
    }
  }
  
  // 収集したデータの処理
  if (totalHighlights > 0) {
    const allHighlights = [];
    for (const bookTitle in allCollectedData) {
      const book = allCollectedData[bookTitle];
      // 書籍情報をハイライトに付加
      book.highlights.forEach(highlight => {
        allHighlights.push({
          book_title: bookTitle,
          author: book.author,
          cover_image_url: book.cover_image_url,
          content: highlight.content,
          location: highlight.location
        });
      });
    }
    
    // バックグラウンドスクリプトに送信
    try {
      console.log(`Booklight AI: 収集した ${allHighlights.length} 件のハイライトを処理します`);
      const result = await processAndStoreHighlights(allHighlights);
      if (result.success) {
        notifyProgress(
          totalCollected, 
          totalCollected, 
          `保存完了: ${result.message || `${allHighlights.length}件のハイライトを保存しました`}`
        );
      } else {
        notifyProgress(
          totalCollected, 
          totalCollected, 
          `保存エラー: ${result.message || '不明なエラー'}`
        );
      }
    } catch (error) {
      notifyProgress(
        totalCollected, 
        totalCollected, 
        `保存エラー: ${error.message}`
      );
    }
  }
  
  // クリーンアップ
  currentCollectionTabId = null;
  originalTabUrl = null;
  allCollectedData = {};
}

// ページ遷移と読み込み待機を行う関数
async function navigateToBookPage(book, tabId) {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(tabUpdateListener);
      reject(new Error(`ページ読み込みタイムアウト: ${book.title}`));
    }, 30000); // 30秒タイムアウト
    
    const tabUpdateListener = (updatedTabId, changeInfo, tab) => {
      // URLの部分一致で確認（クエリパラメータが変わる場合に対応）
      const isTargetUrl = tab.url && (
        tab.url === book.url || 
        (book.bookId && tab.url.includes(book.bookId))
      );
      
      if (updatedTabId === tabId && changeInfo.status === 'complete' && isTargetUrl) {
        chrome.tabs.onUpdated.removeListener(tabUpdateListener);
        clearTimeout(timeoutId);
        
        // ページ読み込み後、コンテンツスクリプトの準備を待つ
        waitForContentScript(tabId)
          .then(() => resolve())
          .catch(error => reject(error));
      }
    };
    
    chrome.tabs.onUpdated.addListener(tabUpdateListener);
    
    // ページ遷移
    chrome.tabs.update(tabId, { url: book.url, active: false })
      .catch(error => {
        chrome.tabs.onUpdated.removeListener(tabUpdateListener);
        clearTimeout(timeoutId);
        reject(error);
      });
  });
}

// ハイライト取得を実行する関数
async function extractBookHighlights(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        // content.jsのextractCurrentBookData関数を呼び出す
        if (typeof extractCurrentBookData === 'function') {
          return extractCurrentBookData();
        } else {
          return { 
            success: false, 
            message: 'extractCurrentBookData関数が見つかりません' 
          };
        }
      }
    });
    
    return results[0]?.result || { 
      success: false, 
      message: 'スクリプト実行結果が取得できませんでした' 
    };
  } catch (error) {
    return { 
      success: false, 
      message: `スクリプト実行エラー: ${error.message}` 
    };
  }
}

// キューから次の書籍を処理する関数（改良版）
async function processBookQueue() {
  if (!isCollectingAll || bookQueue.length === 0) {
    // 収集完了処理
    await finishCollection();
    return;
  }

  const book = bookQueue.shift();
  const totalBooks = Object.keys(allCollectedData).length + bookQueue.length + 1;
  const processedCount = Object.keys(allCollectedData).length;

  try {
    // URLチェックと進捗通知
    if (!book.url) {
      logAndNotify(`スキップ: ${book.title} (URL不明)`, processedCount, totalBooks);
      setTimeout(processBookQueue, 500); // 次の書籍へ（少し間隔を空ける）
      return;
    }

    logAndNotify(`処理中: ${book.title}`, processedCount, totalBooks);

    // ページ遷移と読み込み待機
    try {
      await navigateToBookPage(book, currentCollectionTabId);
      console.log(`Booklight AI: 「${book.title}」のページ読み込みと準備完了`);
    } catch (error) {
      logAndNotify(`ページ読み込みエラー: ${book.title} - ${error.message}`, processedCount, totalBooks);
      setTimeout(processBookQueue, 500);
      return;
    }
    
    // ハイライト取得処理
    const bookData = await extractBookHighlights(currentCollectionTabId);
    
    // 取得結果の処理
    if (bookData.success && bookData.data) {
      const title = bookData.data.book_title || book.title;
      const highlightCount = bookData.data.highlights?.length || 0;
      
      // 収集データに追加
      allCollectedData[title] = {
        url: book.url,
        author: bookData.data.author,
        cover_image_url: bookData.data.cover_image_url,
        highlights: bookData.data.highlights || []
      };
      
      logAndNotify(
        `取得成功: ${title} (${highlightCount}件のハイライト)`, 
        processedCount + 1, 
        totalBooks
      );
    } else {
      logAndNotify(
        `取得失敗: ${book.title} - ${bookData.message || '不明なエラー'}`, 
        processedCount, 
        totalBooks
      );
    }

    // 次の書籍を処理（少し間隔を空ける）
    setTimeout(processBookQueue, 1000);
  } catch (error) {
    // エラーハンドリング
    console.error(`Booklight AI: 書籍処理エラー: ${error.message}`, error);
    logAndNotify(
      `処理エラー: ${book?.title || '不明な書籍'} - ${error.message}`, 
      processedCount, 
      totalBooks
    );
    
    // エラーが発生しても次の書籍を処理
    setTimeout(processBookQueue, 1000);
  }
}

// コンテンツスクリプトの準備を待つ関数
async function waitForContentScript(tabId) {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      reject(new Error('コンテンツスクリプトの準備タイムアウト'));
    }, 10000); // 10秒タイムアウト
    
    // コンテンツスクリプトの準備確認
    function checkContentScript() {
      chrome.scripting.executeScript({
        target: { tabId },
        func: () => {
          return typeof extractCurrentBookData === 'function';
        }
      }).then(results => {
        const isReady = results[0]?.result;
        if (isReady) {
          clearTimeout(timeoutId);
          resolve();
        } else {
          // まだ準備できていない場合は少し待ってから再試行
          setTimeout(checkContentScript, 500);
        }
      }).catch(error => {
        clearTimeout(timeoutId);
        reject(error);
      });
    }
    
    // 確認開始
    checkContentScript();
  });
}

// メッセージリスナー (トップレベルに追加)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("Booklight AI: Background received message:", request.action); // Log received action

  // 非同期処理のため true を返す
  let isAsync = false;

  if (request.action === 'login') {
    isAsync = true; // 非同期処理を示す
    authenticateWithGoogle().then(result => {
      console.log("Booklight AI: Login action result:", result); // Log result
      sendResponse(result);
    }).catch(error => {
      console.error("Booklight AI: Login action error:", error); // Log error
      sendResponse({ success: false, message: `ログイン処理中にエラー: ${error.message}` });
    });
  } else if (request.action === 'logout') {
    isAsync = true; // 非同期処理を示す
    // ログアウト処理 (トークン削除など)
    chrome.storage.local.remove(['authToken', 'userId', 'userEmail', 'userName', 'userPicture', 'authTime'])
      .then(() => {
        console.log("Booklight AI: Logout successful"); // Log success
        sendResponse({ success: true });
      }).catch(error => {
        console.error("Booklight AI: Logout error:", error); // Log error
        sendResponse({ success: false, message: `ログアウト処理中にエラー: ${error.message}` });
      });
  } else if (request.action === 'checkAuth') {
    isAsync = true; // 非同期処理を示す
    validateToken().then(isValid => {
      if (isValid) {
        chrome.storage.local.get(['userName', 'userEmail']).then(userData => {
          console.log("Booklight AI: CheckAuth successful", userData); // Log success
          sendResponse({ success: true, isAuthenticated: true, userName: userData.userName, userEmail: userData.userEmail });
        });
      } else {
        console.log("Booklight AI: CheckAuth failed - token invalid"); // Log failure
        sendResponse({ success: true, isAuthenticated: false });
      }
    }).catch(error => {
      console.error("Booklight AI: CheckAuth error:", error); // Log error
      sendResponse({ success: false, isAuthenticated: false, message: `認証チェックエラー: ${error.message}` });
    });
  } else if (request.action === 'sendHighlights') {
    isAsync = true; // 非同期処理を示す
    if (request.highlights) {
      processAndStoreHighlights(request.highlights).then(result => {
        console.log("Booklight AI: SendHighlights result:", result); // Log result
        sendResponse(result);
      }).catch(error => {
        console.error("Booklight AI: SendHighlights error:", error); // Log error
        sendResponse({ success: false, message: `ハイライト送信処理エラー: ${error.message}` });
      });
    } else {
      console.log("Booklight AI: SendHighlights failed - no highlights provided"); // Log failure
      sendResponse({ success: false, message: '送信するハイライトがありません' });
    }
  } else if (request.action === 'collectAllHighlights') {
      isAsync = true; // 非同期処理を示す
      // コンテンツスクリプトから書籍リストを取得する処理が必要
      // この例では、仮に書籍リストが取得済みとして進める
      // 実際には content script との連携が必要
      console.log("Booklight AI: collectAllHighlights action received (implementation needed)");
      // TODO: コンテンツスクリプトから書籍リストを取得するロジックを追加
      const dummyBooks = [ /* { title: 'Book 1', url: '...' } */ ]; // 仮の書籍リスト
      startCollectingAllBooks(dummyBooks, sendResponse).then(result => {
          // startCollectingAllBooks は初期応答を返し、進捗は別途通知される
          // ここでは初期応答のみ返す
          sendResponse(result);
      }).catch(error => {
          sendResponse({ success: false, message: `一括取得開始エラー: ${error.message}` });
      });

  } else if (request.action === 'cancelCollectAll') {
      isCollectingAll = false; // 収集フラグをリセット
      bookQueue = []; // キューをクリア
      console.log("Booklight AI: 一括取得がキャンセルされました");
      // 必要に応じて進行中のタブ操作を停止する処理を追加
      sendResponse({ success: true, message: '一括取得をキャンセルしました' });
  }
  // 他のアクションもここに追加...

  // 非同期応答の場合は true を返す必要がある
  return isAsync;
});
