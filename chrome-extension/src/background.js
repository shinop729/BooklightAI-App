// APIエンドポイント設定
// const API_BASE_URL = 'http://localhost:8000'; // 開発環境
const API_BASE_URL = 'https://booklight-ai.com'; // 本番環境
const SYNC_API_ENDPOINT = `${API_BASE_URL}/api/sync-highlights`; // 差分同期用エンドポイント
const CSV_EXPORT_KEY = 'csvExportData'; // CSVエクスポート用データキー

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

// --- 一括取得用グローバル変数 ---
let isCollectingAll = false; // 一括取得中フラグ
let progressCallback = null; // 進捗通知用コールバック
let bookQueue = []; // 処理待ち書籍キュー
let allCollectedData = {}; // 全書籍データ格納用
let currentCollectionTabId = null; // 処理中のタブID
let originalTabUrl = null; // 元のタブURL
// --- 一括取得用グローバル変数ここまで ---


/**
 * 文字列からシンプルなハッシュ値を生成する関数 (簡易版)
 * @param {string} str - ハッシュ化する文字列
 * @returns {string} - ハッシュ値
 */
function simpleHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0; // Convert to 32bit integer
  }
  // 衝突を避けるため、より安全なハッシュ関数 (例: SHA-256) のライブラリを使うのが望ましい
  // ここでは簡易的な実装とする
  return hash.toString(16); // 16進数文字列に変換
}

/**
 * ハイライトオブジェクトから一意なID（ハッシュ）を生成する
 * @param {object} highlight - ハイライトオブジェクト ({ content: string, location: string })
 * @returns {string} - ハイライトのハッシュID
 */
function generateHighlightId(highlight) {
  if (!highlight || typeof highlight.content !== 'string' || typeof highlight.location !== 'string') {
    console.warn('Booklight AI: 無効なハイライトデータのためIDを生成できません', highlight);
    return null;
  }
  // 内容と位置情報を組み合わせてハッシュ化
  const key = `${highlight.content.trim()}-${highlight.location.trim()}`;
  return simpleHash(key);
}

/**
 * 書籍データからストレージキーを生成する
 * @param {string} title - 書籍タイトル
 * @param {string} author - 著者名
 * @returns {string} - ストレージキー
 */
function generateBookStorageKey(title, author) {
  const cleanTitle = title?.trim() || '不明な書籍';
  const cleanAuthor = author?.trim() || '不明な著者';
  // キーが長くなりすぎないように注意しつつ、一意性を保つ
  return `sync-${simpleHash(cleanTitle)}-${simpleHash(cleanAuthor)}`;
}

/**
 * 指定された書籍の同期ステータスをローカルストレージから取得する
 * @param {string} storageKey - 書籍のストレージキー
 * @returns {Promise<object|null>} - 同期ステータス ({ lastSyncTimestamp: string, syncedHighlightIds: Set<string> }) または null
 */
async function getBookSyncStatus(storageKey) {
  try {
    const data = await chrome.storage.local.get(storageKey);
    if (data && data[storageKey]) {
      // Setオブジェクトに変換して返す
      const status = data[storageKey];
      status.syncedHighlightIds = new Set(status.syncedHighlightIds || []);
      return status;
    }
    return null; // データがない場合はnull
  } catch (error) {
    console.error(`Booklight AI: ストレージからの同期ステータス取得エラー (${storageKey})`, error);
    return null;
  }
}

/**
 * 書籍の同期ステータスをローカルストレージに保存する
 * @param {string} storageKey - 書籍のストレージキー
 * @param {string} lastSyncTimestamp - 最終同期タイムスタンプ (ISO文字列)
 * @param {Set<string>} syncedHighlightIds - 同期済みハイライトIDのSet
 * @returns {Promise<boolean>} - 保存成功時はtrue
 */
async function saveBookSyncStatus(storageKey, lastSyncTimestamp, syncedHighlightIds) {
  try {
    const dataToStore = {
      [storageKey]: {
        lastSyncTimestamp: lastSyncTimestamp,
        // Setを配列に変換して保存
        syncedHighlightIds: Array.from(syncedHighlightIds)
      }
    };
    await chrome.storage.local.set(dataToStore);
    return true;
  } catch (error) {
    console.error(`Booklight AI: ストレージへの同期ステータス保存エラー (${storageKey})`, error);
    return false;
  }
}

/**
 * CSVエクスポート用の書籍データをローカルストレージに保存/更新する
 * @param {object} bookData - 書籍データ { book_title, author, cover_image_url, highlights: [{ content, location, timestamp? }] }
 */
