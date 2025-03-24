#!/usr/bin/env node

/**
 * クロスブラウザテスト用スクリプト
 * 
 * このスクリプトは、異なるブラウザでアプリケーションを起動し、
 * 基本的な機能が正しく動作することを確認するためのものです。
 * 
 * 使用方法:
 * node scripts/browser-test.js
 */

const { exec } = require('child_process');
const readline = require('readline');
const os = require('os');

// 利用可能なブラウザのリスト
const BROWSERS = {
  chrome: {
    name: 'Google Chrome',
    darwin: 'open -a "Google Chrome" http://localhost:5173',
    win32: 'start chrome http://localhost:5173',
    linux: 'google-chrome http://localhost:5173'
  },
  firefox: {
    name: 'Mozilla Firefox',
    darwin: 'open -a "Firefox" http://localhost:5173',
    win32: 'start firefox http://localhost:5173',
    linux: 'firefox http://localhost:5173'
  },
  safari: {
    name: 'Safari',
    darwin: 'open -a "Safari" http://localhost:5173',
    win32: null,
    linux: null
  },
  edge: {
    name: 'Microsoft Edge',
    darwin: 'open -a "Microsoft Edge" http://localhost:5173',
    win32: 'start msedge http://localhost:5173',
    linux: 'microsoft-edge http://localhost:5173'
  }
};

// 現在のプラットフォーム
const platform = os.platform();

// 利用可能なブラウザを取得
const getAvailableBrowsers = () => {
  return Object.entries(BROWSERS)
    .filter(([_, browser]) => browser[platform])
    .map(([key, browser]) => ({ key, name: browser.name }));
};

// ブラウザを起動
const launchBrowser = (browserKey) => {
  const browser = BROWSERS[browserKey];
  if (!browser || !browser[platform]) {
    console.error(`${browser?.name || browserKey} はこのプラットフォームでサポートされていません。`);
    return false;
  }

  const command = browser[platform];
  console.log(`${browser.name} でアプリケーションを起動しています...`);
  
  exec(command, (error) => {
    if (error) {
      console.error(`エラー: ${error.message}`);
      return false;
    }
  });
  
  return true;
};

// テストチェックリストを表示
const showTestChecklist = () => {
  console.log('\n===== テストチェックリスト =====');
  console.log('以下の機能が正しく動作することを確認してください:');
  console.log('1. ログイン/認証');
  console.log('2. ホームページの表示');
  console.log('3. 書籍一覧の表示とページネーション');
  console.log('4. 書籍詳細の表示');
  console.log('5. 検索機能');
  console.log('6. チャット機能');
  console.log('7. ファイルアップロード');
  console.log('8. レスポンシブデザイン（ブラウザサイズを変更して確認）');
  console.log('9. オフライン機能（ネットワーク接続を切断して確認）');
  console.log('==============================\n');
};

// メイン関数
const main = async () => {
  const availableBrowsers = getAvailableBrowsers();
  
  if (availableBrowsers.length === 0) {
    console.error('サポートされているブラウザが見つかりませんでした。');
    process.exit(1);
  }
  
  console.log('クロスブラウザテストツール');
  console.log('このツールは、異なるブラウザでアプリケーションをテストするためのものです。\n');
  
  console.log('利用可能なブラウザ:');
  availableBrowsers.forEach((browser, index) => {
    console.log(`${index + 1}. ${browser.name}`);
  });
  
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });
  
  rl.question('\n使用するブラウザの番号を入力してください: ', (answer) => {
    const index = parseInt(answer, 10) - 1;
    
    if (isNaN(index) || index < 0 || index >= availableBrowsers.length) {
      console.error('無効な選択です。');
      rl.close();
      return;
    }
    
    const selectedBrowser = availableBrowsers[index];
    const success = launchBrowser(selectedBrowser.key);
    
    if (success) {
      showTestChecklist();
    }
    
    rl.close();
  });
};

// スクリプトの実行
main().catch(error => {
  console.error('エラーが発生しました:', error);
  process.exit(1);
});
