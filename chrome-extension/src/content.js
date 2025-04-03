// content.js ロード確認ログ
console.log("Booklight AI: content.js loaded for:", window.location.href);

// ダミーデータのインポート（開発用）
let dummyData = null;
// 注: コンテンツスクリプトではimportScriptsは使用できません
// 代わりにダミーデータを直接定義するか、バックグラウンドスクリプトから取得する必要があります
try {
  // 開発モードの場合、バックグラウンドスクリプトからダミーデータを取得
  chrome.runtime.sendMessage({ action: 'getDummyData' }, function(response) {
    if (chrome.runtime.lastError) {
      console.warn("Booklight AI: バックグラウンドへの接続に失敗しました。再読み込みが必要な場合があります。", chrome.runtime.lastError.message);
      return;
    }
    if (response && response.success) {
      dummyData = response.data;
      console.log('Booklight AI: バックグラウンドスクリプトからダミーデータを取得しました');
    }
  });
} catch (e) {
  console.log('Booklight AI: ダミーデータの取得に失敗しました', e);
}

// --- 書籍リンク取得機能（修正版）---
function getBookLinks() {
  console.log("Booklight AI: getBookLinks 関数開始 (修正版)");
  try {
    // 各書籍を表すdiv要素をターゲットにするセレクタ
    const bookElementSelector = '.kp-notebook-library-each-book';
    const bookElements = document.querySelectorAll(bookElementSelector);

    console.log(`Booklight AI: セレクタ "${bookElementSelector}" で ${bookElements.length} 件の書籍要素を検出`);

    if (bookElements.length === 0) {
      console.warn('Booklight AI: 書籍要素が見つかりませんでした。');
      return { success: false, message: 'サイドバーから書籍が見つかりません。', data: [] };
    }

    const bookLinks = [];
    const seenBookIds = new Set(); // 重複チェック用

    bookElements.forEach((element, index) => {
      let bookId = null;
      let title = '不明な書籍';
      let author = '不明な著者';
      let url = null;

      // 1. 書籍IDを抽出 (divのid属性を最優先)
      if (element.id && /^[A-Z0-9]{10}$/.test(element.id)) {
          bookId = element.id;
      } else {
          // フォールバック: data-get-annotations-for-asin属性から抽出
          const spanElement = element.querySelector('span[data-get-annotations-for-asin]');
          if (spanElement) {
              try {
                  const data = JSON.parse(spanElement.dataset.getAnnotationsForAsin);
                  if (data && data.asin) {
                      bookId = data.asin;
                  }
              } catch (e) {
                  console.warn(`Booklight AI: data-get-annotations-for-asin のパースに失敗 (要素 ${index})`, e);
              }
          }
      }

      // 2. タイトルと著者を抽出
      const titleElement = element.querySelector('h2.kp-notebook-searchable');
      if (titleElement) {
          title = titleElement.textContent?.trim() || title;
      }
      const authorElement = element.querySelector('p.kp-notebook-searchable');
      if (authorElement) {
          author = authorElement.textContent?.trim().replace(/^著者:\s*/, '') || author; // "著者: " を除去
      }

      // 3. URLを構築
      if (bookId) {
          url = `https://read.amazon.co.jp/notebook?asin=${bookId}&contentLimitState=&ref_=kcr_notebook_lib`;
      }

      // 4. 結果を追加 (有効なIDとURLがあり、重複がない場合)
      if (bookId && url && !seenBookIds.has(bookId)) {
          bookLinks.push({
              title: title,
              author: author, // 著者情報も追加
              url: url,
              bookId: bookId
          });
          seenBookIds.add(bookId);
          console.log(`Booklight AI: 書籍情報を抽出: ID=${bookId}, Title=${title}`);
      } else if (!bookId) {
          console.warn(`Booklight AI: 書籍IDを抽出できませんでした: Title=${title}`);
      } else if (!url) {
           console.warn(`Booklight AI: URLを構築できませんでした: ID=${bookId}, Title=${title}`);
      }
    });

    if (bookLinks.length === 0) {
      console.warn('Booklight AI: 有効な書籍情報を抽出できませんでした。');
      return { success: false, message: '有効な書籍情報を抽出できませんでした。', data: [] };
    }

    console.log(`Booklight AI: 合計 ${bookLinks.length} 件のユニークな書籍情報を抽出しました`);
    console.log("Booklight AI: getBookLinks 関数成功 (修正版)");
    return { success: true, data: bookLinks };

  } catch (error) {
    console.error('Booklight AI: getBookLinks 関数内でエラーが発生しました', error);
    return { success: false, message: `getBookLinks エラー: ${error.message}`, data: [] };
  }
}