async function saveDataForCsvExport(bookData) {
  const { book_title, author, cover_image_url, highlights } = bookData;
  if (!book_title || !author || !Array.isArray(highlights)) {
    console.warn('Booklight AI: CSVエクスポート用のデータ保存に必要な情報が不足しています', bookData);
    return;
  }

  // 書籍IDを生成 (ストレージキーとは別に、データ内のIDとして使用)
  // generateBookStorageKey は 'sync-' プレフィックスが付くので、ここではシンプルなハッシュを使う
  const bookId = simpleHash(`${book_title}-${author}`);

  try {
    const result = await chrome.storage.local.get(CSV_EXPORT_KEY);
    const existingData = result[CSV_EXPORT_KEY] || {};

    // ハイライトデータにタイムスタンプを追加（なければ現在時刻）
    // content.jsから渡されるキー名に合わせる (content -> text)
    const timestampedHighlights = highlights.map(h => ({
      text: h.content, // popup.jsのconvertToCSVとキーを合わせる
      location: h.location,
      timestamp: h.timestamp || new Date().toISOString()
    }));

    // 既存データに今回の書籍データを追加または上書き
    existingData[bookId] = {
      id: bookId, // 書籍IDも保存
      title: book_title,
      author: author,
      coverSrc: cover_image_url, // popup.jsのconvertToCSVとキーを合わせる
      highlights: timestampedHighlights,
      lastUpdated: new Date().toISOString() // 最終更新日時
    };

    await chrome.storage.local.set({ [CSV_EXPORT_KEY]: existingData });
    console.log(`Booklight AI: CSVエクスポート用データを更新しました (Book ID: ${bookId})`);

  } catch (error) {
    console.error('Booklight AI: CSVエクスポート用データの保存中にエラーが発生しました', error);
  }
}


/**
 * 書籍データを同期する（差分検出とAPI送信）
 * @param {object} bookData - コンテンツスクリプトから抽出された書籍データ
 *                           { book_title, author, cover_image_url, highlights: [{ content, location }] }
 * @returns {Promise<object>} - 同期結果 { success, message, offline?, newHighlightsCount?, isNewBook? }
 */
