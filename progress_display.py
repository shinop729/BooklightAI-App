import streamlit as st

def display_summary_progress_in_sidebar():
    """
    サマリ生成の進捗状況をサイドバーに表示する関数
    この関数は各ページで呼び出すことで、ページ間を移動しても進捗状況を確認できる
    """
    # セッション状態に進捗情報がある場合のみ表示
    if "summary_generation_active" in st.session_state and st.session_state.summary_generation_active:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### サマリ生成状況")
        
        progress = st.session_state.summary_progress
        current = st.session_state.summary_current
        total = st.session_state.summary_total
        book_title = st.session_state.summary_current_book
        status = st.session_state.summary_status
        
        # プログレスバーを表示
        st.sidebar.progress(progress)
        
        # 進捗状況のテキスト表示
        percent = int(progress * 100)
        
        if status == "処理中":
            st.sidebar.info(f"サマリ生成中: {percent}% ({current}/{total} 冊完了)")
            st.sidebar.caption(f"現在処理中: 「{book_title}」")
        elif status == "完了":
            st.sidebar.success(f"サマリ生成完了: {total}冊のサマリを生成しました")
            
            # 完了後に表示を消すボタン
            if st.sidebar.button("この通知を閉じる"):
                st.session_state.summary_generation_active = False
                st.rerun()
        elif status == "エラー":
            st.sidebar.error("サマリ生成中にエラーが発生しました")
            
            # エラー後に表示を消すボタン
            if st.sidebar.button("この通知を閉じる"):
                st.session_state.summary_generation_active = False
                st.rerun()
