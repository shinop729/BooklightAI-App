"""
query_processing.py の単体テスト
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock

# テスト対象のモジュールをインポート
# パスが通っていない場合は sys.path に追加する必要がある
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../api/app')))

from utils.query_processing import extract_keywords_from_query

# --- モックの設定 ---

# OpenAI APIのレスポンスを模倣するモッククラス
class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)

class MockMessage:
    def __init__(self, content):
        self.content = content

class MockCompletion:
    def __init__(self, choices):
        self.choices = choices

# --- テストケース ---

@pytest.mark.asyncio
@patch('utils.query_processing.openai_client.chat.completions.create', new_callable=AsyncMock)
async def test_extract_keywords_simple_query(mock_create):
    """単純なクエリからのキーワード抽出テスト"""
    # モックの戻り値を設定
    mock_create.return_value = MockCompletion([MockChoice("贈与, プレゼント, ギフト")])

    query = "贈与について教えて"
    expected_keywords = ["贈与", "プレゼント", "ギフト"]
    actual_keywords = await extract_keywords_from_query(query)

    assert actual_keywords == expected_keywords
    # mock_create が正しい引数で呼び出されたか確認 (オプション)
    mock_create.assert_called_once()
    call_args = mock_create.call_args[1] # キーワード引数を取得
    assert call_args['model'] == "gpt-3.5-turbo"
    assert "質問: 贈与について教えて" in call_args['messages'][0]['content']

@pytest.mark.asyncio
@patch('utils.query_processing.openai_client.chat.completions.create', new_callable=AsyncMock)
async def test_extract_keywords_long_query(mock_create):
    """長いクエリからのキーワード抽出テスト"""
    mock_create.return_value = MockCompletion([MockChoice("戦略, 意思決定, フレームワーク, 競争優位性, 分析")])

    query = "ビジネスにおける戦略的意思決定のためのフレームワークについて、競争優位性を確立するための分析方法を含めて詳しく説明してください。"
    # 期待値はプロンプトとモデルに依存するため、ある程度柔軟に
    expected_keywords_subset = {"戦略", "意思決定", "フレームワーク", "競争優位性", "分析"}
    actual_keywords = await extract_keywords_from_query(query)

    assert len(actual_keywords) <= 5 # 最大5つのはず
    assert set(actual_keywords).issubset(expected_keywords_subset) or len(set(actual_keywords).intersection(expected_keywords_subset)) >= 3 # 部分一致または3つ以上一致

@pytest.mark.asyncio
@patch('utils.query_processing.openai_client.chat.completions.create', new_callable=AsyncMock)
async def test_extract_keywords_specific_topic(mock_create):
    """特定のトピックに関するクエリ"""
    mock_create.return_value = MockCompletion([MockChoice("平家物語, 祇園精舎, 諸行無常, 盛者必衰")])

    query = "平家物語の冒頭、祇園精舎の鐘の声について知りたい"
    expected_keywords = ["平家物語", "祇園精舎", "諸行無常", "盛者必衰"] # モデルによっては冒頭なども含むかも
    actual_keywords = await extract_keywords_from_query(query)

    assert all(kw in expected_keywords or kw in query for kw in actual_keywords) # 期待値か元のクエリに含まれるか

@pytest.mark.asyncio
@patch('utils.query_processing.openai_client.chat.completions.create', new_callable=AsyncMock)
async def test_extract_keywords_max_limit(mock_create):
    """キーワード最大数制限のテスト"""
    # モデルが6つ返した場合を想定
    mock_create.return_value = MockCompletion([MockChoice("キーワード1, キーワード2, キーワード3, キーワード4, キーワード5, キーワード6")])

    query = "たくさんのキーワードが含まれる質問です"
    actual_keywords = await extract_keywords_from_query(query, max_keywords=5)

    assert len(actual_keywords) == 5
    assert actual_keywords == ["キーワード1", "キーワード2", "キーワード3", "キーワード4", "キーワード5"]

@pytest.mark.asyncio
@patch('utils.query_processing.openai_client.chat.completions.create', new_callable=AsyncMock)
async def test_extract_keywords_empty_response(mock_create):
    """APIが空の応答を返した場合"""
    mock_create.return_value = MockCompletion([MockChoice("")])

    query = "何か質問"
    actual_keywords = await extract_keywords_from_query(query)

    assert actual_keywords == []

@pytest.mark.asyncio
@patch('utils.query_processing.openai_client.chat.completions.create', new_callable=AsyncMock)
async def test_extract_keywords_no_comma(mock_create):
    """APIがカンマ区切りでない応答を返した場合"""
    mock_create.return_value = MockCompletion([MockChoice("キーワード1 キーワード2")])

    query = "カンマなし"
    actual_keywords = await extract_keywords_from_query(query)

    # この場合、"キーワード1 キーワード2" が1つのキーワードとして扱われる
    assert actual_keywords == ["キーワード1 キーワード2"]

@pytest.mark.asyncio
@patch('utils.query_processing.openai_client.chat.completions.create', new_callable=AsyncMock)
async def test_extract_keywords_api_error_retry(mock_create):
    """APIエラーとリトライのテスト"""
    from openai import APIConnectionError

    # 最初の2回はエラー、3回目に成功するよう設定
    mock_create.side_effect = [
        APIConnectionError(request=None), # type: ignore
        APIConnectionError(request=None), # type: ignore
        MockCompletion([MockChoice("成功キーワード")])
    ]

    query = "エラーテスト"
    actual_keywords = await extract_keywords_from_query(query)

    assert actual_keywords == ["成功キーワード"]
    assert mock_create.call_count == 3 # 3回呼び出されたはず

@pytest.mark.asyncio
@patch('utils.query_processing.openai_client.chat.completions.create', new_callable=AsyncMock)
async def test_extract_keywords_api_error_max_retry(mock_create):
    """APIエラーで最大リトライ回数に達した場合"""
    from openai import APIConnectionError

    # 常にエラーを発生させる
    mock_create.side_effect = APIConnectionError(request=None) # type: ignore

    query = "最大エラーテスト"
    actual_keywords = await extract_keywords_from_query(query)

    assert actual_keywords == [] # 空リストが返されるはず
    assert mock_create.call_count == 3 # 最大3回呼び出されたはず

@pytest.mark.asyncio
@patch('utils.query_processing.openai_client', None) # クライアントがNoneの場合をシミュレート
async def test_extract_keywords_no_client():
    """OpenAIクライアントが初期化されていない場合"""
    query = "クライアントなしテスト"
    actual_keywords = await extract_keywords_from_query(query)
    assert actual_keywords == []

# --- pytestの実行設定 ---
# このファイル単体で実行する場合: pytest tests/utils/test_query_processing.py
# プロジェクトルートから実行する場合: pytest
