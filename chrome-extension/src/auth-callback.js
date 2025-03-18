// Google認証コールバックを処理するコンテンツスクリプト
(function() {
  console.log('Booklight AI: 認証コールバックスクリプトが読み込まれました');
  
  // URLからトークンとユーザー情報を取得
  function getTokenFromUrl() {
    const url = new URL(window.location.href);
    const token = url.searchParams.get('token');
    const user = url.searchParams.get('user');
    const error = url.searchParams.get('error');
    
    return { token, user, error };
  }
  
  // メイン処理
  function processAuthCallback() {
    try {
      const { token, user, error } = getTokenFromUrl();
      
      if (error) {
        console.error('Booklight AI: 認証エラー', error);
        // エラーメッセージをバックグラウンドスクリプトに送信
        chrome.runtime.sendMessage({
          action: 'google_auth_error',
          error: error
        });
        
        // エラーメッセージを表示
        document.body.innerHTML = `
          <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif;">
            <h2>認証エラー</h2>
            <p>${error}</p>
            <p>ウィンドウを閉じて、再度お試しください。</p>
          </div>
        `;
        return;
      }
      
      if (token && user) {
        console.log('Booklight AI: 認証成功', { user });
        
        // トークンをバックグラウンドスクリプトに送信
        chrome.runtime.sendMessage({
          action: 'google_auth_success',
          token: token,
          user: user
        });
        
        // 成功メッセージを表示
        document.body.innerHTML = `
          <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif;">
            <h2>認証成功</h2>
            <p>ようこそ、${user}さん！</p>
            <p>このウィンドウは自動的に閉じられます。</p>
          </div>
        `;
      } else {
        console.warn('Booklight AI: トークンまたはユーザー情報がありません');
      }
    } catch (error) {
      console.error('Booklight AI: 認証コールバック処理中にエラーが発生しました', error);
    }
  }
  
  // ページ読み込み完了時に実行
  if (document.readyState === 'complete') {
    processAuthCallback();
  } else {
    window.addEventListener('load', processAuthCallback);
  }
})();
