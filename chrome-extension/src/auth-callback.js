// Google認証コールバックを処理するコンテンツスクリプト
(function() {
  console.log('Booklight AI: 認証コールバックスクリプトが読み込まれました');
  
  // URLからトークンとユーザー情報を取得
  function getTokenFromUrl() {
    try {
      const url = new URL(window.location.href);
      const token = url.searchParams.get('token');
      const user = url.searchParams.get('user');
      const error = url.searchParams.get('error');
      
      return { token, user, error };
    } catch (error) {
      console.error('Booklight AI: URLパラメータの解析に失敗しました', error);
      return { error: 'URLパラメータの解析に失敗しました: ' + error.message };
    }
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
        }, (response) => {
          if (chrome.runtime.lastError) {
            console.error('Booklight AI: メッセージ送信エラー', chrome.runtime.lastError);
          } else {
            console.log('Booklight AI: エラーメッセージ送信成功', response);
          }
        });
        
        // エラーメッセージを表示
        document.body.innerHTML = `
          <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; max-width: 600px; margin-left: auto; margin-right: auto;">
            <h2 style="color: #d9534f;">認証エラー</h2>
            <p style="background-color: #f2dede; border: 1px solid #ebccd1; border-radius: 4px; padding: 15px; color: #a94442;">${error}</p>
            <p>ウィンドウを閉じて、再度お試しください。</p>
            <button onclick="window.close()" style="background-color: #5bc0de; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer;">ウィンドウを閉じる</button>
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
        }, (response) => {
          if (chrome.runtime.lastError) {
            console.error('Booklight AI: メッセージ送信エラー', chrome.runtime.lastError);
            
            // エラーメッセージを表示
            document.body.innerHTML = `
              <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; max-width: 600px; margin-left: auto; margin-right: auto;">
                <h2 style="color: #d9534f;">エラー</h2>
                <p style="background-color: #f2dede; border: 1px solid #ebccd1; border-radius: 4px; padding: 15px; color: #a94442;">拡張機能との通信に失敗しました。拡張機能が有効になっていることを確認してください。</p>
                <p>エラー: ${chrome.runtime.lastError.message}</p>
                <button onclick="window.close()" style="background-color: #5bc0de; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer;">ウィンドウを閉じる</button>
              </div>
            `;
          } else {
            console.log('Booklight AI: トークン送信成功', response);
            
            // 成功メッセージを表示
            document.body.innerHTML = `
              <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; max-width: 600px; margin-left: auto; margin-right: auto;">
                <h2 style="color: #5cb85c;">認証成功</h2>
                <p style="background-color: #dff0d8; border: 1px solid #d6e9c6; border-radius: 4px; padding: 15px; color: #3c763d;">ようこそ、${user}さん！</p>
                <p>このウィンドウは自動的に閉じられます。</p>
                <p>自動的に閉じられない場合は、下のボタンをクリックしてください。</p>
                <button onclick="window.close()" style="background-color: #5cb85c; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer;">ウィンドウを閉じる</button>
              </div>
            `;
            
            // 5秒後に自動的にウィンドウを閉じる
            setTimeout(() => {
              window.close();
            }, 5000);
          }
        });
      } else {
        console.warn('Booklight AI: トークンまたはユーザー情報がありません');
        
        // エラーメッセージを表示
        document.body.innerHTML = `
          <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; max-width: 600px; margin-left: auto; margin-right: auto;">
            <h2 style="color: #f0ad4e;">認証情報がありません</h2>
            <p style="background-color: #fcf8e3; border: 1px solid #faebcc; border-radius: 4px; padding: 15px; color: #8a6d3b;">認証情報が見つかりませんでした。再度ログインしてください。</p>
            <button onclick="window.close()" style="background-color: #5bc0de; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer;">ウィンドウを閉じる</button>
          </div>
        `;
      }
    } catch (error) {
      console.error('Booklight AI: 認証コールバック処理中にエラーが発生しました', error);
      
      // エラーメッセージをバックグラウンドスクリプトに送信
      chrome.runtime.sendMessage({
        action: 'google_auth_error',
        error: error.message || '不明なエラー'
      });
      
      // エラーメッセージを表示
      document.body.innerHTML = `
        <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; max-width: 600px; margin-left: auto; margin-right: auto;">
          <h2 style="color: #d9534f;">エラーが発生しました</h2>
          <p style="background-color: #f2dede; border: 1px solid #ebccd1; border-radius: 4px; padding: 15px; color: #a94442;">${error.message || '不明なエラー'}</p>
          <button onclick="window.close()" style="background-color: #5bc0de; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer;">ウィンドウを閉じる</button>
        </div>
      `;
    }
  }
  
  // ページ読み込み完了時に実行
  if (document.readyState === 'complete') {
    processAuthCallback();
  } else {
    window.addEventListener('load', processAuthCallback);
  }
})();