async function syncBookData(bookData) {
  const { book_title, author, cover_image_url, highlights } = bookData;

  if (!book_title || !author) {
      console.warn('Booklight AI: 書籍タイトルまたは著者が不明なため同期をスキップします', bookData);
      return { success: false, message: '書籍タイトルまたは著者が不明です' };
  }

  const storageKey = generateBookStorageKey(book_title, author);
  console.log(`Booklight AI: 書籍「${book_title}」の同期を開始します (Key: ${storageKey})`);

  try {
    // 1. 現在のハイライトIDリストを作成
    const currentHighlightIds = new Map(); // Map<highlightId, highlightObject>
    const validHighlights = highlights.filter(h => h.content); // 有効なハイライトのみ対象
    validHighlights.forEach(h => {
      const id = generateHighlightId(h);
      if (id) {
        currentHighlightIds.set(id, h); // MapにIDと元のハイライトオブジェクトを保存
      }
    });

    // 2. ローカルストレージから前回の同期ステータスを取得
    const previousSyncStatus = await getBookSyncStatus(storageKey);
    const syncedHighlightIds = previousSyncStatus?.syncedHighlightIds || new Set();
    const isNewBook = !previousSyncStatus; // 前回同期ステータスがなければ新規書籍

    console.log(`Booklight AI: 前回同期済みハイライト数: ${syncedHighlightIds.size}, 今回のハイライト数: ${currentHighlightIds.size}, 新規書籍: ${isNewBook}`);

    // 3. 新規ハイライトを特定
    const newHighlights = [];
    for (const [id, highlight] of currentHighlightIds.entries()) {
      if (!syncedHighlightIds.has(id)) {
        newHighlights.push(highlight); // 同期済みIDセットに含まれていないものを新規とする
      }
    }

    console.log(`Booklight AI: 新規ハイライト数: ${newHighlights.length}`);

    // 4. 送信するペイロードを作成
    let payload = null;
    if (isNewBook || newHighlights.length > 0) {
      payload = {
        book: {
          title: book_title,
          author: author,
          cover_image_url: cover_image_url,
          is_new: isNewBook // 新規書籍かどうかを示すフラグ
        },
        highlights: newHighlights // 新規ハイライトのみ送信
      };
    } else {
      // 新規ハイライトがない場合は同期不要
      console.log(`Booklight AI: 書籍「${book_title}」に新規ハイライトはありません。同期をスキップします。`);
      // ローカルの最終同期日時だけ更新しても良いかもしれない
      await saveBookSyncStatus(storageKey, new Date().toISOString(), syncedHighlightIds);
      return { success: true, message: '新規ハイライトはありませんでした', newHighlightsCount: 0, isNewBook: false };
    }

    // 5. APIに差分データを送信
    console.log('Booklight AI: APIに差分データを送信します', payload);

    // 開発モードのダミーレスポンス
    if (DEV_MODE && dummyData) {
      console.log('Booklight AI: 開発モードで差分同期API送信をシミュレートします');
      // ダミーレスポンスを返す
      const currentTimestamp = new Date().toISOString();
      const updatedSyncedIds = new Set([...syncedHighlightIds, ...newHighlights.map(generateHighlightId).filter(id => id)]);
      await saveBookSyncStatus(storageKey, currentTimestamp, updatedSyncedIds);
      return {
          success: true,
          message: `${newHighlights.length}件の新規ハイライトを同期しました (シミュレート)`,
          newHighlightsCount: newHighlights.length,
          isNewBook: isNewBook
      };
    }

    // トークン検証と取得
    const isTokenValid = await validateToken();
    if (!isTokenValid) {
      // 再認証を試みるか、エラーを返す
      console.log('Booklight AI: 認証トークンが無効です。再認証が必要です。');
      // ここで authenticateWithGoogle() を呼ぶか、エラーを返すか選択
      return { success: false, message: '認証が必要です。再度ログインしてください。' };
    }
    const authData = await chrome.storage.local.get(['authToken']);
    if (!authData.authToken) {
      return { success: false, message: 'ログインが必要です' };
    }

    // 新しい差分同期APIエンドポイントにリクエスト
    const response = await fetch(SYNC_API_ENDPOINT, { // 新しいエンドポイントを使用
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authData.authToken}`
      },
      body: JSON.stringify(payload) // 作成したペイロードを送信
    });

    // 6. レスポンス処理とローカルステータス更新
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Booklight AI: 差分同期APIエラー', response.status, errorText);
      if (response.status === 401) {
        await chrome.storage.local.remove(['authToken', 'authTime']);
        return { success: false, message: '認証の有効期限が切れました。再度ログインしてください。' };
      }
      // オフライン判定とキャッシュ処理 (差分データのみキャッシュ)
      if (!navigator.onLine || error.name === 'TypeError') {
         cacheSyncPayload(storageKey, payload); // 差分ペイロードをキャッシュ
         return {
           success: true, // ローカル比較は完了
           offline: true,
           message: 'オフラインのため、差分データをキャッシュしました。オンライン時に同期します。',
           newHighlightsCount: newHighlights.length,
           isNewBook: isNewBook
         };
      }
      return { success: false, message: `APIエラー: ${response.status} ${errorText}` };
    }

    const data = await response.json();
    console.log('Booklight AI: 差分同期API応答', data);

    // 同期成功：ローカルの同期ステータスを更新
    const currentTimestamp = new Date().toISOString();
    // 今回同期したハイライトIDも既存のIDセットに追加
    const updatedSyncedIds = new Set([...syncedHighlightIds, ...newHighlights.map(generateHighlightId).filter(id => id)]);
    await saveBookSyncStatus(storageKey, currentTimestamp, updatedSyncedIds);

    return {
      success: true,
      message: data.message || `${newHighlights.length}件の新規ハイライトを同期しました`,
      newHighlightsCount: newHighlights.length,
      isNewBook: isNewBook
    };

  } catch (error) {
    console.error(`Booklight AI: 書籍「${book_title}」の同期処理中にエラーが発生しました`, error);
    // オフライン判定とキャッシュ処理
     if (!navigator.onLine || error.name === 'TypeError') {
        // ペイロードが生成されていればキャッシュ
        if (payload) {
            cacheSyncPayload(storageKey, payload);
            return {
                success: true, // ローカル比較は完了
                offline: true,
                message: 'オフラインのため、差分データをキャッシュしました。オンライン時に同期します。',
                newHighlightsCount: payload.highlights.length,
                isNewBook: payload.book.is_new
            };
        } else {
             return { success: false, offline: true, message: `オフラインエラー: ${error.message}` };
        }
     }
    return { success: false, message: `同期エラー: ${error.message}` };
  }
}

// --- オフラインキャッシュ処理の修正 ---
let pendingSyncPayloads = {}; // API送信用キャッシュ { storageKey: payload }

// 差分ペイロードをキャッシュに追加
async function cacheSyncPayload(storageKey, payload) {
  pendingSyncPayloads[storageKey] = payload;
  await chrome.storage.local.set({ 'pendingSyncPayloads': pendingSyncPayloads });
  console.log(`Booklight AI: 差分同期ペイロードをキャッシュに保存しました (Key: ${storageKey})`, Object.keys(pendingSyncPayloads).length);
}

// キャッシュされた差分ペイロードを送信
async function sendCachedSyncPayloads() {
  if (Object.keys(pendingSyncPayloads).length === 0 || isOffline()) {
    return;
  }

  console.log('Booklight AI: キャッシュされた差分同期ペイロードを送信します', Object.keys(pendingSyncPayloads).length);

  const keysToSend = Object.keys(pendingSyncPayloads);
  let allSuccess = true;

  for (const storageKey of keysToSend) {
    const payload = pendingSyncPayloads[storageKey];
    console.log(`Booklight AI: キャッシュされたペイロードを送信中 (Key: ${storageKey})`);

    // API送信のみを行うヘルパー関数 (syncBookDataからAPI送信部分を流用)
    const result = await sendSyncPayloadToAPIOnly(payload); // 仮の関数名

    if (result.success) {
      // 送信成功したらキャッシュから削除
      delete pendingSyncPayloads[storageKey];
      console.log(`Booklight AI: キャッシュされたペイロードの送信成功 (Key: ${storageKey})`);

      // ローカルの同期ステータスも更新する必要がある
      const currentTimestamp = new Date().toISOString();
      const previousStatus = await getBookSyncStatus(storageKey);
      const syncedIds = previousStatus?.syncedHighlightIds || new Set();
      const newHighlightIds = payload.highlights.map(generateHighlightId).filter(id => id);
      const updatedSyncedIds = new Set([...syncedIds, ...newHighlightIds]);
      await saveBookSyncStatus(storageKey, currentTimestamp, updatedSyncedIds);

    } else {
      console.error(`Booklight AI: キャッシュされたペイロードの送信に失敗 (Key: ${storageKey})`, result.message);
      allSuccess = false;
      // 失敗した場合はキャッシュに残しておく（リトライのため）
      // 永続的なエラーの場合は削除するロジックも必要かもしれない
    }
  }

  // キャッシュの状態をストレージに保存
  await chrome.storage.local.set({ 'pendingSyncPayloads': pendingSyncPayloads });

  if (allSuccess && keysToSend.length > 0) {
      console.log('Booklight AI: キャッシュされたペイロードの送信が完了しました');
  } else if (!allSuccess) {
      console.warn('Booklight AI: 一部のキャッシュされたペイロードの送信に失敗しました');
  }
}

// 差分ペイロードをAPIに送信するヘルパー関数
async function sendSyncPayloadToAPIOnly(payload) {
    try {
        console.log('Booklight AI: APIに差分ペイロードのみ送信します', payload);
        const isTokenValid = await validateToken();
        if (!isTokenValid) return { success: false, message: '認証トークンが無効です' };
        const authData = await chrome.storage.local.get(['authToken']);
        if (!authData.authToken) return { success: false, message: 'ログインが必要です' };

        const response = await fetch(SYNC_API_ENDPOINT, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authData.authToken}`
          },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          const errorText = await response.text();
          if (response.status === 401) await chrome.storage.local.remove(['authToken', 'authTime']);
          throw new Error(`APIエラー: ${response.status} ${errorText}`);
        }
        const data = await response.json();
        return { success: true, message: data.message };
     } catch (error) {
        console.error('Booklight AI: 差分ペイロードAPI送信エラー', error);
        return { success: false, message: `API送信エラー: ${error.message}` };
    }
}