// extractBookId 関数は getBookLinks 内に統合されたため不要になります。
// 必要であれば、他の場所で使うために残すことも可能です。
/*
function extractBookId(element) {
  // ... (以前のロジック) ...
}
*/

// --- 新機能: 現在表示されている単一書籍のデータを抽出 ---
function extractCurrentBookData() {
  console.log("Booklight AI: extractCurrentBookData 関数が呼び出されました");
  try {
    // 書籍タイトル、著者、カバー画像の取得ロジック (collectHighlightsから流用・調整)
    // メインコンテンツエリアに表示されている書籍情報を対象とする
    const titleElement = document.querySelector('h1.a-spacing-top-small') || document.querySelector('h3.kp-notebook-selectable.kp-notebook-metadata'); // メインタイトル要素を優先
    const bookTitleText = titleElement ? titleElement.textContent.trim() : '不明な書籍';

    let author = '不明な著者';
    let coverImageUrl = null;

    // タイトル要素の近くから著者とカバーを探す (より限定的な範囲で)
    let searchContainer = titleElement?.parentElement;
    for (let j = 0; j < 3 && searchContainer; j++) { // 3レベル程度に限定
         const authorElement = searchContainer.querySelector('p.a-size-base.a-color-secondary.kp-notebook-selectable.kp-notebook-metadata, span.a-color-secondary.a-size-base'); // 著者要素の可能性
         if (authorElement) author = authorElement.textContent.trim().replace(/^by /, ''); // "by " を除去
         const coverImageElement = searchContainer.querySelector('img.kp-notebook-cover-image-border, img.kp-notebook-cover-image'); // カバー画像要素の可能性
         if (coverImageElement) coverImageUrl = coverImageElement.src;
         if (author !== '不明な著者' && coverImageUrl) break; // 両方見つかれば終了
         searchContainer = searchContainer.parentElement;
    }
     // 見つからない場合、ページ全体から探す (フォールバック)
    if (author === '不明な著者') {
        const authorElemFallback = document.querySelector('p.a-size-base.a-color-secondary.kp-notebook-selectable.kp-notebook-metadata, span.a-color-secondary.a-size-base');
        if (authorElemFallback) author = authorElemFallback.textContent.trim().replace(/^by /, '');
    }
    if (!coverImageUrl) {
        const coverElemFallback = document.querySelector('img.kp-notebook-cover-image-border, img.kp-notebook-cover-image');
        if (coverElemFallback) coverImageUrl = coverElemFallback.src;
    }


    console.log(`Booklight AI: 現在の書籍情報: タイトル「${bookTitleText}」, 著者「${author}」`);

    // ハイライト要素を取得 (ページ全体のハイライトを対象)
    const highlightElements = document.querySelectorAll('span#highlight.a-size-base-plus.a-color-base');

    if (!highlightElements || highlightElements.length === 0) {
      console.log(`Booklight AI: 書籍「${bookTitleText}」にハイライトが見つかりませんでした`);
      // ハイライトがなくても書籍情報は返す
      return {
        success: true,
        data: {
          book_title: bookTitleText,
          author: author,
          cover_image_url: coverImageUrl,
          highlights: []
        }
      };
    }

    console.log(`Booklight AI: 書籍「${bookTitleText}」で ${highlightElements.length}件のハイライトを検出しました`);

    // ハイライトデータの作成 (collectHighlightsから流用)
    const highlights = Array.from(highlightElements).map((element, index) => {
        const content = element.textContent ? element.textContent.trim() : '';
        let location = '';
        const highlightElement = element;

        const rowSeparator = highlightElement.closest('.kp-notebook-row-separator');
        if (rowSeparator) {
            const hiddenInput = rowSeparator.querySelector('input[type="hidden"]#kp-annotation-location');
            if (hiddenInput && hiddenInput.value) {
                location = hiddenInput.value.trim();
            } else {
                const headerElement = rowSeparator.querySelector('span#annotationHighlightHeader');
                if (headerElement) {
                    const headerText = headerElement.textContent ? headerElement.textContent.trim() : '';
                    const match = headerText.match(/(?:位置|ページ):\s*(\d+)/);
                    if (match && match[1]) {
                        location = match[1];
                    } else {
                         console.warn(`WARN: Could not extract location number from header text: ${headerText}`);
                    }
                } else {
                     console.warn(`WARN: Could not find header element (span#annotationHighlightHeader) within row separator.`);
                }
            }
        } else {
             console.error(`ERROR: Could not find parent row separator (.kp-notebook-row-separator) for highlight: ${content.substring(0, 20)}...`);
        }

         return {
            // book_title と author はここでは含めず、上位で付与する
            content: content,
            location: location,
        };
    }).filter(h => h.content); // 空のハイライトを除外

    console.log(`Booklight AI: 書籍「${bookTitleText}」から ${highlights.length}件の有効なハイライトを抽出しました`);

    return {
      success: true,
      data: {
        book_title: bookTitleText,
        author: author,
        cover_image_url: coverImageUrl,
        highlights: highlights
      }
    };
  } catch (error) {
    console.error('Booklight AI: 現在の書籍データ収集中にエラーが発生しました', error);
    return {
      success: false,
      message: `現在の書籍データ抽出エラー: ${error.message}`
    };
  }
}


