import os
import subprocess
import threading
import time

def run_fastapi():
    # APIディレクトリに移動
    os.chdir('api')
    
    # Herokuの場合はPORT環境変数を使用
    is_heroku = os.getenv("DYNO") is not None
    if is_heroku:
        # Herokuでは環境変数PORTを使用する必要がある
        port = os.environ.get("PORT", "8000")
        print(f"Heroku環境でFastAPIを起動: ポート {port}")
        
        # デバッグ情報
        print(f"環境変数:")
        print(f"  DYNO: {os.getenv('DYNO')}")
        print(f"  PORT: {os.environ.get('PORT')}")
        print(f"  API_PORT: {os.environ.get('API_PORT')}")
        print(f"  HEROKU_APP_NAME: {os.getenv('HEROKU_APP_NAME')}")
        print(f"  FRONTEND_URL: {os.getenv('FRONTEND_URL')}")
        print(f"  REDIRECT_URI: {os.getenv('REDIRECT_URI')}")
    else:
        # ローカル環境ではデフォルトポートを使用
        port = os.environ.get("API_PORT", "8000")
        print(f"ローカル環境でFastAPIを起動: ポート {port}")
    
    # FastAPIを起動（--root-pathを追加してルーティングを設定）
    subprocess.run(["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port])

def run_streamlit():
    time.sleep(5)  # FastAPIの起動を待つ
    
    # ルートディレクトリに戻る（重要な修正点）
    os.chdir('..')
    
    # デバッグ情報
    current_dir = os.getcwd()
    print(f"現在のディレクトリ: {current_dir}")
    print("ディレクトリ内のファイル:")
    for file in os.listdir(current_dir):
        print(f" - {file}")
    
    # ポート設定
    is_heroku = os.getenv("DYNO") is not None
    if is_heroku:
        # Heroku環境では、FastAPIと同じポートを使用する
        port = os.environ.get("PORT", "8000")
        print(f"Heroku環境でStreamlitを起動: ポート {port}")
    else:
        # ローカル環境ではデフォルトポートを使用
        port = "8501"
        print(f"ローカル環境でStreamlitを起動: ポート {port}")
    
    # FRONTEND_URL環境変数を設定（認証コールバック用）
    if is_heroku:
        app_name = os.getenv("HEROKU_APP_NAME", "")
        if app_name:
            os.environ["FRONTEND_URL"] = f"https://{app_name}.herokuapp.com"
            print(f"FRONTEND_URL設定: {os.environ['FRONTEND_URL']}")
    
    subprocess.run(["streamlit", "run", "Home.py", "--server.port", port, "--server.address", "0.0.0.0"])

if __name__ == "__main__":
    # 現在のディレクトリを保存
    root_dir = os.getcwd()
    
    is_heroku = os.getenv("DYNO") is not None
    if is_heroku:
        # Heroku環境でも両方実行
        # FastAPIをバックグラウンドで実行
        fastapi_thread = threading.Thread(target=run_fastapi)
        fastapi_thread.daemon = True
        fastapi_thread.start()
        
        # Streamlitをメインプロセスとして実行
        run_streamlit()
    else:
        # 開発環境では両方実行
        # FastAPIをバックグラウンドで実行
        fastapi_thread = threading.Thread(target=run_fastapi)
        fastapi_thread.daemon = True
        fastapi_thread.start()
        
        # Streamlitをメインプロセスとして実行
        run_streamlit()
