#!/usr/bin/env node

/**
 * テスト依存関係インストールスクリプト
 * 
 * このスクリプトは、テストに必要なパッケージをインストールします。
 * 
 * 使用方法:
 * node scripts/install-test-deps.js
 */

const { execSync } = require('child_process');
const readline = require('readline');

// インストールするパッケージ
const PACKAGES = [
  { name: 'lighthouse', dev: true },
  { name: 'puppeteer', dev: true },
  { name: 'axe-core', dev: true },
  { name: '@axe-core/puppeteer', dev: true }
];

// パッケージのインストール
const installPackages = () => {
  console.log('テスト用パッケージをインストールしています...\n');
  
  for (const pkg of PACKAGES) {
    const command = `npm install ${pkg.dev ? '-D' : ''} ${pkg.name}`;
    console.log(`実行: ${command}`);
    
    try {
      execSync(command, { stdio: 'inherit' });
      console.log(`✅ ${pkg.name} のインストールが完了しました`);
    } catch (error) {
      console.error(`❌ ${pkg.name} のインストールに失敗しました:`, error.message);
      return false;
    }
    
    console.log('-----------------------------------');
  }
  
  return true;
};

// メイン関数
const main = () => {
  console.log('テスト依存関係インストーラー');
  console.log('このスクリプトは、テストに必要なパッケージをインストールします。\n');
  
  console.log('インストールするパッケージ:');
  PACKAGES.forEach(pkg => {
    console.log(`- ${pkg.name} (${pkg.dev ? 'devDependency' : 'dependency'})`);
  });
  
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });
  
  rl.question('\nインストールを続行しますか？ (y/n): ', (answer) => {
    if (answer.toLowerCase() === 'y') {
      const success = installPackages();
      
      if (success) {
        console.log('\nすべてのパッケージのインストールが完了しました。');
        console.log('以下のコマンドでテストを実行できます:');
        console.log('- npm run test:browser - クロスブラウザテスト');
        console.log('- npm run test:performance - パフォーマンス監査');
        console.log('- npm run test:accessibility - アクセシビリティチェック');
        console.log('- npm run test:all - すべてのテストを実行');
      } else {
        console.error('\nパッケージのインストール中にエラーが発生しました。');
      }
    } else {
      console.log('インストールをキャンセルしました。');
    }
    
    rl.close();
  });
};

// スクリプトの実行
main();
