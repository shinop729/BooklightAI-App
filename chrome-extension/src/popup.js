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
  
  // 認証状態の確認
  function checkAuthStatus() {
    chrome.runtime.sendMessage({ action: 'checkAuth' }, function(response) {
      if (response && response.success && response.isAuthenticated) {
        // ログイン済み
        loginSection.style.display = 'none';
        userSection.style.display = 'block';
        highlightsSection.style.display = 'block';
        userName.textContent = response.userName || 'ユーザー';
      } else {
        // 未ログイン
        loginSection.style.display = 'block';
        userSection.style.display = 'none';
        highlightsSection.style.display = 'none';
      }
    });
  }
  
  // 初期状態の確認
  checkAuthStatus();
  
  // ネットワーク状態の確認
  updateConnectionStatus();
  window.addEventListener('online', updateConnectionStatus);
  window.addEventListener('offline', updateConnectionStatus);
  
  // ログインボタン
  loginBtn.addEventListener('click', function() {
    showStatus('info', 'ログイン中...');
    chrome.runtime.sendMessage({ action: 'login' }, function(response) {
      if (response && response.success) {
        checkAuthStatus();
        showStatus('success', 'ログインしました');
      } else {
        showStatus('error', response ? response.message : 'ログインに失敗しました');
      }
    });
  });
  
  // ログアウトボタン
  logoutBtn.addEventListener('click', function() {
    chrome.runtime.sendMessage({ action: 'logout' }, function(response) {
      if (response && response.success) {
        checkAuthStatus();
        showStatus('info', 'ログアウトしました');
      } else {
        showStatus('error', 'ログアウトに失敗しました');
      }
    });
  });
  
  // ハイライト収集ボタン
  collectBtn.addEventListener('click', function() {
    // ボタンを無効化
    collectBtn.disabled = true;
    
    // 現在のタブでコンテンツスクリプトを実行
    chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
      const currentTab = tabs[0];
      
      // Kindleページかどうかを確認（テストページも許可）
      if (!currentTab.url.includes('read.amazon') && !currentTab.url.includes('test-page.html') && !currentTab.url.includes('file://')) {
        showStatus('error', 'Kindle Web Readerページを開いてください');
        collectBtn.disabled = false;
        return;
      }
      
      // 進捗表示
      showProgressMessage('ハイライトを収集中...', 20);
      
      // コンテンツスクリプトにメッセージを送信
      chrome.tabs.sendMessage(currentTab.id, { action: 'collectHighlights' }, function(response) {
        if (chrome.runtime.lastError) {
          showDetailedError('ページとの通信に失敗しました: ' + chrome.runtime.lastError.message);
          collectBtn.disabled = false;
          return;
        }
        
        if (!response) {
          showDetailedError('ページからの応答がありません。ページが正しく読み込まれているか確認してください。');
          collectBtn.disabled = false;
          return;
        }
        
        if (!response.success) {
          showDetailedError(response.message || 'ハイライトの収集に失敗しました');
          collectBtn.disabled = false;
          return;
        }
        
        // 進捗表示の更新
        showProgressMessage('ハイライトをサーバーに送信中...', 60);
        
        // バックグラウンドスクリプトにハイライトを送信
        chrome.runtime.sendMessage(
          { action: 'sendHighlights', highlights: response.data.highlights },
          function(apiResponse) {
            if (chrome.runtime.lastError) {
              showDetailedError('バックグラウンドスクリプトとの通信に失敗しました: ' + chrome.runtime.lastError.message);
              collectBtn.disabled = false;
              return;
            }
            
            if (!apiResponse) {
              showDetailedError('バックグラウンドスクリプトからの応答がありません');
              collectBtn.disabled = false;
              return;
            }
            
            if (apiResponse.success) {
              if (apiResponse.offline) {
                showStatus('warning', apiResponse.message || 'オフラインモードでハイライトを保存しました');
              } else {
                // 成功メッセージと総ハイライト数を表示
                const totalMessage = apiResponse.total_highlights ? 
                  `（合計: ${apiResponse.total_highlights}件）` : '';
                showStatus('success', `${apiResponse.message} ${totalMessage}`);
              }
            } else {
              showDetailedError(apiResponse.message || 'APIとの通信に失敗しました');
            }
            
            // ボタンを再度有効化
            collectBtn.disabled = false;
          }
        );
      });
    });
  });
  
  // ステータスメッセージの表示
  function showStatus(type, message) {
    statusDiv.className = 'status ' + type;
    statusDiv.textContent = message;
  }
  
  // 詳細なエラーメッセージの表示
  function showDetailedError(error) {
    // エラーの種類に応じた詳細メッセージを表示
    let detailedMessage = "エラーが発生しました。";
    let errorDetails = "";
    
    if (error.includes("401")) {
      detailedMessage = "認証エラー：アカウントに再ログインしてください。";
      errorDetails = "認証トークンが無効か期限切れです。ログアウトして再度ログインしてください。";
    } else if (error.includes("404")) {
      detailedMessage = "APIエンドポイントが見つかりません。";
      errorDetails = "サーバーが見つからないか、リクエストされたリソースが存在しません。開発者にお問い合わせください。";
    } else if (error.includes("500")) {
      detailedMessage = "サーバーエラー：しばらく時間をおいて再試行してください。";
      errorDetails = "サーバー内部でエラーが発生しました。問題が解決しない場合は、開発者にお問い合わせください。";
    } else if (error.includes("timeout")) {
      detailedMessage = "タイムアウト：サーバーの応答に時間がかかっています。";
      errorDetails = "サーバーからの応答がありませんでした。インターネット接続を確認し、しばらく時間をおいて再試行してください。";
    } else if (error.includes("network")) {
      detailedMessage = "ネットワーク接続を確認してください。";
      errorDetails = "インターネット接続に問題があります。Wi-Fi接続を確認し、再試行してください。";
    } else {
      detailedMessage = "予期しないエラーが発生しました。";
      errorDetails = error;
    }
    
    // ステータスメッセージを表示
    showStatus('error', detailedMessage);
    
    // 詳細なエラーメッセージを表示
    const errorDetailsElement = document.getElementById('errorDetails');
    errorDetailsElement.textContent = errorDetails;
    errorDetailsElement.style.display = 'block';
    
    // 3秒後に詳細メッセージを非表示にする
    setTimeout(() => {
      errorDetailsElement.style.display = 'none';
    }, 10000);
  }
  
  // 進捗表示付きのメッセージ
  function showProgressMessage(message, progress) {
    statusDiv.className = 'status info';
    
    // 進捗バーHTML
    const progressBarHtml = `
      <div class="progress-container">
        <div class="progress-bar" style="width: ${progress}%"></div>
      </div>
    `;
    
    statusDiv.innerHTML = `${message} ${progressBarHtml}`;
    
    // エラー詳細を非表示
    document.getElementById('errorDetails').style.display = 'none';
  }
  
  // トースト通知を表示
  function showToast(message, duration = 3000) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
      toast.classList.remove('show');
    }, duration);
  }
  
  // ネットワーク状態の更新
  function updateConnectionStatus() {
    if (navigator.onLine) {
      connectionStatus.className = 'status-indicator online';
      connectionStatus.querySelector('.status-text').textContent = 'オンライン';
    } else {
      connectionStatus.className = 'status-indicator offline';
      connectionStatus.querySelector('.status-text').textContent = 'オフライン';
    }
  }
});
