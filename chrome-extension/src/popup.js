document.addEventListener('DOMContentLoaded', function() {
  // UI要素
  const loginSection = document.getElementById('loginSection');
  const userSection = document.getElementById('userSection');
  const highlightsSection = document.getElementById('highlightsSection');
  const userName = document.getElementById('userName');
  const loginBtn = document.getElementById('loginBtn');
  const logoutBtn = document.getElementById('logoutBtn');
  const collectBtn = document.getElementById('collectBtn');
  const statusDiv = document.getElementById('status');
  const connectionStatus = document.getElementById('connectionStatus');
  const errorDetailsElement = document.getElementById('errorDetails'); // エラー詳細用
  const toastElement = document.getElementById('toast'); // トースト用
  const lastSyncTimeElement = document.getElementById('lastSyncTime'); // 最終同期日時表示用

  // --- 一括取得用UI要素 ---
  const collectAllBtn = document.getElementById('collectAllBtn');
  const collectAllProgress = document.getElementById('collectAllProgress');
  const collectAllProgressText = document.getElementById('collectAllProgressText');
  const collectAllProgressBar = document.getElementById('collectAllProgressBar');
  const cancelCollectAllBtn = document.getElementById('cancelCollectAllBtn');
  // --- 一括取得用UI要素ここまで ---

  let isCollecting = false; // 収集中のフラグ (単一・一括共通)

  // 認証状態と最終同期日時の確認
  function checkAuthAndSyncStatus() {
    chrome.runtime.sendMessage({ action: 'checkAuth' }, function(response) {
      if (chrome.runtime.lastError) {
        console.error("認証チェックエラー:", chrome.runtime.lastError.message);
        showStatus('error', '認証状態の確認に失敗しました');
        setUIState(false, false); // 未ログイン状態にする
        return;
      }
      if (response && response.success && response.isAuthenticated) {
        setUIState(true, false); // ログイン済み、収集中でない状態
        userName.textContent = response.userName || 'ユーザー';
        // ログイン済みの場合、現在の書籍の同期ステータスを取得
        displayCurrentBookSyncStatus();
      } else {
        setUIState(false, false); // 未ログイン状態
        if (lastSyncTimeElement) lastSyncTimeElement.textContent = 'N/A'; // 未ログイン時は表示しない
      }
    });
  }

  // 現在表示している書籍の最終同期日時を表示する関数
  function displayCurrentBookSyncStatus() {
    if (!lastSyncTimeElement) return; // 要素がなければ何もしない

    lastSyncTimeElement.textContent = '取得中...'; // 一時的に表示

    chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
      if (chrome.runtime.lastError || !tabs || tabs.length === 0) {
        lastSyncTimeElement.textContent = '取得失敗';
        return;
      }
      const tabId = tabs[0].id;

      // コンテンツスクリプトに書籍情報を要求 (タイトルと著者を取得するため)
      chrome.tabs.sendMessage(tabId, { action: 'extractCurrentBookData' }, function(bookResponse) {
        if (chrome.runtime.lastError || !bookResponse || !bookResponse.success || !bookResponse.data) {
          lastSyncTimeElement.textContent = '情報取得失敗';
          return;
        }

        const { book_title, author } = bookResponse.data;

        if (!book_title || !author) {
          lastSyncTimeElement.textContent = '書籍情報不足';
          return;
        }

        // バックグラウンドに同期ステータスを要求
        chrome.runtime.sendMessage(
          { action: 'getSyncStatus', bookTitle: book_title, bookAuthor: author },
          function(syncResponse) {
            if (chrome.runtime.lastError || !syncResponse || !syncResponse.success) {
              lastSyncTimeElement.textContent = 'ステータス取得失敗';
              return;
            }

            if (syncResponse.data && syncResponse.data.lastSyncTimestamp) {
              try {
                const date = new Date(syncResponse.data.lastSyncTimestamp);
                lastSyncTimeElement.textContent = date.toLocaleString('ja-JP');
              } catch (e) {
                lastSyncTimeElement.textContent = '日付形式エラー';
              }
            } else {
              lastSyncTimeElement.textContent = '未同期';
            }
          }
        );
      });
    });
  }

  // UIの状態を設定する関数
  function setUIState(loggedIn, collecting) {
    isCollecting = collecting;
    loginSection.style.display = loggedIn ? 'none' : 'block';
    userSection.style.display = loggedIn ? 'block' : 'none';
    highlightsSection.style.display = loggedIn ? 'block' : 'none';

    if (loggedIn) {
      collectBtn.disabled = collecting;
      collectAllBtn.disabled = collecting;
      collectAllProgress.style.display = collecting ? 'block' : 'none';
      cancelCollectAllBtn.style.display = collecting ? 'block' : 'none'; // キャンセルボタン表示
      if (!collecting) {
          // 収集中でなければ通常のステータス表示に戻す
          statusDiv.className = 'status';
          statusDiv.textContent = '';
          errorDetailsElement.style.display = 'none';
      }
    }
  }

  // 初期状態の確認
  checkAuthAndSyncStatus(); // 認証と同期ステータスをチェック

  // ネットワーク状態の確認
  updateConnectionStatus();
  window.addEventListener('online', updateConnectionStatus);
  window.addEventListener('offline', updateConnectionStatus);

  // ログインボタン
  loginBtn.addEventListener('click', function() {
    console.log("Booklight AI: Login button clicked"); // Log
    showStatus('info', 'ログイン中...');
    chrome.runtime.sendMessage({ action: 'login' }, function(response) {
      console.log("Booklight AI: Login response received", response); // Log
      if (chrome.runtime.lastError) {
        console.error("Booklight AI: Login error", chrome.runtime.lastError); // Log error
        showStatus('error', `ログインエラー: ${chrome.runtime.lastError.message}`);
        return;
      }
      if (response && response.success) {
        checkAuthAndSyncStatus(); // UI状態更新を含む (修正)
        showStatus('success', 'ログインしました');
      } else {
        showStatus('error', response ? response.message : 'ログインに失敗しました');
      }
    });
  });

  // ログアウトボタン
  logoutBtn.addEventListener('click', function() {
    console.log("Booklight AI: Logout button clicked"); // Log
    chrome.runtime.sendMessage({ action: 'logout' }, function(response) {
      console.log("Booklight AI: Logout response received", response); // Log
      if (chrome.runtime.lastError) {
        console.error("Booklight AI: Logout error", chrome.runtime.lastError); // Log error
        showStatus('error', `ログアウトエラー: ${chrome.runtime.lastError.message}`);
        return;
      }
      if (response && response.success) {
        checkAuthAndSyncStatus(); // UI状態更新を含む (修正)
        showStatus('info', 'ログアウトしました');
      } else {
        showStatus('error', 'ログアウトに失敗しました');
      }
    });
  });

  // 表示中の書籍を同期ボタン
  collectBtn.addEventListener('click', function() {
    console.log("Booklight AI: Sync Current Book button clicked");
    setUIState(true, true); // 同期開始状態
    showStatus('info', '現在の書籍を同期中...');
    errorDetailsElement.style.display = 'none';
    if (lastSyncTimeElement) lastSyncTimeElement.textContent = '同期中...';

    // バックグラウンドに同期開始を依頼
    // バックグラウンド側でタブ特定、コンテンツスクリプトへの抽出依頼、差分同期を行う
    chrome.runtime.sendMessage({ action: 'syncCurrentBook' }, function(response) {
      console.log("Booklight AI: 'syncCurrentBook' response from background script", response);
      if (chrome.runtime.lastError) {
        console.error("Booklight AI: Error receiving response from background script", chrome.runtime.lastError);
        showDetailedError('バックグラウンドとの通信に失敗しました: ' + chrome.runtime.lastError.message);
      } else if (!response) {
        console.error("Booklight AI: No response from background script for syncCurrentBook");
        showDetailedError('バックグラウンドスクリプトからの応答がありません');
      } else if (response.success) {
        let message = response.message || '同期が完了しました';
        if (response.newHighlightsCount !== undefined) {
            message = `${response.newHighlightsCount}件の新規ハイライトを同期しました。`;
            if (response.isNewBook) {
                message = `新規書籍として同期しました (${response.newHighlightsCount}件のハイライト)`;
            }
        }
        if (response.offline) {
          showStatus('warning', message + ' (オフライン)');
        } else {
          showStatus('success', message);
        }
        // 同期成功後、最終同期日時を再表示
        displayCurrentBookSyncStatus();
      } else {
        showDetailedError(response.message || '同期に失敗しました');
        // 失敗した場合も同期ステータスを更新してみる（エラー表示になるはず）
        displayCurrentBookSyncStatus();
      }
      setUIState(true, false); // 同期終了状態
    });
  });

  // --- 全書籍のハイライト取得ボタン（改良版）---
  collectAllBtn.addEventListener('click', function() {
    console.log("Booklight AI: Collect All button clicked");
    
    // UI状態の更新
    setUIState(true, true); // 収集開始状態
    collectAllProgressText.textContent = '書籍リストを取得中...';
    collectAllProgressBar.style.width = '0%';
    collectAllProgress.style.display = 'block';
    errorDetailsElement.style.display = 'none';
    statusDiv.className = 'status info';
    statusDiv.textContent = '全書籍のハイライト取得を開始しました...';
    
    // 現在のタブ情報を取得
    chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
        if (chrome.runtime.lastError || !tabs || tabs.length === 0) {
            showDetailedError('現在のタブ情報の取得に失敗しました: ' + (chrome.runtime.lastError?.message || 'タブが見つかりません'));
            setUIState(true, false);
            return;
        }
        
        const currentTab = tabs[0];
        
        // Kindleノートブックページかどうかを確認
        if (!currentTab.url || !currentTab.url.includes('read.amazon.co.jp/notebook')) {
            showStatus('error', 'Kindleノートブックページ (read.amazon.co.jp/notebook) を開いてください');
            setUIState(true, false);
            return;
        }
        
        // content.js に書籍リスト取得を依頼
        console.log("Booklight AI: Sending 'getBookList' message to content script");
        chrome.tabs.sendMessage(currentTab.id, { action: 'getBookList' }, function(bookListResponse) {
            if (chrome.runtime.lastError) {
                showDetailedError('コンテンツスクリプトとの通信に失敗: ' + chrome.runtime.lastError.message);
                setUIState(true, false);
                return;
            }
            
            if (!bookListResponse || !bookListResponse.success || !bookListResponse.data || bookListResponse.data.length === 0) {
                showStatus('error', bookListResponse?.message || '書籍リストの取得に失敗しました。Kindleノートブックページを確認してください。');
                setUIState(true, false);
                return;
            }
            
            const bookList = bookListResponse.data;
            console.log(`Booklight AI: Received ${bookList.length} books from content script`);
            
            // 書籍リストを添えて一括取得処理を開始
            startCollection(bookList);
        });
    });
    
    // 一括取得処理を開始する関数 (書籍リストを受け取るように変更)
    function startCollection(bookList) {
        // 進捗表示の初期化 (書籍数を反映)
        updateProgressUI(0, bookList.length, 'バックグラウンド処理を開始中...');
        
        // 現在のタブIDを取得して一緒に送信
        chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
            const currentTabId = tabs.length > 0 ? tabs[0].id : null;
            
            // バックグラウンドに一括取得開始を依頼 (書籍リストとタブIDを渡す)
            console.log("Booklight AI: Sending 'collectAllHighlights' message to background script with book list");
            chrome.runtime.sendMessage({ 
                action: 'collectAllHighlights', 
                bookList: bookList,
                tabId: currentTabId // タブIDを追加
            }, function(response) {
                console.log("Booklight AI: 'collectAllHighlights' initial response:", response);
                
                // エラー処理 (変更なし)
                if (chrome.runtime.lastError) {
                    console.error("Booklight AI: Error sending message:", chrome.runtime.lastError);
                    showDetailedError('バックグラウンドとの通信に失敗: ' + chrome.runtime.lastError.message);
                    setUIState(true, false);
                    return;
                }
                
                // 処理開始エラー（既に実行中など）
                if (response && !response.success) {
                    showStatus('warning', response.message || '一括取得の開始に失敗しました');
                    setUIState(true, false);
                }
                
                // 成功した場合は、進捗は別途 updateProgress メッセージで受信
                console.log("Booklight AI: collectAllHighlights メッセージ送信完了");
            });
        });
    }
    
    // 進捗表示を更新する関数
    function updateProgressUI(processed, total, message) {
        collectAllProgressText.textContent = message || `処理中: ${processed}/${total}`;
        const percentage = total > 0 ? Math.round((processed / total) * 100) : 0;
        collectAllProgressBar.style.width = `${percentage}%`;
        
        // ステータス表示も更新
        if (message.includes('エラー') || message.includes('失敗')) {
            showStatus('error', message);
        } else if (message.includes('完了')) {
            showStatus('success', message);
        } else {
            showStatus('info', message);
        }
    }
  });

  // --- キャンセルボタン（改良版）---
  cancelCollectAllBtn.addEventListener('click', function() {
      console.log("Booklight AI: Cancel button clicked");
      showStatus('warning', '一括取得をキャンセル中...');
      cancelCollectAllBtn.disabled = true; // キャンセルボタンを無効化

      console.log("Booklight AI: Sending 'cancelCollectAll' message to background script");
      chrome.runtime.sendMessage({ action: 'cancelCollectAll' }, function(response) {
          console.log("Booklight AI: 'cancelCollectAll' response:", response);
          
          // ボタンを再度有効化
          cancelCollectAllBtn.disabled = false; 
          
          if (chrome.runtime.lastError) {
              console.error("Booklight AI: Error sending message:", chrome.runtime.lastError);
              showDetailedError('キャンセル処理の通信に失敗: ' + chrome.runtime.lastError.message);
              // UI状態は変更せず、エラーを表示
              return;
          }
          
          if (response && response.success) {
              showStatus('info', response.message || '一括取得をキャンセルしました。');
              setUIState(true, false); // 収集終了状態に戻す
          } else {
              showStatus('error', response ? response.message : 'キャンセルに失敗しました');
              // UI状態は変更せず、エラーを表示
          }
      });
  });

  // --- バックグラウンドからの進捗更新メッセージをリッスン（改良版）---
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'updateProgress') {
      console.log("Booklight AI: Progress update received:", request);
      
      // 収集中の場合のみUIを更新
      if (isCollecting) {
        const { processed, total, message } = request;
        
        // 進捗バーとテキストを更新
        collectAllProgressText.textContent = message || `処理中: ${processed}/${total}`;
        const percentage = total > 0 ? Math.round((processed / total) * 100) : 0;
        collectAllProgressBar.style.width = `${percentage}%`;

        // 完了、エラー、キャンセルのメッセージを判定
        const isError = message.includes('エラー') || message.includes('失敗') || message.includes('タイムアウト');
        const isCancelled = message.includes('キャンセル');
        const isComplete = message.includes('完了');

        // ステータス表示を更新
        if (isError) {
            showStatus('error', message);
            setUIState(true, false); // エラー時は収集終了
        } else if (isCancelled) {
            showStatus('warning', message);
            setUIState(true, false); // キャンセル時は収集終了
        } else if (isComplete) {
            showStatus('success', message);
            setUIState(true, false); // 完了時は収集終了
        } else {
            // 処理中のメッセージ
            showStatus('info', message);
        }
      }
    }
    // 他のメッセージタイプもここで処理可能
  });


  // ステータスメッセージの表示
  function showStatus(type, message) {
    statusDiv.className = 'status ' + type;
    statusDiv.textContent = message;
    // エラーでない場合は詳細を隠す
    if (type !== 'error') {
        errorDetailsElement.style.display = 'none';
    }
    // 収集中でなければ進捗表示も隠す
    if (!isCollecting) {
        collectAllProgress.style.display = 'none';
    }
  }

  // 詳細なエラーメッセージの表示
  function showDetailedError(error) {
    let detailedMessage = "エラーが発生しました。";
    let errorDetails = typeof error === 'string' ? error : JSON.stringify(error); // エラー内容を文字列化

    // 特定のエラーパターンに基づいてメッセージを改善
    if (errorDetails.includes("401")) {
      detailedMessage = "認証エラー：アカウントに再ログインしてください。";
    } else if (errorDetails.includes("404")) {
      detailedMessage = "APIエンドポイントが見つかりません。";
    } else if (errorDetails.includes("500")) {
      detailedMessage = "サーバーエラー：しばらく時間をおいて再試行してください。";
    } else if (errorDetails.includes("timeout") || errorDetails.includes("timed out")) {
      detailedMessage = "タイムアウト：処理に時間がかかりすぎました。";
    } else if (errorDetails.includes("network") || errorDetails.includes("Failed to fetch")) {
      detailedMessage = "ネットワーク接続を確認してください。";
    } else if (errorDetails.includes("No tab with id") || errorDetails.includes("Cannot access contents of url")) {
        detailedMessage = "ページとの通信エラー。ページを再読み込みするか、Kindleページを開き直してください。";
    } else if (errorDetails.includes("getBookLinks is not defined") || errorDetails.includes("extractCurrentBookData is not defined")) {
        detailedMessage = "拡張機能エラー。拡張機能を更新または再インストールしてください。";
    }

    showStatus('error', detailedMessage);

    errorDetailsElement.textContent = errorDetails;
    errorDetailsElement.style.display = 'block';

    // 10秒後に詳細メッセージを非表示にする
    setTimeout(() => {
      if (errorDetailsElement.textContent === errorDetails) { // メッセージが変わっていなければ隠す
          errorDetailsElement.style.display = 'none';
      }
    }, 10000);
  }

  // トースト通知を表示 (既存のまま)
  function showToast(message, duration = 3000) {
    toastElement.textContent = message;
    toastElement.classList.add('show');
    setTimeout(() => {
      toastElement.classList.remove('show');
    }, duration);
  }

  // ネットワーク状態の更新 (既存のまま)
  function updateConnectionStatus() {
    if (navigator.onLine) {
      connectionStatus.className = 'status-indicator online';
      connectionStatus.querySelector('.status-text').textContent = 'オンライン';
    } else {
      connectionStatus.className = 'status-indicator offline';
      connectionStatus.querySelector('.status-text').textContent = 'オフライン';
      showStatus('warning', 'オフラインです。一部機能が制限される可能性があります。');
    }
  }

  // --- CSVダウンロード機能 ---
  const downloadCsvBtn = document.getElementById('downloadCsvBtn');

  if (downloadCsvBtn) {
    downloadCsvBtn.addEventListener('click', async function() {
      console.log("Booklight AI: Download CSV button clicked");
      showStatus('info', 'CSVデータを取得中...');
      downloadCsvBtn.disabled = true; // ボタンを無効化

      try {
        // バックグラウンドスクリプトにCSVエクスポート用データの取得を依頼
        const response = await new Promise((resolve, reject) => {
          chrome.runtime.sendMessage({ action: 'getCsvExportData' }, (res) => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else if (res && res.success) {
              resolve(res);
            } else {
              reject(new Error(res?.message || '全書籍データの取得に失敗しました'));
            }
          });
        });

        const allBookData = response.data;
        if (!allBookData || Object.keys(allBookData).length === 0) {
            throw new Error('ローカルストレージに書籍データが見つかりません');
        }

        // CSVデータを生成 (全書籍データを渡す)
        const csvData = convertToCSV(allBookData);

        // ファイル名を生成
        const filename = `booklight_all_highlights.csv`;

        // CSVファイルをダウンロード
        downloadCSV(csvData, filename);

        showStatus('success', 'CSVファイルをダウンロードしました');

      } catch (error) {
        console.error('Booklight AI: CSVダウンロードエラー', error);
        showDetailedError(`CSVダウンロードエラー: ${error.message}`);
      } finally {
        downloadCsvBtn.disabled = false; // ボタンを有効化
        // 必要に応じてステータス表示をクリア
        // setTimeout(() => showStatus('info', ''), 3000);
      }
    });
  }

  // 全書籍データをCSV形式に変換する関数
  function convertToCSV(allBookData) {
    const header = ['Book Title', 'Author', 'Cover Image URL', 'Highlight Content', 'Location', 'Highlight Timestamp'];

    // エスケープ処理関数 (変更なし)
    const escapeCSV = (field) => {
      if (field === null || field === undefined) {
        return '';
      }
      const stringField = String(field);
      // ダブルクォート、カンマ、改行が含まれる場合はダブルクォートで囲む
      if (stringField.includes('"') || stringField.includes(',') || stringField.includes('\n') || stringField.includes('\r')) {
        // ダブルクォートは二重にする
        const escapedField = stringField.replace(/"/g, '""');
        return `"${escapedField}"`;
      }
      return stringField;
    };

    // ヘッダー行 (変更なし)
    const csvRows = [header.map(escapeCSV).join(',')];

    // データ行 (全書籍データをループ)
    for (const bookId in allBookData) {
      const book = allBookData[bookId];
      if (book && book.title && book.author && Array.isArray(book.highlights)) {
        const { title, author, coverSrc, highlights } = book;
        highlights.forEach(h => {
          const row = [
            title,
            author,
            coverSrc || '', // カバー画像がない場合も考慮
            h.text, // ハイライトのキーを 'text' に合わせる (background.jsの実装に依存)
            h.location,
            h.timestamp || '' // タイムスタンプがない場合も考慮
          ];
          csvRows.push(row.map(escapeCSV).join(','));
        });
      }
    }

    // BOM付きUTF-8で返す
    return '\ufeff' + csvRows.join('\n');
  }

  // CSVデータをファイルとしてダウンロードする関数
  function downloadCSV(csvData, filename) {
    const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url); // 不要になったURLを解放
  }
  // --- CSVダウンロード機能ここまで ---

});
