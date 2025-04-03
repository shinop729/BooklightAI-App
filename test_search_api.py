"""
検索APIをテストするスクリプト

このスクリプトは、検索APIを直接呼び出して結果を確認します。
"""

import requests
import json
import sys

# APIのベースURL
BASE_URL = "http://localhost:8000"

# テスト用のトークン（開発環境用）
DEV_TOKEN = "dev-token-123"

def test_search(keyword):
    """
    検索APIをテストする
    
    Args:
        keyword: 検索キーワード
    """
    # リクエストURL
    url = f"{BASE_URL}/api/search"
    
    # リクエストヘッダー
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEV_TOKEN}"
    }
    
    # リクエストボディ
    data = {
        "keywords": [keyword],
        "hybrid_alpha": 0.7,
        "book_weight": 0.3,
        "use_expanded": True,
        "limit": 30
    }
    
    # リクエスト送信
    try:
        response = requests.post(url, headers=headers, json=data)
        
        # レスポンスの確認
        if response.status_code == 200:
            result = response.json()
            print(f"ステータス: {result.get('success')}")
            
            if result.get('success'):
                data = result.get('data', {})
                results = data.get('results', [])
                total = data.get('total', 0)
                
                print(f"検索結果: {total}件")
                
                # 結果の詳細を表示
                for i, item in enumerate(results, 1):
                    print(f"\n--- 結果 {i} ---")
                    print(f"スコア: {item.get('score')}")
                    print(f"書籍: {item.get('book_title')} ({item.get('book_author')})")
                    print(f"内容: {item.get('content')[:100]}...")
            else:
                print(f"エラー: {result.get('detail')}")
        else:
            print(f"APIエラー: ステータスコード {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    # コマンドライン引数からキーワードを取得
    keyword = "戦略"
    if len(sys.argv) > 1:
        keyword = sys.argv[1]
    
    print(f"キーワード「{keyword}」で検索します...")
    test_search(keyword)