// Kindleノートブックページからハイライトを収集する関数 (既存: 単一ページ内の複数書籍用)
// 注意: この関数は一括取得機能では直接使用されませんが、単独での収集用に残すか検討が必要です。
//       現状は extractCurrentBookData が単一書籍の抽出を担当します。
function collectHighlights() {
  try {
    console.log('Booklight AI: ノートブックページからのハイライト収集を開始します (collectHighlights)');

    // テストモードの確認（URLパラメータに?test=trueが含まれる場合）
    const isTestMode = window.location.search.includes('test=true');
    if (isTestMode && dummyData) {
      console.log('Booklight AI: テストモードでダミーデータを使用します');
      // ダミーデータの形式を調整する必要があるかもしれない
      return { success: true, data: { highlights: dummyData.simulateApiResponse([]).dummyHighlights || [] } };
    }

    // テストページの確認
    const isTestPage = window.location.href.includes('test-page.html');
    if (isTestPage) {
      return collectHighlightsFromTestPage(); // テストページ用関数を呼び出す
    }

    // ページ上の書籍タイトル要素を取得
    const allTitleElements = document.querySelectorAll('h3.kp-notebook-selectable.kp-notebook-metadata');

    if (!allTitleElements || allTitleElements.length === 0) {
        console.log('Booklight AI: 書籍タイトルが見つかりませんでした (collectHighlights)');
        return {
            success: false,
            message: 'ハイライトが見つかりませんでした。Kindleのノートブックページを開いているか確認してください。'
        };
    }

    console.log(`Booklight AI: ${allTitleElements.length}件の書籍タイトルを検出しました (collectHighlights)`);

    let allCollectedHighlights = [];
    const bookLimit = 10; // 取得する書籍の上限 (既存の制限)

    // 最初の10冊の書籍に対して処理
    for (let i = 0; i < Math.min(allTitleElements.length, bookLimit); i++) {
        const titleElement = allTitleElements[i];
        const bookTitleText = titleElement.textContent.trim();

        // タイトル要素から書籍セクションを特定 (親要素を辿る) - 既存ロジック
        let bookContainer = titleElement;
        let author = '不明な著者';
        let coverImageUrl = null;
        for (let j = 0; j < 5 && bookContainer.parentElement; j++) {
             bookContainer = bookContainer.parentElement;
             const authorElement = bookContainer.querySelector('p.a-size-base.a-color-secondary.kp-notebook-selectable.kp-notebook-metadata');
             if (authorElement) author = authorElement.textContent.trim();
             const coverImageElement = bookContainer.querySelector('img.kp-notebook-cover-image-border');
             if (coverImageElement) coverImageUrl = coverImageElement.src;
             const highlightElementsCheck = bookContainer.querySelectorAll('span#highlight.a-size-base-plus.a-color-base');
             if (highlightElementsCheck && highlightElementsCheck.length > 0) {
                 break;
             }
        }

        if (!bookContainer) {
            console.warn(`Booklight AI: 書籍「${bookTitleText}」のコンテナが見つかりませんでした (collectHighlights)`);
            continue;
        }

        console.log(`Booklight AI: 書籍 #${i + 1} 「${bookTitleText}」(${author}) のハイライトを収集します (collectHighlights)`);

        // 特定した書籍コンテナ内のハイライト要素を取得
        const highlightElements = bookContainer.querySelectorAll('span#highlight.a-size-base-plus.a-color-base');

        if (!highlightElements || highlightElements.length === 0) {
          console.log(`Booklight AI: 書籍「${bookTitleText}」にハイライトが見つかりませんでした (collectHighlights)`);
          continue;
        }

        console.log(`Booklight AI: 書籍「${bookTitleText}」で ${highlightElements.length}件のハイライトを検出しました (collectHighlights)`);

        // ハイライトデータの作成 (既存ロジック)
        const highlights = Array.from(highlightElements).map((element, index) => {
            const content = element.textContent ? element.textContent.trim() : '';
            let location = '';
            const highlightElement = element;

            const rowSeparator = highlightElement.closest('.kp-notebook-row-separator');
            if (rowSeparator) {
                const hiddenInput = rowSeparator.querySelector('input[type="hidden"]#kp-annotation-location');
                if (hiddenInput && hiddenInput.value) {
                    location = hiddenInput.value.trim();
                } else {
                    const headerElement = rowSeparator.querySelector('span#annotationHighlightHeader');
                    if (headerElement) {
                        const headerText = headerElement.textContent ? headerElement.textContent.trim() : '';
                        const match = headerText.match(/(?:位置|ページ):\s*(\d+)/);
                        if (match && match[1]) {
                            location = match[1];
                        }
                    }
                }
            }

             return {
                book_title: bookTitleText,
                author: author,
                content: content,
                location: location,
                cover_image_url: coverImageUrl
            };
        }).filter(h => h.content);

        allCollectedHighlights = allCollectedHighlights.concat(highlights);
    } // 書籍ループの終了

    console.log(`Booklight AI: 合計 ${allCollectedHighlights.length}件の有効なハイライトを収集しました (最大${bookLimit}冊, collectHighlights)`);

    if (allCollectedHighlights.length === 0) {
        return {
            success: false,
            message: '有効なハイライトが見つかりませんでした。'
        };
    }

    // 返すデータの形式を統一
    return {
      success: true,
      data: {
        highlights: allCollectedHighlights // 複数書籍のハイライトをフラットなリストで返す
      }
    };
  } catch (error) {
    console.error('Booklight AI: ハイライト収集中にエラーが発生しました (collectHighlights)', error);
    return {
      success: false,
      message: `エラーが発生しました: ${error.message}`
    };
  }
}

