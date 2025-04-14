document.addEventListener('DOMContentLoaded', function() {
  // UI要素
  const loginSection = document.getElementById('loginSection');
  const userSection = document.getElementById('userSection');
  const highlightsSection = document.getElementById('highlightsSection');
  const userName = document.getElementById('userName');
  const loginBtn = document.getElementById('loginBtn');
  const logoutBtn = document.getElementById('logoutBtn');
  const collectBtn = document.getElementById('collectBtn'); // 現在の書籍同期ボタン
  const statusDiv = document.getElementById('status');
  const connectionStatus = document.getElementById('connectionStatus');
  const errorDetailsElement = document.getElementById('errorDetails'); // エラー詳細用
  const toastElement = document.getElementById('toast'); // トースト用
  const lastSyncTimeElement = document.getElementById('lastSyncTime'); // 最終同期日時表示用
  const downloadCsvBtn = document.getElementById('downloadCsvBtn'); // CSVダウンロードボタン

  // --- 書籍リスト同期用UI要素 ---
  const loadBookListBtn = document.getElementById('loadBookListBtn'); // 書籍リスト取得ボタン
  const bookListContainer = document.getElementById('bookListContainer'); // 書籍リストコンテナ
  const syncSelectedBtn = document.getElementById('syncSelectedBtn'); // 選択書籍同期ボタン
  // --- 書籍リスト同期用UI要素ここまで ---

  // --- 一括取得用UI要素 (進捗表示用) ---
  const collectAllProgress = document.getElementById('collectAllProgress');
  const collectAllProgressText = document.getElementById('collectAllProgressText');
  const collectAllProgressBar = document.getElementById('collectAllProgressBar');
  const cancelCollectAllBtn = document.getElementById('cancelCollectAllBtn');
  // --- 一括取得用UI要素ここまで ---

  let isCollecting = false; // 収集中のフラグ (単一・複数共通)
  let currentBookList = []; // 取得した書籍リストを保持

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
      // ページがKindleハイライトページでない可能性も考慮
      chrome.tabs.sendMessage(tabId, { action: 'extractCurrentBookData' }, function(bookResponse) {
        if (chrome.runtime.lastError) {
          // content scriptが注入されていないか、応答がない場合
          if (chrome.runtime.lastError.message?.includes("Receiving end does not exist")) {
            lastSyncTimeElement.textContent = 'N/A (非対象ページ)';
            console.warn("displayCurrentBookSyncStatus: コンテンツスクリプトが実行されていません。Kindleページを開いてください。");
          } else {
            lastSyncTimeElement.textContent = '通信エラー';
            console.error("displayCurrentBookSyncStatus: content script communication error:", chrome.runtime.lastError.message);
          }
          return;
        }
        if (!bookResponse || !bookResponse.success || !bookResponse.data) {
          lastSyncTimeElement.textContent = '情報取得失敗';
          return;
        }

        const { book_title, author } = bookResponse.data;

        if (!book_title || !author || book_title === '不明な書籍') {
          lastSyncTimeElement.textContent = '書籍情報なし';
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
      loadBookListBtn.disabled = collecting; // 書籍リスト取得ボタンも無効化
      syncSelectedBtn.disabled = collecting || currentBookList.length === 0; // 収集中またはリストが空なら無効
      cancelCollectAllBtn.style.display = collecting ? 'block' : 'none'; // キャンセルボタン表示/非表示
      collectAllProgress.style.display = collecting ? 'block' : 'none'; // 進捗表示/非表示

      if (!collecting) {
          // 収集中でなければ通常のステータス表示に戻す
          statusDiv.className = 'status';
          statusDiv.textContent = '';
          errorDetailsElement.style.display = 'none';
          // 進捗表示もリセット
          collectAllProgressText.textContent = '';
          collectAllProgressBar.style.width = '0%';
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
    console.log("Booklight AI: Login button clicked");
    showStatus('info', 'ログイン中...');
    chrome.runtime.sendMessage({ action: 'login' }, function(response) {
      console.log("Booklight AI: Login response received", response);
      if (chrome.runtime.lastError) {
        console.error("Booklight AI: Login error", chrome.runtime.lastError);
        showStatus('error', `ログインエラー: ${chrome.runtime.lastError.message}`);
        return;
      }
      if (response && response.success) {
        checkAuthAndSyncStatus();
        showStatus('success', 'ログインしました');
      } else {
        showStatus('error', response ? response.message : 'ログインに失敗しました');
      }
    });
  });

  // ログアウトボタン
  logoutBtn.addEventListener('click', function() {
    console.log("Booklight AI: Logout button clicked");
    chrome.runtime.sendMessage({ action: 'logout' }, function(response) {
      console.log("Booklight AI: Logout response received", response);
      if (chrome.runtime.lastError) {
        console.error("Booklight AI: Logout error", chrome.runtime.lastError);
        showStatus('error', `ログアウトエラー: ${chrome.runtime.lastError.message}`);
        return;
      }
      if (response && response.success) {
        checkAuthAndSyncStatus();
        showStatus('info', 'ログアウトしました');
        // ログアウトしたら書籍リストもクリア
        bookListContainer.innerHTML = '<p style="text-align: center; color: #888;">書籍リストを読み込んでください</p>';
        bookListContainer.style.display = 'none';
        syncSelectedBtn.style.display = 'none';
        currentBookList = [];
      } else {
        showStatus('error', 'ログアウトに失敗しました');
      }
    });
  });

  // 表示中の書籍を同期ボタン
  collectBtn.addEventListener('click', function() {
    console.log("Booklight AI: Sync Current Book button clicked");
    setUIState(true, true); // 同期開始状態 (isCollecting = true)
    showStatus('info', '現在の書籍を同期中...');
    errorDetailsElement.style.display = 'none';
    if (lastSyncTimeElement) lastSyncTimeElement.textContent = '同期中...';

    // バックグラウンドに同期開始を依頼
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
        // バックエンド差分検出の場合、newHighlightsCount は常に返る想定
        if (response.added_count !== undefined) {
            message = `${response.added_count}件の新規ハイライトを追加しました。`;
        }
        showStatus('success', message);
        // 同期成功後、最終同期日時を再表示
        displayCurrentBookSyncStatus();
      } else {
        showDetailedError(response.message || '同期に失敗しました');
        // 失敗した場合も同期ステータスを更新してみる
        displayCurrentBookSyncStatus();
      }
      setUIState(true, false); // 同期終了状態 (isCollecting = false)
    });
  });

  // --- ライブラリから書籍リストを取得ボタン ---
  loadBookListBtn.addEventListener('click', function() {
    console.log("Booklight AI: Load Book List button clicked");
    showStatus('info', '書籍リストを取得中...');
    bookListContainer.innerHTML = '<p style="text-align: center; color: #888;">読み込み中...</p>'; // 読み込み表示
    bookListContainer.style.display = 'block';
    syncSelectedBtn.style.display = 'none'; // 同期ボタンを隠す
    loadBookListBtn.disabled = true; // 取得中はボタン無効化

    chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
      if (chrome.runtime.lastError || !tabs || tabs.length === 0) {
        showDetailedError('現在のタブ情報の取得に失敗しました: ' + (chrome.runtime.lastError?.message || 'タブが見つかりません'));
        loadBookListBtn.disabled = false;
        bookListContainer.innerHTML = '<p style="text-align: center; color: red;">タブ情報の取得失敗</p>';
        return;
      }
      const currentTab = tabs[0];

      // Kindleノートブックページか確認
      if (!currentTab.url || !currentTab.url.includes('read.amazon.co.jp/notebook')) {
        showStatus('error', 'Kindleノートブックページ (read.amazon.co.jp/notebook) を開いてください');
        loadBookListBtn.disabled = false;
        bookListContainer.innerHTML = '<p style="text-align: center; color: red;">ノートブックページを開いてください</p>';
        return;
      }

      // content.js に書籍リスト取得を依頼
      console.log("Booklight AI: Sending 'getBookList' message to content script");
      chrome.tabs.sendMessage(currentTab.id, { action: 'getBookList' }, function(response) {
        loadBookListBtn.disabled = false; // ボタン有効化
        if (chrome.runtime.lastError) {
          showDetailedError('コンテンツスクリプトとの通信に失敗: ' + chrome.runtime.lastError.message);
          bookListContainer.innerHTML = '<p style="text-align: center; color: red;">通信エラー</p>';
          return;
        }

        if (response && response.success && response.data && response.data.length > 0) {
          currentBookList = response.data; // 取得したリストを保持
          console.log(`Booklight AI: Received ${currentBookList.length} books`);
          displayBookList(currentBookList); // リスト表示関数を呼び出す
          syncSelectedBtn.style.display = 'block'; // 同期ボタン表示
          showStatus('info', `${currentBookList.length}件の書籍が見つかりました。同期する書籍を選択してください。`);
          setUIState(true, false); // ★★★ 追加: 収集中でない状態に更新し、ボタンを有効化 ★★★
        } else {
          showStatus('error', response?.message || '書籍リストの取得に失敗しました。');
          bookListContainer.innerHTML = '<p style="text-align: center; color: red;">リスト取得失敗</p>';
        }
      });
    });
  });

  // --- 選択した書籍を同期ボタン ---
  syncSelectedBtn.addEventListener('click', function() {
    console.log("Booklight AI: Sync Selected button clicked");
    const selectedBooks = [];
    const checkboxes = bookListContainer.querySelectorAll('input[type="checkbox"]:checked');

    checkboxes.forEach(checkbox => {
      // 'selectAllBooks' チェックボックスは除外
      if (checkbox.id === 'selectAllBooks') return;

      const bookId = checkbox.value;
      const book = currentBookList.find(b => b.bookId === bookId);
      if (book) {
        selectedBooks.push(book);
      }
    });

    if (selectedBooks.length === 0) {
      showStatus('warning', '同期する書籍を選択してください。');
      return;
    }

    console.log(`Booklight AI: ${selectedBooks.length}件の書籍を選択して同期を開始します`);

    // UI状態の更新
    setUIState(true, true); // 収集開始状態
    updateProgressUI(0, selectedBooks.length, '選択された書籍の同期を開始中...'); // 進捗初期化
    collectAllProgress.style.display = 'block'; // 進捗表示
    errorDetailsElement.style.display = 'none';
    statusDiv.className = 'status info';
    statusDiv.textContent = '選択された書籍の同期を開始しました...';

    // バックグラウンドに処理を依頼
    chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
      const currentTabId = tabs.length > 0 ? tabs[0].id : null;
      console.log("Booklight AI: Sending 'collectAllHighlights' message to background script with selected books");
      chrome.runtime.sendMessage({
          action: 'collectAllHighlights',
          bookList: selectedBooks, // 選択された書籍リストを渡す
          tabId: currentTabId
      }, function(response) {
          console.log("Booklight AI: 'collectAllHighlights' initial response for selected:", response);
          if (chrome.runtime.lastError) {
              console.error("Booklight AI: Error sending message:", chrome.runtime.lastError);
              showDetailedError('バックグラウンドとの通信に失敗: ' + chrome.runtime.lastError.message);
              setUIState(true, false);
          } else if (response && !response.success) {
              showStatus('warning', response.message || '同期の開始に失敗しました');
              setUIState(true, false);
          }
          // 成功した場合、進捗は updateProgress で受信
      });
    });
  });

  // --- 書籍リストを表示する関数 ---
  function displayBookList(books) {
    bookListContainer.innerHTML = ''; // コンテナをクリア

    // 「すべて選択/解除」チェックボックス
    const selectAllContainer = document.createElement('div');
    selectAllContainer.style.marginBottom = '5px';
    selectAllContainer.style.borderBottom = '1px solid #eee';
    selectAllContainer.style.paddingBottom = '5px';

    const selectAllCheckbox = document.createElement('input');
    selectAllCheckbox.type = 'checkbox';
    selectAllCheckbox.id = 'selectAllBooks';
    selectAllCheckbox.style.marginRight = '5px';
    selectAllCheckbox.addEventListener('change', function() {
        bookListContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            if (cb.id !== 'selectAllBooks') { // 自分自身は除く
                cb.checked = selectAllCheckbox.checked;
            }
        });
    });

    const selectAllLabel = document.createElement('label');
    selectAllLabel.htmlFor = 'selectAllBooks';
    selectAllLabel.textContent = 'すべて選択/解除';
    selectAllLabel.style.fontWeight = 'bold';

    selectAllContainer.appendChild(selectAllCheckbox);
    selectAllContainer.appendChild(selectAllLabel);
    bookListContainer.appendChild(selectAllContainer);

    // 各書籍のチェックボックス
    books.forEach(book => {
      const div = document.createElement('div');
      div.style.marginBottom = '3px';
      div.style.fontSize = '12px';

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = book.bookId; // valueにbookIdを設定
      checkbox.id = `book-${book.bookId}`;
      checkbox.style.marginRight = '5px';
      // 個別チェックボックスの変更で「すべて選択」の状態を更新
      checkbox.addEventListener('change', function() {
          const allCheckboxes = bookListContainer.querySelectorAll('input[type="checkbox"]:not(#selectAllBooks)');
          const allChecked = Array.from(allCheckboxes).every(cb => cb.checked);
          selectAllCheckbox.checked = allChecked;
          const someChecked = Array.from(allCheckboxes).some(cb => cb.checked);
          // 部分選択状態（indeterminate）を設定
          selectAllCheckbox.indeterminate = !allChecked && someChecked;
      });

      const label = document.createElement('label');
      label.htmlFor = `book-${book.bookId}`;
      label.textContent = `${book.title} (${book.author})`;
      label.title = `ID: ${book.bookId}`; // ツールチップでID表示

      div.appendChild(checkbox);
      div.appendChild(label);
      bookListContainer.appendChild(div);
    });
  }

  // --- 進捗表示を更新する関数 ---
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

  // --- キャンセルボタン ---
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

  // --- バックグラウンドからの進捗更新メッセージをリッスン ---
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'updateProgress') {
      console.log("Booklight AI: Progress update received:", request);

      // 収集中の場合のみUIを更新
      if (isCollecting) {
        const { processed, total, message } = request;

        // 進捗バーとテキストを更新
        updateProgressUI(processed, total, message);

        // 完了、エラー、キャンセルのメッセージを判定
        const isError = message.includes('エラー') || message.includes('失敗') || message.includes('タイムアウト');
        const isCancelled = message.includes('キャンセル');
        const isOverallComplete = (processed === total && message.includes('完了'));

        // 収集が終了した場合（完了、エラー、キャンセル）
        if (isError || isCancelled || isOverallComplete) {
            setUIState(true, false); // 収集終了状態に戻す
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
    // 収集中でなければ進捗表示も隠す (setUIStateで制御されるので不要かも)
    // if (!isCollecting) {
    //     collectAllProgress.style.display = 'none';
    // }
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