// --- 一括取得関連関数 ---

/**
 * 進捗状況をpopup.jsに通知する関数
 * @param {number} processed - 処理済み書籍数
 * @param {number} total - 全書籍数
 * @param {string} message - 表示メッセージ
 */
function notifyProgress(processed, total, message) {
  console.log(`Booklight AI: Progress - ${processed}/${total} - ${message}`);
  // popup.jsに進捗を送信
  chrome.runtime.sendMessage({
    action: 'updateProgress',
    processed: processed,
    total: total,
    message: message
  }).catch(error => {
    // ポップアップが閉じている場合などにエラーが発生する可能性がある
    if (error.message.includes("Could not establish connection") || error.message.includes("Receiving end does not exist")) {
      console.warn("Booklight AI: ポップアップへの進捗通知に失敗しました (ポップアップが閉じている可能性があります)");
    } else {
      console.error("Booklight AI: ポップアップへの進捗通知中に予期せぬエラーが発生しました", error);
    }
  });
}

/**
 * 一括取得完了処理
 */
async function completeCollection(status, message) {
  console.log(`Booklight AI: 一括取得完了 (${status}) - ${message}`);
  const totalCount = (allCollectedData && Object.keys(allCollectedData).length) || 0; // 処理済み件数を取得
  const initialTotal = totalCount + bookQueue.length; // 完了時点での合計数 (キューは空のはず)

  notifyProgress(totalCount, initialTotal, message); // 最終ステータスを通知

  // 状態をリセット
  isCollectingAll = false;
  bookQueue = [];
  allCollectedData = {};

  // 元のタブURLに戻す
  if (currentCollectionTabId && originalTabUrl) {
    try {
      await chrome.tabs.update(currentCollectionTabId, { url: originalTabUrl });
      console.log(`Booklight AI: タブ ${currentCollectionTabId} を元のURLに戻しました: ${originalTabUrl}`);
    } catch (error) {
      console.warn(`Booklight AI: タブを元のURLに戻せませんでした (ID: ${currentCollectionTabId})`, error);
    }
  }
  currentCollectionTabId = null;
  originalTabUrl = null;
}

