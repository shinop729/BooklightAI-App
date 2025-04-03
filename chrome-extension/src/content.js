// content.js ロード確認ログ
console.log("Booklight AI: content.js loaded for:", window.location.href);

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

// Kindleノートブックページからハイライトを収集する関数
function collectHighlights() {
  try {
    console.log('Booklight AI: ノートブックページからのハイライト収集を開始します');

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

    // ページ上の書籍タイトル要素を取得
    const allTitleElements = document.querySelectorAll('h3.kp-notebook-selectable.kp-notebook-metadata');

    if (!allTitleElements || allTitleElements.length === 0) {
        console.log('Booklight AI: 書籍タイトルが見つかりませんでした');
        return {
            success: false,
            message: 'ハイライトが見つかりませんでした。Kindleのノートブックページを開いているか確認してください。'
        };
    }

    console.log(`Booklight AI: ${allTitleElements.length}件の書籍タイトルを検出しました`);

    let allCollectedHighlights = [];
    const bookLimit = 10; // 取得する書籍の上限

    // 最初の10冊の書籍に対して処理
    for (let i = 0; i < Math.min(allTitleElements.length, bookLimit); i++) {
        const titleElement = allTitleElements[i];
        const bookTitleText = titleElement.textContent.trim();

        // タイトル要素から書籍セクションを特定 (親要素を辿る)
        let bookContainer = titleElement;
        let author = '不明な著者';
        let coverImageUrl = null;
        for (let j = 0; j < 5 && bookContainer.parentElement; j++) { // 5レベルまで遡る
             bookContainer = bookContainer.parentElement;
             // このコンテナ内に著者とカバー画像があるか探す
             const authorElement = bookContainer.querySelector('p.a-size-base.a-color-secondary.kp-notebook-selectable.kp-notebook-metadata');
             if (authorElement) author = authorElement.textContent.trim();
             const coverImageElement = bookContainer.querySelector('img.kp-notebook-cover-image-border');
             if (coverImageElement) coverImageUrl = coverImageElement.src;
             // ハイライト要素もこのコンテナ内にあるはず
             const highlightElements = bookContainer.querySelectorAll('span#highlight.a-size-base-plus.a-color-base');
             if (highlightElements && highlightElements.length > 0) {
                 break; // ハイライトが見つかるコンテナを特定
             }
        }

        if (!bookContainer) {
            console.warn(`Booklight AI: 書籍「${bookTitleText}」のコンテナが見つかりませんでした。`);
            continue; // 次の書籍へ
        }

        console.log(`Booklight AI: 書籍 #${i + 1} 「${bookTitleText}」(${author}) のハイライトを収集します`);

        // 特定した書籍コンテナ内のハイライト要素を取得
        const highlightElements = bookContainer.querySelectorAll('span#highlight.a-size-base-plus.a-color-base');

        if (!highlightElements || highlightElements.length === 0) {
          console.log(`Booklight AI: 書籍「${bookTitleText}」にハイライトが見つかりませんでした`);
          continue; // 次の書籍へ
        }

        console.log(`Booklight AI: 書籍「${bookTitleText}」で ${highlightElements.length}件のハイライトを検出しました`);

        // ハイライトデータの作成
        const highlights = Array.from(highlightElements).map((element, index) => {
            const content = element.textContent ? element.textContent.trim() : '';
            let location = ''; // mapスコープ内で宣言
            const highlightElement = element; // The span#highlight

            console.log(`--- Highlight ${index + 1} ---`);
            console.log(`Content: ${content.substring(0, 50)}...`);

            // Find the closest ancestor row separator for this specific highlight
            const rowSeparator = highlightElement.closest('.kp-notebook-row-separator');

            if (rowSeparator) {
                console.log(`Found closest rowSeparator:`, rowSeparator.className);

                // Priority: Find the hidden input within this specific rowSeparator
                const hiddenInput = rowSeparator.querySelector('input[type="hidden"]#kp-annotation-location');
                console.log(`Searching for hidden input within rowSeparator:`, hiddenInput);

                if (hiddenInput && hiddenInput.value) {
                    location = hiddenInput.value.trim();
                    console.log(`SUCCESS: Location from hidden input: ${location}`);
                } else {
                    console.log(`INFO: Hidden input not found or has no value. Trying fallback.`);
                    // Fallback: Find the header span within this specific rowSeparator
                    const headerElement = rowSeparator.querySelector('span#annotationHighlightHeader');
                    console.log(`Searching for header element within rowSeparator:`, headerElement);

                    if (headerElement) {
                        const headerText = headerElement.textContent ? headerElement.textContent.trim() : '';
                        console.log(`Header text found: ${headerText}`);
                        const match = headerText.match(/(?:位置|ページ):\s*(\d+)/);
                        if (match && match[1]) {
                            location = match[1];
                            console.log(`SUCCESS: Location from header (fallback): ${location}`);
                        } else {
                            console.warn(`WARN: Could not extract location number from header text: ${headerText}`);
                        }
                    } else {
                        console.warn(`WARN: Could not find header element (span#annotationHighlightHeader) within row separator.`);
                    }
                }
            } else {
                // This case should ideally not happen if the HTML structure is consistent
                console.error(`ERROR: Could not find parent row separator (.kp-notebook-row-separator) for highlight: ${content.substring(0, 20)}...`);
            }

            console.log(`Final location determined for Highlight ${index + 1}: ${location}`);
            console.log(`--- End Highlight ${index + 1} ---`);

             return {
                book_title: bookTitleText,
          author: author,
          content: content,
          location: location,
          cover_image_url: coverImageUrl
        };
        }).filter(h => h.content); // 空のハイライトを除外

        allCollectedHighlights = allCollectedHighlights.concat(highlights);
    } // 書籍ループの終了

    console.log(`Booklight AI: 合計 ${allCollectedHighlights.length}件の有効なハイライトを収集しました (最大${bookLimit}冊)`);

    if (allCollectedHighlights.length === 0) {
        return {
            success: false,
            message: '有効なハイライトが見つかりませんでした。'
        };
    }

    return {
      success: true,
      data: {
        highlights: allCollectedHighlights
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
        const selectors = [
          'div#annotation-scroller .a-row.a-spacing-top-extra-large.kp-notebook-annotation-container',
          '.kp-notebook-highlight', 
          '.kindle-highlight', 
          '.highlight'
        ];
        
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
