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

  // --- 一括取得用UI要素 ---
  const collectAllBtn = document.getElementById('collectAllBtn');
  const collectAllProgress = document.getElementById('collectAllProgress');
  const collectAllProgressText = document.getElementById('collectAllProgressText');
  const collectAllProgressBar = document.getElementById('collectAllProgressBar');
  const cancelCollectAllBtn = document.getElementById('cancelCollectAllBtn');
  // --- 一括取得用UI要素ここまで ---

  let isCollecting = false; // 収集中のフラグ (単一・一括共通)

  // 認証状態の確認
  function checkAuthStatus() {
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
      } else {
        setUIState(false, false); // 未ログイン状態
      }
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
  checkAuthStatus();

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
        checkAuthStatus(); // UI状態更新を含む
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
        checkAuthStatus(); // UI状態更新を含む
        showStatus('info', 'ログアウトしました');
      } else {
        showStatus('error', 'ログアウトに失敗しました');
      }
    });
  });

  // 表示中のハイライト収集ボタン
  collectBtn.addEventListener('click', function() {
    console.log("Booklight AI: Collect button clicked"); // Log
    setUIState(true, true); // 収集開始状態
    showStatus('info', '表示中のハイライトを収集中...');
    errorDetailsElement.style.display = 'none'; // エラー詳細を隠す

    chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
      if (chrome.runtime.lastError || !tabs || tabs.length === 0) {
          showDetailedError('現在のタブ情報の取得に失敗しました: ' + (chrome.runtime.lastError?.message || 'タブが見つかりません'));
          setUIState(true, false); // 収集終了状態
          return;
      }
      const currentTab = tabs[0];

      if (!currentTab.url || (!currentTab.url.includes('read.amazon') && !currentTab.url.includes('test-page.html') && !currentTab.url.includes('file://'))) {
        showStatus('error', 'Kindle Web Readerページを開いてください');
        setUIState(true, false); // 収集終了状態
        return;
      }

      // コンテンツスクリプトにメッセージを送信
      console.log("Booklight AI: Sending 'collectHighlights' message to content script"); // Log
      chrome.tabs.sendMessage(currentTab.id, { action: 'collectHighlights' }, function(response) {
        console.log("Booklight AI: 'collectHighlights' response from content script", response); // Log
        if (chrome.runtime.lastError) {
          console.error("Booklight AI: Error sending message to content script", chrome.runtime.lastError); // Log error
          showDetailedError('ページとの通信に失敗しました: ' + chrome.runtime.lastError.message);
          setUIState(true, false);
          return;
        }
        if (!response) {
          showDetailedError('ページからの応答がありません。ページが正しく読み込まれているか確認してください。');
          setUIState(true, false);
          return;
        }
        if (!response.success) {
          showDetailedError(response.message || 'ハイライトの収集に失敗しました');
          setUIState(true, false);
          return;
        }
        if (!response.data || !response.data.highlights || response.data.highlights.length === 0) {
            showStatus('info', '表示中のページに収集対象のハイライトが見つかりませんでした。');
            setUIState(true, false);
            return;
        }

        showStatus('info', 'ハイライトをサーバーに送信中...');

        // バックグラウンドスクリプトにハイライトを送信
        console.log("Booklight AI: Sending 'sendHighlights' message to background script"); // Log
        chrome.runtime.sendMessage(
          { action: 'sendHighlights', highlights: response.data.highlights },
          function(apiResponse) {
            console.log("Booklight AI: 'sendHighlights' response from background script", apiResponse); // Log
            if (chrome.runtime.lastError) {
              console.error("Booklight AI: Error receiving response from background script", chrome.runtime.lastError); // Log error
              showDetailedError('バックグラウンドスクリプトとの通信に失敗しました: ' + chrome.runtime.lastError.message);
            } else if (!apiResponse) {
              console.error("Booklight AI: No response from background script for sendHighlights"); // Log error
              showDetailedError('バックグラウンドスクリプトからの応答がありません');
            } else if (apiResponse.success) {
              if (apiResponse.offline) {
                showStatus('warning', apiResponse.message || 'オフラインモードでハイライトを保存しました');
              } else {
                const totalMessage = apiResponse.total_highlights ? `（合計: ${apiResponse.total_highlights}件）` : '';
                showStatus('success', `${apiResponse.message || 'ハイライトを保存しました'} ${totalMessage}`);
              }
            } else {
              showDetailedError(apiResponse.message || 'APIとの通信に失敗しました');
            }
            setUIState(true, false); // 収集終了状態
          }
        );
      });
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
        
        // 一括取得処理の開始
        startCollection();
    });
    
    // 一括取得処理を開始する関数
    function startCollection() {
        // 進捗表示の初期化
        updateProgressUI(0, 100, '書籍リストを取得中...');
        
        // バックグラウンドに一括取得開始を依頼
        console.log("Booklight AI: Sending 'collectAllHighlights' message to background script");
        chrome.runtime.sendMessage({ action: 'collectAllHighlights' }, function(response) {
            console.log("Booklight AI: 'collectAllHighlights' initial response:", response);
            
            // エラー処理
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
});