/**
 * ページの読み込み完了を待つヘルパー関数
 * @param {number} tabId - 待機するタブのID
 * @param {number} timeout - タイムアウト時間 (ミリ秒)
 * @returns {Promise<void>} - 読み込み完了時に解決されるPromise
 */
async function waitForTabLoad(tabId, timeout = 30000) { // タイムアウトを30秒に設定
  return new Promise((resolve, reject) => {
    const listener = (updatedTabId, changeInfo, tab) => {
      // 目的のタブIDで、ステータスが 'complete' になったらリスナーを解除して解決
      if (updatedTabId === tabId && changeInfo.status === 'complete') {
        // さらに少し待機して、動的コンテンツの読み込みを考慮 (オプション)
        setTimeout(() => {
          chrome.tabs.onUpdated.removeListener(listener);
          clearTimeout(timer); // タイムアウトをクリア
          console.log(`Booklight AI: タブ ${tabId} の読み込み完了`);
          resolve();
        }, 500); // 0.5秒待機
      }
    };

    // タイムアウト処理
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      console.error(`Booklight AI: タブ ${tabId} の読み込みがタイムアウトしました (${timeout}ms)`);
      reject(new Error(`Tab ${tabId} loading timed out after ${timeout}ms`));
    }, timeout);

    // リスナーを登録
    chrome.tabs.onUpdated.addListener(listener);

    // タブが既に読み込み完了しているかチェック (稀なケースだが念のため)
    chrome.tabs.get(tabId, (tab) => {
      if (chrome.runtime.lastError) {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        reject(new Error(`Failed to get tab ${tabId}: ${chrome.runtime.lastError.message}`));
      } else if (tab && tab.status === 'complete') {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        console.log(`Booklight AI: タブ ${tabId} は既に読み込み完了していました`);
        resolve();
      }
    });
  });
}


/**
 * 書籍キューを処理する関数 (コアロジック実装)
 */
