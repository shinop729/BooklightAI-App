#!/usr/bin/env node

/**
 * アクセシビリティチェックスクリプト
 * 
 * このスクリプトは、アプリケーションのアクセシビリティを評価し、
 * 改善点を特定するためのものです。
 * 
 * 使用方法:
 * node scripts/accessibility-check.js
 * 
 * 必要なパッケージ:
 * npm install -D axe-core puppeteer
 */

const puppeteer = require('puppeteer');
const { AxePuppeteer } = require('@axe-core/puppeteer');
const { writeFileSync, mkdirSync, existsSync } = require('fs');
const { join } = require('path');

// チェック対象のページ
const PAGES = [
  { name: 'ホーム', path: '/' },
  { name: '書籍一覧', path: '/books' },
  { name: '検索', path: '/search' },
  { name: 'チャット', path: '/chat' },
  { name: 'アップロード', path: '/upload' }
];

// 結果の保存先ディレクトリ
const RESULTS_DIR = join(__dirname, '../accessibility-reports');

// 結果ディレクトリの作成
const ensureResultsDir = () => {
  if (!existsSync(RESULTS_DIR)) {
    mkdirSync(RESULTS_DIR, { recursive: true });
  }
};

// 日付フォーマット
const formatDate = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}-${String(now.getMinutes()).padStart(2, '0')}`;
};

// アクセシビリティチェックの実行
const runAccessibilityCheck = async () => {
  console.log('アクセシビリティチェックを開始します...');
  
  // 結果ディレクトリの作成
  ensureResultsDir();
  
  // 日付フォルダの作成
  const dateStr = formatDate();
  const reportDir = join(RESULTS_DIR, dateStr);
  if (!existsSync(reportDir)) {
    mkdirSync(reportDir, { recursive: true });
  }
  
  // Puppeteerの起動
  const browser = await puppeteer.launch({
    headless: 'new',
    defaultViewport: { width: 1280, height: 800 }
  });
  
  // サマリーレポート用のデータ
  const summaryData = [];
  
  // 各ページのチェック
  for (const page of PAGES) {
    console.log(`"${page.name}" ページをチェック中...`);
    
    const url = `http://localhost:5173${page.path}`;
    
    try {
      // ページの読み込み
      const puppeteerPage = await browser.newPage();
      await puppeteerPage.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
      
      // axe-coreによるチェック
      const results = await new AxePuppeteer(puppeteerPage).analyze();
      
      // 結果の集計
      const summary = {
        page: page.name,
        path: page.path,
        violations: results.violations.length,
        passes: results.passes.length,
        incomplete: results.incomplete.length,
        inapplicable: results.inapplicable.length,
        violationsByImpact: {
          critical: results.violations.filter(v => v.impact === 'critical').length,
          serious: results.violations.filter(v => v.impact === 'serious').length,
          moderate: results.violations.filter(v => v.impact === 'moderate').length,
          minor: results.violations.filter(v => v.impact === 'minor').length
        }
      };
      
      // サマリーデータに追加
      summaryData.push(summary);
      
      // 詳細レポートの保存
      const reportPath = join(reportDir, `${page.name.replace(/\s+/g, '-').toLowerCase()}.json`);
      writeFileSync(reportPath, JSON.stringify(results, null, 2));
      
      console.log(`"${page.name}" のチェックが完了しました`);
      console.log(`違反: ${summary.violations} (重大: ${summary.violationsByImpact.critical}, 深刻: ${summary.violationsByImpact.serious})`);
      console.log(`合格: ${summary.passes}`);
      console.log('-----------------------------------');
      
      // ページを閉じる
      await puppeteerPage.close();
    } catch (error) {
      console.error(`"${page.name}" のチェック中にエラーが発生しました:`, error);
    }
  }
  
  // サマリーレポートの作成
  const summaryPath = join(reportDir, 'summary.json');
  writeFileSync(summaryPath, JSON.stringify(summaryData, null, 2));
  
  // HTMLサマリーレポートの作成
  const htmlSummary = generateHtmlSummary(summaryData, dateStr);
  const htmlSummaryPath = join(reportDir, 'summary.html');
  writeFileSync(htmlSummaryPath, htmlSummary);
  
  // ブラウザの終了
  await browser.close();
  
  console.log('\nアクセシビリティチェックが完了しました');
  console.log(`レポートは ${reportDir} に保存されました`);
};

