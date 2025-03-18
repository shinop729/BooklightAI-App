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
    // 現在のタブでコンテンツスクリプトを実行
    chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
      const currentTab = tabs[0];
      
      // Kindleページかどうかを確認（テストページも許可）
      if (!currentTab.url.includes('read.amazon') && !currentTab.url.includes('test-page.html')) {
        showStatus('error', 'Kindle Web Readerページを開いてください');
        return;
      }
      
      showStatus('info', 'ハイライトを収集中...');
      
      // コンテンツスクリプトにメッセージを送信
      chrome.tabs.sendMessage(currentTab.id, { action: 'collectHighlights' }, function(response) {
        if (chrome.runtime.lastError) {
          showStatus('error', 'ページとの通信に失敗しました: ' + chrome.runtime.lastError.message);
          return;
        }
        
        if (response && response.success) {
          // バックグラウンドスクリプトにハイライトを送信
          chrome.runtime.sendMessage(
            { action: 'sendHighlights', highlights: response.data.highlights },
            function(apiResponse) {
              if (apiResponse && apiResponse.success) {
                showStatus('success', apiResponse.message);
              } else {
                showStatus('error', apiResponse ? apiResponse.message : 'APIとの通信に失敗しました');
              }
            }
          );
        } else {
          showStatus('error', response ? response.message : 'ハイライトの収集に失敗しました');
        }
      });
    });
  });
  
  // ステータスメッセージの表示
  function showStatus(type, message) {
    statusDiv.className = 'status ' + type;
    statusDiv.textContent = message;
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