async function processBookQueue() {
  // キャンセルされたかチェック
  if (!isCollectingAll) {
    console.log('Booklight AI: processBookQueue - 処理がキャンセルされました');
    return;
  }

  // キューが空かチェック
  if (bookQueue.length === 0) {
    console.log('Booklight AI: processBookQueue - キューが空になりました');
    await completeCollection('success', '全書籍のハイライト取得が完了しました');
    return;
  }

  // キューから次の書籍を取り出す
  const nextBook = bookQueue.shift();
  const totalBooks = (allCollectedData ? Object.keys(allCollectedData).length : 0) + bookQueue.length + 1;
  const processedCount = totalBooks - bookQueue.length - 1;

  console.log(`Booklight AI: 次の書籍を処理: ${processedCount + 1}/${totalBooks} - ${nextBook.title}`);
  notifyProgress(processedCount, totalBooks, `書籍「${nextBook.title}」のページに移動中...`);

  if (!currentCollectionTabId) {
    console.error('Booklight AI: 処理中のタブIDがありません。処理を中断します。');
    await completeCollection('error', '処理タブが見つからず中断しました');
    return;
  }

  try {
    // タブを指定された書籍のURLに遷移させる
    console.log(`Booklight AI: タブ ${currentCollectionTabId} を ${nextBook.url} に更新します`);
    await chrome.tabs.update(currentCollectionTabId, { url: nextBook.url });

    // ページの読み込み完了を待つ
    console.log(`Booklight AI: タブ ${currentCollectionTabId} の読み込みを待機中...`);
    notifyProgress(processedCount, totalBooks, `書籍「${nextBook.title}」のページを読み込み中...`);
    await waitForTabLoad(currentCollectionTabId); // タイムアウトはデフォルトの30秒

    // content.jsにデータ抽出を依頼
    console.log(`Booklight AI: タブ ${currentCollectionTabId} にデータ抽出を依頼します`);
    notifyProgress(processedCount, totalBooks, `書籍「${nextBook.title}」のハイライトを抽出中...`);
    const extractResponse = await chrome.tabs.sendMessage(currentCollectionTabId, { action: 'extractCurrentBookData' });

    // 抽出データを処理
    if (extractResponse && extractResponse.success && extractResponse.data) {
      console.log(`Booklight AI: 書籍「${nextBook.title}」のデータ抽出成功`);
      allCollectedData[nextBook.bookId] = extractResponse.data; // 収集データに追加

      // 個別同期処理を実行
      notifyProgress(processedCount + 1, totalBooks, `書籍「${nextBook.title}」を同期中...`);
      const syncResult = await syncBookData(extractResponse.data);
      console.log(`Booklight AI: 書籍「${nextBook.title}」同期結果:`, syncResult);

      // CSVエクスポート用データも保存
      await saveDataForCsvExport(extractResponse.data);

      notifyProgress(processedCount + 1, totalBooks, `書籍「${nextBook.title}」処理完了`);
    } else {
      console.warn(`Booklight AI: 書籍「${nextBook.title}」のデータ抽出に失敗: ${extractResponse?.message}`);
      notifyProgress(processedCount + 1, totalBooks, `書籍「${nextBook.title}」の抽出失敗`);
      // エラーがあっても続行する（次の書籍へ）
    }

    // 次の書籍の処理をスケジュール (少し間隔を空ける)
    if (isCollectingAll) {
      setTimeout(processBookQueue, 1500); // 1.5秒後に次の処理へ (API負荷軽減のため少し長めに)
    }

  } catch (error) {
    console.error(`Booklight AI: 書籍「${nextBook.title}」の処理中にエラーが発生しました`, error);
    notifyProgress(processedCount + 1, totalBooks, `書籍「${nextBook.title}」処理中にエラー: ${error.message}`);
    // エラーが発生しても次の書籍の処理に進む
    if (isCollectingAll) {
      setTimeout(processBookQueue, 1500); // 1.5秒後に次の処理へ
    }
  }
}

/**
 * 一括取得処理をキャンセルする関数
 * @returns {Promise<object>} - キャンセル結果 { success, message }
 */
async function cancelCollectAllHighlights() {
  if (!isCollectingAll) {
    console.log('Booklight AI: 一括取得処理は実行されていません');
    return { success: false, message: '一括取得処理は実行されていません' };
  }

  console.log('Booklight AI: 一括取得処理をキャンセルします');
  
  // 処理フラグをオフに
  isCollectingAll = false;
  
  // キューをクリア
  bookQueue = [];
  
  // 元のタブURLに戻す処理
  if (currentCollectionTabId && originalTabUrl) {
    try {
      await chrome.tabs.update(currentCollectionTabId, { url: originalTabUrl });
      console.log(`Booklight AI: タブ ${currentCollectionTabId} を元のURLに戻しました: ${originalTabUrl}`);
    } catch (error) {
      console.warn(`Booklight AI: タブを元のURLに戻せませんでした (ID: ${currentCollectionTabId})`, error);
    }
  }
  
  // 状態をリセット
  currentCollectionTabId = null;
  originalTabUrl = null;
  allCollectedData = {};
  
  return { success: true, message: '一括取得処理をキャンセルしました' };
}

/**
 * 一括取得を開始する関数 (popup.jsから書籍リストとタブIDを受け取る)
 * @param {Array<object>} books - 書籍情報のリスト [{ title, author, url, bookId }]
 * @param {number|null} tabId - 処理に使用するタブID（オプション）
 * @returns {Promise<object>} - 処理開始結果 { success, message }
 */