// HTMLサマリーレポートの生成
const generateHtmlSummary = (data, dateStr) => {
  const rows = data.map(item => `
    <tr>
      <td>${item.page}</td>
      <td>${item.path}</td>
      <td class="${getViolationClass(item.violations)}">${item.violations}</td>
      <td class="${getViolationClass(item.violationsByImpact.critical)}">${item.violationsByImpact.critical}</td>
      <td class="${getViolationClass(item.violationsByImpact.serious)}">${item.violationsByImpact.serious}</td>
      <td class="${getViolationClass(item.violationsByImpact.moderate)}">${item.violationsByImpact.moderate}</td>
      <td class="${getViolationClass(item.violationsByImpact.minor)}">${item.violationsByImpact.minor}</td>
      <td class="passes">${item.passes}</td>
    </tr>
  `).join('');
  
  return `
    <!DOCTYPE html>
    <html lang="ja">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>アクセシビリティチェックサマリー - ${dateStr}</title>
      <style>
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
          line-height: 1.6;
          color: #333;
          max-width: 1200px;
          margin: 0 auto;
          padding: 20px;
        }
        h1 {
          color: #2c3e50;
          border-bottom: 2px solid #eee;
          padding-bottom: 10px;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          margin: 20px 0;
        }
        th, td {
          padding: 12px 15px;
          text-align: left;
          border-bottom: 1px solid #ddd;
        }
        th {
          background-color: #f8f9fa;
          font-weight: bold;
        }
        tr:hover {
          background-color: #f5f5f5;
        }
        .violation-0 {
          color: #28a745;
          font-weight: bold;
        }
        .violation-low {
          color: #ffc107;
          font-weight: bold;
        }
        .violation-high {
          color: #dc3545;
          font-weight: bold;
        }
        .passes {
          color: #28a745;
        }
        .summary {
          margin-top: 30px;
          padding: 15px;
          background-color: #f8f9fa;
          border-radius: 5px;
        }
        .wcag-list {
          column-count: 2;
          column-gap: 20px;
        }
        @media (max-width: 768px) {
          .wcag-list {
            column-count: 1;
          }
        }
      </style>
    </head>
    <body>
      <h1>アクセシビリティチェックサマリー</h1>
      <p>実行日時: ${dateStr.replace('_', ' ')}</p>
      
      <table>
        <thead>
          <tr>
            <th>ページ</th>
            <th>パス</th>
            <th>違反合計</th>
            <th>重大</th>
            <th>深刻</th>
            <th>中程度</th>
            <th>軽微</th>
            <th>合格</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
      
      <div class="summary">
        <h2>アクセシビリティ改善のヒント</h2>
        <p>以下のWCAG 2.1ガイドラインに基づいて改善を検討してください：</p>
        
        <div class="wcag-list">
          <ul>
            <li><strong>知覚可能性</strong>
              <ul>
                <li>テキスト以外のコンテンツに代替テキストを提供する</li>
                <li>時間依存メディアに代替手段を提供する</li>
                <li>コンテンツを様々な方法で提示できるようにする</li>
                <li>ユーザーがコンテンツを見やすく、聞きやすくする</li>
              </ul>
            </li>
            <li><strong>操作可能性</strong>
              <ul>
                <li>すべての機能をキーボードから利用できるようにする</li>
                <li>ユーザーがコンテンツを読み、使用するのに十分な時間を提供する</li>
                <li>発作を引き起こすようなコンテンツを設計しない</li>
                <li>ユーザーがナビゲートし、コンテンツを見つけるのを助ける</li>
              </ul>
            </li>
            <li><strong>理解可能性</strong>
              <ul>
                <li>テキストコンテンツを読みやすく、理解しやすくする</li>
                <li>ウェブページの外観と操作を予測可能にする</li>
                <li>ユーザーが間違いを回避し、修正できるよう支援する</li>
              </ul>
            </li>
            <li><strong>堅牢性</strong>
              <ul>
                <li>支援技術を含む現在および将来のユーザーエージェントとの互換性を最大化する</li>
              </ul>
            </li>
          </ul>
        </div>
        
        <p>詳細な分析は各ページの個別レポートを参照してください。</p>
      </div>
    </body>
    </html>
  `;
};

// 違反数に基づくCSSクラスの取得
const getViolationClass = (count) => {
  if (count === 0) return 'violation-0';
  if (count < 3) return 'violation-low';
  return 'violation-high';
};

// メイン関数
const main = async () => {
  try {
    await runAccessibilityCheck();
  } catch (error) {
    console.error('チェック中にエラーが発生しました:', error);
    process.exit(1);
  }
};

// スクリプトの実行
main();
