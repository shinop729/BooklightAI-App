"""
main.pyファイルの最後に追加するコード
"""

# Remix関連のエンドポイントをインクルード
from app.remix_endpoints import router as remix_router
app.include_router(remix_router)
