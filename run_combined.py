import os
import subprocess
import threading
import time

def run_fastapi():
    os.chdir('api')
    subprocess.run(["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", os.environ.get("API_PORT", "8000")])

def run_streamlit():
    time.sleep(5)  # FastAPIの起動を待つ
    port = os.environ.get("PORT", "8501")
    subprocess.run(["streamlit", "run", "Home.py", "--server.port", port, "--server.address", "0.0.0.0"])

if __name__ == "__main__":
    # FastAPIをバックグラウンドで実行
    fastapi_thread = threading.Thread(target=run_fastapi)
    fastapi_thread.daemon = True
    fastapi_thread.start()
    
    # Streamlitをメインプロセスとして実行
    run_streamlit()