// テストページからハイライトを収集する関数 (既存)
function collectHighlightsFromTestPage() {
  try {
    console.log('Booklight AI: テストページからハイライトを収集します');


    // 書籍情報の取得
    const bookTitle = document.querySelector('h1')?.nextElementSibling?.textContent || '不明な書籍';
    const author = document.querySelector('h1')?.nextElementSibling?.nextElementSibling?.textContent || '不明な著者';
    const coverImageElement = document.querySelector('.cover-image img'); // テストページにカバー画像要素を追加想定
    const coverImageUrl = coverImageElement ? coverImageElement.src : null;

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
          // book_title, author, cover_image_url は上位で付与
          content: content,
          location: location
        });
      }
    });

    console.log(`Booklight AI: テストページから${highlights.length}件のハイライトを収集しました`);

    // 返すデータの形式を extractCurrentBookData に合わせる
    return {
      success: true,
      data: {
        book_title: bookTitle,
        author: author,
        cover_image_url: coverImageUrl,
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

// DOM変更の監視（ページが動的に変更される場合に対応） - 既存
function setupMutationObserver() {
  const targetNode = document.body;
  const config = { childList: true, subtree: true };

  const callback = function(mutationsList, observer) {
    // 既存のロジックは変更なし
    for (const mutation of mutationsList) {
      if (mutation.type === 'childList') {
        const selectors = [
          'div#annotation-scroller .a-row.a-spacing-top-extra-large.kp-notebook-annotation-container',
          '.kp-notebook-highlight',
          '.kindle-highlight',
          '.highlight'
        ];
        for (const selector of selectors) {
          const addedHighlights = Array.from(mutation.addedNodes)
            .filter(node => node.nodeType === 1)
            .filter(node => node.matches && node.matches(selector));
          if (addedHighlights.length > 0) {
            console.log(`Booklight AI: ${addedHighlights.length}件の新しいハイライトを検出しました (MutationObserver)`);
            break;
          }
        }
      }
    }
  };

  const observer = new MutationObserver(callback);
  observer.observe(targetNode, config);
  console.log('Booklight AI: DOM変更の監視を開始しました');
}

// ページ読み込み完了時の処理 - 既存
window.addEventListener('load', function() {
  console.log('Booklight AI: ページが読み込まれました');
  setupMutationObserver();
});

// メッセージリスナーを設定 - 更新
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Booklight AI: コンテンツスクリプトがメッセージを受信しました', request);

  if (request.action === 'collectHighlights') {
    // 既存の単一ページ収集リクエスト
    const result = collectHighlights();
    sendResponse(result);
    return true; // 非同期の可能性も考慮
  }

  // --- 新機能: バックグラウンドからのリクエストに対応 ---
  if (request.action === 'getBookLinks') {
    const result = getBookLinks();
    sendResponse(result);
    return true; // 非同期の可能性も考慮
  }

  if (request.action === 'extractCurrentBookData') {
    const result = extractCurrentBookData();
    sendResponse(result);
    return true; // 非同期の可能性も考慮
  }
  
  // --- ハンドシェイク機能強化 ---
  if (request.action === 'ping') {
    console.log('Booklight AI: pingメッセージを受信しました');
    // 即座にpongで応答
    sendResponse({ action: 'pong', status: 'ready' });
    // さらにバックグラウンドにも直接メッセージを送信（冗長性のため）
    try {
      chrome.runtime.sendMessage({ 
        action: 'pong',
        status: 'ready',
        timestamp: Date.now()
      }).catch(e => console.warn('Booklight AI: pongメッセージ送信エラー', e));
    } catch (e) {
      console.warn('Booklight AI: pongメッセージ送信中にエラーが発生しました', e);
    }
    return true;
  }
  // --- ハンドシェイク機能強化ここまで ---

  // テスト用のダミーデータ挿入（開発用） - 既存
  if (request.action === 'injectDummyData' && request.dummyHTML) {
    try {
      const container = document.createElement('div');
      container.id = 'booklight-dummy-container';
      container.innerHTML = request.dummyHTML;
      document.body.appendChild(container);
      sendResponse({ success: true, message: 'ダミーデータを挿入しました' });
    } catch (error) {
      sendResponse({ success: false, message: `ダミーデータの挿入に失敗しました: ${error.message}` });
    }
    return true;
  }

  // 他のメッセージタイプがあればここに追加

  // 未知のアクションの場合は false を返すか、何も返さない
  console.log("Booklight AI: 未知のアクションまたは処理不要:", request.action);
  // return true; // 非同期レスポンスの可能性がある場合は常にtrueを返すのが安全
});

// 初期化メッセージ
console.log('Booklight AI: コンテンツスクリプトが読み込まれました (更新版)');

// バックグラウンドに準備完了を通知
chrome.runtime.sendMessage({ action: "contentScriptReady" }).catch(e => console.warn("Booklight AI: バックグラウンドへの準備完了通知に失敗しました。", e));
console.log("Booklight AI: contentScriptReady メッセージを送信しました");
