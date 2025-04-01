# main.pyの最後に追加するコード
# このファイルの内容をmain.pyの最後に手動で追加してください

# Remix関連のエンドポイントをインクルード
from app.remix_endpoints import router as remix_router
app.include_router(remix_router)