async function startCollectingAllBooks(books, tabId = null) {
  if (isCollectingAll) {
    console.warn('Booklight AI: 一括取得処理が既に実行中です');
    return { success: false, message: '既に一括取得処理が実行中です' };
  }
  if (!Array.isArray(books) || books.length === 0) {
    console.error('Booklight AI: 一括取得のための書籍リストが無効です');
    return { success: false, message: '書籍リストが無効です' };
  }

  console.log(`Booklight AI: 一括取得を開始します。対象書籍数: ${books.length}`);

  // 初期化
  isCollectingAll = true;
  bookQueue = [...books]; // 受け取った書籍リストでキューを初期化
  allCollectedData = {}; // 収集データリセット
  currentCollectionTabId = null; // リセット
  originalTabUrl = null; // リセット

  // 現在のタブを取得して保存し、処理を開始
  try {
    // 渡されたtabIdがあればそれを使用、なければクエリで取得
    if (tabId) {
      currentCollectionTabId = tabId;
      try {
        const tab = await chrome.tabs.get(tabId);
        originalTabUrl = tab.url; // 元のURLを保存
      } catch (e) {
        console.warn(`Booklight AI: 指定されたタブID ${tabId} の情報取得に失敗しました`, e);
        // タブIDは使用するが、URLは取得できなかった場合は null のまま
      }
    } else {
      // 従来の方法（フォールバック）
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs.length > 0) {
        currentCollectionTabId = tabs[0].id;
        originalTabUrl = tabs[0].url; // 元のURLを保存
      } else {
        // すべてのタブを取得して最初のタブを使用（最終手段）
        const allTabs = await chrome.tabs.query({ currentWindow: true });
        if (allTabs.length > 0) {
          currentCollectionTabId = allTabs[0].id;
          originalTabUrl = allTabs[0].url;
        } else {
          throw new Error('利用可能なタブが見つかりません');
        }
      }
    }

    console.log(`Booklight AI: 処理タブID: ${currentCollectionTabId}, 元のURL: ${originalTabUrl || '不明'}`);

    // 処理開始通知
    notifyProgress(0, bookQueue.length, '一括取得を開始します...');

    // 最初の書籍の処理を開始 (少し遅延させる)
    setTimeout(processBookQueue, 500); // 500ms後にキュー処理を開始

    return { success: true, message: '一括取得を開始しました' };
  } catch (error) {
    // tryブロック内で発生したエラーをキャッチ
    console.error('Booklight AI: 一括取得開始エラー', error);
    isCollectingAll = false; // 状態をリセット
    bookQueue = [];
    currentCollectionTabId = null;
    originalTabUrl = null;
    // エラーメッセージを返す
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
    const tokenExpiryTime = 25 * 60 * 1000; // 25分をミリ秒で表現

    // トークンが有効期限内かチェック
    if (tokenAge < tokenExpiryTime) {
      return true; // 有効期限内
    }

    // 有効期限切れの場合、リフレッシュを試みる
    console.log('Booklight AI: トークンの有効期限が切れています。リフレッシュを試みます。');
    const refreshSuccess = await refreshToken();
    return refreshSuccess;
  } catch (error) {
    console.error('Booklight AI: トークン検証エラー', error);
    return false;
  }
}

// オフライン状態を確認する関数
function isOffline() {
  return !navigator.onLine;
}

// メッセージリスナーの設定
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Booklight AI: メッセージを受信しました', request.action);
  
  // 認証状態の確認
  if (request.action === 'checkAuth') {
    checkAuthStatus().then(sendResponse);
    return true; // 非同期レスポンスを示す
  }
  
  // ログイン処理
  if (request.action === 'login') {
    authenticateWithGoogle().then(sendResponse);
    return true;
  }
  
  // ログアウト処理
  if (request.action === 'logout') {
    logoutUser().then(sendResponse);
    return true;
  }
  
  // 現在の書籍を同期
  if (request.action === 'syncCurrentBook') {
    syncCurrentBookHighlights().then(sendResponse);
    return true;
  }
  
  // 一括取得開始 (書籍リストとタブIDを受け取るように修正)
  if (request.action === 'collectAllHighlights') {
    if (!request.bookList) {
      sendResponse({ success: false, message: '書籍リストが提供されていません' });
      return false; // 同期応答
    }
    startCollectingAllBooks(request.bookList, request.tabId).then(sendResponse);
    return true; // 非同期応答
  }

  // 一括取得キャンセル
  if (request.action === 'cancelCollectAll') {
    cancelCollectAllHighlights().then(sendResponse);
    return true;
  }

  // 書籍の同期ステータスを取得
  if (request.action === 'getSyncStatus') {
    getSyncStatus(request.bookTitle, request.bookAuthor).then(sendResponse);
    return true;
  }

  // CSVエクスポート用データを取得
  else if (request.action === 'getCsvExportData') {
    console.log('Booklight AI: getCsvExportData アクションを受信');
    chrome.storage.local.get(CSV_EXPORT_KEY, (result) => {
      if (chrome.runtime.lastError) {
        console.error('Booklight AI: CSVエクスポートデータの取得エラー', chrome.runtime.lastError);
        sendResponse({ success: false, message: `ストレージ取得エラー: ${chrome.runtime.lastError.message}` });
      } else {
        sendResponse({ success: true, data: result[CSV_EXPORT_KEY] || {} }); // データがない場合は空オブジェクトを返す
      }
    });
    return true; // 非同期応答
  }

  // ダミーデータを取得 (コンテンツスクリプトからのリクエスト)
  else if (request.action === 'getDummyData') {
    console.log('Booklight AI: getDummyData アクションを受信');
    if (DEV_MODE && dummyData) {
      sendResponse({ success: true, data: dummyData });
    } else {
      sendResponse({ success: false, message: 'Dummy data not available or not in dev mode' });
    }
    return false; // 同期的に応答するのでfalse
  }
});

