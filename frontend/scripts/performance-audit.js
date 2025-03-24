#!/usr/bin/env node

/**
 * パフォーマンス監査スクリプト
 * 
 * このスクリプトは、アプリケーションのパフォーマンスを測定し、
 * 改善点を特定するためのものです。
 * 
 * 使用方法:
 * node scripts/performance-audit.js
 * 
 * 必要なパッケージ:
 * npm install -D lighthouse puppeteer
 */

const lighthouse = require('lighthouse');
const puppeteer = require('puppeteer');
const { writeFileSync, mkdirSync, existsSync } = require('fs');
const { join } = require('path');

// 監査対象のページ
const PAGES = [
  { name: 'ホーム', path: '/' },
  { name: '書籍一覧', path: '/books' },
  { name: '検索', path: '/search' },
  { name: 'チャット', path: '/chat' },
  { name: 'アップロード', path: '/upload' }
];

// 結果の保存先ディレクトリ
const RESULTS_DIR = join(__dirname, '../performance-reports');

// Lighthouseの設定
const LIGHTHOUSE_OPTIONS = {
  logLevel: 'info',
  output: 'html',
  onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'],
  port: 0
};

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

// パフォーマンス監査の実行
const runAudit = async () => {
  console.log('パフォーマンス監査を開始します...');
  
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
  
  // 各ページの監査
  for (const page of PAGES) {
    console.log(`"${page.name}" ページを監査中...`);
    
    const url = `http://localhost:5173${page.path}`;
    
    try {
      // Lighthouseの実行
      const { lhr } = await lighthouse(url, LIGHTHOUSE_OPTIONS, null);
      
      // スコアの取得
      const scores = {
        performance: lhr.categories.performance.score * 100,
        accessibility: lhr.categories.accessibility.score * 100,
        bestPractices: lhr.categories['best-practices'].score * 100,
        seo: lhr.categories.seo.score * 100
      };
      
      // サマリーデータに追加
      summaryData.push({
        page: page.name,
        path: page.path,
        ...scores
      });
      
      // HTMLレポートの保存
      const reportPath = join(reportDir, `${page.name.replace(/\s+/g, '-').toLowerCase()}.html`);
      writeFileSync(reportPath, lhr.report);
      
      console.log(`"${page.name}" の監査が完了しました`);
      console.log(`パフォーマンス: ${scores.performance.toFixed(0)}%`);
      console.log(`アクセシビリティ: ${scores.accessibility.toFixed(0)}%`);
      console.log(`ベストプラクティス: ${scores.bestPractices.toFixed(0)}%`);
      console.log(`SEO: ${scores.seo.toFixed(0)}%`);
      console.log('-----------------------------------');
    } catch (error) {
      console.error(`"${page.name}" の監査中にエラーが発生しました:`, error);
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
  
  console.log('\nパフォーマンス監査が完了しました');
  console.log(`レポートは ${reportDir} に保存されました`);
};

// HTMLサマリーレポートの生成
const generateHtmlSummary = (data, dateStr) => {
  const rows = data.map(item => `
    <tr>
      <td>${item.page}</td>
      <td>${item.path}</td>
      <td class="${getScoreClass(item.performance)}">${item.performance.toFixed(0)}%</td>
      <td class="${getScoreClass(item.accessibility)}">${item.accessibility.toFixed(0)}%</td>
      <td class="${getScoreClass(item.bestPractices)}">${item.bestPractices.toFixed(0)}%</td>
      <td class="${getScoreClass(item.seo)}">${item.seo.toFixed(0)}%</td>
    </tr>
  `).join('');
  
  return `
    <!DOCTYPE html>
    <html lang="ja">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>パフォーマンス監査サマリー - ${dateStr}</title>
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
        .score-good {
          color: #28a745;
          font-weight: bold;
        }
        .score-average {
          color: #ffc107;
          font-weight: bold;
        }
        .score-poor {
          color: #dc3545;
          font-weight: bold;
        }
        .summary {
          margin-top: 30px;
          padding: 15px;
          background-color: #f8f9fa;
          border-radius: 5px;
        }
      </style>
    </head>
    <body>
      <h1>パフォーマンス監査サマリー</h1>
      <p>実行日時: ${dateStr.replace('_', ' ')}</p>
      
      <table>
        <thead>
          <tr>
            <th>ページ</th>
            <th>パス</th>
            <th>パフォーマンス</th>
            <th>アクセシビリティ</th>
            <th>ベストプラクティス</th>
            <th>SEO</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
      
      <div class="summary">
        <h2>改善のヒント</h2>
        <ul>
          <li><strong>パフォーマンス</strong>: 画像の最適化、不要なJavaScriptの削減、レンダリングブロッキングリソースの最小化</li>
          <li><strong>アクセシビリティ</strong>: 適切なコントラスト比、ARIA属性の正しい使用、キーボードナビゲーションの確保</li>
          <li><strong>ベストプラクティス</strong>: HTTPSの使用、適切なエラーハンドリング、最新のブラウザAPIの使用</li>
          <li><strong>SEO</strong>: 適切なメタタグ、レスポンシブデザイン、構造化データの使用</li>
        </ul>
        <p>詳細な分析は各ページの個別レポートを参照してください。</p>
      </div>
    </body>
    </html>
  `;
};

// スコアに基づくCSSクラスの取得
const getScoreClass = (score) => {
  if (score >= 90) return 'score-good';
  if (score >= 70) return 'score-average';
  return 'score-poor';
};

// メイン関数
const main = async () => {
  try {
    await runAudit();
  } catch (error) {
    console.error('監査中にエラーが発生しました:', error);
    process.exit(1);
  }
};

// スクリプトの実行
main();
