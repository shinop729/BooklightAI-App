// Google認証コールバックを処理するコンテンツスクリプト
(function() {
  console.log('Booklight AI: 認証コールバックスクリプトが読み込まれました');
  console.log('Booklight AI: URL', window.location.href);
  
  // URLとクッキーからトークンとユーザー情報を取得
  function getTokenFromUrl() {
    try {
      const url = new URL(window.location.href);
      let token = url.searchParams.get('token');
      const user = url.searchParams.get('user');
      const error = url.searchParams.get('error');
      
      // クッキーからトークンを取得（可能な場合）
      if (!token) {
        const getCookie = (name) => {
          const value = `; ${document.cookie}`;
          const parts = value.split(`; ${name}=`);
          if (parts.length === 2) return parts.pop().split(';').shift();
          return null;
        };
        
        const cookieToken = getCookie('auth_token');
        if (cookieToken) {
          console.log('Booklight AI: クッキーからトークンを取得しました');
          token = cookieToken;
        }
      }
      
      // デバッグ情報の出力
      console.log('Booklight AI: URL', window.location.href);
      console.log('Booklight AI: クエリパラメータ', new URL(window.location.href).searchParams.toString());
      console.log('Booklight AI: 認証情報', { 
        user: user || 'なし', 
        token: token ? '存在します' : 'なし',
        error: error || 'なし' 
      });
      
      // ドキュメントのHTML内容をログに出力（デバッグ用）
      console.log('Booklight AI: ドキュメント内容', document.documentElement.outerHTML.substring(0, 500) + '...');
      
      return { token, user, error };
    } catch (error) {
      console.error('Booklight AI: URLパラメータの解析に失敗しました', error);
      return { error: 'URLパラメータの解析に失敗しました: ' + error.message };
    }
  }
  
  // メイン処理
  function processAuthCallback() {
    try {
      // 既にHTMLコンテンツが設定されている場合は処理をスキップ
      if (document.body.innerHTML.includes('認証成功') || document.body.innerHTML.includes('認証エラー')) {
        console.log('Booklight AI: 既にHTMLコンテンツが設定されています。処理をスキップします。');
        return;
      }
      
      const { token, user, error } = getTokenFromUrl();
      
      // URLパラメータの詳細をログに出力
      console.log('Booklight AI: URL', window.location.href);
      console.log('Booklight AI: URLパラメータ', new URL(window.location.href).searchParams.toString());
      
      // ページ内のスクリプトタグを確認
      const scripts = document.querySelectorAll('script');
      console.log(`Booklight AI: ページ内のスクリプトタグ数: ${scripts.length}`);
      for (let i = 0; i < scripts.length; i++) {
        console.log(`Booklight AI: スクリプト[${i}] type=${scripts[i].type}, src=${scripts[i].src}`);
      }
      
      if (error) {
        console.error('Booklight AI: 認証エラー', error);
        // エラーメッセージをバックグラウンドスクリプトに送信
        try {
          chrome.runtime.sendMessage({
            action: 'google_auth_error',
            error: error
          }, (response) => {
            if (chrome.runtime.lastError) {
              console.error('Booklight AI: メッセージ送信エラー', chrome.runtime.lastError);
            } else {
              console.log('Booklight AI: エラーメッセージ送信成功', response);
            }
          });
        } catch (e) {
          console.error('Booklight AI: chrome.runtime.sendMessageの呼び出しに失敗しました', e);
        }
        return;
      }
      
      if (token && user) {
        console.log('Booklight AI: 認証成功', { user });
        
        // トークンをバックグラウンドスクリプトに送信
        try {
          // 直接グローバルスコープからchromeオブジェクトにアクセス
          if (typeof chrome !== 'undefined' && chrome.runtime) {
            chrome.runtime.sendMessage({
              action: 'google_auth_success',
              token: token,
              user: user
            }, (response) => {
              if (chrome.runtime.lastError) {
                console.error('Booklight AI: メッセージ送信エラー', chrome.runtime.lastError);
              } else {
                console.log('Booklight AI: トークン送信成功', response);
                
                // 5秒後に自動的にウィンドウを閉じる
                setTimeout(() => {
                  window.close();
                }, 5000);
              }
            });
          } else {
            console.warn('Booklight AI: chrome.runtime APIが利用できません');
            
            // 代替手段として、windowオブジェクトにメッセージを保存
            window.BOOKLIGHT_AUTH_DATA = { token, user };
            console.log('Booklight AI: 認証データをwindowオブジェクトに保存しました');
            
            // 10秒後に自動的にウィンドウを閉じる
            setTimeout(() => {
              window.close();
            }, 10000);
          }
        } catch (e) {
          console.error('Booklight AI: chrome.runtime.sendMessageの呼び出しに失敗しました', e);
          console.error(e.stack);
          
          // 代替手段として、windowオブジェクトにメッセージを保存
          window.BOOKLIGHT_AUTH_DATA = { token, user };
          console.log('Booklight AI: 認証データをwindowオブジェクトに保存しました（エラー発生後）');
          
          // 10秒後に自動的にウィンドウを閉じる
          setTimeout(() => {
            window.close();
          }, 10000);
        }
      } else {
        console.warn('Booklight AI: トークンまたはユーザー情報がありません');
        // ページ内容はサーバーから返されるHTMLを使用するため、ここでは何もしない
      }
    } catch (error) {
      console.error('Booklight AI: 認証コールバック処理中にエラーが発生しました', error);
      console.error(error.stack);
      
      // エラーメッセージをバックグラウンドスクリプトに送信
      try {
        if (typeof chrome !== 'undefined' && chrome.runtime) {
          chrome.runtime.sendMessage({
            action: 'google_auth_error',
            error: error.message || '不明なエラー'
          });
        }
      } catch (e) {
        console.error('Booklight AI: chrome.runtime.sendMessageの呼び出しに失敗しました', e);
      }
    }
  }
  
  // ページ読み込み完了時に実行
  if (document.readyState === 'complete') {
    processAuthCallback();
  } else {
    window.addEventListener('load', processAuthCallback);
  }
  
  // DOMContentLoadedイベントでも実行（より早いタイミング）
  window.addEventListener('DOMContentLoaded', processAuthCallback);
  
  // DOMの変更を監視して、認証情報が動的に追加された場合に対応
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
        // DOMが変更されたら再度処理を実行
        processAuthCallback();
      }
    }
  });
  
  // body要素の監視
  if (document.body) {
    observer.observe(document.body, { childList: true, subtree: true });
  } else {
    // bodyがまだ存在しない場合は、DOMContentLoadedイベントで監視を開始
    window.addEventListener('DOMContentLoaded', () => {
      observer.observe(document.body, { childList: true, subtree: true });
    });
  }
  
  // 30秒後に監視を停止（リソース節約のため）
  setTimeout(() => {
    observer.disconnect();
    console.log('Booklight AI: DOM監視を停止しました');
  }, 30000);
  
  // 定期的に認証情報をチェック（バックアップ手段）
  let checkCount = 0;
  const maxChecks = 10;
  const checkInterval = setInterval(() => {
    checkCount++;
    console.log(`Booklight AI: 定期チェック ${checkCount}/${maxChecks}`);
    processAuthCallback();
    
    if (checkCount >= maxChecks) {
      clearInterval(checkInterval);
      console.log('Booklight AI: 定期チェックを停止しました');
    }
  }, 1000);
})();