// 書籍の同期ステータスを取得する関数
async function getSyncStatus(bookTitle, bookAuthor) {
  try {
    console.log(`Booklight AI: 書籍「${bookTitle}」の同期ステータスを取得します`);
    
    if (!bookTitle || !bookAuthor) {
      return { 
        success: false, 
        message: '書籍タイトルまたは著者が指定されていません' 
      };
    }
    
    // ストレージキーを生成
    const storageKey = generateBookStorageKey(bookTitle, bookAuthor);
    
    // 同期ステータスを取得
    const syncStatus = await getBookSyncStatus(storageKey);
    
    if (syncStatus) {
      return {
        success: true,
        data: {
          lastSyncTimestamp: syncStatus.lastSyncTimestamp,
          syncedHighlightsCount: syncStatus.syncedHighlightIds.size
        }
      };
    } else {
      return {
        success: true,
        data: null, // 同期履歴なし
        message: '同期履歴がありません'
      };
    }
  } catch (error) {
    console.error('Booklight AI: 同期ステータス取得エラー', error);
    return {
      success: false,
      message: `同期ステータス取得エラー: ${error.message}`
    };
  }
}

// 認証状態を確認する関数
async function checkAuthStatus() {
  try {
    const authData = await chrome.storage.local.get(['authToken', 'userId', 'userName', 'userEmail', 'authTime']);
    
    if (authData.authToken) {
      // トークンの有効性を確認
      const isValid = await validateToken();
      
      if (isValid) {
        return {
          success: true,
          isAuthenticated: true,
          userId: authData.userId,
          userName: authData.userName,
          userEmail: authData.userEmail
        };
      } else {
        // トークンが無効な場合
        return {
          success: true,
          isAuthenticated: false,
          message: 'トークンが無効です'
        };
      }
    } else {
      // トークンがない場合
      return {
        success: true,
        isAuthenticated: false
      };
    }
  } catch (error) {
    console.error('Booklight AI: 認証状態確認エラー', error);
    return {
      success: false,
      message: `認証状態確認エラー: ${error.message}`
    };
  }
}

// ユーザーをログアウトする関数
async function logoutUser() {
  try {
    await chrome.storage.local.remove(['authToken', 'userId', 'userName', 'userEmail', 'authTime']);
    return {
      success: true,
      message: 'ログアウトしました'
    };
  } catch (error) {
    console.error('Booklight AI: ログアウトエラー', error);
    return {
      success: false,
      message: `ログアウトエラー: ${error.message}`
    };
  }
}

// 現在表示中の書籍のハイライトを同期する関数
async function syncCurrentBookHighlights() {
  try {
    // 現在のタブを取得
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs || tabs.length === 0) {
      return { success: false, message: 'アクティブなタブが見つかりません' };
    }
    
    const tabId = tabs[0].id;
    
    // コンテンツスクリプトに書籍データの抽出を依頼
    const extractResponse = await chrome.tabs.sendMessage(tabId, { action: 'extractCurrentBookData' });
    
    if (!extractResponse || !extractResponse.success) {
      return { 
        success: false, 
        message: extractResponse?.message || 'ハイライトデータの抽出に失敗しました' 
      };
    }

    // 抽出されたデータをCSVエクスポート用に保存
    await saveDataForCsvExport(extractResponse.data);
    
    // 抽出されたデータを同期
    const syncResult = await syncBookData(extractResponse.data);
    return syncResult;
    
  } catch (error) {
    console.error('Booklight AI: 現在の書籍の同期エラー', error);
    return {
      success: false,
      message: `同期エラー: ${error.message}`
    };
  }
}
