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
        # Herokuでは内部的にAPI用のポートを設定
        api_port = os.environ.get("API_PORT", "8000")
        print(f"Heroku環境でFastAPIを起動: ポート {api_port}")
    else:
        # ローカル環境ではデフォルトポートを使用
        api_port = os.environ.get("API_PORT", "8000")
        print(f"ローカル環境でFastAPIを起動: ポート {api_port}")
    
    subprocess.run(["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", api_port])

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
    
    # Herokuの場合はPORT環境変数を使用
    is_heroku = os.getenv("DYNO") is not None
    if is_heroku:
        # Herokuでは環境変数PORTを使用する必要がある
        port = os.environ.get("PORT", "8501")
        print(f"Heroku環境でStreamlitを起動: ポート {port}")
    else:
        # ローカル環境ではデフォルトポートを使用
        port = os.environ.get("PORT", "8501")
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
    
    # FastAPIをバックグラウンドで実行
    fastapi_thread = threading.Thread(target=run_fastapi)
    fastapi_thread.daemon = True
    fastapi_thread.start()
    
    # Streamlitをメインプロセスとして実行
    run_streamlit()
