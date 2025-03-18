// ダミーデータのインポート（開発用）
let dummyData = null;
// 注: コンテンツスクリプトではimportScriptsは使用できません
// 代わりにダミーデータを直接定義するか、バックグラウンドスクリプトから取得する必要があります
try {
  // 開発モードの場合、バックグラウンドスクリプトからダミーデータを取得
  chrome.runtime.sendMessage({ action: 'getDummyData' }, function(response) {
    if (response && response.success) {
      dummyData = response.data;
      console.log('Booklight AI: バックグラウンドスクリプトからダミーデータを取得しました');
    }
  });
} catch (e) {
  console.log('Booklight AI: ダミーデータの取得に失敗しました', e);
}

// Kindle Web Readerからハイライトを収集する関数
function collectHighlights() {
  try {
    console.log('Booklight AI: ハイライト収集を開始します');
    
    // テストモードの確認（URLパラメータに?test=trueが含まれる場合）
    const isTestMode = window.location.search.includes('test=true');
    if (isTestMode && dummyData) {
      console.log('Booklight AI: テストモードでダミーデータを使用します');
      return dummyData.simulateHighlightCollection();
    }
    
    // テストページの確認
    const isTestPage = window.location.href.includes('test-page.html');
    if (isTestPage) {
      return collectHighlightsFromTestPage();
    }
    
    // 書籍情報の取得
    // 注: 実際のKindle Web ReaderのDOM構造に合わせて調整が必要
    const bookTitle = document.querySelector('.reader-title') ? 
                      document.querySelector('.reader-title').textContent.trim() : 
                      document.querySelector('.book-title')?.textContent?.trim() || 
                      document.title || 'Unknown Book';
    
    const authorElement = document.querySelector('.reader-author') || document.querySelector('.book-author');
    const author = authorElement ? authorElement.textContent.trim() : 'Unknown Author';
    
    console.log(`Booklight AI: 書籍「${bookTitle}」(${author})のハイライトを収集します`);
    
    // ハイライト要素の取得
    // 注: 実際のKindle Web ReaderのDOM構造に合わせて調整が必要
    // 複数のセレクタを試行
    const selectors = [
      '.kp-notebook-highlight',
      '.kindle-highlight',
      '.highlight',
      'a-size-base-plus a-color-base'
    ];
    
    let highlightElements = [];
    for (const selector of selectors) {
      const elements = document.querySelectorAll(selector);
      if (elements && elements.length > 0) {
        highlightElements = elements;
        console.log(`Booklight AI: セレクタ '${selector}' でハイライトを検出しました`);
        break;
      }
    }
    
    if (!highlightElements || highlightElements.length === 0) {
      console.log('Booklight AI: ハイライトが見つかりませんでした');
      return { 
        success: false, 
        message: 'ハイライトが見つかりませんでした。Kindleのハイライトページを開いているか確認してください。' 
      };
    }
    
    console.log(`Booklight AI: ${highlightElements.length}件のハイライトを検出しました`);
    
    // ハイライトデータの作成
    const highlights = Array.from(highlightElements).map(element => {
      // 複数のセレクタを試行してハイライトテキストを取得
      let content = '';
      const contentSelectors = [
        '.kp-notebook-highlight-text',
        '.highlight-text',
        '.highlight-content'
      ];
      
      for (const selector of contentSelectors) {
        const contentElement = element.querySelector(selector);
        if (contentElement && contentElement.textContent) {
          content = contentElement.textContent.trim();
          break;
        }
      }
      
      // 位置情報の取得
      let location = '';
      // データ属性から取得
      if (element.hasAttribute('data-location')) {
        location = element.getAttribute('data-location');
      } else {
        // 位置情報を含む要素を探す
        const locationSelectors = [
          '.kp-notebook-highlight-location',
          '.highlight-location',
          '.location'
        ];
        
        for (const selector of locationSelectors) {
          const locationElement = element.querySelector(selector);
          if (locationElement && locationElement.textContent) {
            location = locationElement.textContent.trim();
            break;
          }
        }
      }
      
      return {
        book_title: bookTitle,
        author: author,
        content: content,
        location: location
      };
    }).filter(h => h.content); // 空のハイライトを除外
    
    console.log(`Booklight AI: ${highlights.length}件のハイライトを収集しました`);
    
    return {
      success: true,
      data: {
        book_title: bookTitle,
        author: author,
        highlights: highlights
      }
    };
  } catch (error) {
    console.error('Booklight AI: ハイライト収集中にエラーが発生しました', error);
    return { 
      success: false, 
      message: `エラーが発生しました: ${error.message}` 
    };
  }
}

