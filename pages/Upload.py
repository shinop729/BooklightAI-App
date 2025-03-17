import streamlit as st
import pandas as pd
import os
import sys
import shutil
from pathlib import Path

# 親ディレクトリをパスに追加（Homeモジュールをインポートするため）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auth

# ページ設定
st.set_page_config(
    page_title="ハイライトアップロード | Booklight AI", 
    page_icon="📤",
    layout="centered",
    initial_sidebar_state="expanded"
)

# サイドバー設定
st.sidebar.image("images/booklight_ai_banner.png", use_container_width=True)
st.sidebar.title("Booklight AI")
st.sidebar.markdown("📚 あなたの読書をAIが照らす")
st.sidebar.markdown("---")

# サイドバーにログイン/ログアウトボタンを追加
if auth.is_user_authenticated():
    user_info = st.session_state.user_info
    st.sidebar.markdown(f"### ようこそ、{user_info.get('name', 'ユーザー')}さん！")
    st.sidebar.markdown(f"📧 {user_info.get('email', '')}")
    
    if st.sidebar.button("ログアウト"):
        auth.logout()
        st.rerun()  # ページをリロード
else:
    st.sidebar.markdown("### ログイン")
    auth_url = auth.get_google_auth_url()
    if auth_url:
        st.sidebar.markdown(f"[Googleでログイン]({auth_url})")
    else:
        st.sidebar.error("認証設定が不完全です。.envファイルを確認してください。")

# サイドバーナビゲーション
st.sidebar.markdown("---")
st.sidebar.markdown("### ナビゲーション")
st.sidebar.markdown("[🏠 ホーム](Home.py)")
st.sidebar.markdown("[🔍 検索モード](pages/Search.py)")
st.sidebar.markdown("[💬 チャットモード](pages/Chat.py)")
st.sidebar.markdown("[📚 書籍一覧](pages/BookList.py)")
st.sidebar.markdown("[📤 ハイライトアップロード](pages/Upload.py)")

def process_kindle_highlights(file):
    """Kindleハイライトファイルを処理してDataFrameに変換"""
    try:
        # テキストファイルを読み込み
        content = file.getvalue().decode("utf-8")
        
        # 行ごとに分割
        lines = content.split("\n")
        
        # データを格納するリスト
        data = []
        current_book = ""
        current_author = ""
        current_highlight = ""
        
        for line in lines:
            line = line.strip()
            
            # 空行はスキップ
            if not line:
                continue
                
            # 書籍タイトルと著者の行
            if "(" in line and ")" in line and not line.startswith("- "):
                parts = line.split("(")
                if len(parts) >= 2:
                    current_book = parts[0].strip()
                    current_author = parts[1].replace(")", "").strip()
                    current_highlight = ""
                    
            # ハイライト内容の行
            elif line.startswith("- "):
                if current_highlight:  # 前のハイライトがあれば保存
                    data.append({
                        "書籍タイトル": current_book,
                        "著者": current_author,
                        "ハイライト内容": current_highlight
                    })
                
                # 新しいハイライト
                current_highlight = line[2:].strip()
                
            # ハイライトの続き
            else:
                current_highlight += " " + line
        
        # 最後のハイライトを追加
        if current_highlight:
            data.append({
                "書籍タイトル": current_book,
                "著者": current_author,
                "ハイライト内容": current_highlight
            })
        
        # DataFrameに変換
        df = pd.DataFrame(data)
        return df
    
    except Exception as e:
        st.error(f"ファイル処理中にエラーが発生しました: {str(e)}")
        return None

def save_highlights_for_user(df, user_id):
    """ユーザー固有のディレクトリにハイライトを保存"""
    # ユーザーディレクトリのパス
    user_dir = auth.USER_DATA_DIR / "docs" / user_id
    user_dir.mkdir(exist_ok=True)
    
    # CSVファイルとして保存
    csv_path = user_dir / "KindleHighlights.csv"
    df.to_csv(csv_path, index=False)
    
    # テキストファイルとしても保存
    txt_path = user_dir / "KindleHighlights.txt"
    
    with open(txt_path, "w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            f.write(f"{row['書籍タイトル']} ({row['著者']})\n")
            f.write(f"- {row['ハイライト内容']}\n\n")
    
    return csv_path, txt_path

def main():
    st.title("Kindleハイライトのアップロード")
    
    # 認証フローの処理
    auth_success = auth.handle_auth_flow()
    if auth_success:
        st.success("ログインに成功しました！")
        st.rerun()
    
    # ログインしていない場合はログインを促す
    if not auth.is_user_authenticated():
        st.warning("この機能を使用するには、Googleアカウントでログインしてください。")
        st.info("サイドバーの「Googleでログイン」ボタンからログインできます。")
        return
    
    # ユーザー情報
    user_id = auth.get_current_user_id()
    user_name = st.session_state.user_info.get("name", "ユーザー")
    
    st.write(f"### {user_name}さんのKindleハイライト")
    
    # ファイルアップロード
    st.write("#### ハイライトファイルのアップロード")
    st.write("Kindleアプリからエクスポートしたハイライトファイル（.txt）をアップロードしてください。")
    
    uploaded_file = st.file_uploader("Kindleハイライトファイル（.txt）を選択", type=["txt"])
    
    if uploaded_file is not None:
        # ファイルを処理
        df = process_kindle_highlights(uploaded_file)
        
        if df is not None and not df.empty:
            # プレビュー表示
            st.write(f"#### プレビュー（{len(df)}件のハイライト）")
            st.dataframe(df)
            
            # 保存ボタン
            if st.button("ハイライトを保存"):
                csv_path, txt_path = save_highlights_for_user(df, user_id)
                st.success(f"ハイライトを保存しました！")
                st.info(f"保存先: {csv_path}")
                
                # 既存のハイライトとの統合オプション
                st.write("#### 既存のハイライトとの統合")
                st.write("アップロードしたハイライトは、あなた専用のフォルダに保存されました。")
                st.write("ホームページやその他の機能では、あなた専用のハイライトが使用されます。")
        else:
            st.error("ハイライトの抽出に失敗しました。ファイル形式を確認してください。")
    
    # 既存のハイライト表示
    user_highlights_path = auth.USER_DATA_DIR / "docs" / user_id / "KindleHighlights.csv"
    if user_highlights_path.exists():
        st.write("#### 現在保存されているハイライト")
        df_existing = pd.read_csv(user_highlights_path)
        st.write(f"{len(df_existing)}件のハイライトが保存されています。")
        
        if st.checkbox("保存済みハイライトを表示"):
            st.dataframe(df_existing)
    else:
        st.info("まだハイライトが保存されていません。上記のフォームからアップロードしてください。")

if __name__ == "__main__":
    main()
