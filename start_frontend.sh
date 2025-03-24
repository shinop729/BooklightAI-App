#!/bin/bash
# start_frontend.sh - Booklight AI フロントエンド開発サーバー起動スクリプト

# 色の定義
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Booklight AI フロントエンド開発サーバー起動スクリプト ===${NC}"

# 現在のディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Reactフロントエンド起動
echo -e "${GREEN}Reactフロントエンドを起動しています...${NC}"
cd "$SCRIPT_DIR/frontend" && npm run dev

echo -e "${GREEN}フロントエンドサーバーが停止しました。${NC}"
