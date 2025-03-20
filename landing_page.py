import streamlit as st
import os
from dotenv import load_dotenv
import auth

def local_css(file_name):
    """Load and inject a local CSS file into the Streamlit app"""
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def setup_app():
    """アプリの基本設定"""
    load_dotenv()
    
    st.set_page_config(page_title="Booklight AI", layout="wide")
    
    # CSSの読み込み
    if os.path.exists("style.css"):
        local_css("style.css")

def main():
    setup_app()
    
    # ユーザーディレクトリの作成
    auth.create_user_directories()
    
    # 認証フローの処理
    auth_success = auth.handle_auth_flow()
    if auth_success:
        st.success("ログインに成功しました！")
        # ログイン成功時はページをリロード
        st.rerun()
    
    # ログイン状態のチェック
    if auth.is_user_authenticated():
        # ログイン済みの場合はログイン後のコンテンツを表示
        user_info = st.session_state.user_info
        
        # サイドバーにログイン情報とナビゲーションを表示
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"### ようこそ、{user_info.get('name', 'ユーザー')}さん！")
        st.sidebar.markdown(f"📧 {user_info.get('email', '')}")
        
        if st.sidebar.button("ログアウト"):
            auth.logout()
            st.rerun()  # ページをリロード
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("[🔍 検索モード](pages/Search.py)")
        st.sidebar.markdown("[💬 チャットモード](pages/Chat.py)")
        st.sidebar.markdown("[📚 書籍一覧](pages/BookList.py)")
        st.sidebar.markdown("[📤 ハイライトアップロード](pages/Upload.py)")
        
        # メインコンテンツ
        user_id = auth.get_current_user_id()
        st.title(f"{user_info.get('name', 'ユーザー')}さんのBooklight AI")
        st.info("ログイン中です。あなた専用のハイライトデータが表示されます。")
        
        # ここにログイン後のコンテンツを表示
        st.success("ログインに成功しました！以下のメニューからご利用ください：")
        
        # 機能へのリンクを表示
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 🔍 検索")
            st.markdown("ハイライトを検索します")
            st.link_button("検索ページへ", "pages/Search.py", use_container_width=True)
        
        with col2:
            st.markdown("### 💬 チャット")
            st.markdown("AIとチャットします")
            st.link_button("チャットページへ", "pages/Chat.py", use_container_width=True)
        
        with col3:
            st.markdown("### 📚 書籍一覧")
            st.markdown("書籍の一覧を表示します")
            st.link_button("書籍一覧ページへ", "pages/BookList.py", use_container_width=True)
        
        return
    
    # ヘッダーセクション
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0;">
        <h1 style="color: #4A90E2; font-size: 3rem;">Booklight AI</h1>
        <p style="font-size: 1.5rem; margin-top: 1rem;">📚 あなたの読書をAIが照らす</p>
    </div>
    """, unsafe_allow_html=True)
    
    # メイン説明セクション
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("""
        ## Booklight AIとは？
        
        Booklight AIは、あなたのKindleハイライトを自動的に収集し、AIを活用して新しい視点から読書体験を豊かにするサービスです。
        
        ### 主な機能
        
        - **ハイライト自動収集**: Chromeエクステンションで簡単にハイライトを収集
        - **AI検索**: 自然言語でハイライトを検索
        - **AIチャット**: ハイライトの内容についてAIと対話
        - **書籍サマリー**: AIによる書籍の要約生成
        """)
        
        # ログインボタン
        st.markdown("### サービスを利用する")
        auth_url = auth.get_google_auth_url()
        if auth_url:
            st.link_button("Googleでログイン", auth_url, use_container_width=True)
        else:
            st.error("認証設定が不完全です。管理者にお問い合わせください。")
    
    with col2:
        # サービスイメージ画像
        if os.path.exists("images/booklight_ai_banner.png"):
            st.image("images/booklight_ai_banner.png", use_container_width=True)
    
    # 機能詳細セクション
    st.markdown("---")
    st.markdown("## 機能詳細")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 🔍 AI検索
        
        自然言語でハイライトを検索できます。「創造性について書かれた部分」のような抽象的な検索も可能です。
        """)
    
    with col2:
        st.markdown("""
        ### 💬 AIチャット
        
        あなたの読書内容についてAIと対話できます。理解を深めたり、新しい視点を得たりするのに役立ちます。
        """)
    
    with col3:
        st.markdown("""
        ### 📚 書籍サマリー
        
        AIがハイライトから書籍の要点をまとめます。読書の振り返りや復習に最適です。
        """)
    
    # フッターセクション
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0;">
        <p>© 2025 Booklight AI</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
