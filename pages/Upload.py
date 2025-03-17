import streamlit as st
import pandas as pd
import os
import sys
import shutil
from pathlib import Path

# 親ディレクトリをパスに追加（Homeモジュールをインポートするため）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auth
from book_summary_generator import BookSummaryGenerator

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
        # ファイル名から拡張子を取得
        file_name = file.name.lower()
        
        # CSVファイルの場合
        if file_name.endswith('.csv'):
            # pandasのread_csvを使用して直接CSVを解析
            df = pd.read_csv(file, encoding="utf-8")
            
            # 必要なカラムが存在するか確認
            required_columns = ["書籍タイトル", "著者", "ハイライト内容"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.warning(f"CSVファイルに以下のカラムがありません: {', '.join(missing_columns)}")
                st.info("CSVファイルには「書籍タイトル」「著者」「ハイライト内容」の3つのカラムが必要です。")
                return None
                
            return df
            
        # テキストファイルの場合
        else:
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

def generate_book_summaries(df, user_id, update_progress=None):
    """ハイライトから書籍ごとのサマリを生成して保存"""
    try:
        # 処理開始メッセージ
        st.info("サマリ生成処理を開始します...")
        
        # APIキーの確認
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            st.error("OpenAI APIキーが設定されていません。.envファイルを確認してください。")
            return None
        
        # BookSummaryGeneratorのインスタンスを作成
        st.info("BookSummaryGeneratorを初期化中...")
        generator = BookSummaryGenerator(api_key=api_key)
        
        # 書籍数の確認
        book_count = len(df.groupby(["書籍タイトル", "著者"]))
        st.info(f"合計 {book_count} 冊の書籍のサマリを生成します。この処理には数分かかる場合があります。")
        
        # サマリを生成して保存
        st.info("サマリ生成処理を実行中...")
        summary_path = generator.generate_and_save_summaries(df, user_id, update_progress)
        
        # 成功メッセージ
        st.success(f"サマリ生成が完了しました！")
        return summary_path
    except Exception as e:
        st.error(f"サマリ生成中にエラーが発生しました: {str(e)}")
        import traceback
        st.error(f"詳細エラー: {traceback.format_exc()}")
        return None

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
    st.write("Kindleアプリからエクスポートしたハイライトファイル（.txt）またはCSVファイル（.csv）をアップロードしてください。")
    
    uploaded_file = st.file_uploader("ハイライトファイルを選択", type=["txt", "csv"])
    
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
                
                # 書籍数を取得
                book_count = len(df.groupby(["書籍タイトル", "著者"]))
                
                # セッション状態に進捗情報を初期化
                st.session_state.summary_generation_active = True
                st.session_state.summary_progress = 0
                st.session_state.summary_current = 0
                st.session_state.summary_total = book_count
                st.session_state.summary_current_book = ""
                st.session_state.summary_status = "処理中"
                
                # サマリ生成の進捗状況を表示するためのプレースホルダー
                summary_status = st.empty()
                summary_status.info("書籍ごとのサマリを生成中です。これには数分かかる場合があります...")
                
                # プログレスバーを表示
                progress_bar = st.progress(0)
                
                # 進捗状況を更新するコールバック関数
                def update_progress(current, total, book_title):
                    progress = current / total
                    # セッション状態を更新
                    st.session_state.summary_progress = progress
                    st.session_state.summary_current = current
                    st.session_state.summary_total = total
                    st.session_state.summary_current_book = book_title
                    
                    # UIを更新
                    progress_bar.progress(progress)
                    percent = int(progress * 100)
                    summary_status.info(f"書籍ごとのサマリを生成中です... {percent}% ({current}/{total} 冊完了)")
                    st.caption(f"現在処理中: 「{book_title}」")
                
                # サマリ生成処理の実行
                with st.spinner("サマリ生成中..."):
                    # 進捗状況を更新するコールバック関数を渡す
                    summary_path = generate_book_summaries(df, user_id, update_progress)
                
                if summary_path:
                    # 完了状態を設定
                    st.session_state.summary_status = "完了"
                    st.session_state.summary_progress = 1.0
                    
                    summary_status.success(f"書籍ごとのサマリを生成しました！")
                    st.info(f"サマリ保存先: {summary_path}")
                    
                    # 生成されたサマリの確認
                    if Path(summary_path).exists():
                        try:
                            summary_df = pd.read_csv(summary_path)
                            st.success(f"{len(summary_df)}冊の書籍のサマリが正常に生成されました。")
                            
                            # サマリの一部を表示
                            if not summary_df.empty:
                                with st.expander("生成されたサマリのサンプル"):
                                    sample_book = summary_df.iloc[0]
                                    st.write(f"**書籍タイトル**: {sample_book['書籍タイトル']}")
                                    st.write(f"**著者**: {sample_book['著者']}")
                                    st.write(f"**要約**:\n{sample_book['要約'][:500]}...")
                        except Exception as e:
                            st.error(f"サマリファイルの読み込み中にエラーが発生しました: {e}")
                    else:
                        st.error(f"サマリファイルが見つかりません: {summary_path}")
                else:
                    # エラー状態を設定
                    st.session_state.summary_status = "エラー"
                    summary_status.error("サマリの生成に失敗しました。")
                
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