// テストページからハイライトを収集する関数
function collectHighlightsFromTestPage() {
  try {
    console.log('Booklight AI: テストページからハイライトを収集します');
    
    // 書籍情報の取得
    const bookTitle = document.querySelector('h1')?.nextElementSibling?.textContent || '不明な書籍';
    const author = document.querySelector('h1')?.nextElementSibling?.nextElementSibling?.textContent || '不明な著者';
    
    // ハイライト要素の取得
    const highlightElements = document.querySelectorAll('.kindle-highlight');
    
    if (!highlightElements || highlightElements.length === 0) {
      console.log('Booklight AI: テストページにハイライトが見つかりませんでした');
      return {
        success: false,
        message: 'テストページにハイライトが見つかりませんでした'
      };
    }
    
    // ハイライトデータの作成
    const highlights = [];
    highlightElements.forEach(element => {
      const content = element.textContent?.trim();
      const locationElement = element.nextElementSibling;
      const location = locationElement ? locationElement.textContent?.trim() : '';
      
      if (content) {
        highlights.push({
          book_title: bookTitle,
          author: author,
          content: content,
          location: location
        });
      }
    });
    
    console.log(`Booklight AI: テストページから${highlights.length}件のハイライトを収集しました`);
    
    return {
      success: true,
      data: {
        book_title: bookTitle,
        author: author,
        highlights: highlights
      }
    };
  } catch (error) {
    console.error('Booklight AI: テストページからのハイライト収集中にエラーが発生しました', error);
    return {
      success: false,
      message: `エラーが発生しました: ${error.message}`
    };
  }
}

// DOM変更の監視（ページが動的に変更される場合に対応）
function setupMutationObserver() {
  // ハイライトコンテナの監視
  const targetNode = document.body;
  
  // オブザーバーの設定
  const config = { childList: true, subtree: true };
  
  // 変更が検出されたときのコールバック
  const callback = function(mutationsList, observer) {
    for (const mutation of mutationsList) {
      if (mutation.type === 'childList') {
        // ハイライト要素が追加されたかどうかを確認
        const selectors = ['.kp-notebook-highlight', '.kindle-highlight', '.highlight'];
        
        for (const selector of selectors) {
          const addedHighlights = Array.from(mutation.addedNodes)
            .filter(node => node.nodeType === 1) // 要素ノードのみ
            .filter(node => node.matches && node.matches(selector));
          
          if (addedHighlights.length > 0) {
            console.log(`Booklight AI: ${addedHighlights.length}件の新しいハイライトを検出しました`);
            break;
          }
        }
      }
    }
  };
  
  // オブザーバーのインスタンスを作成
  const observer = new MutationObserver(callback);
  
  // 対象ノードの監視を開始
  observer.observe(targetNode, config);
  
  console.log('Booklight AI: DOM変更の監視を開始しました');
}

// ページ読み込み完了時の処理
window.addEventListener('load', function() {
  console.log('Booklight AI: ページが読み込まれました');
  setupMutationObserver();
});

// メッセージリスナーを設定
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Booklight AI: メッセージを受信しました', request);
  
  if (request.action === 'collectHighlights') {
    const result = collectHighlights();
    sendResponse(result);
  }
  
  // テスト用のダミーデータ挿入（開発用）
  if (request.action === 'injectDummyData' && request.dummyHTML) {
    try {
      // ページにダミーHTMLを挿入
      const container = document.createElement('div');
      container.id = 'booklight-dummy-container';
      container.innerHTML = request.dummyHTML;
      document.body.appendChild(container);
      sendResponse({ success: true, message: 'ダミーデータを挿入しました' });
    } catch (error) {
      sendResponse({ success: false, message: `ダミーデータの挿入に失敗しました: ${error.message}` });
    }
  }
  
  return true; // 非同期レスポンスのために必要
});

// 初期化メッセージ
console.log('Booklight AI: コンテンツスクリプトが読み込まれました');
